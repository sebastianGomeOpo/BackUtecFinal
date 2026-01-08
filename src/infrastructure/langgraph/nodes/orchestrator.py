"""
AI Orchestrator Node - Proactive Sales Supervisor

This node monitors the conversation and can intervene proactively:
1. Detects conversation stage (discovery, proposal, optimization, commitment, checkout)
2. Identifies hesitation patterns
3. Injects proactive messages to guide the sale
4. Tracks conversion metrics

The orchestrator acts BEFORE the sales agent to inject context/guidance.
"""
import re
from typing import Dict, Any, List
from datetime import datetime
from ..state import AgentState


# Hesitation patterns that indicate the user is unsure
HESITATION_PATTERNS = [
    r"\b(no se|no sé|no estoy seguro|dejame pensar|lo pienso|mas tarde|después|luego)\b",
    r"\b(es caro|muy caro|precio alto|mucho dinero|no tengo|presupuesto)\b",
    r"\b(cual recomiendas|que me recomiendas|cual es mejor|no se cual)\b",
    r"\b(hmm|mmm|ehh|bueno|pues|este)\b",
    r"\?.*\?",  # Multiple questions indicate confusion
]

# Stage detection patterns - more specific to avoid false positives
STAGE_PATTERNS = {
    "discovery": [
        r"\b(busco|necesito|quiero comprar|me gustaria|estoy buscando)\b",
        r"\b(tengo \d+ dolares|presupuesto de|amoblar|decorar|renovar)\b",
        r"\b(hola|buenos dias|buenas tardes|buenas noches)\b",
        r"\b(que venden|que productos|tienen)\b",
    ],
    "proposal": [
        r"\b(muestrame|ver opciones|mostrar|catalogo)\b",
        r"\b(que tienes en|que tienen de|hay de)\b",
        r"\b(propuesta|sugerencia|recomendacion)\b",
    ],
    "optimization": [
        r"\b(otro color|diferente|alternativa|mas barato|mas economico|mas caro|premium)\b",
        r"\b(quitar del carrito|eliminar|reducir cantidad|menos unidades)\b",
        r"\b(cambiar por|reemplazar|sustituir)\b",
    ],
    "commitment": [
        r"\b(agrega al carrito|añadir al carrito|quiero este|me llevo este|lo quiero|agregar el \d+)\b",
        r"\b(agregar todo|toda la propuesta)\b",
    ],
    "checkout": [
        r"\b(pagar|confirmar orden|finalizar compra|proceder al pago)\b",
        r"\b(mi direccion es|entrega en|enviar a|horario de entrega)\b",
        r"\b(crear orden|generar orden)\b",
    ],
}

# Proactive interventions based on stage and metrics
INTERVENTIONS = {
    "too_long_in_discovery": {
        "condition": lambda s: s.get("conversation_stage") == "discovery" and s.get("stage_message_count", 0) > 4,
        "message": "Veo que tienes varias ideas. ¿Te gustaría que te prepare una propuesta personalizada basada en lo que me has contado?",
    },
    "hesitation_detected": {
        "condition": lambda s: s.get("hesitation_signals", 0) >= 2,
        "message": "Entiendo que es una decisión importante. La mayoría de nuestros clientes eligen [PRODUCTO_POPULAR]. ¿Te gustaría que te cuente por qué?",
    },
    "cart_abandonment_risk": {
        "condition": lambda s: s.get("products_added_to_cart", 0) > 0 and s.get("products_removed_from_cart", 0) > 0,
        "message": "Noté que quitaste algunos productos. ¿Hay algo que pueda mejorar? Puedo ofrecerte alternativas o un descuento especial.",
    },
    "stuck_in_optimization": {
        "condition": lambda s: s.get("conversation_stage") == "optimization" and s.get("stage_message_count", 0) > 5,
        "message": "Ya tienes una buena selección en tu carrito. ¿Quieres que procedamos con la compra? Puedo mostrarte las opciones de entrega.",
    },
    "empty_cart_after_proposal": {
        "condition": lambda s: s.get("conversation_stage") == "proposal" and s.get("total_products_shown", 0) > 5 and s.get("products_added_to_cart", 0) == 0,
        "message": "Te mostré varias opciones. ¿Cuál te llamó más la atención? Puedo darte más detalles sobre cualquiera de ellos.",
    },
}


