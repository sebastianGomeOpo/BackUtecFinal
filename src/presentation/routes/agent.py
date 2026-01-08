"""
Agent endpoints - LangGraph Sales Agent with Supervisor
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json

from ...infrastructure.langgraph.graph import get_sales_graph
from ...infrastructure.database.mongodb import MongoDB
from ...infrastructure.services.stock_reservation import get_stock_service
from ...infrastructure.langgraph.nodes.followup_monitor import get_followup_monitor

router = APIRouter()


# Request/Response models
class StartConversationRequest(BaseModel):
    user_id: Optional[str] = "guest"


class SendMessageRequest(BaseModel):
    conversation_id: str
    message: str
    user_id: Optional[str] = "guest"


class HumanResponseRequest(BaseModel):
    conversation_id: str
    escalation_id: str
    action: str  # "approve", "rewrite", "reject"
    supervisor_response: Optional[str] = None


class ConversationResponse(BaseModel):
    conversation_id: str
    message: str
    status: str
    requires_human: Optional[bool] = False
    escalation: Optional[dict] = None
    reasoning_trace: Optional[List[dict]] = []
    cart: Optional[List[dict]] = []
    coupon: Optional[dict] = None


# Endpoints
@router.post("/start", response_model=ConversationResponse)
async def start_conversation(request: StartConversationRequest):
    """Start a new conversation with the Sales Agent"""
    try:
        graph = get_sales_graph()
        result = await graph.start_conversation(user_id=request.user_id)
        
        return ConversationResponse(
            conversation_id=result["conversation_id"],
            message=result["message"],
            status="started",
            reasoning_trace=result.get("reasoning_trace", [])
        )
    except Exception as e:
        import traceback
        print(f"Error starting conversation: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message", response_model=ConversationResponse)
async def send_message(request: SendMessageRequest):
    """Send a message to the Sales Agent"""
    try:
        db = MongoDB.get_database()
        
        # Check if conversation is paused due to escalation
        conversation = await db.conversations.find_one({"conversation_id": request.conversation_id})
        if conversation and conversation.get("status") == "escalated":
            escalation_id = conversation.get("escalation_id")
            return ConversationResponse(
                conversation_id=request.conversation_id,
                message="Tu consulta está siendo atendida por un supervisor. Por favor espera mientras te asistimos.",
                status="paused",
                requires_human=True,
                escalation={"id": escalation_id, "status": "pending"},
                reasoning_trace=[],
                cart=[]
            )
        
        graph = get_sales_graph()
        result = await graph.process_message(
            conversation_id=request.conversation_id,
            message=request.message,
            user_id=request.user_id
        )
        
        # Check for applied coupon
        coupon_data = await db.cart_coupons.find_one({"conversation_id": request.conversation_id})
        coupon = None
        if coupon_data:
            coupon = {
                "coupon_code": coupon_data.get("coupon_code"),
                "discount_percent": coupon_data.get("discount_percent"),
                "discount_amount": coupon_data.get("discount"),
                "original_total": coupon_data.get("original_total"),
                "new_total": coupon_data.get("new_total")
            }
        
        return ConversationResponse(
            conversation_id=result["conversation_id"],
            message=result["message"],
            status=result.get("status", "completed"),
            requires_human=result.get("requires_human", False),
            escalation=result.get("escalation"),
            reasoning_trace=result.get("reasoning_trace", []),
            cart=result.get("cart", []),
            coupon=coupon
        )
    except Exception as e:
        import traceback
        print(f"Error processing message: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/human/respond", response_model=ConversationResponse)
async def human_respond(request: HumanResponseRequest):
    """Handle human supervisor response to an escalation"""
    try:
        db = MongoDB.get_database()
        
        # Update escalation status
        await db.escalations.update_one(
            {"id": request.escalation_id},
            {
                "$set": {
                    "status": request.action,
                    "supervisor_response": request.supervisor_response,
                    "resolved_at": datetime.utcnow()
                }
            }
        )
        
        # Resume conversation (remove paused status)
        await db.conversations.update_one(
            {"conversation_id": request.conversation_id},
            {
                "$set": {
                    "status": "active",
                    "resumed_at": datetime.utcnow()
                },
                "$unset": {
                    "escalation_id": "",
                    "paused_at": ""
                }
            }
        )
        
        # Determine response message based on action
        if request.action == "approve":
            message = "Tu consulta ha sido revisada. ¿En qué más puedo ayudarte?"
        elif request.action == "rewrite":
            message = request.supervisor_response or "Un supervisor ha respondido a tu consulta."
        else:  # reject
            message = "Lo sentimos, no podemos procesar esta solicitud. Si tienes alguna otra consulta sobre nuestros productos, estaré encantado de ayudarte."
        
        # Store supervisor message in conversation
        await db.conversation_messages.insert_one({
            "conversation_id": request.conversation_id,
            "role": "supervisor",
            "content": message,
            "action": request.action,
            "escalation_id": request.escalation_id,
            "timestamp": datetime.utcnow()
        })
        
        return ConversationResponse(
            conversation_id=request.conversation_id,
            message=message,
            status=request.action,
            reasoning_trace=[{
                "agent": "Supervisor",
                "action": request.action,
                "reasoning": f"Supervisor respondió con acción: {request.action}",
                "timestamp": datetime.utcnow().isoformat(),
                "result": {"action": request.action}
            }]
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error handling human response: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reasoning/{conversation_id}")
async def get_reasoning_trace(conversation_id: str):
    """Get the reasoning trace for a conversation"""
    try:
        graph = get_sales_graph()
        trace = await graph.get_reasoning_trace(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "reasoning_trace": trace
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/escalations")
async def get_pending_escalations():
    """Get all pending escalations for supervisor dashboard"""
    try:
        db = MongoDB.get_database()
        cursor = db.escalations.find({"status": "pending"}).sort("timestamp", -1).limit(50)
        
        escalations = []
        async for doc in cursor:
            doc.pop("_id", None)
            escalations.append(doc)
        
        return {
            "escalations": escalations,
            "count": len(escalations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/escalations/all")
async def get_all_escalations():
    """Get all escalations (for history)"""
    try:
        db = MongoDB.get_database()
        cursor = db.escalations.find({}).sort("timestamp", -1).limit(100)
        
        escalations = []
        async for doc in cursor:
            doc.pop("_id", None)
            escalations.append(doc)
        
        return {
            "escalations": escalations,
            "count": len(escalations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/escalation/{escalation_id}")
async def get_escalation(escalation_id: str):
    """Get a specific escalation"""
    try:
        db = MongoDB.get_database()
        escalation = await db.escalations.find_one({"id": escalation_id})
        
        if not escalation:
            raise HTTPException(status_code=404, detail="Escalation not found")
        
        escalation.pop("_id", None)
        return escalation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket for real-time escalation notifications
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


@router.websocket("/ws/escalations")
async def websocket_escalations(websocket: WebSocket):
    """WebSocket for real-time escalation notifications"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for any messages
            data = await websocket.receive_text()
            
            # Echo back or handle commands
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def notify_new_escalation(escalation: dict):
    """Notify all connected supervisors of a new escalation"""
    await manager.broadcast({
        "type": "new_escalation",
        "escalation": escalation,
        "timestamp": datetime.utcnow().isoformat()
    })


