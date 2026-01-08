"""
Memory Optimizer Node - Conversation Context Manager

LÓGICA DE MEMORIA (usando Upstash Redis):
1. Primeros 10 mensajes: Se inyectan COMPLETOS como contexto
2. Después de 10 mensajes: Se hace un RESUMEN de esos 10
3. Siguientes mensajes: RESUMEN + nuevos mensajes (hasta 10 nuevos)
4. Al llegar a 10 nuevos: RESUMEN_ANTERIOR + RESUMEN_NUEVOS = NUEVO_RESUMEN
5. Repetir indefinidamente

REDIS vs MONGODB:
- Redis: Estado volátil (mensajes recientes, resúmenes, sesión) - sub-ms latency
- MongoDB: Persistencia a largo plazo (historial completo, analytics)
"""
from typing import Dict, Any, List
from datetime import datetime
import time
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from ..state import AgentState, AgentReasoning, Message
from ....config import settings

# Try to import Redis, fallback to None if not available
try:
    from ...services.upstash_redis import get_redis
    REDIS_AVAILABLE = True
except Exception as e:
    print(f"[MEMORY] Redis not available, using MongoDB fallback: {e}")
    REDIS_AVAILABLE = False
    get_redis = None

# Threshold for summarization
MESSAGES_BEFORE_SUMMARY = 10


def _get_llm():
    """Get LLM instance using model from settings"""
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.2
    )


async def get_memory_state(conversation_id: str) -> Dict[str, Any]:
    """
    Recupera el estado de memoria desde Redis (sub-ms latency).
    Fallback a MongoDB si Redis no está disponible.
    """
    start = time.time()
    
    if REDIS_AVAILABLE and get_redis:
        try:
            redis = get_redis()
            memory = await redis.get_memory(conversation_id)
            elapsed = (time.time() - start) * 1000
            print(f"[MEMORY] get_memory_state from Redis: {elapsed:.2f}ms")
            return memory
        except Exception as e:
            print(f"[MEMORY] Redis error, falling back to MongoDB: {e}")
    
    # Fallback to MongoDB
    from ...database.mongodb import MongoDB
    db = MongoDB.get_database()
    memory = await db.conversation_memory.find_one({"conversation_id": conversation_id})
    elapsed = (time.time() - start) * 1000
    print(f"[MEMORY] get_memory_state from MongoDB: {elapsed:.2f}ms")
    
    if not memory:
        return {
            "summary": "",
            "messages_since_summary": 0,
            "total_messages": 0,
            "summary_count": 0
        }
    memory.pop("_id", None)
    return memory


async def save_memory_state(conversation_id: str, memory_state: Dict[str, Any]):
    """Guarda el estado de memoria en Redis con fallback a MongoDB."""
    start = time.time()
    
    if REDIS_AVAILABLE and get_redis:
        try:
            redis = get_redis()
            await redis.set_memory(conversation_id, memory_state)
            elapsed = (time.time() - start) * 1000
            print(f"[MEMORY] save_memory_state to Redis: {elapsed:.2f}ms")
            return
        except Exception as e:
            print(f"[MEMORY] Redis error, falling back to MongoDB: {e}")
    
    # Fallback to MongoDB
    from ...database.mongodb import MongoDB
    db = MongoDB.get_database()
    memory_state["conversation_id"] = conversation_id
    memory_state["updated_at"] = datetime.utcnow()
    await db.conversation_memory.update_one(
        {"conversation_id": conversation_id},
        {"$set": memory_state},
        upsert=True
    )
    elapsed = (time.time() - start) * 1000
    print(f"[MEMORY] save_memory_state to MongoDB: {elapsed:.2f}ms")