def detect_stage(message: str, current_stage: str) -> str:
    """Detect conversation stage based on message content"""
    message_lower = message.lower()
    
    # Check each stage's patterns
    stage_scores = {}
    for stage, patterns in STAGE_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, message_lower, re.IGNORECASE))
        if score > 0:
            stage_scores[stage] = score
    
    if not stage_scores:
        return current_stage or "discovery"
    
    # Return stage with highest score
    detected = max(stage_scores, key=stage_scores.get)
    
    # Stage progression logic - can only move forward or stay
    stage_order = ["discovery", "proposal", "optimization", "commitment", "checkout", "completed"]
    current_idx = stage_order.index(current_stage) if current_stage in stage_order else 0
    detected_idx = stage_order.index(detected) if detected in stage_order else 0
    
    # Allow moving forward or staying, but not going back more than 1 stage
    if detected_idx >= current_idx - 1:
        return detected
    return current_stage


def count_hesitation_signals(message: str) -> int:
    """Count hesitation patterns in message"""
    message_lower = message.lower()
    count = 0
    for pattern in HESITATION_PATTERNS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            count += 1
    return count


def get_intervention(state: AgentState) -> str:
    """Check if any intervention should be triggered"""
    for name, intervention in INTERVENTIONS.items():
        if intervention["condition"](state):
            print(f"[ORCHESTRATOR] Triggering intervention: {name}")
            return intervention["message"]
    return None


async def orchestrator_node(state: AgentState) -> Dict[str, Any]:
    """
    AI Orchestrator that monitors and guides the conversation.
    
    Runs BEFORE the sales agent to:
    1. Update conversation stage
    2. Detect hesitation
    3. Inject proactive guidance
    """
    conversation_id = state.get("conversation_id", "")
    messages = state.get("messages", [])
    current_stage = state.get("conversation_stage") or "discovery"
    stage_message_count = state.get("stage_message_count", 0)
    hesitation_signals = state.get("hesitation_signals", 0)
    
    # Get last user message
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
    
    if not last_user_message:
        return {
            "messages": [],  # Don't add messages - prevent reducer duplication
            "conversation_stage": current_stage,
            "stage_message_count": stage_message_count,
            "orchestrator_intervention": None,
            "reasoning_trace": [{
                "agent": "Orchestrator",
                "action": "skip",
                "reasoning": "No user message to analyze",
                "timestamp": datetime.utcnow().isoformat(),
                "result": {}
            }]
        }
    
    # Detect new stage
    new_stage = detect_stage(last_user_message, current_stage)
    
    # Update stage message count
    if new_stage != current_stage:
        stage_message_count = 1
        print(f"[ORCHESTRATOR] Stage changed: {current_stage} -> {new_stage}")
    else:
        stage_message_count += 1
    
    # Count hesitation signals
    new_hesitation = count_hesitation_signals(last_user_message)
    hesitation_signals += new_hesitation
    
    if new_hesitation > 0:
        print(f"[ORCHESTRATOR] Detected {new_hesitation} hesitation signals (total: {hesitation_signals})")
    
    # Check for intervention
    temp_state = {
        **state,
        "conversation_stage": new_stage,
        "stage_message_count": stage_message_count,
        "hesitation_signals": hesitation_signals,
    }
    intervention = get_intervention(temp_state)
    
    reasoning = {
        "agent": "Orchestrator",
        "action": "analyze",
        "reasoning": f"Stage: {new_stage} (msg #{stage_message_count}), Hesitation: {hesitation_signals}",
        "timestamp": datetime.utcnow().isoformat(),
        "result": {
            "stage": new_stage,
            "stage_changed": new_stage != current_stage,
            "hesitation_detected": new_hesitation > 0,
            "intervention": intervention is not None
        }
    }
    
    if intervention:
        print(f"[ORCHESTRATOR] Intervention: {intervention[:50]}...")
    
    return {
        "messages": [],  # Don't add messages - prevent reducer duplication
        "conversation_stage": new_stage,
        "stage_message_count": stage_message_count,
        "hesitation_signals": hesitation_signals,
        "orchestrator_intervention": intervention,
        "reasoning_trace": [reasoning]
    }
