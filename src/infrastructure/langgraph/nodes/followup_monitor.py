"""
Follow-up Monitor Agent
Monitors conversation inactivity and sends follow-up messages
Max 3 follow-ups per conversation, 1 minute interval
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from ...database.mongodb import MongoDB


class FollowUpMonitor:
    """
    Monitors conversations for inactivity and triggers follow-up messages.
    - Triggers after 1 minute of user inactivity
    - Maximum 3 follow-ups per conversation
    - Stops if user responds
    """
    
    INACTIVITY_THRESHOLD_SECONDS = 60  # 1 minute
    MAX_FOLLOWUPS = 3
    
    FOLLOWUP_MESSAGES = [
        "¿Hay algo más en lo que pueda ayudarte? Estoy aquí para resolver cualquier duda sobre nuestros productos.",
        "¿Te gustaría que te muestre más opciones o tienes alguna pregunta sobre los productos que vimos?",
        "Si necesitas más tiempo para decidir, no hay problema. Recuerda que los productos en tu carrito están reservados por 5 minutos. ¿Puedo ayudarte en algo más?"
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
                await asyncio.sleep(self.INACTIVITY_THRESHOLD_SECONDS)
                
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
                
                # Check if enough time has passed since last user message
                time_since_message = datetime.utcnow() - last_user_message
                
                if time_since_message.total_seconds() >= self.INACTIVITY_THRESHOLD_SECONDS:
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
        """Send a follow-up message"""
        message = self.FOLLOWUP_MESSAGES[followup_index % len(self.FOLLOWUP_MESSAGES)]
        
        # Log the follow-up
        db = self._get_db()
        await db.followup_logs.insert_one({
            "conversation_id": conversation_id,
            "message": message,
            "followup_number": followup_index + 1,
            "sent_at": datetime.utcnow()
        })
        
        print(f"📤 Follow-up #{followup_index + 1} sent to {conversation_id}")
        
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
