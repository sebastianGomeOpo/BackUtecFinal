"""
Follow-up Monitor Agent
Monitors conversation inactivity and sends follow-up messages
Random interval between 20-120 seconds
Now with intelligent context-aware messaging
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from ...database.mongodb import MongoDB
from ...services.stock_reservation import get_stock_service


class FollowUpMonitor:
    """
    Monitors conversations for inactivity and triggers follow-up messages.
    - Triggers after random 20-120 seconds of user inactivity
    - Progressive discount offers
    - Stops if user responds
    """
    
    INACTIVITY_MIN_SECONDS = 20
    INACTIVITY_MAX_SECONDS = 120
    MAX_FOLLOWUPS = 999  # Unlimited follow-ups
    MAX_DISCOUNT_PERCENT = 20  # Maximum discount cap
    
    # Discount percentages for each follow-up level (0=no discount, then progressive)
    FOLLOWUP_DISCOUNT_LEVELS = [0, 5, 8, 10, 12, 15, 18, 20]
    
    # Context-aware message templates
    MESSAGES_NO_CART = [
        "Sigo aqui para ayudarte. ¿Que tipo de productos estas buscando hoy? Puedo mostrarte nuestras mejores opciones.",
        "¿Necesitas ayuda para encontrar algo especifico? Tenemos una gran variedad de productos para el hogar.",
        "Si me cuentas que espacio quieres decorar o amoblar, puedo armarte una propuesta personalizada.",
    ]
    
    MESSAGES_WITH_CART = [
        "Veo que tienes {cart_count} producto(s) en tu carrito por ${cart_total:.2f}. ¿Te ayudo a completar tu compra?",
        "Tengo una sorpresa: si confirmas tu compra ahora, te aplico un **{discount}% de descuento** sobre los ${cart_total:.2f} de tu carrito.",
        "Tu carrito con {cart_count} producto(s) esta reservado por tiempo limitado. Te ofrezco **{discount}% de descuento** para que no lo pierdas.",
        "Ultima oportunidad: **{discount}% de descuento** en tu carrito de ${cart_total:.2f}. ¿Procedemos con la compra?",
    ]
    
    MESSAGES_VIEWED_PRODUCTS = [
        "¿Sigues interesado en los productos que viste? Puedo darte mas detalles o buscar alternativas.",
        "Si alguno de los productos que te mostre te interesa, puedo agregarlo a tu carrito con un descuento especial.",
    ]
    
    def __init__(self):
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._followup_callbacks: Dict[str, callable] = {}
    
    def _get_db(self) -> AsyncIOMotorDatabase:
        return MongoDB.get_database()
    
    async def start_monitoring(
        self,
        conversation_id: str,
        callback: callable
    ):
        """
        Start monitoring a conversation for inactivity
        
        Args:
            conversation_id: The conversation to monitor
            callback: Async function to call when follow-up is needed
                      Should accept (conversation_id, message) as args
        """
        # Cancel existing monitoring for this conversation
        await self.stop_monitoring(conversation_id)
        
        # Store callback
        self._followup_callbacks[conversation_id] = callback
        
        # Start new monitoring task
        self._monitoring_tasks[conversation_id] = asyncio.create_task(
            self._monitor_conversation(conversation_id)
        )
    
    async def stop_monitoring(self, conversation_id: str):
        """Stop monitoring a conversation"""
        if conversation_id in self._monitoring_tasks:
            self._monitoring_tasks[conversation_id].cancel()
            try:
                await self._monitoring_tasks[conversation_id]
            except asyncio.CancelledError:
                pass
            del self._monitoring_tasks[conversation_id]
        
        if conversation_id in self._followup_callbacks:
            del self._followup_callbacks[conversation_id]
    
    async def reset_timer(self, conversation_id: str):
        """Reset the inactivity timer for a conversation (called when assistant responds)"""
        db = self._get_db()
        
        await db.conversation_activity.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "last_assistant_response": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
    
    async def _monitor_conversation(self, conversation_id: str):
        """Background task to monitor a single conversation"""
        db = self._get_db()
        
        while True:
            try:
                # Random wait between 20-120 seconds
                wait_time = random.randint(self.INACTIVITY_MIN_SECONDS, self.INACTIVITY_MAX_SECONDS)
                await asyncio.sleep(wait_time)
                
                # Get conversation activity
                activity = await db.conversation_activity.find_one({
                    "conversation_id": conversation_id
                })
                
                if not activity:
                    continue
                
                last_assistant_response = activity.get("last_assistant_response")
                followup_count = activity.get("followup_count", 0)
                
                if not last_assistant_response:
                    continue
                
                # Check if enough time has passed since last assistant response (minimum threshold)
                time_since_message = datetime.utcnow() - last_assistant_response
                
                if time_since_message.total_seconds() >= self.INACTIVITY_MIN_SECONDS:
                    # Check if we haven't exceeded max follow-ups
                    if followup_count < self.MAX_FOLLOWUPS:
                        # Send follow-up
                        await self._send_followup(conversation_id, followup_count)
                        
                        # Update follow-up count
                        await db.conversation_activity.update_one(
                            {"conversation_id": conversation_id},
                            {
                                "$set": {
                                    "followup_count": followup_count + 1,
                                    "last_followup": datetime.utcnow()
                                }
                            }
                        )
                    else:
                        # Max follow-ups reached, stop monitoring
                        print(f"🛑 Max follow-ups reached for {conversation_id}")
                        break
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error monitoring {conversation_id}: {e}")
                await asyncio.sleep(10)
    
    async def _get_conversation_context(self, conversation_id: str) -> Dict:
        """Get conversation context including cart and viewed products"""
        try:
            stock_service = get_stock_service()
            cart = await stock_service.get_cart_total(conversation_id)
            
            cart_items = cart.get("items", [])
            cart_total = cart.get("total", 0)
            cart_count = len(cart_items)
            
            # Get viewed products from Redis
            db = self._get_db()
            activity = await db.conversation_activity.find_one({"conversation_id": conversation_id})
            has_viewed_products = activity.get("has_viewed_products", False) if activity else False
            
            return {
                "has_cart": cart_count > 0,
                "cart_count": cart_count,
                "cart_total": cart_total,
                "cart_items": cart_items,
                "has_viewed_products": has_viewed_products
            }
        except Exception as e:
            print(f"[FOLLOWUP] Error getting context: {e}")
            return {"has_cart": False, "cart_count": 0, "cart_total": 0, "cart_items": [], "has_viewed_products": False}
    
    async def _send_followup(self, conversation_id: str, followup_index: int):
        """Send a context-aware follow-up message with progressive discount offers"""
        # Get conversation context
        context = await self._get_conversation_context(conversation_id)
        
        # Calculate discount based on followup index
        discount_index = min(followup_index, len(self.FOLLOWUP_DISCOUNT_LEVELS) - 1)
        discount_percent = self.FOLLOWUP_DISCOUNT_LEVELS[discount_index]
        
        # Select message based on context
        if context["has_cart"]:
            # Has items in cart - offer discounts
            msg_index = min(followup_index, len(self.MESSAGES_WITH_CART) - 1)
            message = self.MESSAGES_WITH_CART[msg_index].format(
                cart_count=context["cart_count"],
                cart_total=context["cart_total"],
                discount=discount_percent if discount_percent > 0 else 5
            )
            # Only apply discount if cart has items
            if discount_percent == 0 and followup_index > 0:
                discount_percent = 5  # Start with 5% for cart users
        elif context["has_viewed_products"]:
            # Viewed products but no cart
            msg_index = min(followup_index, len(self.MESSAGES_VIEWED_PRODUCTS) - 1)
            message = self.MESSAGES_VIEWED_PRODUCTS[msg_index]
            discount_percent = 0  # No discount without cart
        else:
            # No cart, no viewed products - just help
            msg_index = min(followup_index, len(self.MESSAGES_NO_CART) - 1)
            message = self.MESSAGES_NO_CART[msg_index]
            discount_percent = 0  # No discount without cart
        
        # If max discount reached and has cart, keep offering max
        if followup_index >= len(self.FOLLOWUP_DISCOUNT_LEVELS) and context["has_cart"]:
            discount_percent = self.MAX_DISCOUNT_PERCENT
            message = f"Sigo aqui para ayudarte. Recuerda que tienes un **{discount_percent}% de descuento** en tu carrito de ${context['cart_total']:.2f}. ¿Procedemos con tu compra?"
        
        db = self._get_db()
        
        # Log the follow-up with discount info
        await db.followup_logs.insert_one({
            "conversation_id": conversation_id,
            "message": message,
            "followup_number": followup_index + 1,
            "discount_percent": discount_percent,
            "sent_at": datetime.utcnow()
        })
        
        # Store pending discount offer for this conversation
        if discount_percent > 0:
            await db.pending_discounts.update_one(
                {"conversation_id": conversation_id},
                {
                    "$set": {
                        "discount_percent": discount_percent,
                        "offered_at": datetime.utcnow(),
                        "expires_at": datetime.utcnow() + timedelta(minutes=5),
                        "applied": False
                    }
                },
                upsert=True
            )
        
        print(f"📤 Follow-up #{followup_index + 1} sent to {conversation_id} (discount: {discount_percent}%)")
        
        # Call the callback if registered
        if conversation_id in self._followup_callbacks:
            callback = self._followup_callbacks[conversation_id]
            try:
                await callback(conversation_id, message)
            except Exception as e:
                print(f"Error in follow-up callback: {e}")
    
    async def get_followup_status(self, conversation_id: str) -> Dict:
        """Get follow-up status for a conversation"""
        db = self._get_db()
        
        activity = await db.conversation_activity.find_one({
            "conversation_id": conversation_id
        })
        
        if not activity:
            return {
                "conversation_id": conversation_id,
                "followup_count": 0,
                "max_followups": self.MAX_FOLLOWUPS,
                "is_monitoring": conversation_id in self._monitoring_tasks
            }
        
        return {
            "conversation_id": conversation_id,
            "followup_count": activity.get("followup_count", 0),
            "max_followups": self.MAX_FOLLOWUPS,
            "last_user_message": activity.get("last_user_message"),
            "last_followup": activity.get("last_followup"),
            "is_monitoring": conversation_id in self._monitoring_tasks
        }
    
    async def initialize_conversation(self, conversation_id: str):
        """Initialize activity tracking for a new conversation"""
        db = self._get_db()
        
        await db.conversation_activity.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "last_user_message": datetime.utcnow(),
                    "followup_count": 0,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )


# Global instance
_followup_monitor: Optional[FollowUpMonitor] = None


def get_followup_monitor() -> FollowUpMonitor:
    """Get or create the global follow-up monitor instance"""
    global _followup_monitor
    if _followup_monitor is None:
        _followup_monitor = FollowUpMonitor()
    return _followup_monitor
