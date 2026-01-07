"""
Human Node - RF-HIT-01 to RF-HIT-02
Handles human-in-the-loop intervention for escalated conversations
"""
from typing import Dict, Any
from datetime import datetime
from ..state import AgentState, AgentReasoning, Message, EscalationRequest
from ...database.mongodb import MongoDB


async def save_escalation(escalation: EscalationRequest) -> None:
    """Save escalation request to MongoDB for supervisor dashboard"""
    db = MongoDB.get_database()
    await db.escalations.insert_one({
        **escalation,
        "created_at": datetime.utcnow().isoformat()
    })


async def get_escalation(escalation_id: str) -> Dict[str, Any]:
    """Get escalation by ID"""
    db = MongoDB.get_database()
    return await db.escalations.find_one({"id": escalation_id})


async def update_escalation(escalation_id: str, status: str, supervisor_response: str = None) -> None:
    """Update escalation status"""
    db = MongoDB.get_database()
    update_data = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat()
    }
    if supervisor_response:
        update_data["supervisor_response"] = supervisor_response
    
    await db.escalations.update_one(
        {"id": escalation_id},
        {"$set": update_data}
    )


async def human_node(state: AgentState) -> AgentState:
    """
    RF-HIT-01 to RF-HIT-02: Human Node
    
    This node is triggered when:
    1. Supervisor classifies message as UNSAFE
    2. SalesAgent explicitly escalates
    
    The graph will interrupt here (interrupt_before=["human_node"])
    allowing a human operator to:
    - Approve: Let the original message pass
    - Rewrite: Modify the bot's response manually
    
    This node saves the escalation to MongoDB and waits for human input.
    """
    escalation = state.get("escalation")
    conversation_id = state.get("conversation_id", "")
    
    if not escalation:
        # No escalation, shouldn't be here
        return {
            **state,
            "current_node": "human_node",
            "next_node": "memory_optimizer",
            "reasoning_trace": [{
                "agent": "HumanNode",
                "action": "skip",
                "reasoning": "No hay escalación pendiente",
                "timestamp": datetime.utcnow().isoformat(),
                "result": None
            }]
        }
    
    # Save escalation to MongoDB for supervisor dashboard
    await save_escalation(escalation)
    
    reasoning: AgentReasoning = {
        "agent": "HumanNode",
        "action": "escalate",
        "reasoning": f"Conversación escalada. Motivo: {escalation.get('reason')}. Esperando intervención humana.",
        "timestamp": datetime.utcnow().isoformat(),
        "result": {
            "escalation_id": escalation.get("id"),
            "status": "pending",
            "reason": escalation.get("reason"),
            "classification": escalation.get("classification")
        }
    }
    
    # Generate waiting message for user
    waiting_message: Message = {
        "role": "assistant",
        "content": "Tu consulta ha sido transferida a un supervisor. Un representante te atenderá en breve. Gracias por tu paciencia.",
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": {
            "escalation_id": escalation.get("id"),
            "status": "waiting_for_human"
        }
    }
    
    return {
        **state,
        "messages": [waiting_message],
        "current_node": "human_node",
        "next_node": None,  # Graph pauses here
        "reasoning_trace": [reasoning]
    }


async def process_human_response(
    state: AgentState,
    action: str,
    supervisor_response: str = None
) -> AgentState:
    """
    Process human supervisor's response
    
    Actions:
    - "approve": Let the conversation continue normally
    - "rewrite": Use supervisor's custom response
    - "reject": End the conversation
    """
    escalation = state.get("escalation")
    
    if not escalation:
        return state
    
    escalation_id = escalation.get("id")
    
    if action == "approve":
        # Update escalation status
        await update_escalation(escalation_id, "approved")
        
        reasoning: AgentReasoning = {
            "agent": "HumanNode",
            "action": "approve",
            "reasoning": "Supervisor aprobó continuar la conversación",
            "timestamp": datetime.utcnow().isoformat(),
            "result": {"action": "approved"}
        }
        
        return {
            **state,
            "requires_human": False,
            "escalation": {**escalation, "status": "approved"},
            "current_node": "human_node",
            "next_node": "sales_agent",  # Continue to sales agent
            "reasoning_trace": [reasoning]
        }
    
    elif action == "rewrite":
        # Update escalation with supervisor response
        await update_escalation(escalation_id, "rewritten", supervisor_response)
        
        # Create message from supervisor
        supervisor_message: Message = {
            "role": "supervisor",
            "content": supervisor_response,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "escalation_id": escalation_id,
                "action": "rewritten"
            }
        }
        
        reasoning: AgentReasoning = {
            "agent": "HumanNode",
            "action": "rewrite",
            "reasoning": f"Supervisor reescribió respuesta: {supervisor_response[:100]}...",
            "timestamp": datetime.utcnow().isoformat(),
            "result": {"action": "rewritten", "response_length": len(supervisor_response)}
        }
        
        return {
            **state,
            "messages": [supervisor_message],
            "requires_human": False,
            "escalation": {**escalation, "status": "rewritten", "supervisor_response": supervisor_response},
            "current_node": "human_node",
            "next_node": "memory_optimizer",
            "reasoning_trace": [reasoning]
        }
    
    elif action == "reject":
        # Update escalation status
        await update_escalation(escalation_id, "rejected")
        
        # Create rejection message
        rejection_message: Message = {
            "role": "assistant",
            "content": "Lo sentimos, no podemos procesar esta solicitud. Si tienes alguna otra consulta sobre nuestros productos, estaré encantado de ayudarte.",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "escalation_id": escalation_id,
                "action": "rejected"
            }
        }
        
        reasoning: AgentReasoning = {
            "agent": "HumanNode",
            "action": "reject",
            "reasoning": "Supervisor rechazó la solicitud",
            "timestamp": datetime.utcnow().isoformat(),
            "result": {"action": "rejected"}
        }
        
        return {
            **state,
            "messages": [rejection_message],
            "requires_human": False,
            "escalation": {**escalation, "status": "rejected"},
            "current_node": "human_node",
            "next_node": "memory_optimizer",
            "reasoning_trace": [reasoning]
        }
    
    return state
