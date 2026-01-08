"""
Sales Agent Node V3 - LLM Agnostic with LangChain Tools
- Uses LangChain @tool decorator for LLM-agnostic tool definitions
- Uses ChatOpenAI (can be swapped for any LangChain-compatible LLM)
- Products displayed in HTML table with images
- Stock validation with temporary reservations (15 min TTL)
- Full cart management with order confirmation
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import re
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from ..state import AgentState
from ....config import settings
from ...vectorstore.pinecone_store import PineconeStore
from ...repositories.product_repository import MongoProductRepository
from ...services.stock_reservation import get_stock_service
from ...services.cloudflare_r2 import get_r2_service
from ...database.mongodb import MongoDB
from .memory_optimizer import get_memory_state
from ...services.upstash_redis import get_redis


# Session product mapping (index/SKU -> UUID) - NOT a cache, needed for "producto 1" resolution
_session_product_map: Dict[str, Dict[str, Any]] = {}

# Tool context (conversation_id, user_id)
_tool_context: Dict[str, Dict[str, str]] = {}


def set_tool_context(conversation_id: str, user_id: str, messages: list = None):
    """Set context for tools to use"""
    global _tool_context
    _tool_context["current"] = {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "messages": messages or []
    }


def get_tool_context() -> Dict[str, str]:
    """Get current tool context"""
    return _tool_context.get("current", {"conversation_id": "", "user_id": "anonymous"})


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _save_product_mapping(conversation_id: str, products: List[Dict]):
    """Save multiple mappings: index, SKU, and name -> product_id"""
    global _session_product_map
    mapping = {
        "by_index": {},
        "by_sku": {},
        "by_name": {},
        "products": products
    }
    for p in products:
        mapping["by_index"][p["index"]] = p["id"]
        mapping["by_sku"][p["sku"].upper()] = p["id"]
        mapping["by_name"][p["name"].lower()] = p["id"]
    _session_product_map[conversation_id] = mapping


def _calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity score between two texts using word overlap.
    Returns a score between 0 and 1.
    """
    # Normalize texts
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    # Remove common stop words
    stop_words = {'de', 'con', 'y', 'el', 'la', 'los', 'las', 'un', 'una', 'para', 'en', 'del'}
    words1 = words1 - stop_words
    words2 = words2 - stop_words
    
    if not words1 or not words2:
        return 0.0
    
    # Calculate Jaccard similarity + bonus for substring matches
    intersection = words1 & words2
    union = words1 | words2
    jaccard = len(intersection) / len(union) if union else 0
    
    # Bonus for substring containment
    text1_lower = text1.lower()
    text2_lower = text2.lower()
    substring_bonus = 0.3 if text1_lower in text2_lower or text2_lower in text1_lower else 0
    
    # Bonus for matching key words (first significant word)
    significant_words1 = [w for w in text1.lower().split() if len(w) > 3 and w not in stop_words]
    significant_words2 = [w for w in text2.lower().split() if len(w) > 3 and w not in stop_words]
    
    keyword_bonus = 0
    for w1 in significant_words1:
        for w2 in significant_words2:
            if w1 in w2 or w2 in w1:
                keyword_bonus = 0.4
                break
    
    return min(1.0, jaccard + substring_bonus + keyword_bonus)


def _find_best_match(identifier: str, products: List[Dict], threshold: float = 0.3) -> Optional[Dict]:
    """Find the best matching product from a list using similarity scoring.
    Returns the product dict or None if no good match found.
    """
    if not products or not identifier:
        return None
    
    best_match = None
    best_score = 0
    
    for product in products:
        product_name = product.get("name", "")
        score = _calculate_similarity(identifier, product_name)
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = product
    
    return best_match


async def _resolve_product_id(conversation_id: str, identifier: str) -> str:
    """Resolve product by index, SKU, or name similarity from session mapping.
    
    Uses fuzzy matching to find products even with partial or misspelled names.
    Only searches within products shown to the user in the current conversation.
    """
    global _session_product_map
    identifier = str(identifier).strip()
    
    # If it's already a UUID format (8-4-4-4-12 pattern), return as-is
    uuid_pattern = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', re.IGNORECASE)
    if uuid_pattern.match(identifier):
        return identifier
    
    mapping = _session_product_map.get(conversation_id, {})
    
    # If no mapping exists, return None to indicate product not found
    if not mapping:
        return None
    
    # Try to parse as index (1, 2, 3...) - MOST COMMON CASE
    try:
        index = int(identifier)
        if index in mapping.get("by_index", {}):
            return mapping["by_index"][index]
        # Index out of range
        return None
    except ValueError:
        pass
    
    # Try exact SKU match (case insensitive)
    sku_upper = identifier.upper()
    if sku_upper in mapping.get("by_sku", {}):
        return mapping["by_sku"][sku_upper]
    
    # Try partial SKU match only within session products
    for sku, pid in mapping.get("by_sku", {}).items():
        if sku_upper in sku or sku in sku_upper:
            return pid
    
    # Try exact name match (case insensitive)
    name_lower = identifier.lower()
    if name_lower in mapping.get("by_name", {}):
        return mapping["by_name"][name_lower]
    
    # Use similarity matching for partial/fuzzy name matches
    products = mapping.get("products", [])
    best_match = _find_best_match(identifier, products, threshold=0.3)
    
    if best_match:
        return best_match.get("id")
    
    # If not found in session mapping, return None
    return None


def _generate_products_table(products: List[Dict]) -> str:
    """Generate HTML cards for products with add buttons"""
    if not products:
        return "<p>No hay productos disponibles.</p>"
    
    cards = []
    for p in products:
        stock_badge = f'<span style="color:#059669;font-size:11px;">{p["stock"]} disponibles</span>' if p["available"] else '<span style="color:#dc2626;font-size:11px;">Sin stock</span>'
        image_html = f'<img src="{p["image_url"]}" alt="{p["name"]}" style="width:80px;height:80px;object-fit:cover;border-radius:8px;">' if p["image_url"] else '<div style="width:80px;height:80px;background:#f3f4f6;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#9ca3af;">Sin img</div>'
        
        card = f'''
        <div class="product-card" data-index="{p["index"]}" data-name="{p["name"]}" style="display:flex;gap:12px;padding:12px;background:white;border-radius:12px;border:1px solid #e5e7eb;margin-bottom:10px;transition:all 0.2s;cursor:pointer;" onmouseover="this.style.borderColor='#4F46E5';this.style.boxShadow='0 4px 12px rgba(79,70,229,0.15)'" onmouseout="this.style.borderColor='#e5e7eb';this.style.boxShadow='none'">
            <div style="flex-shrink:0;">{image_html}</div>
            <div style="flex:1;min-width:0;">
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                    <span style="background:#4F46E5;color:white;font-size:11px;font-weight:bold;padding:2px 8px;border-radius:10px;">#{p["index"]}</span>
                    <span style="font-size:10px;color:#6b7280;background:#f3f4f6;padding:2px 6px;border-radius:4px;">{p["category"]}</span>
                </div>
                <div style="font-weight:600;color:#1f2937;font-size:14px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{p["name"]}</div>
                <div style="font-size:10px;color:#9ca3af;margin-bottom:6px;">SKU: {p["sku"]}</div>
                <div style="display:flex;align-items:center;justify-content:space-between;">
                    <div>
                        <span style="font-size:18px;font-weight:bold;color:#059669;">${p["price"]:,.2f}</span>
                        <div>{stock_badge}</div>
                    </div>
                    <button class="add-btn" data-index="{p["index"]}" style="background:#4F46E5;color:white;border:none;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:4px;transition:background 0.2s;" onmouseover="this.style.background='#4338ca'" onmouseout="this.style.background='#4F46E5'">
                        <span style="font-size:16px;">+</span> Agregar
                    </button>
                </div>
            </div>
        </div>'''
        cards.append(card)
    
    html = f'<div style="margin:10px 0;">{"".join(cards)}</div>'
    
    return html


def _generate_cart_html(cart: Dict) -> str:
    """Generate HTML for cart display with action buttons"""
    items_html = []
    for item in cart["items"]:
        items_html.append(f'''
        <div class="cart-item" data-product-id="{item.get("product_id", "")}" data-product-name="{item["product_name"]}" style="display:flex;align-items:center;gap:12px;padding:12px;background:white;border-radius:10px;margin-bottom:8px;border:1px solid #e5e7eb;">
            <div style="flex:1;">
                <div style="font-weight:600;color:#1f2937;font-size:13px;">{item["product_name"]}</div>
                <div style="font-size:12px;color:#6b7280;">${item["price"]:,.2f} c/u</div>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                <button class="qty-btn minus-btn" data-product="{item["product_name"]}" style="width:28px;height:28px;border-radius:6px;border:1px solid #d1d5db;background:white;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;" onmouseover="this.style.background='#f3f4f6'" onmouseout="this.style.background='white'">-</button>
                <span style="min-width:24px;text-align:center;font-weight:600;">{item["quantity"]}</span>
                <button class="qty-btn plus-btn" data-product="{item["product_name"]}" style="width:28px;height:28px;border-radius:6px;border:1px solid #d1d5db;background:white;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;" onmouseover="this.style.background='#f3f4f6'" onmouseout="this.style.background='white'">+</button>
            </div>
            <div style="text-align:right;min-width:70px;">
                <div style="font-weight:bold;color:#059669;">${item["subtotal"]:,.2f}</div>
            </div>
            <button class="remove-btn" data-product="{item["product_name"]}" style="width:28px;height:28px;border-radius:6px;border:none;background:#fee2e2;color:#dc2626;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;" onmouseover="this.style.background='#fecaca'" onmouseout="this.style.background='#fee2e2'" title="Eliminar">✕</button>
        </div>''')
    
    return f'''
    <div style="margin:10px 0;padding:15px;background:#f9fafb;border-radius:12px;border:1px solid #e5e7eb;">
        <div style="font-weight:600;color:#1f2937;margin-bottom:12px;font-size:14px;">Tu Carrito ({len(cart["items"])} productos)</div>
        {"".join(items_html)}
        <div style="display:flex;justify-content:space-between;align-items:center;padding-top:12px;border-top:2px solid #e5e7eb;margin-top:8px;">
            <span style="font-weight:600;color:#374151;">TOTAL:</span>
            <span style="font-size:20px;font-weight:bold;color:#059669;">${cart["total"]:,.2f}</span>
        </div>
        <p style="font-size:11px;color:#6b7280;margin-top:8px;">Los productos estan reservados por 15 minutos. Confirma tu orden para completar la compra.</p>
    </div>
    '''