# Cart endpoints
@router.get("/cart/{conversation_id}")
async def get_cart(conversation_id: str):
    """Get cart for a conversation"""
    try:
        stock_service = get_stock_service()
        cart = await stock_service.get_cart_total(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "cart": cart
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConfirmOrderRequest(BaseModel):
    conversation_id: str
    user_id: Optional[str] = "guest"


@router.post("/cart/confirm")
async def confirm_order(request: ConfirmOrderRequest):
    """Confirm order and deduct stock"""
    try:
        stock_service = get_stock_service()
        result = await stock_service.confirm_order(
            conversation_id=request.conversation_id,
            user_id=request.user_id
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Orders endpoints
@router.get("/orders")
async def get_orders(page: int = 1, page_size: int = 10):
    """Get all orders with pagination"""
    try:
        db = MongoDB.get_database()
        
        # Get total count
        total_count = await db.orders.count_documents({})
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
        
        # Get paginated orders
        skip = (page - 1) * page_size
        cursor = db.orders.find({}).sort("created_at", -1).skip(skip).limit(page_size)
        
        orders = []
        async for doc in cursor:
            doc.pop("_id", None)
            orders.append(doc)
        
        return {
            "orders": orders,
            "count": len(orders),
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get a specific order"""
    try:
        db = MongoDB.get_database()
        order = await db.orders.find_one({"order_id": order_id})
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        order.pop("_id", None)
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Follow-up endpoints
@router.post("/followup/start/{conversation_id}")
async def start_followup_monitoring(conversation_id: str):
    """Start follow-up monitoring for a conversation"""
    try:
        monitor = get_followup_monitor()
        
        async def followup_callback(conv_id: str, message: str):
            # Store follow-up message in conversation
            db = MongoDB.get_database()
            await db.conversation_messages.insert_one({
                "conversation_id": conv_id,
                "role": "assistant",
                "content": message,
                "type": "followup",
                "timestamp": datetime.utcnow()
            })
            # Broadcast to WebSocket
            await manager.broadcast({
                "type": "followup",
                "conversation_id": conv_id,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        await monitor.initialize_conversation(conversation_id)
        await monitor.start_monitoring(conversation_id, followup_callback)
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "Follow-up monitoring started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/followup/stop/{conversation_id}")
async def stop_followup_monitoring(conversation_id: str):
    """Stop follow-up monitoring for a conversation"""
    try:
        monitor = get_followup_monitor()
        await monitor.stop_monitoring(conversation_id)
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "Follow-up monitoring stopped"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/followup/reset/{conversation_id}")
async def reset_followup_timer(conversation_id: str):
    """Reset follow-up timer (called when user sends message)"""
    try:
        monitor = get_followup_monitor()
        await monitor.reset_timer(conversation_id)
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "Follow-up timer reset"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/followup/status/{conversation_id}")
async def get_followup_status(conversation_id: str):
    """Get follow-up status for a conversation"""
    try:
        monitor = get_followup_monitor()
        status = await monitor.get_followup_status(conversation_id)
        
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/followup/messages/{conversation_id}")
async def get_followup_messages(conversation_id: str, since: str = None):
    """Get pending follow-up messages for a conversation (for polling)"""
    try:
        db = MongoDB.get_database()
        
        query = {
            "conversation_id": conversation_id,
            "type": "followup"
        }
        
        if since:
            from datetime import datetime
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                query["timestamp"] = {"$gt": since_dt}
            except:
                pass
        
        cursor = db.conversation_messages.find(query).sort("timestamp", 1)
        messages = []
        async for doc in cursor:
            doc.pop("_id", None)
            if hasattr(doc.get("timestamp"), "isoformat"):
                doc["timestamp"] = doc["timestamp"].isoformat()
            messages.append(doc)
        
        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "count": len(messages)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
