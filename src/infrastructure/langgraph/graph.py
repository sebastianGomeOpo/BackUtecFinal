"""
LangGraph Sales Agent Graph
Compiles the graph with all nodes and edges
"""
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient
from .state import AgentState
from src.config import settings
from .nodes.context_injector import context_injector_node
from .nodes.supervisor import supervisor_node
from .nodes.sales_agent_v3 import sales_agent_node_v3 as sales_agent_node
from .nodes.reverse_logistics_agent import reverse_logistics_agent_node
from .nodes.human_node import human_node, process_human_response
from .nodes.memory_optimizer import memory_optimizer_node


def route_after_supervisor(state: AgentState) -> str:
    """
    Route based on supervisor classification and intent detection.
    Supervisor decides which specialized agent should handle the request.
    """
    if state.get("requires_human") or state.get("classification") == "UNSAFE":
        return "human_node"
    
    # Check intent for routing to specialized agents
    intent = state.get("intent", "sales")
    if intent == "reverse_logistics":
        return "reverse_logistics_agent"
    
    return "sales_agent"


def route_after_sales_agent(state: AgentState) -> str:
    """Route based on sales agent decision"""
    if state.get("requires_human"):
        return "human_node"
    return "memory_optimizer"


def route_after_reverse_logistics_agent(state: AgentState) -> str:
    """Route based on reverse logistics agent decision"""
    if state.get("requires_human"):
        return "human_node"
    return "memory_optimizer"


def route_after_human_node(state: AgentState) -> str:
    """Route based on human decision"""
    next_node = state.get("next_node")
    if next_node == "sales_agent":
        return "sales_agent"
    if next_node == "reverse_logistics_agent":
        return "reverse_logistics_agent"
    return "memory_optimizer"


def create_sales_graph() -> StateGraph:
    """
    Create the Sales Agent Graph with Supervisor architecture
    
    Flow:
    1. ContextInjector -> Loads user profile
    2. Supervisor -> Classifies message (SAFE/UNSAFE)
    3a. If SAFE -> SalesAgent -> MemoryOptimizer -> END
    3b. If UNSAFE -> HumanNode (interrupt) -> MemoryOptimizer -> END
    """
    
    # Create graph with state schema
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("context_injector", context_injector_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("sales_agent", sales_agent_node)
    graph.add_node("reverse_logistics_agent", reverse_logistics_agent_node)
    graph.add_node("human_node", human_node)
    graph.add_node("memory_optimizer", memory_optimizer_node)
    
    # Set entry point
    graph.set_entry_point("context_injector")
    
    # Add edges
    graph.add_edge("context_injector", "supervisor")
    
    # Conditional routing after supervisor
    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "sales_agent": "sales_agent",
            "reverse_logistics_agent": "reverse_logistics_agent",
            "human_node": "human_node"
        }
    )
    
    # Conditional routing after sales agent
    graph.add_conditional_edges(
        "sales_agent",
        route_after_sales_agent,
        {
            "human_node": "human_node",
            "memory_optimizer": "memory_optimizer"
        }
    )
    
    # Conditional routing after reverse logistics agent
    graph.add_conditional_edges(
        "reverse_logistics_agent",
        route_after_reverse_logistics_agent,
        {
            "human_node": "human_node",
            "memory_optimizer": "memory_optimizer"
        }
    )
    
    # Conditional routing after human node
    graph.add_conditional_edges(
        "human_node",
        route_after_human_node,
        {
            "sales_agent": "sales_agent",
            "reverse_logistics_agent": "reverse_logistics_agent",
            "memory_optimizer": "memory_optimizer"
        }
    )
    
    # End after memory optimizer
    graph.add_edge("memory_optimizer", END)
    
    return graph


