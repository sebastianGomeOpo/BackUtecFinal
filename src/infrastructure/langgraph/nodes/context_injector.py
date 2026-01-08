"""
Context Injector Node - RF-CTX-01 to RF-CTX-04
Retrieves user profile and injects context into state
"""
from typing import Dict, Any
from datetime import datetime
from ..state import AgentState, UserContext, AgentReasoning
from ...database.mongodb import MongoDB


async def get_user_profile(user_id: str) -> Dict[str, Any]:
    """
    RF-CTX-02: Retrieve user profile from MongoDB
    If user doesn't exist, create a Guest profile
    """
    db = MongoDB.get_database()
    
    user = await db.users.find_one({"user_id": user_id})
    
    if not user:
        # Create Guest profile
        guest_profile = {
            "user_id": user_id,
            "name": "Guest",
            "purchase_history": [],
            "preferences": {
                "tone": "friendly",
                "size": None,
                "favorite_color": None
            },
            "created_at": datetime.utcnow().isoformat()
        }
        await db.users.insert_one(guest_profile)
        return guest_profile
    
    return user


def generate_system_prompt(user_context: UserContext) -> str:
    """
    RF-CTX-03: Generate system prompt with user context
    Includes: name, last 3 purchases, preferred tone
    """
    name = user_context.get("name", "Guest")
    history = user_context.get("purchase_history", [])[-3:]  # Last 3 purchases
    tone = user_context.get("preferences", {}).get("tone", "friendly")
    preferences = user_context.get("preferences", {})
    
    # Build purchase history summary
    history_text = ""
    if history:
        history_items = [f"- {p.get('product_name', 'Producto')}" for p in history]
        history_text = f"\nHistorial de compras recientes:\n" + "\n".join(history_items)
    
    # Build preferences summary
    pref_text = ""
    if preferences.get("size"):
        pref_text += f"\n- Talla preferida: {preferences['size']}"
    if preferences.get("favorite_color"):
        pref_text += f"\n- Color favorito: {preferences['favorite_color']}"
    
    return f"""[CONTEXTO DEL CLIENTE - NO MOSTRAR AL USUARIO]
Cliente: {name}
Tono de comunicación: {tone}{history_text}
Preferencias conocidas:{pref_text if pref_text else ' Ninguna registrada'}

INSTRUCCIONES:
- Personaliza las respuestas según el perfil del cliente
- Si tiene historial, sugiere productos relacionados
- Usa el tono de comunicación preferido
- NO menciones que tienes acceso a su perfil
"""


async def context_injector_node(state: AgentState) -> AgentState:
    """
    RF-CTX-01 to RF-CTX-04: Context Injector Node
    
    - Accepts user_id from state
    - Retrieves user profile from MongoDB
    - Generates personalized system prompt
    - Injects into state['user_context'] (invisible to chat)
    """
    conversation_id = state.get("conversation_id", "")
    
    # Extract user_id from conversation metadata or use default
    user_id = state.get("user_context", {}).get("user_id", "guest")
    
    # Get user profile from MongoDB
    user_profile = await get_user_profile(user_id)
    
    # Build user context
    user_context: UserContext = {
        "user_id": user_profile.get("user_id", user_id),
        "name": user_profile.get("name", "Guest"),
        "purchase_history": user_profile.get("purchase_history", []),
        "preferences": user_profile.get("preferences", {}),
        "tone": user_profile.get("preferences", {}).get("tone", "friendly")
    }
    
    # Generate system prompt (for internal use)
    system_prompt = generate_system_prompt(user_context)
    
    # Add reasoning trace
    reasoning: AgentReasoning = {
        "agent": "ContextInjector",
        "action": "inject_context",
        "reasoning": f"Perfil cargado para usuario '{user_context['name']}'. Historial: {len(user_context['purchase_history'])} compras.",
        "timestamp": datetime.utcnow().isoformat(),
        "result": {
            "user_id": user_context["user_id"],
            "name": user_context["name"],
            "has_history": len(user_context["purchase_history"]) > 0
        }
    }
    
    return {
        **state,
        "messages": [],  # Don't add any messages - pass empty to prevent reducer duplication
        "user_context": user_context,
        "reasoning_trace": [reasoning],
        "current_node": "context_injector",
        "next_node": "supervisor"
    }
