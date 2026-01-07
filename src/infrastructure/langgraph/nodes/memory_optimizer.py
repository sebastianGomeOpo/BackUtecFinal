"""
Memory Optimizer Node - RF-MEM-01 to RF-MEM-02
Handles conversation compression and insight extraction
"""
from typing import Dict, Any, List
from datetime import datetime
import json
import httpx
from ..state import AgentState, AgentReasoning, Message
from ....config import settings
from ...database.mongodb import MongoDB


async def compress_messages(messages: List[Message]) -> str:
    """
    RF-MEM-01: Compress old messages using LLM
    Uses gpt-4o-mini for fast, cheap summarization
    """
    if len(messages) < 5:
        return ""
    
    # Get oldest 5 messages to compress
    old_messages = messages[:5]
    
    messages_text = "\n".join([
        f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
        for msg in old_messages
    ])
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Resume la siguiente conversación en 2-3 oraciones, manteniendo los puntos clave y cualquier producto mencionado."
                        },
                        {
                            "role": "user",
                            "content": messages_text
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 200
                },
                timeout=15.0
            )
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error compressing messages: {e}")
        return ""


async def extract_insights(messages: List[Message], user_id: str) -> Dict[str, Any]:
    """
    RF-MEM-02: Extract new preferences from conversation
    Updates user profile in MongoDB
    """
    if not messages:
        return {}
    
    # Get recent messages for analysis
    recent_messages = messages[-10:]
    
    messages_text = "\n".join([
        f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
        for msg in recent_messages
    ])
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": """Analiza la conversación y extrae preferencias del cliente.
Responde SOLO con JSON válido:
{
    "preferences_found": true/false,
    "preferences": {
        "size": "talla si se menciona o null",
        "favorite_color": "color si se menciona o null",
        "style": "estilo preferido o null",
        "budget_range": "rango de presupuesto o null"
    },
    "interests": ["lista de categorías de interés"]
}"""
                        },
                        {
                            "role": "user",
                            "content": messages_text
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": 200
                },
                timeout=15.0
            )
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Parse JSON
            try:
                insights = json.loads(content)
                
                # Update user profile if preferences found
                if insights.get("preferences_found") and user_id:
                    db = MongoDB.get_database()
                    
                    update_data = {}
                    prefs = insights.get("preferences", {})
                    
                    for key, value in prefs.items():
                        if value:
                            update_data[f"preferences.{key}"] = value
                    
                    if insights.get("interests"):
                        update_data["interests"] = insights["interests"]
                    
                    if update_data:
                        await db.users.update_one(
                            {"user_id": user_id},
                            {"$set": update_data}
                        )
                
                return insights
            except json.JSONDecodeError:
                return {}
                
    except Exception as e:
        print(f"Error extracting insights: {e}")
        return {}


async def memory_optimizer_node(state: AgentState) -> AgentState:
    """
    RF-MEM-01 to RF-MEM-02: Memory Optimizer Node
    
    - Compresses history if > 10 messages
    - Extracts insights from conversation
    - Updates user profile with new preferences
    """
    messages = state.get("messages", [])
    message_count = len(messages)
    user_context = state.get("user_context", {})
    user_id = user_context.get("user_id", "")
    
    reasoning_steps = []
    compressed_history = state.get("compressed_history", "")
    
    # RF-MEM-01: Compress if > 10 messages
    if message_count > 10:
        # Compress oldest 5 messages
        summary = await compress_messages(messages)
        
        if summary:
            compressed_history = summary
            # Keep only last 5 messages + compressed history
            messages = messages[-5:]
            
            reasoning_steps.append({
                "agent": "MemoryOptimizer",
                "action": "compress",
                "reasoning": f"Historial comprimido. {message_count} mensajes reducidos a 5 + resumen.",
                "timestamp": datetime.utcnow().isoformat(),
                "result": {
                    "original_count": message_count,
                    "new_count": len(messages),
                    "summary_length": len(summary)
                }
            })
    
    # RF-MEM-02: Extract insights periodically (every 5 messages)
    if message_count > 0 and message_count % 5 == 0:
        insights = await extract_insights(messages, user_id)
        
        if insights.get("preferences_found"):
            reasoning_steps.append({
                "agent": "MemoryOptimizer",
                "action": "extract_insights",
                "reasoning": f"Preferencias extraídas: {insights.get('preferences', {})}",
                "timestamp": datetime.utcnow().isoformat(),
                "result": insights
            })
    
    # If no optimization was done, add a simple trace
    if not reasoning_steps:
        reasoning_steps.append({
            "agent": "MemoryOptimizer",
            "action": "check",
            "reasoning": f"Verificación de memoria. Mensajes: {message_count}. Sin optimización necesaria.",
            "timestamp": datetime.utcnow().isoformat(),
            "result": {"message_count": message_count}
        })
    
    # State size is now controlled by custom reducers in state.py
    # No need for aggressive truncation here
    return {
        **state,
        "messages": messages if message_count > 10 else state.get("messages", []),
        "message_count": len(messages),
        "compressed_history": compressed_history,
        "current_node": "memory_optimizer",
        "next_node": None,
        "reasoning_trace": reasoning_steps
    }
