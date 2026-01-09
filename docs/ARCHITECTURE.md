# Sales Agent - Architecture Documentation

## System Overview

This is a LangGraph-based sales agent with the following components:

### Tech Stack
- **Framework**: LangGraph + FastAPI
- **LLM**: OpenAI GPT-4o-mini
- **Database**: SQLite (local)
- **Vector Store**: ChromaDB (local)
- **Memory**: Upstash Redis (optional)
- **Observability**: LangSmith

## Graph Flow

```
User Message → Context Injector → Supervisor → Orchestrator → Sales Agent → Memory Optimizer → Response
                                      ↓
                                 Human Node (if unsafe)
```

## Nodes

### 1. Context Injector
- Loads user profile from database
- Injects conversation history summary
- Sets up user preferences

### 2. Supervisor
- Classifies incoming messages
- Detects unsafe/inappropriate content
- Routes to human intervention if needed

### 3. Orchestrator
- Analyzes conversation stage (discovery, consideration, decision)
- Detects hesitation signals
- Provides proactive guidance to sales agent

### 4. Sales Agent
- Main conversation handler
- Product search and recommendations
- Cart management
- Price objection handling

### 5. Reverse Logistics Agent
- Handles returns and exchanges
- Order tracking
- Customer support for post-purchase

### 6. Human Node
- Human-in-the-loop intervention
- Supervisor can approve/reject/rewrite responses
- Used for escalated or unsafe cases

### 7. Memory Optimizer
- Summarizes conversations after 10 messages
- Compresses history for context efficiency
- Maintains important details (products, budget, decisions)

## State Schema

```python
AgentState = {
    "conversation_id": str,
    "messages": List[Message],
    "user_context": Dict,
    "reasoning_trace": List[AgentReasoning],
    "classification": str,  # SAFE, UNSAFE, PENDING
    "escalation": Optional[EscalationInfo],
    "requires_human": bool,
    "cart": List[CartItem],
    "message_count": int,
    "compressed_history": Optional[str],
    "current_node": str,
    "next_node": Optional[str],
    "error": Optional[str]
}
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/agent/start` | Start new conversation |
| POST | `/api/agent/message` | Send message |
| GET | `/api/agent/{id}/reasoning` | Get reasoning trace |
| POST | `/api/agent/{id}/human-response` | Handle human intervention |
| GET | `/api/products` | List products |
| GET | `/api/health` | Health check |

## Evaluation

Run evaluations with LangSmith:
```bash
python -m evaluation.run_evaluation
```

## Environment Variables

```env
OPENAI_API_KEY=sk-...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=your-project-name
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
CHROMA_PERSIST_DIR=./data/chroma_db
```