def _generate_delivery_slots_html(slots_by_date: List[Dict]) -> str:
    """Generate HTML for delivery slots selection - Matrix format (days x hours)"""
    # Define time slots and row codes
    time_slots = ["09:00 - 12:00", "12:00 - 15:00", "15:00 - 18:00", "18:00 - 21:00"]
    row_codes = ["A", "B", "C", "D", "E", "F", "G"]  # Up to 7 days
    
    # Build matrix: day -> {time_slot -> code}
    slot_matrix = {}
    code_to_slot = {}  # For reverse lookup
    
    for day_idx, day in enumerate(slots_by_date[:7]):  # Max 7 days
        row_code = row_codes[day_idx]
        day_key = f"{day['day_name'][:3]} {day['date'].split('-')[2]}/{day['date'].split('-')[1]}"
        slot_matrix[day_key] = {"day_name": day["day_name"], "date": day["date"], "slots": {}}
        
        for slot in day["slots"]:
            time_range = slot["time"]
            # Find column index
            col_idx = -1
            for i, ts in enumerate(time_slots):
                if ts == time_range:
                    col_idx = i + 1
                    break
            if col_idx > 0:
                code = f"{row_code}{col_idx}"
                slot_matrix[day_key]["slots"][time_range] = code
                code_to_slot[code] = {"date": day["date"], "time": time_range, "day_name": day["day_name"]}
    
    # Generate HTML table
    rows_html = []
    for day_idx, (day_key, day_data) in enumerate(slot_matrix.items()):
        row_code = row_codes[day_idx]
        cells = [f'<td style="padding:8px;font-weight:bold;background:#f8fafc;">{day_key}</td>']
        
        for i, ts in enumerate(time_slots):
            code = day_data["slots"].get(ts)
            if code:
                cells.append(f'<td style="padding:8px;text-align:center;"><span style="background:#4F46E5;color:white;padding:4px 8px;border-radius:4px;font-weight:bold;font-size:12px;">{code}</span></td>')
            else:
                cells.append('<td style="padding:8px;text-align:center;color:#ccc;">-</td>')
        
        rows_html.append(f'<tr style="border-bottom:1px solid #eee;">{"".join(cells)}</tr>')
    
    return f"""
    <div style="margin:10px 0;">
        <h4 style="color:#4F46E5;margin-bottom:10px;">Selecciona tu Horario de Entrega</h4>
        <table style="width:100%;border-collapse:collapse;font-size:13px;border:1px solid #e5e7eb;">
            <thead>
                <tr style="background:#4F46E5;color:white;">
                    <th style="padding:10px;text-align:left;">Dia</th>
                    <th style="padding:10px;text-align:center;">Manana<br><span style="font-size:10px;font-weight:normal;">09-12h</span></th>
                    <th style="padding:10px;text-align:center;">Mediodia<br><span style="font-size:10px;font-weight:normal;">12-15h</span></th>
                    <th style="padding:10px;text-align:center;">Tarde<br><span style="font-size:10px;font-weight:normal;">15-18h</span></th>
                    <th style="padding:10px;text-align:center;">Noche<br><span style="font-size:10px;font-weight:normal;">18-21h</span></th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows_html)}
            </tbody>
        </table>
        <p style="font-size:12px;color:#666;margin-top:10px;background:#f0f9ff;padding:8px;border-radius:4px;">
            <strong>Indica el codigo del horario.</strong> Ej: "A2" = {list(slot_matrix.keys())[0] if slot_matrix else 'Primer dia'} de 12-15h
        </p>
    </div>
    """


def _generate_final_order_html(order: Dict) -> str:
    """Generate final order confirmation HTML"""
    items_rows = []
    for item in order["items"]:
        items_rows.append(f"""
        <tr>
            <td style="padding:6px;border-bottom:1px solid #eee;">{item["product_name"]}</td>
            <td style="padding:6px;text-align:center;border-bottom:1px solid #eee;">{item["quantity"]}</td>
            <td style="padding:6px;text-align:right;border-bottom:1px solid #eee;">${item["unit_price"]:,.2f}</td>
            <td style="padding:6px;text-align:right;border-bottom:1px solid #eee;">${item["subtotal"]:,.2f}</td>
        </tr>
        """)
    
    return f"""
    <div style="border:3px solid #059669;border-radius:12px;padding:20px;margin:10px 0;background:#f0fdf4;">
        <div style="text-align:center;margin-bottom:15px;">
            <h2 style="color:#059669;margin:10px 0;">Pedido Confirmado</h2>
            <p style="font-size:24px;font-weight:bold;color:#059669;margin:0;">#{order["order_number"]}</p>
        </div>
        
        <div style="background:white;border-radius:8px;padding:15px;margin:15px 0;">
            <h4 style="margin:0 0 10px 0;color:#333;">Productos</h4>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead>
                    <tr style="background:#f5f5f5;">
                        <th style="padding:8px;text-align:left;">Producto</th>
                        <th style="padding:8px;text-align:center;">Cant.</th>
                        <th style="padding:8px;text-align:right;">Precio</th>
                        <th style="padding:8px;text-align:right;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(items_rows)}
                </tbody>
                <tfoot>
                    <tr style="font-weight:bold;background:#059669;color:white;">
                        <td colspan="3" style="padding:10px;text-align:right;">TOTAL:</td>
                        <td style="padding:10px;text-align:right;">${order["total"]:,.2f}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        
        <div style="display:flex;gap:15px;margin:15px 0;">
            <div style="flex:1;background:white;border-radius:8px;padding:15px;">
                <h4 style="margin:0 0 10px 0;color:#333;">Cliente</h4>
                <p style="margin:5px 0;font-size:13px;"><strong>{order["customer"]["name"]}</strong></p>
                <p style="margin:5px 0;font-size:13px;">{order["customer"]["id_type"]}: {order["customer"]["id_number"]}</p>
                <p style="margin:5px 0;font-size:13px;">Tel: {order["customer"]["phone"]}</p>
                <p style="margin:5px 0;font-size:13px;">Email: {order["customer"]["email"]}</p>
            </div>
            <div style="flex:1;background:white;border-radius:8px;padding:15px;">
                <h4 style="margin:0 0 10px 0;color:#333;">Entrega</h4>
                <p style="margin:5px 0;font-size:13px;"><strong>{order["delivery"]["slot_label"]}</strong></p>
                <p style="margin:5px 0;font-size:13px;">{order["delivery"]["address"]}</p>
                {f'<p style="margin:5px 0;font-size:12px;color:#666;">Ref: {order["delivery"]["reference"]}</p>' if order["delivery"].get("reference") else ''}
            </div>
        </div>
        
        <p style="text-align:center;color:#666;font-size:12px;margin-top:15px;">
            Recibiras un correo de confirmacion a {order["customer"]["email"]}
        </p>
    </div>
    """


# ============================================================================
# LANGCHAIN TOOLS (LLM-AGNOSTIC)
# ============================================================================