class SalesGraph:
    """
    Wrapper class for the Sales Agent Graph
    Provides methods for running the graph and handling human intervention
    """
    
    def __init__(self):
        self.graph = create_sales_graph()
        # Use MongoDB for checkpoint persistence
        # State size is controlled by custom reducers in state.py
        self.mongo_client = MongoClient(settings.mongodb_uri)
        self.checkpointer = MongoDBSaver(
            self.mongo_client,
            db_name=settings.mongodb_db_name
        )
        self.app = self.graph.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["human_node"]  # RF-HIT-01: Interrupt before human node
        )
    
    async def start_conversation(self, user_id: str = "guest") -> Dict[str, Any]:
        """Start a new conversation"""
        import uuid
        from datetime import datetime
        
        conversation_id = str(uuid.uuid4())[:12]
        
        initial_state: AgentState = {
            "conversation_id": conversation_id,
            "messages": [],
            "user_context": {"user_id": user_id},
            "reasoning_trace": [],
            "classification": "PENDING",
            "escalation": None,
            "requires_human": False,
            "cart": [],
            "message_count": 0,
            "compressed_history": None,
            "current_node": "start",
            "next_node": "context_injector",
            "error": None
        }
        
        # Run context injection
        config = {"configurable": {"thread_id": conversation_id}}
        result = await self.app.ainvoke(initial_state, config)
        
        return {
            "conversation_id": conversation_id,
            "message": "¡Hola! Soy Taylor, tu asistente de ventas. ¿En qué puedo ayudarte hoy?",
            "reasoning_trace": result.get("reasoning_trace", [])
        }
    
    async def process_message(
        self,
        conversation_id: str,
        message: str,
        user_id: str = "guest"
    ) -> Dict[str, Any]:
        """Process a user message through the graph"""
        from datetime import datetime
        
        # Create user message
        user_message = {
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": None
        }
        
        # Get current state or create new
        config = {"configurable": {"thread_id": conversation_id}}
        
        try:
            current_state = self.app.get_state(config)
            state_values = current_state.values if current_state else {}
        except:
            state_values = {}
        
        # Build input state
        input_state: AgentState = {
            "conversation_id": conversation_id,
            "messages": state_values.get("messages", []) + [user_message],
            "user_context": state_values.get("user_context", {"user_id": user_id}),
            "reasoning_trace": [],
            "classification": "PENDING",
            "escalation": state_values.get("escalation"),
            "requires_human": False,
            "cart": state_values.get("cart", []),
            "message_count": len(state_values.get("messages", [])) + 1,
            "compressed_history": state_values.get("compressed_history"),
            "current_node": "start",
            "next_node": "context_injector",
            "error": None
        }
        
        # Run graph
        result = await self.app.ainvoke(input_state, config)
        
        # Check if interrupted for human intervention
        if result.get("requires_human"):
            return {
                "conversation_id": conversation_id,
                "message": result.get("messages", [{}])[-1].get("content", ""),
                "requires_human": True,
                "escalation": result.get("escalation"),
                "reasoning_trace": result.get("reasoning_trace", []),
                "status": "escalated"
            }
        
        # Get response from state messages
        assistant_message = ""
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") in ["assistant", "supervisor"]:
                assistant_message = msg.get("content", "")
                break
        
        return {
            "conversation_id": conversation_id,
            "message": assistant_message,
            "requires_human": False,
            "cart": result.get("cart", []),
            "reasoning_trace": result.get("reasoning_trace", []),
            "status": "completed"
        }
    
    async def handle_human_response(
        self,
        conversation_id: str,
        action: str,
        supervisor_response: str = None
    ) -> Dict[str, Any]:
        """
        RF-HIT-02: Handle human supervisor response
        
        Actions:
        - approve: Continue with original flow
        - rewrite: Use supervisor's custom response
        - reject: End conversation
        """
        config = {"configurable": {"thread_id": conversation_id}}
        
        try:
            current_state = self.app.get_state(config)
            state_values = current_state.values if current_state else {}
        except:
            return {"error": "Conversation not found"}
        
        # Process human response
        updated_state = await process_human_response(
            state_values,
            action,
            supervisor_response
        )
        
        # Continue graph execution if needed
        if updated_state.get("next_node"):
            result = await self.app.ainvoke(updated_state, config)
            return {
                "conversation_id": conversation_id,
                "message": result.get("messages", [{}])[-1].get("content", ""),
                "reasoning_trace": result.get("reasoning_trace", []),
                "status": "completed"
            }
        
        return {
            "conversation_id": conversation_id,
            "message": updated_state.get("messages", [{}])[-1].get("content", ""),
            "reasoning_trace": updated_state.get("reasoning_trace", []),
            "status": action
        }
    
    async def get_reasoning_trace(self, conversation_id: str) -> list:
        """Get full reasoning trace for a conversation"""
        config = {"configurable": {"thread_id": conversation_id}}
        
        try:
            current_state = self.app.get_state(config)
            return current_state.values.get("reasoning_trace", []) if current_state else []
        except:
            return []


# Global instance
_sales_graph: Optional[SalesGraph] = None


def get_sales_graph() -> SalesGraph:
    """Get or create the global SalesGraph instance"""
    global _sales_graph
    if _sales_graph is None:
        _sales_graph = SalesGraph()
    return _sales_graph
