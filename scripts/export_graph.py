"""
Export LangGraph visualization
==============================
Generates Mermaid diagram and PNG image of the sales agent graph.

Usage:
    python scripts/export_graph.py
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.infrastructure.langgraph.graph import create_sales_graph


def export_mermaid():
    """Export graph as Mermaid diagram."""
    graph = create_sales_graph()
    compiled = graph.compile()

    # Get Mermaid representation
    mermaid_code = compiled.get_graph().draw_mermaid()

    # Save to file
    output_path = "docs/graph_diagram.md"
    os.makedirs("docs", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Sales Agent Graph - LangGraph Architecture\n\n")
        f.write("```mermaid\n")
        f.write(mermaid_code)
        f.write("\n```\n\n")
        f.write("## Nodes Description\n\n")
        f.write("| Node | Description |\n")
        f.write("|------|-------------|\n")
        f.write("| **context_injector** | Loads user profile and context |\n")
        f.write("| **supervisor** | Classifies messages (SAFE/UNSAFE) |\n")
        f.write("| **orchestrator** | Analyzes conversation stage, detects hesitation |\n")
        f.write("| **sales_agent** | Main sales conversation handler |\n")
        f.write("| **reverse_logistics_agent** | Handles returns/exchanges |\n")
        f.write("| **human_node** | Human-in-the-loop intervention |\n")
        f.write("| **memory_optimizer** | Summarizes long conversations |\n")

    print(f"[OK] Mermaid diagram saved to: {output_path}")
    print(f"\n{mermaid_code}")

    return mermaid_code


def export_png():
    """Export graph as PNG image (requires graphviz)."""
    try:
        graph = create_sales_graph()
        compiled = graph.compile()

        output_path = "docs/graph_diagram.png"
        os.makedirs("docs", exist_ok=True)

        # Try to generate PNG
        png_data = compiled.get_graph().draw_mermaid_png()

        with open(output_path, "wb") as f:
            f.write(png_data)

        print(f"[OK] PNG diagram saved to: {output_path}")
        return True

    except Exception as e:
        print(f"[WARN] Could not generate PNG: {e}")
        print("[INFO] You can use the Mermaid code at https://mermaid.live to generate images")
        return False


def export_ascii():
    """Export simple ASCII representation of the graph."""
    ascii_diagram = """
    ┌─────────────────────────────────────────────────────────────────┐
    │                     SALES AGENT GRAPH                           │
    └─────────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │  START (Entry)   │
                              └────────┬─────────┘
                                       │
                                       ▼
                         ┌─────────────────────────┐
                         │   context_injector      │
                         │  (Load user profile)    │
                         └───────────┬─────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │      supervisor         │
                         │  (Classify: SAFE/UNSAFE)│
                         └───────────┬─────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │ SAFE           │                │ UNSAFE
                    ▼                │                ▼
        ┌───────────────────┐       │      ┌───────────────────┐
        │   orchestrator    │       │      │    human_node     │
        │ (Stage analysis)  │       │      │ (Intervention)    │
        └─────────┬─────────┘       │      └─────────┬─────────┘
                  │                 │                │
         ┌────────┴────────┐       │                │
         │                 │       │                │
         ▼                 ▼       │                │
    ┌──────────┐    ┌──────────┐  │                │
    │  sales   │    │ reverse  │  │                │
    │  agent   │    │ logistics│  │                │
    └────┬─────┘    └────┬─────┘  │                │
         │               │        │                │
         └───────┬───────┘        │                │
                 │                │                │
                 ▼                │                │
        ┌───────────────────┐     │                │
        │ memory_optimizer  │◄────┴────────────────┘
        │ (Summarize long   │
        │  conversations)   │
        └─────────┬─────────┘
                  │
                  ▼
            ┌──────────┐
            │   END    │
            └──────────┘
    """

    output_path = "docs/graph_ascii.txt"
    os.makedirs("docs", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ascii_diagram)

    print(f"[OK] ASCII diagram saved to: {output_path}")
    print(ascii_diagram)


def export_architecture_overview():
    """Export complete architecture documentation."""
    doc = """# Sales Agent - Architecture Documentation

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
"""

    output_path = "docs/ARCHITECTURE.md"
    os.makedirs("docs", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)

    print(f"[OK] Architecture doc saved to: {output_path}")


if __name__ == "__main__":
    print("="*60)
    print("EXPORTING GRAPH DOCUMENTATION")
    print("="*60 + "\n")

    print("[STEP 1] Generating Mermaid diagram...")
    export_mermaid()

    print("\n[STEP 2] Generating ASCII diagram...")
    export_ascii()

    print("\n[STEP 3] Generating PNG (if available)...")
    export_png()

    print("\n[STEP 4] Generating Architecture documentation...")
    export_architecture_overview()

    print("\n" + "="*60)
    print("EXPORT COMPLETE")
    print("="*60)
    print("\nFiles generated in ./docs/:")
    print("  - graph_diagram.md   (Mermaid)")
    print("  - graph_ascii.txt    (ASCII art)")
    print("  - graph_diagram.png  (Image, if graphviz available)")
    print("  - ARCHITECTURE.md    (Full documentation)")
    print("\nTip: Paste Mermaid code at https://mermaid.live for online editing")