@tool
async def search_products(query: str, limit: int = 5) -> str:
    """
    Busca productos en el catalogo. Devuelve una tabla con imagen, precio y stock disponible.
    
    Args:
        query: Termino de busqueda (ej: 'sofa', 'lampara', 'mesa')
        limit: Numero maximo de resultados (default: 5)
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        vectorstore = PineconeStore()
        stock_service = get_stock_service()
        r2_service = get_r2_service()
        
        results = await vectorstore.search_products(query=query, top_k=limit)
        
        if not results:
            return json.dumps({
                "success": True,
                "products": [],
                "html_table": "<p>No se encontraron productos para tu busqueda.</p>",
                "message": f"No se encontraron productos para: {query}"
            })
        
        db = MongoDB.get_database()
        products = []
        
        for i, result in enumerate(results):
            product_id = result.get("id")
            product = await db.products.find_one({"id": product_id})
            
            if product:
                available_stock = await stock_service.get_available_stock(product_id)
                
                image_key = product.get("image_key", "")
                image_url = ""
                if image_key:
                    try:
                        image_url = r2_service.get_signed_url(image_key, expires_in=3600)
                    except:
                        image_url = ""
                
                products.append({
                    "index": i + 1,
                    "id": product_id,
                    "name": product.get("name"),
                    "description": product.get("description", "")[:100] + "...",
                    "category": product.get("category"),
                    "price": product.get("price", 0),
                    "stock": available_stock,
                    "available": available_stock > 0,
                    "image_url": image_url,
                    "sku": product.get("sku", "")
                })
        
        _save_product_mapping(conversation_id, products)
        html_table = _generate_products_table(products)
        
        return json.dumps({
            "success": True,
            "products": products,
            "html_table": html_table,
            "count": len(products),
            "query": query
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def check_stock(product_id: str) -> str:
    """
    Verifica stock disponible y precio de un producto especifico.
    
    Args:
        product_id: ID del producto
    """
    try:
        product_repo = MongoProductRepository()
        stock_service = get_stock_service()
        
        product = await product_repo.get_by_id(product_id)
        
        if not product:
            return json.dumps({"success": False, "error": "Producto no encontrado"})
        
        available_stock = await stock_service.get_available_stock(product_id)
        
        return json.dumps({
            "success": True,
            "product_id": product_id,
            "product_name": product.name,
            "total_stock": product.stock,
            "available_stock": available_stock,
            "reserved": product.stock - available_stock,
            "available": available_stock > 0,
            "price": product.price
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def add_to_cart(product_id: str, quantity: int = 1) -> str:
    """
    Agrega producto al carrito con reserva temporal de 15 minutos.
    IMPORTANTE: Solo acepta el numero de la tabla (#1, #2, etc.) o el SKU exacto del producto mostrado.
    
    Args:
        product_id: Numero de la tabla (1, 2, 3...) o SKU exacto del producto
        quantity: Cantidad a agregar (default: 1)
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        user_id = ctx["user_id"]
        
        stock_service = get_stock_service()
        
        resolved_id = await _resolve_product_id(conversation_id, product_id)
        
        # If product not found in session, return helpful error
        if resolved_id is None:
            # Get available products from session to show user
            mapping = _session_product_map.get(conversation_id, {})
            available_products = mapping.get("products", [])
            
            if not available_products:
                return json.dumps({
                    "success": False,
                    "error": f"No encontre el producto '{product_id}'. Primero busca productos con search_products para ver las opciones disponibles.",
                    "suggestion": "Usa search_products para buscar el producto que el cliente quiere."
                })
            
            # Build list of available options
            options = [f"#{p['index']} - {p['name']} (SKU: {p['sku']})" for p in available_products[:5]]
            return json.dumps({
                "success": False,
                "error": f"No encontre el producto '{product_id}' en los resultados mostrados.",
                "available_products": options,
                "suggestion": "Pide al cliente que indique el numero (#) o SKU exacto de la tabla mostrada."
            })
        
        result = await stock_service.reserve_stock(
            conversation_id=conversation_id,
            product_id=resolved_id,
            quantity=quantity,
            user_id=user_id
        )
        
        if not result.get("success"):
            return json.dumps(result)
        
        cart = await stock_service.get_cart_total(conversation_id)
        
        return json.dumps({
            "success": True,
            "action": "added",
            "product_name": result.get("product_name"),
            "quantity": quantity,
            "reserved_until": result.get("expires_at"),
            "cart_total": cart["total"],
            "cart_items": cart["item_count"],
            "message": f"Agregado: {result.get('product_name')} x{quantity}. Reservado por 15 minutos."
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def remove_from_cart(product_id: str, quantity: Optional[int] = None) -> str:
    """
    Elimina producto del carrito.
    
    Args:
        product_id: ID del producto
        quantity: Cantidad a eliminar (null = todo)
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        stock_service = get_stock_service()
        
        result = await stock_service.remove_from_cart(
            conversation_id=conversation_id,
            product_id=product_id,
            quantity=quantity
        )
        
        if result.get("success"):
            cart = await stock_service.get_cart_total(conversation_id)
            result["cart_total"] = cart["total"]
            result["cart_items"] = cart["item_count"]
        
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def get_cart() -> str:
    """
    Muestra el carrito actual con todos los productos y el total.
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        stock_service = get_stock_service()
        cart = await stock_service.get_cart_total(conversation_id)
        
        if not cart["items"]:
            return json.dumps({
                "success": True,
                "cart": cart,
                "html": "<p>Tu carrito esta vacio.</p>"
            })
        
        html = _generate_cart_html(cart)
        
        return json.dumps({
            "success": True,
            "cart": cart,
            "html": html
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def get_delivery_slots() -> str:
    """
    Obtiene los horarios de entrega disponibles para los proximos 7 dias.
    Usar cuando el cliente quiere finalizar la compra o preguntar por fechas de entrega.
    """
    try:
        db = MongoDB.get_database()
        slots = await db.delivery_slots.find(
            {"available": True, "$expr": {"$lt": ["$current_orders", "$max_orders"]}}
        ).sort([("date", 1), ("time_start", 1)]).to_list(30)
        
        if not slots:
            return json.dumps({"success": False, "error": "No hay horarios de entrega disponibles"})
        
        slots_by_date = {}
        for slot in slots:
            date = slot["date"]
            if date not in slots_by_date:
                slots_by_date[date] = {
                    "date": date,
                    "day_name": slot["day_name"],
                    "slots": []
                }
            slots_by_date[date]["slots"].append({
                "id": str(slot["_id"]),
                "time": f"{slot['time_start']} - {slot['time_end']}",
                "label": slot["label"]
            })
        
        html = _generate_delivery_slots_html(list(slots_by_date.values()))
        
        return json.dumps({
            "success": True,
            "slots": list(slots_by_date.values()),
            "html": html
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def select_delivery_slot(slot_code: str) -> str:
    """
    Selecciona un horario de entrega usando el codigo de la tabla (A1, B2, C3, etc.).
    La tabla muestra dias como filas (A=primer dia, B=segundo, etc.) y horas como columnas (1=09-12h, 2=12-15h, 3=15-18h, 4=18-21h).
    
    Ejemplos de uso:
    - "A2" -> select_delivery_slot(slot_code="A2") = Primer dia, 12-15h
    - "B1" -> select_delivery_slot(slot_code="B1") = Segundo dia, 09-12h
    - "C4" -> select_delivery_slot(slot_code="C4") = Tercer dia, 18-21h
    - "quiero el A3" -> select_delivery_slot(slot_code="A3")
    - "el B2 por favor" -> select_delivery_slot(slot_code="B2")
    
    Args:
        slot_code: Codigo del horario (A1, A2, B1, B2, etc.)
    """
    try:
        db = MongoDB.get_database()
        slots = await db.delivery_slots.find(
            {"available": True, "$expr": {"$lt": ["$current_orders", "$max_orders"]}}
        ).sort([("date", 1), ("time_start", 1)]).to_list(30)
        
        if not slots:
            return json.dumps({"success": False, "error": "No hay horarios disponibles"})
        
        # Parse the code (e.g., "A2" -> row=0, col=2)
        slot_code = slot_code.upper().strip()
        
        # Validate format: must be letter + number (A1, B2, etc.)
        import re
        if not re.match(r'^[A-G][1-4]$', slot_code):
            return json.dumps({
                "success": False, 
                "error": f"El codigo '{slot_code}' no es valido. Debes seleccionar un codigo de la tabla como A1, B2, C3, etc. La letra indica el dia (A-G) y el numero la hora (1=09-12h, 2=12-15h, 3=15-18h, 4=18-21h). Por favor revisa la tabla y dime el codigo que prefieres."
            })
        
        row_letter = slot_code[0]
        col_number = slot_code[1:]
        
        row_codes = ["A", "B", "C", "D", "E", "F", "G"]
        time_slots = ["09:00", "12:00", "15:00", "18:00"]
        
        if row_letter not in row_codes:
            return json.dumps({"success": False, "error": f"Letra de dia invalida. Usa A-G"})
        
        try:
            col_idx = int(col_number) - 1
            if col_idx < 0 or col_idx > 3:
                return json.dumps({"success": False, "error": "Numero de hora invalido. Usa 1-4"})
        except:
            return json.dumps({"success": False, "error": "Codigo invalido. Usa formato como A1, B2, C3"})
        
        row_idx = row_codes.index(row_letter)
        target_time = time_slots[col_idx]
        
        # Group slots by date
        slots_by_date = {}
        for slot in slots:
            date = slot["date"]
            if date not in slots_by_date:
                slots_by_date[date] = []
            slots_by_date[date].append(slot)
        
        dates = sorted(slots_by_date.keys())
        if row_idx >= len(dates):
            return json.dumps({"success": False, "error": f"Dia no disponible. Solo hay {len(dates)} dias disponibles"})
        
        target_date = dates[row_idx]
        selected_slot = None
        
        for slot in slots_by_date[target_date]:
            if slot["time_start"] == target_time:
                selected_slot = slot
                break
        
        if not selected_slot:
            return json.dumps({"success": False, "error": f"Horario {slot_code} no disponible. Elige otro de la tabla"})
        
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        await db.pending_orders.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "selected_slot_code": slot_code,
                    "selected_slot": {
                        "id": str(selected_slot["_id"]),
                        "date": selected_slot["date"],
                        "day_name": selected_slot["day_name"],
                        "time_start": selected_slot["time_start"],
                        "time_end": selected_slot["time_end"],
                        "label": selected_slot["label"]
                    },
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return json.dumps({
            "success": True,
            "message": f"Horario {slot_code} seleccionado: {selected_slot['day_name']} {selected_slot['date'].split('-')[2]}/{selected_slot['date'].split('-')[1]} de {selected_slot['time_start']} a {selected_slot['time_end']}",
            "selected_slot": {
                "code": slot_code,
                "date": selected_slot["date"],
                "day_name": selected_slot["day_name"],
                "time": f"{selected_slot['time_start']} - {selected_slot['time_end']}",
                "label": selected_slot["label"]
            },
            "next_step": "Ahora necesito los datos del cliente para completar la orden: nombre completo, tipo y numero de documento, telefono, email y direccion de entrega."
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def create_order(
    customer_name: str,
    customer_id_type: str,
    customer_id_number: str,
    phone: str,
    email: str,
    address: str,
    address_reference: str = ""
) -> str:
    """
    Crea la orden final con los datos del cliente.
    SOLO usar despues de que el cliente haya seleccionado un horario con select_delivery_slot
    y haya proporcionado TODOS sus datos.
    
    Args:
        customer_name: Nombre completo del cliente
        customer_id_type: Tipo de documento (DNI, RUC, CE, Pasaporte)
        customer_id_number: Numero de documento
        phone: Numero de telefono celular
        email: Correo electronico
        address: Direccion completa de entrega
        address_reference: Referencia de la direccion (opcional)
    """
    import uuid
    from bson import ObjectId
    # Generate unique order number first to avoid null key errors
    order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        user_id = ctx["user_id"]
        
        db = MongoDB.get_database()
        stock_service = get_stock_service()
        
        cart = await stock_service.get_cart_total(conversation_id)
        if not cart["items"]:
            return json.dumps({"success": False, "error": "El carrito esta vacio"})
        
        # Get the previously selected delivery slot
        pending_order = await db.pending_orders.find_one({"conversation_id": conversation_id})
        if not pending_order or not pending_order.get("selected_slot"):
            return json.dumps({
                "success": False, 
                "error": "No has seleccionado un horario de entrega. Por favor selecciona uno primero."
            })
        
        selected_slot = pending_order["selected_slot"]
        slot_id = ObjectId(selected_slot["id"])
        
        order = {
            "order_number": order_number,
            "conversation_id": conversation_id,
            "status": "confirmed",
            "customer": {
                "name": customer_name,
                "id_type": customer_id_type,
                "id_number": customer_id_number,
                "phone": phone,
                "email": email
            },
            "delivery": {
                "address": address,
                "reference": address_reference,
                "date": selected_slot["date"],
                "time_start": selected_slot["time_start"],
                "time_end": selected_slot["time_end"],
                "slot_label": selected_slot["label"]
            },
            "items": [
                {
                    "product_id": item["product_id"],
                    "product_name": item["product_name"],
                    "quantity": item["quantity"],
                    "unit_price": item["price"],
                    "subtotal": item["subtotal"]
                }
                for item in cart["items"]
            ],
            "subtotal": cart["total"],
            "delivery_fee": 0,
            "total": cart["total"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        await db.orders.insert_one(order)
        await stock_service.confirm_order(conversation_id, user_id)
        await db.delivery_slots.update_one(
            {"_id": slot_id},
            {"$inc": {"current_orders": 1}}
        )
        
        html = _generate_final_order_html(order)
        
        return json.dumps({
            "success": True,
            "order_number": order_number,
            "total": order["total"],
            "customer_name": customer_name,
            "delivery_date": order["delivery"]["date"],
            "html": html
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def escalate_to_human(reason: str) -> str:
    """
    Escala a supervisor humano cuando el cliente esta frustrado o requiere asistencia especial.
    
    Args:
        reason: Motivo de la escalacion (describe claramente el problema del cliente)
    """
    import uuid
    from ...database.mongodb import MongoDB
    
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        user_id = ctx["user_id"]
        messages_from_ctx = ctx.get("messages", [])
        
        db = MongoDB.get_database()
        
        # Use messages from context (passed from sales_agent_node)
        messages = messages_from_ctx if messages_from_ctx else []
        
        # Convert messages to serializable format
        serializable_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                serializable_messages.append({
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                    "timestamp": msg.get("timestamp", datetime.utcnow().isoformat())
                })
        
        # Get last user message
        last_user_message = ""
        for msg in reversed(serializable_messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break
        
        # Generate case summary using LLM
        case_summary = await _generate_case_summary(serializable_messages, reason)
        
        # Create escalation record
        escalation_id = str(uuid.uuid4())[:8]
        escalation = {
            "id": escalation_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "reason": reason,
            "case_summary": case_summary,
            "original_message": last_user_message,
            "classification": "agent_escalation",
            "status": "pending",
            "messages": serializable_messages[-20:] if serializable_messages else [],
            "timestamp": datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow()
        }
        
        # Save to MongoDB
        await db.escalations.insert_one(escalation)
        
        # Mark conversation as paused
        await db.conversations.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "status": "escalated",
                    "escalation_id": escalation_id,
                    "paused_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return json.dumps({
            "success": True,
            "action": "escalate",
            "escalation_id": escalation_id,
            "reason": reason,
            "message": "Tu consulta ha sido transferida a un supervisor. Un representante te atendera en breve."
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })


async def _generate_case_summary(messages: list, reason: str) -> str:
    """Generate a summary of the case for the supervisor"""
    try:
        from langchain_openai import ChatOpenAI
        from ...config import settings
        
        # Build conversation text
        conversation_text = ""
        for msg in messages[-10:]:  # Last 10 messages
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if content and len(content) < 500:  # Skip very long messages (HTML tables)
                    conversation_text += f"{role}: {content}\n"
        
        if not conversation_text:
            return f"Cliente escalado. Motivo: {reason}"
        
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.3
        )
        
        prompt = f"""Analiza esta conversacion y genera un resumen ejecutivo para el supervisor.

CONVERSACION:
{conversation_text}

MOTIVO DE ESCALACION: {reason}

Genera un resumen breve (maximo 3 oraciones) que incluya:
1. Que queria el cliente
2. Cual es el problema o queja
3. Que necesita el supervisor hacer

Responde SOLO con el resumen, sin titulos ni formato."""

        response = await llm.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        return f"Cliente escalado. Motivo: {reason}"


# ============================================================================
# BUDGET & COUPON TOOLS
# ============================================================================

@tool
async def create_budget_proposal(budget: float, room_type: str = "general") -> str:
    """
    Crea una propuesta de productos optimizada para un presupuesto dado.
    Usar cuando el cliente indica un presupuesto maximo y quiere recomendaciones.
    
    Args:
        budget: Presupuesto maximo en dolares
        room_type: Tipo de ambiente (general, sala, dormitorio, cocina, bano, comedor)
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        room_essentials = {
            "general": ["cama", "sofa", "mesa", "silla", "lampara", "espejo"],
            "sala": ["sofa", "mesa centro", "lampara", "estante"],
            "dormitorio": ["cama", "mesita noche", "lampara", "espejo"],
            "cocina": ["mesa", "silla", "estante"],
            "bano": ["espejo", "organizador"],
            "comedor": ["mesa comedor", "silla", "lampara"]
        }
        
        search_terms = room_essentials.get(room_type.lower(), room_essentials["general"])
        
        all_products = []
        pinecone_store = PineconeStore()
        for term in search_terms:
            results = await pinecone_store.search_products(term, top_k=5)
            for p in results:
                if p.get("stock", 0) > 0 and p.get("price", 0) > 0:
                    all_products.append(p)
        
        seen_ids = set()
        unique_products = []
        for p in all_products:
            pid = p.get("product_id") or p.get("id")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                unique_products.append(p)
        
        unique_products.sort(key=lambda x: x.get("price", 0))
        
        proposal = []
        total = 0
        remaining = budget
        categories_covered = set()
        
        for product in unique_products:
            price = product.get("price", 0)
            category = product.get("category", "").lower()
            if price <= remaining and category not in categories_covered:
                proposal.append({
                    "product_id": product.get("product_id") or product.get("id"),
                    "name": product.get("name", ""),
                    "category": product.get("category", ""),
                    "price": price,
                    "sku": product.get("sku", ""),
                    "stock": product.get("stock", 0)
                })
                total += price
                remaining -= price
                categories_covered.add(category)
        
        for product in unique_products:
            price = product.get("price", 0)
            pid = product.get("product_id") or product.get("id")
            if any(p["product_id"] == pid for p in proposal):
                continue
            if price <= remaining and len(proposal) < 10:
                proposal.append({
                    "product_id": pid,
                    "name": product.get("name", ""),
                    "category": product.get("category", ""),
                    "price": price,
                    "sku": product.get("sku", ""),
                    "stock": product.get("stock", 0)
                })
                total += price
                remaining -= price
        
        if not proposal:
            return json.dumps({"success": False, "error": f"No encontre productos dentro de tu presupuesto de ${budget:,.2f}"})
        
        # Build proper session mapping with by_index, by_sku, by_name structures
        mapping = {
            "by_index": {},
            "by_sku": {},
            "by_name": {},
            "products": []
        }
        for idx, p in enumerate(proposal, 1):
            mapping["by_index"][str(idx)] = p["product_id"]
            mapping["by_sku"][p["sku"].upper()] = p["product_id"]
            mapping["by_name"][p["name"].lower()] = p["product_id"]
            mapping["products"].append({
                "index": idx,
                "name": p["name"],
                "sku": p["sku"],
                "product_id": p["product_id"]
            })
        
        # Save to both memory and Redis for persistence
        _session_product_map[conversation_id] = mapping
        try:
            redis = get_redis()
            await redis.set_product_mapping(conversation_id, mapping)
            print(f"[PRODUCTS] Saved {len(mapping['products'])} products to Redis for {conversation_id}")
        except Exception as e:
            print(f"[PRODUCTS] Failed to save to Redis: {e}")
        
        r2_service = get_r2_service()
        cards = []
        for idx, p in enumerate(proposal, 1):
            try:
                image_key = f"products/{p['product_id']}.jpg"
                image_url = r2_service.get_signed_url(image_key) if r2_service else ""
            except:
                image_url = ""
            img_html = f'<img src="{image_url}" style="width:60px;height:60px;object-fit:cover;border-radius:8px;">' if image_url else '<div style="width:60px;height:60px;background:#e5e7eb;border-radius:8px;"></div>'
            cards.append(f'''
            <div class="product-card" data-index="{idx}" style="display:flex;gap:10px;padding:10px;background:white;border-radius:10px;border:1px solid #e5e7eb;margin-bottom:8px;cursor:pointer;transition:all 0.2s;" onmouseover="this.style.borderColor='#4F46E5'" onmouseout="this.style.borderColor='#e5e7eb'">
                <div style="flex-shrink:0;">{img_html}</div>
                <div style="flex:1;min-width:0;">
                    <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">
                        <span style="background:#4F46E5;color:white;font-size:10px;font-weight:bold;padding:2px 6px;border-radius:8px;">#{idx}</span>
                        <span style="font-size:9px;color:#6b7280;background:#f3f4f6;padding:2px 4px;border-radius:3px;">{p["category"]}</span>
                    </div>
                    <div style="font-weight:600;color:#1f2937;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{p["name"]}</div>
                    <div style="font-size:16px;font-weight:bold;color:#059669;">${p["price"]:,.2f}</div>
                </div>
                <button class="add-btn" data-index="{idx}" style="align-self:center;background:#4F46E5;color:white;border:none;padding:6px 12px;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;" onmouseover="this.style.background='#4338ca'" onmouseout="this.style.background='#4F46E5'">+ Agregar</button>
            </div>''')
        
        html = f'''
        <div style="margin:10px 0;border:2px solid #4F46E5;border-radius:12px;padding:15px;background:#f8fafc;">
            <h3 style="color:#4F46E5;margin:0 0 5px 0;">Propuesta para tu Presupuesto</h3>
            <p style="color:#666;font-size:12px;margin:0 0 15px 0;">Presupuesto: <strong>${budget:,.2f}</strong> | Ambiente: <strong>{room_type.title()}</strong></p>
            <div style="max-height:400px;overflow-y:auto;">{"".join(cards)}</div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:12px;background:#059669;border-radius:8px;margin-top:12px;">
                <div>
                    <div style="color:white;font-size:12px;">TOTAL: <strong style="font-size:18px;">${total:,.2f}</strong></div>
                    <div style="color:#bbf7d0;font-size:11px;">Te sobran: ${remaining:,.2f}</div>
                </div>
                <button class="add-all-btn" style="background:white;color:#059669;border:none;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:bold;cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='#f0fdf4'" onmouseout="this.style.background='white'">Agregar Todo al Carrito</button>
            </div>
        </div>'''
        
        return json.dumps({"success": True, "budget": budget, "room_type": room_type, "total": total, "remaining": remaining, "items_count": len(proposal), "proposal": proposal, "html_table": html})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def add_budget_proposal_to_cart() -> str:
    """
    Agrega todos los productos de la propuesta de presupuesto al carrito.
    Usar cuando el cliente acepta la propuesta completa.
    Si un producto ya está en el carrito, incrementa su cantidad.
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        user_id = ctx["user_id"]
        
        # Try to get mapping from memory first, then from Redis
        mapping = _session_product_map.get(conversation_id)
        if not mapping:
            try:
                redis = get_redis()
                mapping = await redis.get_product_mapping(conversation_id)
                if mapping:
                    _session_product_map[conversation_id] = mapping
                    print(f"[PRODUCTS] Loaded {len(mapping.get('products', []))} products from Redis")
            except Exception as e:
                print(f"[PRODUCTS] Failed to load from Redis: {e}")
        
        if not mapping:
            return json.dumps({"success": False, "error": "No hay una propuesta activa. Primero dime tu presupuesto para crear una propuesta."})
        
        mapping = _session_product_map[conversation_id]
        
        # Get product IDs from by_index which has the correct mapping
        if "by_index" in mapping:
            product_ids = list(mapping["by_index"].values())
        else:
            # Fallback: get from numeric keys (1, 2, 3...)
            product_ids = [pid for key, pid in mapping.items() if key.isdigit()]
        
        if not product_ids:
            return json.dumps({"success": False, "error": "No hay productos en la propuesta."})
        
        stock_service = get_stock_service()
        
        # Get current cart to check for existing products
        current_cart = await stock_service.get_cart_total(conversation_id)
        existing_product_ids = {item["product_id"] for item in current_cart.get("items", [])}
        
        added = []
        already_in_cart = []
        failed = []
        
        for product_id in product_ids:
            try:
                # If product already in cart, increment quantity instead
                if product_id in existing_product_ids:
                    print(f"[CART] Product {product_id} already in cart, incrementing...")
                    result = await stock_service.update_cart_quantity(
                        conversation_id=conversation_id,
                        product_id=product_id,
                        quantity_change=1
                    )
                    if result.get("success"):
                        already_in_cart.append(result.get("product_name", product_id))
                    else:
                        print(f"[CART] Failed to increment {product_id}: {result.get('error')}")
                        failed.append(f"{product_id}: {result.get('error', 'Error')}")
                else:
                    print(f"[CART] Adding new product {product_id}...")
                    result = await stock_service.reserve_stock(
                        conversation_id=conversation_id, 
                        user_id=user_id, 
                        product_id=product_id, 
                        quantity=1
                    )
                    if result.get("success"):
                        added.append(result.get("product_name", product_id))
                    else:
                        print(f"[CART] Failed to add {product_id}: {result.get('error')}")
                        failed.append(f"{product_id}: {result.get('error', 'Error')}")
            except Exception as e:
                print(f"[CART] Exception for {product_id}: {str(e)}")
                failed.append(f"{product_id}: {str(e)}")
        
        cart = await stock_service.get_cart_total(conversation_id)
        html = _generate_cart_html(cart) if cart.get("items") else ""
        
        # Build message
        parts = []
        if added:
            parts.append(f"Agregue {len(added)} productos nuevos")
        if already_in_cart:
            parts.append(f"incremente cantidad de {len(already_in_cart)} que ya tenias")
        
        message = " y ".join(parts) + "." if parts else "No se agregaron productos."
        if failed:
            message += f" ({len(failed)} fallaron por falta de stock)"
        
        return json.dumps({
            "success": True, 
            "added_count": len(added), 
            "added_products": added,
            "incremented_count": len(already_in_cart),
            "incremented_products": already_in_cart,
            "failed_count": len(failed),
            "failed_details": failed,
            "cart_total": cart.get("total", 0),
            "cart_items": cart.get("item_count", 0),
            "html": html,
            "message": message
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def get_cross_sell_recommendations(product_id: str = "") -> str:
    """
    Obtiene recomendaciones de productos complementarios para cross-selling.
    Usar despues de que el cliente agrega algo al carrito para sugerir productos que combinan.
    
    Args:
        product_id: ID del producto base (opcional, si no se da usa el ultimo agregado al carrito)
    """
    import random
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        db = MongoDB.get_database()
        stock_service = get_stock_service()
        pinecone_store = PineconeStore()
        
        # Get cart to find what to cross-sell
        cart = await stock_service.get_cart_total(conversation_id)
        if not cart.get("items") and not product_id:
            return json.dumps({"success": False, "error": "Carrito vacio, no hay base para recomendar"})
        
        # Get base product category
        base_product = None
        if product_id:
            base_product = await db.products.find_one({"product_id": product_id})
        elif cart.get("items"):
            last_item = cart["items"][-1]
            base_product = await db.products.find_one({"product_id": last_item["product_id"]})
        
        if not base_product:
            return json.dumps({"success": False, "error": "No se encontro producto base"})
        
        # Cross-sell mapping by category
        cross_sell_map = {
            "Dormitorio": ["Iluminación", "Ropa de Cama", "Decoración"],
            "Muebles de Sala": ["Iluminación", "Decoración", "Textiles"],
            "Iluminación": ["Decoración", "Muebles de Sala"],
            "Comedor": ["Iluminación", "Decoración", "Cocina"],
            "Ropa de Cama": ["Dormitorio", "Textiles"],
            "Decoración": ["Iluminación", "Muebles de Sala"],
            "Baño": ["Decoración", "Textiles"],
            "Cocina": ["Comedor", "Decoración"]
        }
        
        base_category = base_product.get("category", "")
        related_categories = cross_sell_map.get(base_category, ["Decoración", "Iluminación"])
        
        # Search for complementary products
        recommendations = []
        for cat in related_categories[:2]:
            results = await pinecone_store.search_products(cat, top_k=3)
            for p in results:
                if p.get("stock", 0) > 0 and p.get("product_id") != base_product.get("product_id"):
                    # Add simulated rating
                    rating = round(random.uniform(4.2, 4.9), 1)
                    reviews = random.randint(50, 300)
                    recommendations.append({
                        "product_id": p.get("product_id") or p.get("id"),
                        "name": p.get("name"),
                        "category": p.get("category"),
                        "price": p.get("price"),
                        "stock": p.get("stock"),
                        "rating": rating,
                        "reviews": reviews,
                        "reason": f"Combina perfecto con tu {base_product.get('name', 'producto')}"
                    })
                    if len(recommendations) >= 3:
                        break
            if len(recommendations) >= 3:
                break
        
        if not recommendations:
            return json.dumps({"success": True, "recommendations": [], "message": "No hay recomendaciones disponibles"})
        
        # Generate HTML
        r2_service = get_r2_service()
        rows = []
        for idx, p in enumerate(recommendations, 1):
            try:
                image_url = r2_service.get_signed_url(f"products/{p['product_id']}.jpg") if r2_service else ""
            except:
                image_url = ""
            img_html = f'<img src="{image_url}" style="width:40px;height:40px;object-fit:cover;border-radius:4px;">' if image_url else ""
            stars = "★" * int(p["rating"]) + "☆" * (5 - int(p["rating"]))
            stock_badge = '<span style="color:#dc2626;font-size:10px;">¡Ultimas unidades!</span>' if p["stock"] < 10 else ""
            rows.append(f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px;">{img_html}</td><td style="padding:8px;"><strong>{p["name"]}</strong><br><span style="color:#f59e0b;font-size:11px;">{stars}</span> <span style="font-size:10px;color:#666;">({p["reviews"]} reseñas)</span><br>{stock_badge}</td><td style="padding:8px;text-align:right;font-weight:bold;color:#059669;">${p["price"]:,.2f}</td></tr>')
        
        html = f'<div style="margin:10px 0;border:2px solid #f59e0b;border-radius:12px;padding:15px;background:#fffbeb;"><h4 style="color:#d97706;margin:0 0 10px 0;">Clientes que compraron esto tambien llevaron:</h4><table style="width:100%;border-collapse:collapse;font-size:13px;">{"".join(rows)}</table><p style="font-size:11px;color:#666;margin-top:10px;">¿Te gustaria agregar alguno? Solo dime cual.</p></div>'
        
        return json.dumps({"success": True, "recommendations": recommendations, "html_table": html, "base_product": base_product.get("name")})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def create_bundle_offer(product_ids: str) -> str:
    """
    Crea una oferta de bundle/combo con descuento adicional.
    Usar cuando el cliente tiene varios productos y se puede ofrecer un descuento por llevar el combo.
    
    Args:
        product_ids: IDs de productos separados por coma para el bundle
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        db = MongoDB.get_database()
        stock_service = get_stock_service()
        
        # Parse product IDs
        ids = [pid.strip() for pid in product_ids.split(",")]
        if len(ids) < 2:
            return json.dumps({"success": False, "error": "Un bundle necesita al menos 2 productos"})
        
        # Get products
        products = []
        total_price = 0
        for pid in ids:
            product = await db.products.find_one({"product_id": pid})
            if product and product.get("stock", 0) > 0:
                products.append(product)
                total_price += product.get("price", 0)
        
        if len(products) < 2:
            return json.dumps({"success": False, "error": "No se encontraron suficientes productos para el bundle"})
        
        # Calculate bundle discount (5% for 2 items, 8% for 3+)
        discount_percent = 5 if len(products) == 2 else 8
        discount_amount = total_price * (discount_percent / 100)
        bundle_price = total_price - discount_amount
        
        # Save bundle offer
        bundle_id = f"BUNDLE-{conversation_id[:8]}"
        await db.bundle_offers.update_one(
            {"conversation_id": conversation_id},
            {"$set": {
                "bundle_id": bundle_id,
                "products": [{"product_id": p["product_id"], "name": p["name"], "price": p["price"]} for p in products],
                "original_total": total_price,
                "discount_percent": discount_percent,
                "discount_amount": discount_amount,
                "bundle_price": bundle_price,
                "created_at": datetime.utcnow()
            }},
            upsert=True
        )
        
        # Generate HTML
        items_html = "".join([f'<li style="margin:5px 0;">{p["name"]} - ${p["price"]:,.2f}</li>' for p in products])
        html = f'''
        <div style="margin:10px 0;border:3px solid #059669;border-radius:12px;padding:15px;background:linear-gradient(135deg,#f0fdf4,#dcfce7);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <h4 style="color:#059669;margin:0;">Oferta Combo Especial</h4>
                <span style="background:#059669;color:white;padding:4px 12px;border-radius:20px;font-weight:bold;">-{discount_percent}%</span>
            </div>
            <ul style="margin:10px 0;padding-left:20px;font-size:13px;">{items_html}</ul>
            <div style="border-top:2px dashed #059669;padding-top:10px;margin-top:10px;">
                <div style="display:flex;justify-content:space-between;font-size:13px;color:#666;">
                    <span>Precio normal:</span>
                    <span style="text-decoration:line-through;">${total_price:,.2f}</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:13px;color:#059669;">
                    <span>Tu ahorro:</span>
                    <span>-${discount_amount:,.2f}</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:18px;font-weight:bold;color:#059669;margin-top:5px;">
                    <span>Precio Combo:</span>
                    <span>${bundle_price:,.2f}</span>
                </div>
            </div>
            <p style="font-size:11px;color:#666;margin-top:10px;text-align:center;">Di "acepto el combo" para agregarlo a tu carrito con el descuento.</p>
        </div>
        '''
        
        return json.dumps({
            "success": True,
            "bundle_id": bundle_id,
            "products_count": len(products),
            "original_total": total_price,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "bundle_price": bundle_price,
            "html": html
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def check_stock_urgency(product_id: str) -> str:
    """
    Verifica el stock de un producto y genera mensaje de urgencia si es bajo.
    Usar para crear sensacion de escasez cuando el stock es limitado.
    
    Args:
        product_id: ID del producto a verificar
    """
    import random
    try:
        db = MongoDB.get_database()
        product = await db.products.find_one({"product_id": product_id})
        
        if not product:
            return json.dumps({"success": False, "error": "Producto no encontrado"})
        
        stock = product.get("stock", 0)
        name = product.get("name", "")
        
        # Generate urgency message based on stock level
        urgency_level = "none"
        message = ""
        
        if stock == 0:
            urgency_level = "out_of_stock"
            message = f"Lo siento, {name} esta agotado. ¿Te muestro alternativas similares?"
        elif stock <= 3:
            urgency_level = "critical"
            message = f"¡Solo quedan {stock} unidades de {name}! Este es uno de nuestros productos mas vendidos y vuela rapido."
        elif stock <= 10:
            urgency_level = "low"
            # Simulate recent purchases
            recent_buyers = random.randint(3, 8)
            message = f"Stock limitado: quedan {stock} unidades de {name}. {recent_buyers} personas lo compraron en las ultimas 24 horas."
        elif stock <= 20:
            urgency_level = "medium"
            message = f"Disponible: {stock} unidades de {name}. Es uno de nuestros productos populares."
        else:
            urgency_level = "normal"
            message = f"Tenemos {stock} unidades disponibles de {name}."
        
        return json.dumps({
            "success": True,
            "product_id": product_id,
            "product_name": name,
            "stock": stock,
            "urgency_level": urgency_level,
            "message": message
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def offer_financing(total_amount: float) -> str:
    """
    Ofrece opciones de financiamiento para el monto dado.
    Usar cuando el cliente duda por el precio o menciona que es caro.
    
    Args:
        total_amount: Monto total a financiar
    """
    try:
        if total_amount < 100:
            return json.dumps({"success": False, "error": "Financiamiento disponible para compras mayores a $100"})
        
        # Calculate financing options
        options = []
        
        # 3 cuotas sin interés
        if total_amount >= 100:
            options.append({"cuotas": 3, "monto_cuota": round(total_amount / 3, 2), "interes": 0, "total": total_amount})
        
        # 6 cuotas sin interés
        if total_amount >= 200:
            options.append({"cuotas": 6, "monto_cuota": round(total_amount / 6, 2), "interes": 0, "total": total_amount})
        
        # 12 cuotas sin interés
        if total_amount >= 500:
            options.append({"cuotas": 12, "monto_cuota": round(total_amount / 12, 2), "interes": 0, "total": total_amount})
        
        # Generate HTML
        rows = "".join([f'<tr style="border-bottom:1px solid #eee;"><td style="padding:10px;text-align:center;font-weight:bold;color:#4F46E5;">{o["cuotas"]}x</td><td style="padding:10px;text-align:center;font-size:18px;font-weight:bold;">${o["monto_cuota"]:,.2f}</td><td style="padding:10px;text-align:center;color:#059669;font-weight:bold;">Sin interes</td></tr>' for o in options])
        
        html = f'''
        <div style="margin:10px 0;border:2px solid #4F46E5;border-radius:12px;padding:15px;background:#f8fafc;">
            <h4 style="color:#4F46E5;margin:0 0 10px 0;">Opciones de Pago - Total: ${total_amount:,.2f}</h4>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <thead>
                    <tr style="background:#4F46E5;color:white;">
                        <th style="padding:10px;">Cuotas</th>
                        <th style="padding:10px;">Monto/Cuota</th>
                        <th style="padding:10px;">Interes</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <p style="font-size:11px;color:#666;margin-top:10px;text-align:center;">Todas las tarjetas de credito aceptadas. El financiamiento se procesa al confirmar la orden.</p>
        </div>
        '''
        
        return json.dumps({"success": True, "total_amount": total_amount, "options": options, "html": html})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def offer_extended_warranty(product_id: str) -> str:
    """
    Ofrece garantia extendida para un producto.
    Usar despues de que el cliente decide comprar un producto de alto valor.
    
    Args:
        product_id: ID del producto
    """
    try:
        db = MongoDB.get_database()
        product = await db.products.find_one({"product_id": product_id})
        
        if not product:
            return json.dumps({"success": False, "error": "Producto no encontrado"})
        
        price = product.get("price", 0)
        name = product.get("name", "")
        
        # Calculate warranty prices (based on product price)
        warranty_1y = round(price * 0.05, 2)  # 5% for 1 year
        warranty_2y = round(price * 0.08, 2)  # 8% for 2 years
        warranty_3y = round(price * 0.10, 2)  # 10% for 3 years
        
        html = f'''
        <div style="margin:10px 0;border:2px solid #8b5cf6;border-radius:12px;padding:15px;background:#faf5ff;">
            <h4 style="color:#8b5cf6;margin:0 0 10px 0;">Protege tu {name}</h4>
            <p style="font-size:12px;color:#666;margin-bottom:10px;">Garantia extendida con cobertura total: reparacion o reemplazo sin costo.</p>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <tr style="border-bottom:1px solid #e9d5ff;">
                    <td style="padding:8px;">+1 año adicional</td>
                    <td style="padding:8px;text-align:right;font-weight:bold;color:#8b5cf6;">+${warranty_1y:,.2f}</td>
                </tr>
                <tr style="border-bottom:1px solid #e9d5ff;">
                    <td style="padding:8px;">+2 años adicionales</td>
                    <td style="padding:8px;text-align:right;font-weight:bold;color:#8b5cf6;">+${warranty_2y:,.2f}</td>
                </tr>
                <tr style="background:#f3e8ff;">
                    <td style="padding:8px;font-weight:bold;">+3 años adicionales <span style="color:#059669;font-size:10px;">RECOMENDADO</span></td>
                    <td style="padding:8px;text-align:right;font-weight:bold;color:#8b5cf6;">+${warranty_3y:,.2f}</td>
                </tr>
            </table>
            <p style="font-size:11px;color:#666;margin-top:10px;">¿Te gustaria agregar garantia extendida? Solo dime cuantos años.</p>
        </div>
        '''
        
        return json.dumps({
            "success": True,
            "product_id": product_id,
            "product_name": name,
            "product_price": price,
            "warranty_options": [
                {"years": 1, "price": warranty_1y},
                {"years": 2, "price": warranty_2y},
                {"years": 3, "price": warranty_3y}
            ],
            "html": html
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def apply_coupon(coupon_code: str) -> str:
    """
    Aplica un cupon de descuento al carrito actual.
    
    Args:
        coupon_code: Codigo del cupon a aplicar
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        db = MongoDB.get_database()
        stock_service = get_stock_service()
        
        cart = await stock_service.get_cart_total(conversation_id)
        if not cart.get("items"):
            return json.dumps({"success": False, "error": "El carrito esta vacio"})
        
        coupon = await db.coupons.find_one({"code": coupon_code.upper(), "active": True})
        if not coupon:
            return json.dumps({"success": False, "error": "Cupon no valido o expirado"})
        
        if coupon.get("used_count", 0) >= coupon.get("usage_limit", 0):
            return json.dumps({"success": False, "error": "Este cupon ya alcanzo su limite de uso"})
        
        if cart["total"] < coupon.get("min_purchase", 0):
            return json.dumps({"success": False, "error": f"Compra minima de ${coupon['min_purchase']} requerida"})
        
        if coupon["discount_type"] == "percentage":
            discount = cart["total"] * (coupon["discount_value"] / 100)
            discount = min(discount, coupon.get("max_discount", discount))
        else:
            discount = coupon["discount_value"]
        
        new_total = cart["total"] - discount
        
        await db.cart_coupons.update_one(
            {"conversation_id": conversation_id},
            {"$set": {"coupon_code": coupon_code.upper(), "discount": discount, "discount_percent": coupon["discount_value"], "original_total": cart["total"], "new_total": new_total, "applied_at": datetime.utcnow()}},
            upsert=True
        )
        
        return json.dumps({"success": True, "coupon_code": coupon_code.upper(), "discount_percent": coupon["discount_value"], "discount_amount": discount, "original_total": cart["total"], "new_total": new_total, "message": f"Cupon {coupon_code.upper()} aplicado. Descuento: ${discount:,.2f} ({coupon['discount_value']}%)"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def get_available_coupons() -> str:
    """
    Obtiene los cupones disponibles para el cliente.
    Usar cuando el cliente pregunta por descuentos o promociones.
    """
    try:
        db = MongoDB.get_database()
        coupons = await db.coupons.find({"active": True, "is_followup": False}).to_list(10)
        
        if not coupons:
            return json.dumps({"success": True, "coupons": [], "message": "No hay cupones disponibles en este momento."})
        
        coupon_list = []
        for c in coupons:
            if c.get("used_count", 0) < c.get("usage_limit", 0):
                coupon_list.append({"code": c["code"], "description": c["description"], "discount": f"{c['discount_value']}%" if c["discount_type"] == "percentage" else f"${c['discount_value']}", "min_purchase": c.get("min_purchase", 0)})
        
        return json.dumps({"success": True, "coupons": coupon_list, "count": len(coupon_list)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def apply_followup_discount(level: int = 1) -> str:
    """
    Aplica descuento automatico de follow-up.
    Level 1 = 10%, Level 2 = 15%.
    Solo usar cuando se ofrece descuento por follow-up.
    
    Args:
        level: Nivel del descuento (1=10%, 2=15%)
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        db = MongoDB.get_database()
        stock_service = get_stock_service()
        
        cart = await stock_service.get_cart_total(conversation_id)
        if not cart.get("items"):
            return json.dumps({"success": False, "error": "El carrito esta vacio"})
        
        coupon_code = "FOLLOWUP10" if level == 1 else "FOLLOWUP15"
        coupon = await db.coupons.find_one({"code": coupon_code, "active": True})
        
        if not coupon:
            return json.dumps({"success": False, "error": "Descuento no disponible"})
        
        discount = cart["total"] * (coupon["discount_value"] / 100)
        discount = min(discount, coupon.get("max_discount", discount))
        new_total = cart["total"] - discount
        
        await db.cart_coupons.update_one(
            {"conversation_id": conversation_id},
            {"$set": {"coupon_code": coupon_code, "discount": discount, "discount_percent": coupon["discount_value"], "original_total": cart["total"], "new_total": new_total, "is_followup": True, "followup_level": level, "applied_at": datetime.utcnow()}},
            upsert=True
        )
        
        await db.coupons.update_one({"code": coupon_code}, {"$inc": {"used_count": 1}})
        
        return json.dumps({"success": True, "coupon_code": coupon_code, "discount_percent": coupon["discount_value"], "discount_amount": discount, "original_total": cart["total"], "new_total": new_total, "message": f"Descuento especial del {coupon['discount_value']}% aplicado. Ahorras ${discount:,.2f}!"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def update_cart_quantity(product_id: str, new_quantity: int) -> str:
    """
    Actualiza la cantidad de un producto en el carrito.
    Usa esto cuando el cliente quiere cambiar la cantidad de un producto ya agregado.
    
    Args:
        product_id: Identificador del producto (numero, SKU o nombre)
        new_quantity: Nueva cantidad deseada (debe ser mayor a 0)
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        user_id = ctx["user_id"]
        
        if new_quantity < 1:
            return json.dumps({"success": False, "error": "La cantidad debe ser al menos 1. Para eliminar usa vaciar_producto_carrito."})
        
        stock_service = get_stock_service()
        
        # Resolve product ID
        resolved_id = await _resolve_product_id(conversation_id, product_id)
        
        # First remove the product completely
        await stock_service.remove_from_cart(
            conversation_id=conversation_id,
            product_id=resolved_id,
            quantity=None  # Remove all
        )
        
        # Then add with new quantity
        result = await stock_service.reserve_stock(
            conversation_id=conversation_id,
            product_id=resolved_id,
            quantity=new_quantity,
            user_id=user_id
        )
        
        if not result.get("success"):
            return json.dumps(result)
        
        cart = await stock_service.get_cart_total(conversation_id)
        html = _generate_cart_html(cart) if cart["items"] else "<p>Tu carrito esta vacio.</p>"
        
        return json.dumps({
            "success": True,
            "action": "updated",
            "product_name": result.get("product_name"),
            "new_quantity": new_quantity,
            "cart_total": cart["total"],
            "cart_items": cart["item_count"],
            "html": html,
            "message": f"Cantidad actualizada: {result.get('product_name')} ahora tiene {new_quantity} unidades."
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def remove_product_from_cart(product_identifier: str) -> str:
    """
    Elimina completamente un producto del carrito.
    Usa esto cuando el cliente quiere quitar un producto especifico.
    
    Args:
        product_identifier: Nombre del producto o parte del nombre (ej: "lampara", "espejo", "lampara de pie")
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        stock_service = get_stock_service()
        
        # Get current cart to find the product
        cart = await stock_service.get_cart_total(conversation_id)
        
        if not cart["items"]:
            return json.dumps({
                "success": False,
                "error": "El carrito esta vacio."
            })
        
        # Convert cart items to product format for similarity matching
        cart_products = [
            {"id": item["product_id"], "name": item["product_name"]}
            for item in cart["items"]
        ]
        
        # Use similarity matching to find the best match
        best_match = _find_best_match(product_identifier, cart_products, threshold=0.25)
        
        if not best_match:
            # List available products in cart
            cart_product_names = [f"- {item['product_name']}" for item in cart["items"]]
            return json.dumps({
                "success": False,
                "error": f"No encontre '{product_identifier}' en el carrito.",
                "cart_products": cart_product_names,
                "suggestion": "Productos en el carrito:\n" + "\n".join(cart_product_names)
            })
        
        # Find the full item data
        found_item = next((item for item in cart["items"] if item["product_id"] == best_match["id"]), None)
        
        result = await stock_service.remove_from_cart(
            conversation_id=conversation_id,
            product_id=best_match["id"],
            quantity=None  # Remove all
        )
        
        if not result.get("success"):
            return json.dumps(result)
        
        updated_cart = await stock_service.get_cart_total(conversation_id)
        html = _generate_cart_html(updated_cart) if updated_cart["items"] else "<p>Tu carrito esta vacio.</p>"
        
        # Store pending discount offer for this specific product (5% off if they add it back)
        db = MongoDB.get_database()
        await db.pending_product_discounts.update_one(
            {"conversation_id": conversation_id, "product_id": best_match["id"]},
            {
                "$set": {
                    "product_name": best_match["name"],
                    "product_price": found_item["price"] if found_item else 0,
                    "discount_percent": 5,
                    "created_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(minutes=15)
                }
            },
            upsert=True
        )
        
        # Build discount offer message
        discounted_price = found_item["price"] * 0.95 if found_item else 0
        discount_offer = f'''
        <div style="margin-top:10px;padding:12px;background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;">
            <div style="font-weight:600;color:#92400e;font-size:13px;">Oferta especial para ti</div>
            <div style="color:#78350f;font-size:12px;margin-top:4px;">
                Si decides volver a agregar <strong>{best_match["name"]}</strong>, te doy un <strong>5% de descuento</strong> (${discounted_price:,.2f} en lugar de ${found_item["price"]:,.2f}).
            </div>
            <button class="add-back-btn" data-product="{best_match["name"]}" style="margin-top:8px;background:#f59e0b;color:white;border:none;padding:8px 16px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Agregar con 5% descuento</button>
        </div>''' if found_item else ""
        
        return json.dumps({
            "success": True,
            "action": "removed",
            "product_id": best_match["id"],
            "product_name": best_match["name"],
            "cart_total": updated_cart["total"],
            "cart_items": updated_cart["item_count"],
            "html": html + discount_offer,
            "discount_available": True,
            "discount_percent": 5,
            "message": f"Eliminado: {best_match['name']} del carrito."
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def clear_cart() -> str:
    """
    Vacia completamente el carrito, eliminando todos los productos.
    Usa esto cuando el cliente quiere empezar de nuevo o cancelar su compra.
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        stock_service = get_stock_service()
        
        # Get current cart to know what to remove
        cart = await stock_service.get_cart_total(conversation_id)
        
        if not cart["items"]:
            return json.dumps({
                "success": True,
                "message": "El carrito ya estaba vacio."
            })
        
        # Remove each item
        removed_count = 0
        for item in cart["items"]:
            await stock_service.remove_from_cart(
                conversation_id=conversation_id,
                product_id=item["product_id"],
                quantity=None
            )
            removed_count += 1
        
        return json.dumps({
            "success": True,
            "action": "cleared",
            "removed_items": removed_count,
            "html": "<p>Tu carrito esta vacio.</p>",
            "message": f"Carrito vaciado. Se eliminaron {removed_count} productos."
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def confirm_cart_before_checkout() -> str:
    """
    Muestra un resumen detallado del carrito para confirmacion antes del checkout.
    Usa esto antes de pedir los datos del cliente para que confirme su pedido.
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        stock_service = get_stock_service()
        cart = await stock_service.get_cart_total(conversation_id)
        
        if not cart["items"]:
            return json.dumps({
                "success": False,
                "error": "El carrito esta vacio. Agrega productos antes de continuar."
            })
        
        # Generate detailed confirmation HTML
        items_rows = []
        for i, item in enumerate(cart["items"], 1):
            items_rows.append(f"""
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:10px;text-align:center;">{i}</td>
                <td style="padding:10px;">{item["product_name"]}</td>
                <td style="padding:10px;text-align:center;">{item["quantity"]}</td>
                <td style="padding:10px;text-align:right;">${item["price"]:,.2f}</td>
                <td style="padding:10px;text-align:right;font-weight:bold;">${item["subtotal"]:,.2f}</td>
            </tr>
            """)
        
        html = f"""
        <div style="border:2px solid #4F46E5;border-radius:12px;padding:20px;margin:10px 0;background:#f8fafc;">
            <h3 style="color:#4F46E5;margin:0 0 15px 0;text-align:center;">Resumen de tu Pedido</h3>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <thead>
                    <tr style="background:#4F46E5;color:white;">
                        <th style="padding:10px;text-align:center;">#</th>
                        <th style="padding:10px;text-align:left;">Producto</th>
                        <th style="padding:10px;text-align:center;">Cant.</th>
                        <th style="padding:10px;text-align:right;">Precio</th>
                        <th style="padding:10px;text-align:right;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(items_rows)}
                </tbody>
                <tfoot>
                    <tr style="background:#059669;color:white;font-weight:bold;">
                        <td colspan="4" style="padding:12px;text-align:right;">TOTAL A PAGAR:</td>
                        <td style="padding:12px;text-align:right;font-size:18px;">${cart["total"]:,.2f}</td>
                    </tr>
                </tfoot>
            </table>
            <p style="text-align:center;color:#666;font-size:12px;margin-top:15px;">
                Los productos estan reservados por 15 minutos. Confirma para continuar con el checkout.
            </p>
        </div>
        """
        
        return json.dumps({
            "success": True,
            "cart": cart,
            "html": html,
            "message": "Resumen del pedido listo para confirmacion.",
            "requires_confirmation": True
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def lookup_order(order_number: str, total_amount: float) -> str:
    """
    Consulta el estado de un pedido anterior.
    Por seguridad, requiere el numero de orden Y el monto total para verificar.
    
    Args:
        order_number: Numero de orden (ej: ORD-20260106-1234)
        total_amount: Monto total del pedido para verificacion
    """
    try:
        db = MongoDB.get_database()
        
        # Find order by number
        order = await db.orders.find_one({"order_number": order_number})
        
        if not order:
            return json.dumps({
                "success": False,
                "error": f"No se encontro el pedido {order_number}. Verifica el numero de orden."
            })
        
        # Verify total amount (with small tolerance for floating point)
        if abs(order["total"] - total_amount) > 0.01:
            return json.dumps({
                "success": False,
                "error": "El monto total no coincide. Por seguridad, no podemos mostrar los detalles del pedido."
            })
        
        # Generate order details HTML
        items_rows = []
        for item in order.get("items", []):
            items_rows.append(f"""
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;">{item["product_name"]}</td>
                <td style="padding:8px;text-align:center;">{item["quantity"]}</td>
                <td style="padding:8px;text-align:right;">${item["unit_price"]:,.2f}</td>
                <td style="padding:8px;text-align:right;">${item["subtotal"]:,.2f}</td>
            </tr>
            """)
        
        status_colors = {
            "confirmed": "#059669",
            "processing": "#2563eb",
            "shipped": "#7c3aed",
            "delivered": "#16a34a",
            "cancelled": "#dc2626"
        }
        status_labels = {
            "confirmed": "Confirmado",
            "processing": "En Proceso",
            "shipped": "Enviado",
            "delivered": "Entregado",
            "cancelled": "Cancelado"
        }
        
        status = order.get("status", "confirmed")
        status_color = status_colors.get(status, "#666")
        status_label = status_labels.get(status, status)
        
        html = f"""
        <div style="border:2px solid {status_color};border-radius:12px;padding:20px;margin:10px 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3 style="color:#333;margin:0;">Pedido #{order["order_number"]}</h3>
                <span style="background:{status_color};color:white;padding:5px 12px;border-radius:20px;font-size:12px;">{status_label}</span>
            </div>
            
            <div style="background:#f5f5f5;border-radius:8px;padding:12px;margin-bottom:15px;">
                <p style="margin:5px 0;font-size:13px;"><strong>Cliente:</strong> {order["customer"]["name"]}</p>
                <p style="margin:5px 0;font-size:13px;"><strong>Entrega:</strong> {order["delivery"]["slot_label"]}</p>
                <p style="margin:5px 0;font-size:13px;"><strong>Direccion:</strong> {order["delivery"]["address"]}</p>
            </div>
            
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead>
                    <tr style="background:#f5f5f5;">
                        <th style="padding:8px;text-align:left;">Producto</th>
                        <th style="padding:8px;text-align:center;">Cant.</th>
                        <th style="padding:8px;text-align:right;">Precio</th>
                        <th style="padding:8px;text-align:right;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(items_rows)}
                </tbody>
                <tfoot>
                    <tr style="border-top:2px solid #333;font-weight:bold;">
                        <td colspan="3" style="padding:10px;text-align:right;">TOTAL:</td>
                        <td style="padding:10px;text-align:right;">${order["total"]:,.2f}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        """
        
        return json.dumps({
            "success": True,
            "order_number": order["order_number"],
            "status": status_label,
            "total": order["total"],
            "customer_name": order["customer"]["name"],
            "delivery_date": order["delivery"]["date"],
            "html": html
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def cancel_order(order_number: str, total_amount: float, reason: str = "") -> str:
    """
    Solicita la cancelacion de un pedido.
    Por seguridad, requiere el numero de orden Y el monto total para verificar.
    Solo se pueden cancelar pedidos en estado 'confirmed'.
    
    Args:
        order_number: Numero de orden (ej: ORD-20260106-1234)
        total_amount: Monto total del pedido para verificacion
        reason: Motivo de la cancelacion (opcional)
    """
    try:
        db = MongoDB.get_database()
        
        # Find order by number
        order = await db.orders.find_one({"order_number": order_number})
        
        if not order:
            return json.dumps({
                "success": False,
                "error": f"No se encontro el pedido {order_number}."
            })
        
        # Verify total amount
        if abs(order["total"] - total_amount) > 0.01:
            return json.dumps({
                "success": False,
                "error": "El monto total no coincide. Por seguridad, no podemos procesar esta solicitud."
            })
        
        # Check if order can be cancelled
        if order.get("status") != "confirmed":
            return json.dumps({
                "success": False,
                "error": f"El pedido no puede ser cancelado porque ya esta en estado '{order.get('status')}'."
            })
        
        # Update order status
        await db.orders.update_one(
            {"order_number": order_number},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": datetime.utcnow(),
                    "cancellation_reason": reason,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Restore stock for each item
        for item in order.get("items", []):
            await db.products.update_one(
                {"id": item["product_id"]},
                {"$inc": {"stock": item["quantity"]}}
            )
        
        # Restore delivery slot capacity
        if order.get("delivery", {}).get("slot_id"):
            await db.delivery_slots.update_one(
                {"_id": order["delivery"]["slot_id"]},
                {"$inc": {"current_orders": -1}}
            )
        
        return json.dumps({
            "success": True,
            "order_number": order_number,
            "status": "cancelled",
            "message": f"Pedido {order_number} cancelado exitosamente. El stock ha sido restaurado.",
            "refund_info": "El reembolso se procesara en 3-5 dias habiles si aplica."
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# List of all tools
SALES_TOOLS = [
    search_products,
    check_stock,
    add_to_cart,
    update_cart_quantity,
    remove_product_from_cart,
    remove_from_cart,  # Keep for backward compatibility
    clear_cart,
    get_cart,
    confirm_cart_before_checkout,
    get_delivery_slots,
    select_delivery_slot,
    create_order,
    lookup_order,
    cancel_order,
    escalate_to_human,
    # Budget & Coupon tools
    create_budget_proposal,
    add_budget_proposal_to_cart,
    apply_coupon,
    get_available_coupons,
    apply_followup_discount,
    # Sales strategy tools
    get_cross_sell_recommendations,
    create_bundle_offer,
    check_stock_urgency,
    offer_financing,
    offer_extended_warranty
]


# ============================================================================
# LLM CONFIGURATION (AGNOSTIC - Can swap ChatOpenAI for any LangChain LLM)
# ============================================================================

def get_llm():
    """
    Get the LLM instance. This is the ONLY place where the LLM provider is configured.
    To change providers, just swap ChatOpenAI for ChatAnthropic, ChatGoogleGenerativeAI, etc.
    
    OPTIMIZED: Lower temperature for faster, more consistent responses.
    """
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3  # Reduced from 0.7 for faster, more deterministic responses
    )


def get_system_prompt(user_context: Dict, cart_summary: str) -> str:
    """Generate system prompt for the sales agent"""
    return f"""Eres Taylor, una asistente de ventas experta para articulos del hogar.

**Personalidad:** Calida, profesional, orientada a soluciones.

**Herramientas Disponibles:**
- search_products: Buscar productos en el catalogo
- check_stock: Verificar stock de un producto
- add_to_cart: Agregar producto al carrito (SOLO con numero # o SKU exacto)
- update_cart_quantity: Cambiar cantidad de un producto en el carrito
- remove_product_from_cart: Eliminar un producto del carrito
- clear_cart: Vaciar todo el carrito
- get_cart: Ver carrito actual
- confirm_cart_before_checkout: Mostrar resumen antes de pagar
- get_delivery_slots: Ver horarios de entrega (tabla con codigos A1, B2, etc.)
- select_delivery_slot: Seleccionar horario con codigo (A1, B2, C3, etc.)
- create_order: Crear orden final (SOLO despues de seleccionar horario y tener todos los datos)
- lookup_order: Consultar pedido anterior (requiere numero + monto total)
- cancel_order: Cancelar pedido (requiere numero + monto total)
- escalate_to_human: Escalar a supervisor humano
- create_budget_proposal: Crear propuesta optimizada para un presupuesto
- add_budget_proposal_to_cart: Agregar toda la propuesta al carrito
- apply_coupon: Aplicar cupon de descuento
- get_available_coupons: Ver cupones disponibles
- apply_followup_discount: Aplicar descuento de follow-up (hasta 20%)
- get_cross_sell_recommendations: Obtener productos complementarios (USAR despues de agregar al carrito)
- create_bundle_offer: Crear oferta combo con descuento adicional
- check_stock_urgency: Verificar stock y generar urgencia si es bajo
- offer_financing: Mostrar opciones de pago en cuotas
- offer_extended_warranty: Ofrecer garantia extendida

**REGLA CRITICA - add_to_cart SOLO CON NUMERO O SKU:**

Cuando uses add_to_cart, SIEMPRE pasa el NUMERO de la tabla (1, 2, 3...) o el SKU EXACTO.
NUNCA pases nombres de productos ni descripciones.

Ejemplos CORRECTOS de add_to_cart:
- Cliente dice "quiero el primero" -> add_to_cart(product_id="1", quantity=1)
- Cliente dice "dame el #2" -> add_to_cart(product_id="2", quantity=1)
- Cliente dice "quiero 2 del tercero" -> add_to_cart(product_id="3", quantity=2)
- Cliente dice "agrega el ESPEJO-BANO-LED" -> add_to_cart(product_id="ESPEJO-BANO-LED", quantity=1)

Ejemplos INCORRECTOS (NUNCA hagas esto):
- add_to_cart(product_id="espejo de baño", quantity=1) <- MAL, usa el numero
- add_to_cart(product_id="Espejo Decorativo", quantity=1) <- MAL, usa el numero
- add_to_cart(product_id="el espejo", quantity=1) <- MAL, usa el numero

**REGLA CRITICA - SIEMPRE MOSTRAR OPCIONES PRIMERO:**

NUNCA agregues productos al carrito automaticamente. SIEMPRE usa search_products primero para mostrar opciones al cliente.

Ejemplos:
- "quiero una cama" -> search_products("cama") -> mostrar opciones -> cliente elige -> add_to_cart
- "dame un juego de ollas" -> search_products("juego de ollas") -> mostrar opciones -> cliente elige -> add_to_cart
- "necesito lamparas" -> search_products("lamparas") -> mostrar opciones -> cliente elige -> add_to_cart
- "me llevo un sofa" -> search_products("sofa") -> mostrar opciones -> cliente elige -> add_to_cart

USA add_to_cart SOLO cuando el cliente:
1. Ya vio las opciones y elige una especifica: "quiero el #2", "dame el primero", "agrega el SKU-123"
2. Indica un producto especifico por numero o SKU de la tabla mostrada

El flujo SIEMPRE es: Buscar -> Mostrar opciones -> Cliente elige -> Agregar al carrito (CON NUMERO)

**Proceso de Venta:**
1. Entender necesidad -> search_products
2. Mostrar opciones con tabla (imagen, precio, stock, SKU)
3. Cliente elige -> add_to_cart (reserva 15 min) - AGREGA INMEDIATAMENTE sin pedir confirmacion
4. DESPUES de agregar al carrito -> get_cross_sell_recommendations() para sugerir complementos
5. Si quiere modificar -> update_cart_quantity o remove_product_from_cart
6. Antes de checkout -> confirm_cart_before_checkout
7. Cliente confirma -> get_delivery_slots (muestra tabla con codigos A1, B2, etc.)
8. Cliente selecciona horario -> select_delivery_slot(slot_code="A2")
9. Pedir datos del cliente (nombre, DNI, telefono, email, direccion)
10. Cuando tenga TODOS los datos -> create_order(...)

**CRITICO - Agregar al Carrito:**
- Cuando el cliente dice "quiero el 1" o "agrega el edredon" -> USA add_to_cart INMEDIATAMENTE
- NO pidas confirmacion, NO preguntes "confirmo que agregue?", simplemente AGREGALO
- Si el cliente ya vio productos y dice un numero o nombre, AGREGALO sin volver a buscar

**CRITICO - Seleccion de Horario:**
La tabla muestra dias como filas (A=primer dia, B=segundo, etc.) y horas como columnas (1=09-12h, 2=12-15h, 3=15-18h, 4=18-21h).
- "A2" -> select_delivery_slot(slot_code="A2") = Primer dia, 12-15h
- "D2" -> select_delivery_slot(slot_code="D2") = Cuarto dia, 12-15h
- Cuando el cliente dice un codigo como "D2" -> USA select_delivery_slot INMEDIATAMENTE
- NO vuelvas a mostrar la tabla si el cliente ya eligio uno
- NO vuelvas a llamar select_delivery_slot si ya lo seleccionaste

**CRITICO - Crear Orden:**
- SOLO llama create_order UNA VEZ cuando tengas TODOS los datos del cliente
- Si ya llamaste create_order exitosamente, NO lo vuelvas a llamar
- Si el cliente dice "procede" y ya tienes los datos, llama create_order
- Si falta algun dato, PREGUNTA por el dato faltante, no repitas select_delivery_slot

**ESTRATEGIAS DE VENTA (USAR ACTIVAMENTE):**

1. CROSS-SELLING: Despues de agregar al carrito, SIEMPRE usa get_cross_sell_recommendations() para sugerir productos complementarios.

2. URGENCIA/ESCASEZ: Si el stock es bajo, usa check_stock_urgency() para crear sensacion de urgencia.
   - "Solo quedan 3 unidades!"
   - "X personas lo compraron hoy"

3. BUNDLES: Si el cliente tiene 2+ productos, ofrece create_bundle_offer() con descuento adicional (5-8%).

4. FINANCIAMIENTO: Si el cliente duda por precio o dice "es caro", usa offer_financing() para mostrar cuotas sin interes.

5. GARANTIA EXTENDIDA: Para productos de alto valor (>$300), ofrece offer_extended_warranty().

6. SOCIAL PROOF: Menciona ratings y reseñas de los productos cuando los muestres.

**CRITICO - CUANDO EL CLIENTE ELIMINA O REDUCE PRODUCTOS:**
Actua como un vendedor real que quiere retener la venta:
- Si elimina un producto: Pregunta amablemente "¿Hubo algo que no te convencio?" y ofrece:
  1. Un descuento del 5% si lo vuelve a agregar (el sistema ya lo guarda automaticamente)
  2. Sugerir un producto alternativo similar pero mas economico
  3. Preguntar si el precio es el problema para ofrecer financiamiento
- Si reduce cantidad: Pregunta si hay algo que puedas mejorar y menciona que con mas unidades podria obtener mejor precio
- NUNCA solo digas "listo, eliminado" - siempre intenta recuperar la venta
- Muestra el boton de "Agregar con 5% descuento" que viene en el HTML de la respuesta

**PRESUPUESTO:**
- "tengo X dolares para amoblar" -> create_budget_proposal(budget=X, room_type="general")
- "presupuesto de X para la sala" -> create_budget_proposal(budget=X, room_type="sala")

**CUPONES Y DESCUENTOS:**
- Preguntas por descuentos -> get_available_coupons()
- Aplicar cupon -> apply_coupon(coupon_code="CODIGO")
- Follow-up con descuento -> apply_followup_discount(level=X) donde X es el % (5, 8, 10, 12, 15, 18, 20)

**Reglas CRITICAS:**
- NUNCA inventes precios o stock
- SIEMPRE usa las herramientas para datos reales
- NO ofrezcas productos sin stock
- Los productos se reservan 15 minutos
- SE PROACTIVO: sugiere productos, ofrece descuentos, crea urgencia
- Actua como un vendedor real que quiere cerrar la venta

**Contexto del Cliente:**
{user_context.get('system_prompt', '')}

**Carrito Actual:**
{cart_summary if cart_summary else 'Vacio'}
"""


# ============================================================================
# SALES AGENT NODE (LangGraph)
# ============================================================================

async def sales_agent_node_v3(state: AgentState) -> AgentState:
    """
    Sales Agent Node V3 - LLM Agnostic with LangChain Tools
    """
    messages = state.get("messages", [])
    user_context = state.get("user_context", {})
    conversation_id = state.get("conversation_id", "")
    user_id = state.get("user_id", "anonymous")
    
    # Set tool context for this conversation (including messages for escalation)
    set_tool_context(conversation_id, user_id, messages)
    
    reasoning_steps = state.get("reasoning_trace", [])
    
    # Get current cart summary
    stock_service = get_stock_service()
    cart_data = await stock_service.get_cart_total(conversation_id)
    cart_summary = ""
    if cart_data.get("items"):
        cart_summary = f"{cart_data['item_count']} items, Total: ${cart_data['total']:,.2f}"
    
    # Get memory state (resumen de conversación anterior)
    memory_state = await get_memory_state(conversation_id)
    conversation_summary = memory_state.get("summary", "")
    
    if conversation_summary:
        print(f"\n[AGENT] Inyectando resumen de memoria ({len(conversation_summary)} chars)")
        print(f"[AGENT] Resumen: {conversation_summary[:200]}...")
    
    try:
        # Get LLM with tools bound
        llm = get_llm()
        llm_with_tools = llm.bind_tools(SALES_TOOLS)
        
        # Build messages for LLM
        system_prompt = get_system_prompt(user_context, cart_summary)
        
        # Inject conversation summary if exists
        if conversation_summary:
            system_prompt += f"\n\n**RESUMEN DE LA CONVERSACIÓN ANTERIOR:**\n{conversation_summary}"
        
        lc_messages = [SystemMessage(content=system_prompt)]
        
        # Add recent conversation messages (limit to last 10)
        recent_messages = messages[-10:] if len(messages) > 10 else messages
        print(f"[AGENT] Enviando {len(recent_messages)} mensajes recientes al LLM")
        for msg in recent_messages:
            content = msg.get("content", "")
            if content and len(content) > 2000:
                content = content[:2000] + "... [truncado]"
            if content:
                if msg.get("role") == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif msg.get("role") == "assistant":
                    lc_messages.append(AIMessage(content=content))
        
        # Invoke LLM
        response = await llm_with_tools.ainvoke(lc_messages)
        
        final_message = ""
        tool_results = []
        
        # Check for tool calls
        if response.tool_calls:
            for tool_call in response.tool_calls:
                func_name = tool_call["name"]
                func_args = tool_call["args"]
                
                # Log reasoning
                reasoning_steps.append({
                    "agent": "SalesAgent",
                    "action": f"tool:{func_name}",
                    "reasoning": f"Ejecutando {func_name} con args: {json.dumps(func_args, ensure_ascii=False)}",
                    "timestamp": datetime.utcnow().isoformat(),
                    "result": None
                })
                
                # Execute tool
                tool_func = None
                for t in SALES_TOOLS:
                    if t.name == func_name:
                        tool_func = t
                        break
                
                if tool_func:
                    result_str = await tool_func.ainvoke(func_args)
                    result = json.loads(result_str)
                    
                    # Add specific reasoning for certain tools
                    if func_name == "search_products":
                        reasoning_steps.append({
                            "agent": "Pinecone",
                            "action": "semantic_search",
                            "reasoning": f"Busqueda semantica: '{func_args.get('query')}' -> {result.get('count', 0)} resultados",
                            "timestamp": datetime.utcnow().isoformat(),
                            "result": {"query": func_args.get("query"), "results_count": result.get("count", 0)}
                        })
                    elif func_name == "add_to_cart" and result.get("success"):
                        reasoning_steps.append({
                            "agent": "StockReservation",
                            "action": "reserve",
                            "reasoning": f"Reserva creada: {result.get('product_name')} x{func_args.get('quantity', 1)} por 15 minutos",
                            "timestamp": datetime.utcnow().isoformat(),
                            "result": {"reserved_until": result.get("reserved_until")}
                        })
                    elif func_name == "create_order" and result.get("success"):
                        reasoning_steps.append({
                            "agent": "OrderService",
                            "action": "create_order",
                            "reasoning": f"Orden creada: {result.get('order_number')}. Stock actualizado.",
                            "timestamp": datetime.utcnow().isoformat(),
                            "result": {"order_number": result.get("order_number"), "total": result.get("total")}
                        })
                    elif func_name == "escalate_to_human":
                        return {
                            **state,
                            "requires_human": True,
                            "escalation": {
                                "id": str(datetime.utcnow().timestamp())[:8],
                                "conversation_id": conversation_id,
                                "reason": func_args.get("reason", "Escalacion solicitada"),
                                "classification": "agent_escalation",
                                "timestamp": datetime.utcnow().isoformat()
                            },
                            "reasoning_trace": reasoning_steps
                        }
                    
                    # Serialize result for checkpoint
                    try:
                        serialized_result = json.loads(json.dumps(result, default=str))
                    except:
                        serialized_result = {"status": "completed"}
                    
                    reasoning_steps[-1]["result"] = serialized_result
                    tool_results.append({
                        "tool_call_id": tool_call.get("id", ""),
                        "result": serialized_result
                    })
            
            # Get follow-up response with tool results
            lc_messages.append(response)
            for tr in tool_results:
                lc_messages.append(ToolMessage(
                    content=json.dumps(tr["result"]),
                    tool_call_id=tr["tool_call_id"]
                ))
            
            follow_up = await llm_with_tools.ainvoke(lc_messages)
            llm_response = follow_up.content or ""
            
            # Collect HTML from tool results
            html_parts = []
            message_parts = []
            for tr in tool_results:
                if isinstance(tr["result"], dict):
                    if "html_table" in tr["result"]:
                        html_parts.append(tr["result"]["html_table"])
                    elif "html" in tr["result"]:
                        html_parts.append(tr["result"]["html"])
                    elif "message" in tr["result"]:
                        message_parts.append(tr["result"]["message"])
            
            # Build final message
            if html_parts:
                final_message = "\n\n".join(html_parts)
            elif message_parts:
                final_message = "\n".join(message_parts)
                if llm_response:
                    final_message = llm_response
            else:
                final_message = llm_response
        else:
            final_message = response.content or ""
        
        # Log final response
        reasoning_steps.append({
            "agent": "SalesAgent",
            "action": "response",
            "reasoning": f"Respuesta generada ({len(final_message)} chars)",
            "timestamp": datetime.utcnow().isoformat(),
            "result": {"response_preview": final_message[:100] + "..." if len(final_message) > 100 else final_message}
        })
        
        # Get updated cart
        stock_service = get_stock_service()
        cart_items = await stock_service.get_cart(conversation_id)
        
        return {
            **state,
            "messages": [{"role": "assistant", "content": final_message}],
            "reasoning_trace": reasoning_steps,
            "cart": cart_items,
            "current_node": "sales_agent",
            "next_node": "memory_optimizer"
        }
        
    except Exception as e:
        error_message = f"Error en el agente de ventas: {str(e)}"
        reasoning_steps.append({
            "agent": "SalesAgent",
            "action": "error",
            "reasoning": error_message,
            "timestamp": datetime.utcnow().isoformat(),
            "result": {"error": str(e)}
        })
        
        return {
            **state,
            "messages": [{"role": "assistant", "content": "Lo siento, ocurrio un error. Por favor intenta de nuevo."}],
            "reasoning_trace": reasoning_steps,
            "current_node": "sales_agent",
            "next_node": "memory_optimizer"
        }
