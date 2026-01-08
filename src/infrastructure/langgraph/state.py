"""
State definition for the Sales Agent Graph

IMPORTANT: We use custom reducers to prevent infinite state accumulation.
- messages: Limited to last 10 messages to avoid checkpoint bloat
- reasoning_trace: Limited to last 5 steps
This prevents MongoDB DocumentTooLarge errors (16MB limit).
"""
from typing import TypedDict, List, Optional, Literal, Annotated
from datetime import datetime


class Message(TypedDict):
    """Chat message structure"""
    role: Literal["user", "assistant", "system", "supervisor"]
    content: str
    timestamp: str
    metadata: Optional[dict]


class UserContext(TypedDict):
    """User context for personalization"""
    user_id: str
    name: str
    purchase_history: List[dict]
    preferences: dict
    tone: str


class AgentReasoning(TypedDict):
    """Reasoning step from an agent"""
    agent: str
    action: str
    reasoning: str
    timestamp: str
    result: Optional[dict]


class EscalationRequest(TypedDict):
    """Escalation request to human supervisor"""
    id: str
    conversation_id: str
    reason: str
    classification: str
    original_message: str
    timestamp: str
    status: Literal["pending", "approved", "rewritten", "rejected"]
    supervisor_response: Optional[str]


class CartItem(TypedDict):
    """Shopping cart item"""
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    subtotal: float


def messages_reducer(existing: List[Message], new: List[Message]) -> List[Message]:
    """
    Custom reducer for messages that:
    1. Appends new messages to existing
    2. Keeps only the last 10 messages to prevent checkpoint bloat
    """
    if existing is None:
        existing = []
    if new is None:
        new = []
    
    combined = existing + new
    
    # Keep only last 10 messages
    limited = combined[-10:] if len(combined) > 10 else combined
    
    return limited


def reasoning_reducer(existing: List[AgentReasoning], new: List[AgentReasoning]) -> List[AgentReasoning]:
    """
    Custom reducer for reasoning trace that keeps only last 5 steps.
    """
    if existing is None:
        existing = []
    if new is None:
        new = []
    
    combined = existing + new
    
    # Keep only last 5 reasoning steps
    return combined[-5:] if len(combined) > 5 else combined


class AgentState(TypedDict):
    """Main state for the Sales Agent Graph"""
    # Conversation
    conversation_id: str
    messages: Annotated[List[Message], messages_reducer]
    
    # User context (invisible to chat)
    user_context: Optional[UserContext]
    
    # Agent reasoning trace (for dashboard) - limited to prevent bloat
    reasoning_trace: Annotated[List[AgentReasoning], reasoning_reducer]
    
    # Current classification
    classification: Literal["SAFE", "UNSAFE", "PENDING"]
    
    # Intent for routing to specialized agents
    intent: Optional[Literal["sales", "reverse_logistics"]]
    
    # Escalation
    escalation: Optional[EscalationRequest]
    requires_human: bool
    
    # Shopping cart
    cart: List[CartItem]
    
    # Memory optimization
    message_count: int
    compressed_history: Optional[str]
    
    # Control flow
    current_node: str
    next_node: Optional[str]
    error: Optional[str]