async def create_summary(messages: List[Dict], existing_summary: str = "") -> str:
    """
    Crea un resumen de los mensajes usando LLM.
    Si hay un resumen existente, lo combina con el nuevo.
    """
    messages_text = "\n".join([
        f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')[:500]}"
        for msg in messages
    ])
    
    try:
        llm = _get_llm()
        
        if existing_summary:
            prompt = f"""Tienes un resumen anterior de la conversación y nuevos mensajes.
Combina ambos en UN SOLO resumen coherente y conciso.

RESUMEN ANTERIOR:
{existing_summary}

NUEVOS MENSAJES:
{messages_text}

IMPORTANTE: El resumen debe incluir:
- Productos mostrados con sus números (#1, #2, etc.) y nombres exactos
- SKUs de productos mencionados
- Estado actual del carrito
- Presupuesto del cliente si lo mencionó
- Decisiones tomadas por el cliente
- Cualquier información relevante para continuar la venta

Genera el resumen combinado (máximo 400 palabras):"""
        else:
            prompt = f"""Resume la siguiente conversación de ventas.

MENSAJES:
{messages_text}

IMPORTANTE: El resumen debe incluir:
- Productos mostrados con sus números (#1, #2, etc.) y nombres exactos
- SKUs de productos mencionados
- Estado actual del carrito
- Presupuesto del cliente si lo mencionó
- Decisiones tomadas por el cliente

Genera el resumen (máximo 300 palabras):"""
        
        response = await llm.ainvoke([
            SystemMessage(content="Eres un asistente que resume conversaciones de ventas manteniendo información crítica."),
            HumanMessage(content=prompt)
        ])
        
        return response.content
        
    except Exception as e:
        print(f"[MEMORY] ERROR creating summary: {e}")
        # Fallback: concatenar
        if existing_summary:
            return f"{existing_summary}\n\n[Nuevos mensajes]: {messages_text[:500]}"
        return messages_text[:800]


async def memory_optimizer_node(state: AgentState) -> AgentState:
    """
    Memory Optimizer Node - Se ejecuta DESPUÉS de cada interacción.
    
    LÓGICA:
    - Cuenta mensajes desde el último resumen
    - Si hay 10+ mensajes nuevos, crea resumen
    - El resumen se acumula con resúmenes anteriores
    """
    messages = state.get("messages", [])
    conversation_id = state.get("conversation_id", "")
    
    if not conversation_id:
        return {**state, "current_node": "memory_optimizer", "next_node": None}
    
    # Get current memory state
    memory = await get_memory_state(conversation_id)
    
    total_messages = len(messages)
    messages_since_summary = memory.get("messages_since_summary", 0) + 1
    existing_summary = memory.get("summary", "")
    summary_count = memory.get("summary_count", 0)
    
    print(f"\n[MEMORY] === Estado de Memoria ===")
    print(f"[MEMORY] Conversation: {conversation_id}")
    print(f"[MEMORY] Total mensajes: {total_messages}")
    print(f"[MEMORY] Mensajes desde último resumen: {messages_since_summary}")
    print(f"[MEMORY] Resúmenes realizados: {summary_count}")
    print(f"[MEMORY] Tiene resumen existente: {'Sí' if existing_summary else 'No'}")
    
    new_summary = existing_summary
    
    # Check if we need to create a summary
    if messages_since_summary >= MESSAGES_BEFORE_SUMMARY:
        print(f"\n[MEMORY] >>> CREANDO RESUMEN (alcanzados {messages_since_summary} mensajes) <<<")
        
        # Get the last 10 messages to summarize
        messages_to_summarize = messages[-MESSAGES_BEFORE_SUMMARY:]
        
        # Create summary
        new_summary = await create_summary(messages_to_summarize, existing_summary)
        
        print(f"[MEMORY] Resumen creado ({len(new_summary)} caracteres):")
        print(f"[MEMORY] ---")
        print(f"[MEMORY] {new_summary[:500]}...")
        print(f"[MEMORY] ---")
        
        # Reset counter
        messages_since_summary = 0
        summary_count += 1
    
    # Save memory state
    await save_memory_state(conversation_id, {
        "conversation_id": conversation_id,
        "summary": new_summary,
        "messages_since_summary": messages_since_summary,
        "total_messages": total_messages,
        "summary_count": summary_count
    })
    
    print(f"[MEMORY] Estado guardado. Próximo resumen en: {MESSAGES_BEFORE_SUMMARY - messages_since_summary} mensajes")
    print(f"[MEMORY] =============================\n")
    
    return {
        **state,
        "messages": [],  # Don't add messages - prevent reducer duplication
        "compressed_history": new_summary,
        "current_node": "memory_optimizer",
        "next_node": None,
        "reasoning_trace": state.get("reasoning_trace", [])
    }


async def get_context_for_agent(conversation_id: str, recent_messages: List[Dict]) -> str:
    """
    Construye el contexto para inyectar al agente.
    
    Retorna:
    - Si hay resumen: RESUMEN + últimos mensajes (hasta 10)
    - Si no hay resumen: últimos 10 mensajes completos
    """
    memory = await get_memory_state(conversation_id)
    summary = memory.get("summary", "")
    
    parts = []
    
    if summary:
        parts.append(f"**CONTEXTO PREVIO DE LA CONVERSACIÓN:**\n{summary}")
        print(f"[MEMORY] Inyectando resumen al agente ({len(summary)} chars)")
    
    # Always include recent messages (the agent will receive these anyway)
    # This function is for additional context injection if needed
    
    return "\n\n".join(parts) if parts else ""
