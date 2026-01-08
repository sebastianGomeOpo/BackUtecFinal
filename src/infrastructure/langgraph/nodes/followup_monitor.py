"""
Follow-up Monitor Agent
Monitors conversation inactivity and sends follow-up messages
Random interval between 20-120 seconds
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from ...database.mongodb import MongoDB


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
    
    FOLLOWUP_MESSAGES = [
        "Hola, sigo aqui para ayudarte. Si tienes alguna pregunta sobre los productos o necesitas una recomendacion, con gusto te asesoro.",
        "Tengo una sorpresa para ti: si confirmas tu compra ahora, te aplico un **5% de descuento** automatico. Es mi forma de agradecerte por elegirnos.",
        "Veo que aun estas pensando. Te cuento que puedo mejorar tu oferta a un **8% de descuento**. Es una oportunidad que no quiero que te pierdas.",
        "Quiero que te lleves lo mejor. Por eso, te ofrezco un **10% de descuento** exclusivo solo para ti. Esta oferta es por tiempo limitado.",
        "Se que a veces necesitamos pensarlo bien. Para ayudarte a decidir, te ofrezco **12% de descuento**. Es un precio especial que no encontraras en otro lado.",
        "Esta es mi mejor oferta: **15% de descuento**. Realmente quiero que te lleves estos productos a un precio increible.",
        "Voy a hacer algo especial por ti: **18% de descuento**. Es el maximo que puedo ofrecer y vale la pena aprovecharlo.",
        "Mi oferta final y la mejor que tengo: **20% de descuento**. No puedo mejorar esto, pero estoy segura de que te encantara tu compra."
    ]
    
    # Discount percentages for each follow-up level (0=no discount, then progressive)
    FOLLOWUP_DISCOUNT_LEVELS = [0, 5, 8, 10, 12, 15, 18, 20]
    
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
        """Reset the inactivity timer for a conversation (called when user sends message)"""
        db = self._get_db()
        
        await db.conversation_activity.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "last_user_message": datetime.utcnow(),
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
                
                last_user_message = activity.get("last_user_message")
                followup_count = activity.get("followup_count", 0)
                
                if not last_user_message:
                    continue
                
                # Check if enough time has passed since last user message (minimum threshold)
                time_since_message = datetime.utcnow() - last_user_message
                
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
    
    async def _send_followup(self, conversation_id: str, followup_index: int):
        """Send a follow-up message with progressive discount offers"""
        # Cap the index to the last message/discount level (max 20%)
        capped_index = min(followup_index, len(self.FOLLOWUP_MESSAGES) - 1)
        message = self.FOLLOWUP_MESSAGES[capped_index]
        discount_percent = self.FOLLOWUP_DISCOUNT_LEVELS[min(capped_index, len(self.FOLLOWUP_DISCOUNT_LEVELS) - 1)]
        
        # If we've reached max discount, keep repeating the max offer
        if followup_index >= len(self.FOLLOWUP_MESSAGES):
            discount_percent = self.MAX_DISCOUNT_PERCENT
            message = f"Sigo aqui para ayudarte. Recuerda que tienes un **{discount_percent}% de descuento** esperandote. ¿Procedemos con tu compra?"
        
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
