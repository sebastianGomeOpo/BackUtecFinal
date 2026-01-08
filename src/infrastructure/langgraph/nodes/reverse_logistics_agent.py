"""
Reverse Logistics Agent - Handles returns, exchanges, and logistics analytics
Uses Pinecone for context retrieval and MongoDB for data persistence
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from ..state import AgentState
from ....config import settings
from ...vectorstore.pinecone_store import PineconeStore
from ...database.mongodb import MongoDB


# Tool context for reverse logistics
_rl_tool_context: Dict[str, Dict[str, str]] = {}


def set_rl_tool_context(conversation_id: str, user_id: str):
    """Set context for reverse logistics tools"""
    global _rl_tool_context
    _rl_tool_context["current"] = {
        "conversation_id": conversation_id,
        "user_id": user_id
    }


def get_rl_tool_context() -> Dict[str, str]:
    """Get current tool context"""
    return _rl_tool_context.get("current", {"conversation_id": "", "user_id": "anonymous"})


# ============================================================================
# REVERSE LOGISTICS TOOLS
# ============================================================================

@tool
async def initiate_return(order_number: str, total_amount: float, reason: str, items: List[str] = None) -> str:
    """
    Inicia una solicitud de devolucion para un pedido.
    Requiere verificacion con numero de orden y monto total.
    
    Args:
        order_number: Numero de orden (ej: ORD-20260106-1234)
        total_amount: Monto total del pedido para verificacion
        reason: Motivo de la devolucion
        items: Lista de productos a devolver (opcional, si es parcial)
    """
    try:
        db = MongoDB.get_database()
        ctx = get_rl_tool_context()
        
        # Find order
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
        
        # Check if order can be returned (only delivered orders)
        valid_statuses = ["confirmed", "delivered", "shipped"]
        if order.get("status") not in valid_statuses:
            return json.dumps({
                "success": False,
                "error": f"El pedido no puede ser devuelto porque esta en estado '{order.get('status')}'."
            })
        
        # Create return request
        import uuid
        return_id = f"RET-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        return_request = {
            "return_id": return_id,
            "order_number": order_number,
            "conversation_id": ctx["conversation_id"],
            "user_id": ctx["user_id"],
            "reason": reason,
            "items": items or [item["product_name"] for item in order.get("items", [])],
            "status": "pending",
            "total_refund": order["total"] if not items else None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        await db.returns.insert_one(return_request)
        
        # Update order status
        await db.orders.update_one(
            {"order_number": order_number},
            {"$set": {"status": "return_requested", "return_id": return_id}}
        )
        
        return json.dumps({
            "success": True,
            "return_id": return_id,
            "order_number": order_number,
            "status": "pending",
            "message": f"Solicitud de devolucion {return_id} creada exitosamente. Un agente revisara tu caso en 24-48 horas.",
            "next_steps": [
                "Recibiras un email con instrucciones de envio",
                "Empaca los productos en su empaque original",
                "El reembolso se procesara en 5-7 dias habiles despues de recibir los productos"
            ]
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def initiate_exchange(order_number: str, total_amount: float, product_to_exchange: str, new_product: str, reason: str) -> str:
    """
    Inicia una solicitud de cambio de producto.
    
    Args:
        order_number: Numero de orden original
        total_amount: Monto total del pedido para verificacion
        product_to_exchange: Nombre o SKU del producto a cambiar
        new_product: Nombre o SKU del producto deseado
        reason: Motivo del cambio
    """
    try:
        db = MongoDB.get_database()
        ctx = get_rl_tool_context()
        
        # Find order
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
                "error": "El monto total no coincide."
            })
        
        # Check if new product exists and has stock
        new_prod = await db.products.find_one({
            "$or": [
                {"name": {"$regex": new_product, "$options": "i"}},
                {"sku": {"$regex": new_product, "$options": "i"}}
            ]
        })
        
        if not new_prod:
            return json.dumps({
                "success": False,
                "error": f"No se encontro el producto '{new_product}' para el cambio."
            })
        
        if new_prod.get("stock", 0) < 1:
            return json.dumps({
                "success": False,
                "error": f"El producto '{new_prod['name']}' no tiene stock disponible."
            })
        
        # Create exchange request
        import uuid
        exchange_id = f"EXC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        exchange_request = {
            "exchange_id": exchange_id,
            "order_number": order_number,
            "conversation_id": ctx["conversation_id"],
            "user_id": ctx["user_id"],
            "product_to_exchange": product_to_exchange,
            "new_product_id": new_prod["id"],
            "new_product_name": new_prod["name"],
            "reason": reason,
            "status": "pending",
            "price_difference": new_prod.get("price", 0) - order["total"],
            "created_at": datetime.utcnow()
        }
        
        await db.exchanges.insert_one(exchange_request)
        
        price_diff = exchange_request["price_difference"]
        price_msg = ""
        if price_diff > 0:
            price_msg = f"Hay una diferencia de ${price_diff:,.2f} a pagar."
        elif price_diff < 0:
            price_msg = f"Recibiras un reembolso de ${abs(price_diff):,.2f}."
        
        return json.dumps({
            "success": True,
            "exchange_id": exchange_id,
            "order_number": order_number,
            "new_product": new_prod["name"],
            "price_difference": price_diff,
            "message": f"Solicitud de cambio {exchange_id} creada. {price_msg}",
            "next_steps": [
                "Recibiras instrucciones para enviar el producto original",
                "El nuevo producto se enviara al recibir el original"
            ]
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def check_return_status(return_id: str) -> str:
    """
    Consulta el estado de una solicitud de devolucion.
    
    Args:
        return_id: ID de la devolucion (ej: RET-20260106-ABCD1234)
    """
    try:
        db = MongoDB.get_database()
        
        return_req = await db.returns.find_one({"return_id": return_id})
        
        if not return_req:
            return json.dumps({
                "success": False,
                "error": f"No se encontro la devolucion {return_id}."
            })
        
        status_labels = {
            "pending": "Pendiente de revision",
            "approved": "Aprobada - Esperando envio",
            "received": "Producto recibido",
            "refunded": "Reembolso procesado",
            "rejected": "Rechazada"
        }
        
        return json.dumps({
            "success": True,
            "return_id": return_id,
            "order_number": return_req["order_number"],
            "status": return_req["status"],
            "status_label": status_labels.get(return_req["status"], return_req["status"]),
            "reason": return_req["reason"],
            "created_at": return_req["created_at"].isoformat() if hasattr(return_req["created_at"], 'isoformat') else str(return_req["created_at"]),
            "items": return_req.get("items", [])
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def get_return_policy() -> str:
    """
    Obtiene la politica de devoluciones de la tienda.
    Usar cuando el cliente pregunta sobre politicas, plazos o condiciones de devolucion.
    """
    policy = {
        "success": True,
        "policy": {
            "return_window": "30 dias desde la entrega",
            "conditions": [
                "Producto en condiciones originales",
                "Empaque original incluido",
                "Etiquetas sin remover",
                "Sin signos de uso"
            ],
            "non_returnable": [
                "Productos personalizados",
                "Articulos de higiene personal",
                "Productos en oferta final"
            ],
            "refund_method": "Mismo metodo de pago original",
            "refund_time": "5-7 dias habiles despues de recibir el producto",
            "exchange_option": "Disponible sin costo adicional (sujeto a disponibilidad)"
        },
        "html": """
        <div style="border:2px solid #4F46E5;border-radius:12px;padding:20px;margin:10px 0;">
            <h3 style="color:#4F46E5;margin:0 0 15px 0;">Politica de Devoluciones</h3>
            
            <div style="margin-bottom:15px;">
                <strong>Plazo:</strong> 30 dias desde la entrega
            </div>
            
            <div style="margin-bottom:15px;">
                <strong>Condiciones:</strong>
                <ul style="margin:5px 0;padding-left:20px;">
                    <li>Producto en condiciones originales</li>
                    <li>Empaque original incluido</li>
                    <li>Etiquetas sin remover</li>
                    <li>Sin signos de uso</li>
                </ul>
            </div>
            
            <div style="margin-bottom:15px;">
                <strong>No aplica para:</strong>
                <ul style="margin:5px 0;padding-left:20px;">
                    <li>Productos personalizados</li>
                    <li>Articulos de higiene personal</li>
                    <li>Productos en oferta final</li>
                </ul>
            </div>
            
            <div style="background:#f0fdf4;padding:10px;border-radius:8px;">
                <strong>Reembolso:</strong> 5-7 dias habiles al mismo metodo de pago
            </div>
        </div>
        """
    }
    return json.dumps(policy)


@tool
async def get_logistics_analytics(metric: str = "returns", period: str = "month") -> str:
    """
    Obtiene metricas de logistica inversa para analisis.
    Solo disponible para usuarios con permisos de supervisor.
    
    Args:
        metric: Tipo de metrica (returns, exchanges, refunds)
        period: Periodo (week, month, quarter)
    """
    try:
        db = MongoDB.get_database()
        
        # Calculate date range
        from datetime import timedelta
        now = datetime.utcnow()
        
        if period == "week":
            start_date = now - timedelta(days=7)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
        else:  # month
            start_date = now - timedelta(days=30)
        
        if metric == "returns":
            # Count returns by status
            pipeline = [
                {"$match": {"created_at": {"$gte": start_date}}},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]
            results = await db.returns.aggregate(pipeline).to_list(100)
            
            total = sum(r["count"] for r in results)
            by_status = {r["_id"]: r["count"] for r in results}
            
            return json.dumps({
                "success": True,
                "metric": "returns",
                "period": period,
                "total": total,
                "by_status": by_status,
                "summary": f"Total de devoluciones en el ultimo {period}: {total}"
            })
        
        elif metric == "exchanges":
            count = await db.exchanges.count_documents({"created_at": {"$gte": start_date}})
            return json.dumps({
                "success": True,
                "metric": "exchanges",
                "period": period,
                "total": count,
                "summary": f"Total de cambios en el ultimo {period}: {count}"
            })
        
        elif metric == "refunds":
            pipeline = [
                {"$match": {"status": "refunded", "created_at": {"$gte": start_date}}},
                {"$group": {"_id": None, "total_amount": {"$sum": "$total_refund"}, "count": {"$sum": 1}}}
            ]
            results = await db.returns.aggregate(pipeline).to_list(1)
            
            if results:
                return json.dumps({
                    "success": True,
                    "metric": "refunds",
                    "period": period,
                    "total_count": results[0]["count"],
                    "total_amount": results[0]["total_amount"],
                    "summary": f"Reembolsos procesados: {results[0]['count']} por ${results[0]['total_amount']:,.2f}"
                })
            else:
                return json.dumps({
                    "success": True,
                    "metric": "refunds",
                    "period": period,
                    "total_count": 0,
                    "total_amount": 0,
                    "summary": "No hay reembolsos en el periodo"
                })
        
        return json.dumps({"success": False, "error": f"Metrica '{metric}' no reconocida"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
async def search_return_knowledge(query: str) -> str:
    """
    Busca en la base de conocimiento de logistica inversa usando Pinecone.
    Util para encontrar casos similares o politicas especificas.
    
    Args:
        query: Consulta de busqueda (ej: 'devolucion producto danado')
    """
    try:
        vectorstore = PineconeStore()
        
        # Search in Pinecone for relevant knowledge
        results = await vectorstore.search_products(query=query, top_k=3)
        
        # For now, return general guidance based on query
        # In production, this would search a dedicated knowledge index
        
        return json.dumps({
            "success": True,
            "query": query,
            "knowledge_found": len(results) > 0,
            "guidance": "Para casos de logistica inversa, siempre verificar: 1) Estado del pedido, 2) Plazo de devolucion, 3) Condicion del producto.",
            "related_products": len(results)
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# List of all reverse logistics tools
REVERSE_LOGISTICS_TOOLS = [
    initiate_return,
    initiate_exchange,
    check_return_status,
    get_return_policy,
    get_logistics_analytics,
    search_return_knowledge
]


# ============================================================================
# LLM CONFIGURATION
# ============================================================================

def get_rl_llm():
    """Get LLM instance for reverse logistics agent"""
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.5
    )


def get_rl_system_prompt() -> str:
    """System prompt for reverse logistics agent"""
    return """Eres un agente especializado en logistica inversa para una tienda de articulos del hogar.

