"""
Supervisor Node - RF-SEC-01 to RF-SEC-03
Classifies messages as SAFE or UNSAFE and routes accordingly
"""
from typing import Dict, Any, Literal
from datetime import datetime
from ..state import AgentState, AgentReasoning, EscalationRequest
import uuid


# Unsafe patterns and keywords
UNSAFE_PATTERNS = {
    "jailbreak": [
        "ignore your instructions",
        "ignore previous instructions", 
        "forget your rules",
        "pretend you are",
        "act as if you have no restrictions",
        "bypass your programming",
        "DAN mode",
        "developer mode"
    ],
    "illegal": [
        "how to hack",
        "how to steal",
        "illegal drugs",
        "weapons",
        "explosives",
        "how to hurt",
        "how to kill"
    ],
    "insults": [
        "estúpido",
        "idiota",
        "inútil",
        "imbécil",
        "maldito",
        "basura",
        "porquería",
        "fuck",
        "shit",
        "damn"
    ],
    "competitor": [
        "precio en amazon",
        "mejor en mercadolibre",
        "comprar en falabella",
        "ripley tiene mejor",
        "sodimac precio"
    ]
}


# Intent patterns for routing to specialized agents
REVERSE_LOGISTICS_PATTERNS = [
    "devolucion", "devolver", "devuelvo",
    "cambio", "cambiar", "intercambio",
    "reembolso", "reembolsar",
    "return", "refund",
    "no me sirve", "no funciona", "defectuoso",
    "producto danado", "llego roto", "llego mal",
    "quiero regresar", "quiero devolver",
    "politica de devolucion", "politica de cambio",
    "estado de mi devolucion", "estado del cambio",
    "RET-", "EXC-"  # Return/Exchange IDs
]


def detect_intent(message: str) -> Literal["sales", "reverse_logistics"]:
    """
    Detect user intent to route to the appropriate agent.
    
    Returns: 'sales' or 'reverse_logistics'
    """
    message_lower = message.lower()
    
    for pattern in REVERSE_LOGISTICS_PATTERNS:
        if pattern.lower() in message_lower:
            return "reverse_logistics"
    
    return "sales"


def classify_message(message: str) -> tuple[Literal["SAFE", "UNSAFE"], str, str]:
    """
    RF-SEC-01: Classify message as SAFE or UNSAFE
    RF-SEC-02: Apply blocking criteria
    
    Returns: (classification, category, reason)
    """
    message_lower = message.lower()
    
    for category, patterns in UNSAFE_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in message_lower:
                reasons = {
                    "jailbreak": "Intento de manipulación del sistema detectado",
                    "illegal": "Contenido potencialmente ilegal detectado",
                    "insults": "Lenguaje ofensivo detectado",
                    "competitor": "Consulta sobre competencia directa"
                }
                return "UNSAFE", category, reasons.get(category, "Contenido no permitido")
    
    return "SAFE", "normal", "Mensaje válido para procesamiento"


async def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor Node - Central routing and security
    
    Responsibilities:
    1. Classify messages as SAFE or UNSAFE
    2. Detect intent to route to specialized agents:
       - Sales Agent: Product inquiries, purchases, orders
       - Reverse Logistics Agent: Returns, exchanges, refunds
    3. Route UNSAFE messages to Human Node for review
    """
    messages = state.get("messages", [])
    
    if not messages:
        return {
            **state,
            "classification": "SAFE",
            "current_node": "supervisor",
            "next_node": "sales_agent",
            "reasoning_trace": [{
                "agent": "Supervisor",
                "action": "classify",
                "reasoning": "No hay mensajes para clasificar",
                "timestamp": datetime.utcnow().isoformat(),
                "result": {"classification": "SAFE"}
            }]
        }
    
    # Get last user message
    last_message = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_message = msg.get("content", "")
            break
    
    if not last_message:
        return {
            **state,
            "classification": "SAFE",
            "current_node": "supervisor",
            "next_node": "sales_agent",
            "reasoning_trace": [{
                "agent": "Supervisor",
                "action": "classify",
                "reasoning": "No hay mensaje de usuario para clasificar",
                "timestamp": datetime.utcnow().isoformat(),
                "result": {"classification": "SAFE"}
            }]
        }
    
    # First pass: Pattern matching
    classification, category, reason = classify_message(last_message)
    
    # Build reasoning trace
    reasoning: AgentReasoning = {
        "agent": "Supervisor",
        "action": "classify_message",
        "reasoning": f"Clasificación: {classification}. Categoría: {category}. {reason}",
        "timestamp": datetime.utcnow().isoformat(),
        "result": {
            "classification": classification,
            "category": category,
            "reason": reason,
            "message_preview": last_message[:100] + "..." if len(last_message) > 100 else last_message
        }
    }
    
    # RF-SEC-03: Routing decision
    if classification == "UNSAFE":
        # Create escalation request
        escalation: EscalationRequest = {
            "id": str(uuid.uuid4())[:8],
            "conversation_id": state.get("conversation_id", ""),
            "reason": reason,
            "classification": category,
            "original_message": last_message,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending",
            "supervisor_response": None
        }
        
        # Save escalation to MongoDB immediately
        from ...database.mongodb import MongoDB
        import asyncio
        
        async def save_escalation():
            db = MongoDB.get_database()
            await db.escalations.insert_one({
                **escalation,
                "created_at": datetime.utcnow().isoformat()
            })
        
        asyncio.create_task(save_escalation())
        
        return {
            **state,
            "classification": "UNSAFE",
            "escalation": escalation,
            "requires_human": True,
            "current_node": "supervisor",
            "next_node": "human_node",
            "reasoning_trace": [reasoning]
        }
    
    # SAFE: Detect intent and route to appropriate agent
    intent = detect_intent(last_message)
    
    # Add intent detection to reasoning
    intent_reasoning: AgentReasoning = {
        "agent": "Supervisor",
        "action": "detect_intent",
        "reasoning": f"Intent detectado: {intent}",
        "timestamp": datetime.utcnow().isoformat(),
        "result": {
            "intent": intent,
            "routed_to": "reverse_logistics_agent" if intent == "reverse_logistics" else "sales_agent"
        }
    }
    
    next_agent = "reverse_logistics_agent" if intent == "reverse_logistics" else "sales_agent"
    
    return {
        **state,
        "classification": "SAFE",
        "intent": intent,
        "escalation": None,
        "requires_human": False,
        "current_node": "supervisor",
        "next_node": next_agent,
        "reasoning_trace": [reasoning, intent_reasoning]
    }
