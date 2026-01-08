"""
Sales Agent Node V3 - LLM Agnostic with LangChain Tools
- Uses LangChain @tool decorator for LLM-agnostic tool definitions
- Uses ChatOpenAI (can be swapped for any LangChain-compatible LLM)
- Products displayed in HTML table with images
- Stock validation with temporary reservations (5 min TTL)
- Full cart management with order confirmation
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
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


async def _resolve_product_id(conversation_id: str, identifier: str) -> str:
    """Resolve product by index, SKU, name, or UUID"""
    global _session_product_map
    identifier = str(identifier).strip()
    
    # If it's already a UUID format (8-4-4-4-12 pattern), return as-is
    uuid_pattern = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', re.IGNORECASE)
    if uuid_pattern.match(identifier):
        return identifier
    
    mapping = _session_product_map.get(conversation_id, {})
    
    # Try to parse as index (1, 2, 3...)
    try:
        index = int(identifier)
        if index in mapping.get("by_index", {}):
            return mapping["by_index"][index]
    except ValueError:
        pass
    
    # Try SKU (case insensitive)
    sku_upper = identifier.upper()
    if sku_upper in mapping.get("by_sku", {}):
        return mapping["by_sku"][sku_upper]
    
    # Try partial SKU match
    for sku, pid in mapping.get("by_sku", {}).items():
        if sku_upper in sku or sku in sku_upper:
            return pid
    
    # Try name (case insensitive, partial match)
    name_lower = identifier.lower()
    for name, pid in mapping.get("by_name", {}).items():
        if name_lower in name or name in name_lower:
            return pid
    
    # If not found in mapping, try to find in MongoDB by SKU or name
    db = MongoDB.get_database()
    
    # Try exact SKU match first
    product = await db.products.find_one({"sku": {"$regex": f"^{identifier}$", "$options": "i"}})
    if product:
        return product["id"]
    
    # Try partial SKU match
    product = await db.products.find_one({"sku": {"$regex": identifier, "$options": "i"}})
    if product:
        return product["id"]
    
    # Try name match with regex
    product = await db.products.find_one({"name": {"$regex": identifier, "$options": "i"}})
    if product:
        return product["id"]
    
    # Try splitting words and matching any
    words = identifier.lower().split()
    if len(words) > 1:
        for word in words:
            if len(word) > 3:  # Skip short words
                product = await db.products.find_one({"name": {"$regex": word, "$options": "i"}})
                if product:
                    return product["id"]
    
    # Last resort: use Pinecone semantic search
    try:
        from ...vectorstore.pinecone_store import PineconeStore
        vectorstore = PineconeStore()
        results = await vectorstore.search_products(identifier, top_k=1)
        if results and len(results) > 0:
            return results[0].get("id", identifier)
    except Exception:
        pass
    
    return identifier


def _generate_products_table(products: List[Dict]) -> str:
    """Generate HTML table for products with SKU"""
    if not products:
        return "<p>No hay productos disponibles.</p>"
    
    rows = []
    for p in products:
        stock_badge = f'<span style="color:green;">{p["stock"]} disp.</span>' if p["available"] else '<span style="color:red;">Sin stock</span>'
        image_html = f'<img src="{p["image_url"]}" alt="{p["name"]}" style="width:50px;height:50px;object-fit:cover;border-radius:4px;">' if p["image_url"] else '<span style="color:#999;">-</span>'
        
        row = f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px;text-align:center;font-weight:bold;color:#4F46E5;">{p["index"]}</td><td style="padding:8px;text-align:center;">{image_html}</td><td style="padding:8px;"><strong>{p["name"]}</strong><br/><small style="color:#666;">{p["category"]}</small><br/><code style="font-size:10px;background:#f0f0f0;padding:2px 4px;border-radius:3px;">{p["sku"]}</code></td><td style="padding:8px;text-align:right;font-weight:bold;color:#059669;">${p["price"]:,.2f}</td><td style="padding:8px;text-align:center;">{stock_badge}</td></tr>'
        rows.append(row)
    
    tbody_content = ''.join(rows)
    
    html = f'<table style="width:100%;border-collapse:collapse;margin:10px 0;font-size:14px;"><thead><tr style="background:#4F46E5;color:white;"><th style="padding:10px;text-align:center;border-radius:8px 0 0 0;">#</th><th style="padding:10px;text-align:center;">Imagen</th><th style="padding:10px;text-align:left;">Producto / SKU</th><th style="padding:10px;text-align:right;">Precio</th><th style="padding:10px;text-align:center;border-radius:0 8px 0 0;">Stock</th></tr></thead><tbody>{tbody_content}</tbody></table><p style="font-size:12px;color:#666;margin-top:8px;">Puedes agregar productos indicando el <strong>#</strong>, <strong>SKU</strong> o <strong>nombre</strong>. Ej: "Quiero 2 del producto 1" o "Agrega el ESP-CIR-ORO-80"</p>'
    
    return html


def _generate_cart_html(cart: Dict) -> str:
    """Generate HTML for cart display"""
    rows = []
    for item in cart["items"]:
        rows.append(f"""
        <tr>
            <td>{item["product_name"]}</td>
            <td style="text-align:center;">{item["quantity"]}</td>
            <td style="text-align:right;">${item["price"]:,.2f}</td>
            <td style="text-align:right;font-weight:bold;">${item["subtotal"]:,.2f}</td>
        </tr>
        """)
    
    return f"""
    <table style="width:100%;border-collapse:collapse;margin:10px 0;">
        <thead>
            <tr style="background:#f5f5f5;border-bottom:2px solid #ddd;">
                <th style="padding:8px;text-align:left;">Producto</th>
                <th style="padding:8px;text-align:center;">Cant.</th>
                <th style="padding:8px;text-align:right;">Precio</th>
                <th style="padding:8px;text-align:right;">Subtotal</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
        <tfoot>
            <tr style="border-top:2px solid #333;font-weight:bold;">
                <td colspan="3" style="padding:8px;text-align:right;">TOTAL:</td>
                <td style="padding:8px;text-align:right;">${cart["total"]:,.2f}</td>
            </tr>
        </tfoot>
    </table>
    <p style="font-size:12px;color:#666;">Los productos estan reservados por 5 minutos. Confirma tu orden para completar la compra.</p>
    """


def _generate_delivery_slots_html(slots_by_date: List[Dict]) -> str:
    """Generate HTML for delivery slots selection"""
    rows = []
    slot_index = 1
    for day in slots_by_date:
        for slot in day["slots"]:
            rows.append(f"""
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px;text-align:center;font-weight:bold;color:#4F46E5;">{slot_index}</td>
                <td style="padding:8px;">{day["day_name"]} {day["date"].split('-')[2]}/{day["date"].split('-')[1]}</td>
                <td style="padding:8px;">{slot["time"]}</td>
            </tr>
            """)
            slot_index += 1
    
    return f"""
    <div style="margin:10px 0;">
        <h4 style="color:#4F46E5;margin-bottom:10px;">Horarios de Entrega Disponibles</h4>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <thead>
                <tr style="background:#4F46E5;color:white;">
                    <th style="padding:10px;text-align:center;">#</th>
                    <th style="padding:10px;text-align:left;">Fecha</th>
                    <th style="padding:10px;text-align:left;">Horario</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        <p style="font-size:12px;color:#666;margin-top:8px;">Indica el numero del horario que prefieres. Ej: "Quiero el horario 3"</p>
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
    Agrega producto al carrito con reserva temporal de 5 minutos.
    Acepta: numero de tabla (#), SKU o nombre del producto.
    
    Args:
        product_id: Identificador del producto (numero, SKU o nombre)
        quantity: Cantidad a agregar (default: 1)
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        user_id = ctx["user_id"]
        
        stock_service = get_stock_service()
        
        resolved_id = await _resolve_product_id(conversation_id, product_id)
        
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
            "message": f"Agregado: {result.get('product_name')} x{quantity}. Reservado por 5 minutos."
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
async def select_delivery_slot(slot_number: int) -> str:
    """
    Selecciona un horario de entrega de la lista mostrada.
    Usar cuando el cliente indica que numero de horario quiere.
    Ejemplos de uso:
    - "el 17" -> select_delivery_slot(slot_number=17)
    - "quiero el horario 3" -> select_delivery_slot(slot_number=3)
    - "el domingo 11/01 a las 12" -> buscar el numero correspondiente y usar select_delivery_slot
    - "prefiero el 5" -> select_delivery_slot(slot_number=5)
    
    Args:
        slot_number: Numero del horario seleccionado de la lista (1, 2, 3, etc.)
    """
    try:
        db = MongoDB.get_database()
        slots = await db.delivery_slots.find(
            {"available": True, "$expr": {"$lt": ["$current_orders", "$max_orders"]}}
        ).sort([("date", 1), ("time_start", 1)]).to_list(30)
        
        if not slots:
            return json.dumps({"success": False, "error": "No hay horarios disponibles"})
        
        if slot_number < 1 or slot_number > len(slots):
            return json.dumps({
                "success": False, 
                "error": f"Numero de horario invalido. Debe ser entre 1 y {len(slots)}"
            })
        
        selected_slot = slots[slot_number - 1]
        
        # Store selected slot in context for later use
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        # Save selection to database for this conversation
        await db.pending_orders.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "selected_slot_index": slot_number,
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
            "message": f"Horario seleccionado: {selected_slot['day_name']} {selected_slot['date']} de {selected_slot['time_start']} a {selected_slot['time_end']}",
            "selected_slot": {
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
async def remove_product_from_cart(product_id: str) -> str:
    """
    Elimina completamente un producto del carrito.
    Usa esto cuando el cliente quiere quitar un producto especifico.
    
    Args:
        product_id: Identificador del producto (numero, SKU o nombre)
    """
    try:
        ctx = get_tool_context()
        conversation_id = ctx["conversation_id"]
        
        stock_service = get_stock_service()
        
        # Resolve product ID
        resolved_id = await _resolve_product_id(conversation_id, product_id)
        
        result = await stock_service.remove_from_cart(
            conversation_id=conversation_id,
            product_id=resolved_id,
            quantity=None  # Remove all
        )
        
        if not result.get("success"):
            return json.dumps(result)
        
        cart = await stock_service.get_cart_total(conversation_id)
        html = _generate_cart_html(cart) if cart["items"] else "<p>Tu carrito esta vacio.</p>"
        
        return json.dumps({
            "success": True,
            "action": "removed",
            "product_name": result.get("product_name", "Producto"),
            "cart_total": cart["total"],
            "cart_items": cart["item_count"],
            "html": html,
            "message": f"Producto eliminado del carrito."
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
                Los productos estan reservados por 5 minutos. Confirma para continuar con el checkout.
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
    escalate_to_human
]


# ============================================================================
# LLM CONFIGURATION (AGNOSTIC - Can swap ChatOpenAI for any LangChain LLM)
# ============================================================================

def get_llm():
    """
    Get the LLM instance. This is the ONLY place where the LLM provider is configured.
    To change providers, just swap ChatOpenAI for ChatAnthropic, ChatGoogleGenerativeAI, etc.
    """
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.7
    )


def get_system_prompt(user_context: Dict, cart_summary: str) -> str:
    """Generate system prompt for the sales agent"""
    return f"""Eres Taylor, una asistente de ventas experta para articulos del hogar.

**Personalidad:** Calida, profesional, orientada a soluciones.

**Herramientas Disponibles:**
- search_products: Buscar productos en el catalogo
- check_stock: Verificar stock de un producto
- add_to_cart: Agregar producto al carrito (acepta #, SKU o nombre del producto)
- update_cart_quantity: Cambiar cantidad de un producto en el carrito
- remove_product_from_cart: Eliminar un producto del carrito
- clear_cart: Vaciar todo el carrito
- get_cart: Ver carrito actual
- confirm_cart_before_checkout: Mostrar resumen antes de pagar
- get_delivery_slots: Ver horarios de entrega disponibles
- select_delivery_slot: Seleccionar horario de entrega (USAR cuando el cliente indica un numero de horario)
- create_order: Crear orden final (SOLO despues de seleccionar horario y tener todos los datos del cliente)
- lookup_order: Consultar pedido anterior (requiere numero + monto total)
- cancel_order: Cancelar pedido (requiere numero + monto total)
- escalate_to_human: Escalar a supervisor humano

**IMPORTANTE - Cuando usar add_to_cart vs search_products:**

USA add_to_cart INMEDIATAMENTE cuando el cliente usa verbos de compra/adquisicion:
- "quiero X" -> add_to_cart
- "dame X" -> add_to_cart  
- "agrega X" -> add_to_cart
- "ponme X" -> add_to_cart
- "me llevo X" -> add_to_cart
- "voy a llevar X" -> add_to_cart
- "necesito X" -> add_to_cart
- "compro X" -> add_to_cart

Ejemplos concretos de add_to_cart:
- "quiero 2 muebles tv" -> add_to_cart(product_id="mueble tv", quantity=2)
- "dame 1 tocador con espejo" -> add_to_cart(product_id="tocador espejo", quantity=1)
- "ponme 3 lamparas" -> add_to_cart(product_id="lampara", quantity=3)
- "me llevo el sofa" -> add_to_cart(product_id="sofa", quantity=1)

USA search_products SOLO para preguntas exploratorias SIN intencion de compra inmediata:
- "tienes muebles?" -> search_products
- "que lamparas hay?" -> search_products
- "muestrame espejos" -> search_products
- "busco sofas" -> search_products
- "me gustaria ver opciones de X" -> search_products

**Proceso de Venta:**
1. Entender necesidad -> search_products
2. Mostrar opciones con tabla (imagen, precio, stock, SKU)
3. Cliente elige -> add_to_cart (reserva 5 min)
4. Si quiere modificar -> update_cart_quantity o remove_product_from_cart
5. Antes de checkout -> confirm_cart_before_checkout
6. Cliente confirma -> get_delivery_slots (muestra lista numerada de horarios)
7. Cliente selecciona horario -> select_delivery_slot(slot_number=X)
   IMPORTANTE: Cuando el cliente dice "el 17", "quiero el horario 3", "el domingo a las 12" (buscar el numero correspondiente), etc. -> USA select_delivery_slot
8. Recopilar datos del cliente:
   - Nombre completo
   - Tipo documento (DNI, RUC, CE, Pasaporte)
   - Numero documento
   - Telefono
   - Email
   - Direccion
   - Referencia (opcional)
9. Crear orden -> create_order (ya tiene el horario guardado)

**CRITICO - Seleccion de Horario:**
Cuando el cliente indica un numero de horario de la lista mostrada, SIEMPRE usa select_delivery_slot:
- "el 17" -> select_delivery_slot(slot_number=17)
- "quiero el horario 3" -> select_delivery_slot(slot_number=3)
- "prefiero el 5" -> select_delivery_slot(slot_number=5)
- "el primero" -> select_delivery_slot(slot_number=1)
- "el ultimo" -> select_delivery_slot(slot_number=25) (o el numero correspondiente)
NO vuelvas a mostrar la lista de horarios si el cliente ya eligio uno.

**Consulta de Pedidos:**
- Para consultar un pedido: pedir numero de orden + monto total (seguridad)
- Para cancelar: solo pedidos en estado "confirmed"

**Reglas CRITICAS:**
- NUNCA inventes precios o stock
- SIEMPRE usa las herramientas para datos reales
- NO ofrezcas productos sin stock
- Los productos se reservan 5 minutos
- Para consultar/cancelar pedidos: SIEMPRE pedir numero + monto total
- Cuando el cliente dice "quiero", "dame", "agrega", "ponme", "me llevo" + producto -> USA add_to_cart, NO search_products

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
    
    try:
        # Get LLM with tools bound
        llm = get_llm()
        llm_with_tools = llm.bind_tools(SALES_TOOLS)
        
        # Build messages for LLM
        system_prompt = get_system_prompt(user_context, cart_summary)
        lc_messages = [SystemMessage(content=system_prompt)]
        
        # Add recent conversation messages (limit to last 10)
        recent_messages = messages[-10:] if len(messages) > 10 else messages
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
                            "reasoning": f"Reserva creada: {result.get('product_name')} x{func_args.get('quantity', 1)} por 5 minutos",
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