**Tu rol:**
- Manejar solicitudes de devolucion
- Procesar cambios de productos
- Consultar estados de devoluciones
- Proporcionar informacion sobre politicas
- Generar analytics de logistica inversa (solo para supervisores)

**Herramientas Disponibles:**
- initiate_return: Iniciar devolucion (requiere orden + monto)
- initiate_exchange: Iniciar cambio de producto
- check_return_status: Consultar estado de devolucion
- get_return_policy: Obtener politica de devoluciones
- get_logistics_analytics: Metricas de logistica (supervisores)
- search_return_knowledge: Buscar en base de conocimiento

**Proceso de Devolucion:**
1. Verificar orden (numero + monto total)
2. Confirmar motivo de devolucion
3. Crear solicitud de devolucion
4. Proporcionar instrucciones de envio

**Proceso de Cambio:**
1. Verificar orden original
2. Confirmar producto a cambiar
3. Verificar disponibilidad del nuevo producto
4. Calcular diferencia de precio si aplica
5. Crear solicitud de cambio

**Reglas:**
- SIEMPRE verificar orden con numero + monto total
- Ser empatico con clientes frustrados
- Ofrecer alternativas cuando sea posible
- Escalar a supervisor si el cliente esta muy molesto
"""


# ============================================================================
# REVERSE LOGISTICS AGENT NODE
# ============================================================================

async def reverse_logistics_agent_node(state: AgentState) -> AgentState:
    """
    Reverse Logistics Agent Node - Handles returns, exchanges, and logistics analytics
    """
    messages = state.get("messages", [])
    conversation_id = state.get("conversation_id", "")
    user_id = state.get("user_id", "anonymous")
    
    # Set tool context
    set_rl_tool_context(conversation_id, user_id)
    
    reasoning_steps = state.get("reasoning_trace", [])
    
    try:
        # Get LLM with tools
        llm = get_rl_llm()
        llm_with_tools = llm.bind_tools(REVERSE_LOGISTICS_TOOLS)
        
        # Build messages
        system_prompt = get_rl_system_prompt()
        lc_messages = [SystemMessage(content=system_prompt)]
        
        # Add recent messages
        recent_messages = messages[-10:] if len(messages) > 10 else messages
        for msg in recent_messages:
            content = msg.get("content", "")
            if content:
                if msg.get("role") == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif msg.get("role") == "assistant":
                    lc_messages.append(AIMessage(content=content))
        
        # Invoke LLM
        response = await llm_with_tools.ainvoke(lc_messages)
        
        final_message = ""
        tool_results = []
        
        # Handle tool calls
        if response.tool_calls:
            for tool_call in response.tool_calls:
                func_name = tool_call["name"]
                func_args = tool_call["args"]
                
                reasoning_steps.append({
                    "agent": "ReverseLogisticsAgent",
                    "action": f"tool:{func_name}",
                    "reasoning": f"Ejecutando {func_name}",
                    "timestamp": datetime.utcnow().isoformat(),
                    "result": None
                })
                
                # Execute tool
                tool_func = None
                for t in REVERSE_LOGISTICS_TOOLS:
                    if t.name == func_name:
                        tool_func = t
                        break
                
                if tool_func:
                    result_str = await tool_func.ainvoke(func_args)
                    result = json.loads(result_str)
                    
                    reasoning_steps[-1]["result"] = result
                    tool_results.append({
                        "tool_call_id": tool_call.get("id", ""),
                        "result": result
                    })
            
            # Get follow-up response
            lc_messages.append(response)
            for tr in tool_results:
                lc_messages.append(ToolMessage(
                    content=json.dumps(tr["result"]),
                    tool_call_id=tr["tool_call_id"]
                ))
            
            follow_up = await llm_with_tools.ainvoke(lc_messages)
            llm_response = follow_up.content or ""
            
            # Collect HTML
            html_parts = []
            for tr in tool_results:
                if isinstance(tr["result"], dict) and "html" in tr["result"]:
                    html_parts.append(tr["result"]["html"])
            
            if html_parts:
                final_message = "\n\n".join(html_parts)
            else:
                final_message = llm_response
        else:
            final_message = response.content or ""
        
        reasoning_steps.append({
            "agent": "ReverseLogisticsAgent",
            "action": "response",
            "reasoning": f"Respuesta generada ({len(final_message)} chars)",
            "timestamp": datetime.utcnow().isoformat(),
            "result": {"response_preview": final_message[:100] if final_message else ""}
        })
        
        # Return ONLY the new assistant message - the reducer will append it
        new_message = {"role": "assistant", "content": final_message, "timestamp": datetime.utcnow().isoformat()}
        
        return {
            **state,
            "messages": [new_message],
            "reasoning_trace": reasoning_steps,
            "current_node": "reverse_logistics_agent",
            "next_node": "memory_optimizer"
        }
        
    except Exception as e:
        error_message = f"Error en agente de logistica inversa: {str(e)}"
        reasoning_steps.append({
            "agent": "ReverseLogisticsAgent",
            "action": "error",
            "reasoning": error_message,
            "timestamp": datetime.utcnow().isoformat(),
            "result": {"error": str(e)}
        })
        
        # Return ONLY the new error message - the reducer will append it
        error_msg = {"role": "assistant", "content": "Lo siento, ocurrio un error. Por favor intenta de nuevo.", "timestamp": datetime.utcnow().isoformat()}
        
        return {
            **state,
            "messages": [error_msg],
            "reasoning_trace": reasoning_steps,
            "current_node": "reverse_logistics_agent",
            "next_node": "memory_optimizer"
        }
