"""
LangSmith Evaluation Script for Sales Agent
============================================
Professional evaluation setup with custom metrics for sales agent testing.

Usage:
    python -m evaluation.run_evaluation

This script:
1. Creates/updates a dataset in LangSmith
2. Runs the sales agent against test cases
3. Evaluates responses with LLM-as-judge
4. Outputs results to LangSmith dashboard
"""
import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load env vars first
load_dotenv()

from langsmith import Client
from langsmith.evaluation import evaluate
from langsmith.schemas import Example, Run

# Import your graph
from src.infrastructure.langgraph.graph import SalesGraph


# ============================================================
# CONFIGURATION
# ============================================================
DATASET_NAME = "sales-agent-evaluation"
DATASET_DESCRIPTION = "Test cases for UTEC Sales Agent evaluation"
EXPERIMENT_PREFIX = "sales-agent"


# ============================================================
# TEST CASES DATASET
# ============================================================
TEST_CASES = [
    # === GREETING & INTENT ===
    {
        "input": {"message": "Hola"},
        "expected": {
            "should_contain": ["hola", "ayudar", "busca"],
            "category": "greeting",
            "should_be_helpful": True
        }
    },
    {
        "input": {"message": "Buenas tardes, estoy buscando muebles"},
        "expected": {
            "should_contain": ["muebles", "qué tipo", "busca"],
            "category": "greeting_with_intent",
            "should_be_helpful": True
        }
    },

    # === PRODUCT SEARCH ===
    {
        "input": {"message": "Quiero ver camas"},
        "expected": {
            "should_contain": ["cama"],
            "category": "product_search",
            "should_show_products": True
        }
    },
    {
        "input": {"message": "Tienen sofás de cuero?"},
        "expected": {
            "should_contain": ["sofá", "cuero"],
            "category": "specific_search",
            "should_show_products": True
        }
    },
    {
        "input": {"message": "Busco una mesa de comedor para 6 personas"},
        "expected": {
            "should_contain": ["mesa", "comedor"],
            "category": "specific_search",
            "should_show_products": True
        }
    },

    # === BUDGET HANDLING ===
    {
        "input": {"message": "Mi presupuesto es de 500 soles"},
        "expected": {
            "should_acknowledge_budget": True,
            "category": "budget",
            "should_be_helpful": True
        }
    },
    {
        "input": {"message": "Algo económico, no tengo mucho dinero"},
        "expected": {
            "should_contain": ["precio", "económic", "presupuesto"],
            "category": "budget_concern",
            "should_be_helpful": True
        }
    },

    # === OBJECTIONS ===
    {
        "input": {"message": "Es muy caro"},
        "expected": {
            "should_handle_objection": True,
            "category": "price_objection",
            "should_not_be_pushy": True
        }
    },
    {
        "input": {"message": "Voy a pensarlo"},
        "expected": {
            "should_handle_objection": True,
            "category": "hesitation",
            "should_not_be_pushy": True
        }
    },

    # === CART OPERATIONS ===
    {
        "input": {"message": "Agrega el producto #1 al carrito"},
        "expected": {
            "should_confirm_action": True,
            "category": "cart_add",
            "should_be_helpful": True
        }
    },

    # === EDGE CASES ===
    {
        "input": {"message": "asdfghjkl"},
        "expected": {
            "should_ask_clarification": True,
            "category": "gibberish",
            "should_be_polite": True
        }
    },
    {
        "input": {"message": "Cuál es el horario de atención?"},
        "expected": {
            "category": "off_topic",
            "should_be_helpful": True
        }
    },

    # === CLOSING ===
    {
        "input": {"message": "Quiero finalizar mi compra"},
        "expected": {
            "should_contain": ["compra", "carrito", "pago"],
            "category": "checkout",
            "should_be_helpful": True
        }
    },
]


# ============================================================
# CUSTOM EVALUATORS
# ============================================================

def sales_effectiveness_evaluator(run: Run, example: Example) -> dict:
    """
    Evaluates if the sales agent response is effective.
    Checks for key sales behaviors.
    """
    response = run.outputs.get("response", "").lower()
    expected = example.outputs or {}

    score = 0.0
    reasoning = []

    # Check for required content
    if "should_contain" in expected:
        keywords = expected["should_contain"]
        found = sum(1 for kw in keywords if kw.lower() in response)
        keyword_score = found / len(keywords) if keywords else 1.0
        score += keyword_score * 0.4
        reasoning.append(f"Keywords: {found}/{len(keywords)}")
    else:
        score += 0.4  # No keyword requirement

    # Check helpfulness indicators
    helpful_indicators = ["puedo", "ayudar", "gustar", "mostrar", "opciones", "disponible"]
    helpful_count = sum(1 for ind in helpful_indicators if ind in response)
    helpfulness_score = min(helpful_count / 3, 1.0)
    score += helpfulness_score * 0.3
    reasoning.append(f"Helpfulness indicators: {helpful_count}")

    # Check for engagement (questions, suggestions)
    has_question = "?" in response
    has_suggestion = any(word in response for word in ["te recomiendo", "sugiero", "podrías", "qué te parece"])
    engagement_score = (0.5 if has_question else 0) + (0.5 if has_suggestion else 0)
    score += engagement_score * 0.3
    reasoning.append(f"Engagement: question={has_question}, suggestion={has_suggestion}")

    return {
        "key": "sales_effectiveness",
        "score": score,
        "comment": " | ".join(reasoning)
    }


def response_quality_evaluator(run: Run, example: Example) -> dict:
    """
    Evaluates response quality: length, clarity, professionalism.
    """
    response = run.outputs.get("response", "")

    score = 0.0
    reasoning = []

    # Length check (not too short, not too long)
    length = len(response)
    if 50 <= length <= 500:
        length_score = 1.0
    elif 20 <= length < 50 or 500 < length <= 800:
        length_score = 0.7
    else:
        length_score = 0.3
    score += length_score * 0.3
    reasoning.append(f"Length: {length} chars")

    # Professionalism (no slang, proper greeting)
    unprofessional = ["jajaja", "xd", "lol", "wtf", "omg"]
    is_professional = not any(word in response.lower() for word in unprofessional)
    score += (1.0 if is_professional else 0.0) * 0.3
    reasoning.append(f"Professional: {is_professional}")

    # Completeness (ends properly, not cut off)
    ends_properly = response.strip().endswith((".", "!", "?", "😊"))
    score += (1.0 if ends_properly else 0.5) * 0.2
    reasoning.append(f"Complete: {ends_properly}")

    # Spanish language check
    spanish_indicators = ["de", "la", "el", "que", "en", "un", "es"]
    spanish_count = sum(1 for ind in spanish_indicators if f" {ind} " in response.lower())
    is_spanish = spanish_count >= 2
    score += (1.0 if is_spanish else 0.0) * 0.2
    reasoning.append(f"Spanish: {is_spanish}")

    return {
        "key": "response_quality",
        "score": score,
        "comment": " | ".join(reasoning)
    }


def safety_evaluator(run: Run, example: Example) -> dict:
    """
    Checks for unsafe or inappropriate content.
    """
    response = run.outputs.get("response", "").lower()

    # List of unsafe patterns
    unsafe_patterns = [
        "no puedo ayudar",
        "error",
        "exception",
        "null",
        "undefined",
        "traceback",
    ]

    # Offensive language (basic check)
    offensive_words = ["idiota", "estúpido", "tonto", "imbécil"]

    has_unsafe = any(pattern in response for pattern in unsafe_patterns)
    has_offensive = any(word in response for word in offensive_words)

    if has_offensive:
        score = 0.0
        comment = "Contains offensive language"
    elif has_unsafe:
        score = 0.5
        comment = "Contains error indicators"
    else:
        score = 1.0
        comment = "Safe response"

    return {
        "key": "safety",
        "score": score,
        "comment": comment
    }


# ============================================================
# AGENT TARGET FUNCTION
# ============================================================

async def initialize_services():
    """Initialize database and vector store (like API lifespan does)."""
    from src.infrastructure.database.sqlite_db import Database
    from src.infrastructure.vectorstore.chroma_store import ChromaStore
    from src.config import settings

    # Always reconnect since each asyncio.run() creates a new event loop
    await Database.connect()

    try:
        await ChromaStore.initialize(settings.chroma_persist_dir)
    except Exception:
        pass  # ChromaDB might already be initialized


async def run_sales_agent_async(inputs: dict) -> dict:
    """
    Target function that runs the sales agent.
    This is what gets evaluated.
    """
    import uuid

    # Initialize services for this event loop
    await initialize_services()

    # Use unique user_id per test to avoid UNIQUE constraint errors
    test_user_id = f"eval_user_{uuid.uuid4().hex[:8]}"

    graph = SalesGraph()

    # Start conversation
    start_result = await graph.start_conversation(user_id=test_user_id)
    conversation_id = start_result["conversation_id"]

    # Process message
    result = await graph.process_message(
        conversation_id=conversation_id,
        message=inputs["message"],
        user_id=test_user_id
    )

    return {
        "response": result.get("message", ""),
        "conversation_id": conversation_id,
        "status": result.get("status", "unknown"),
        "reasoning_trace": result.get("reasoning_trace", [])
    }


def run_sales_agent(inputs: dict) -> dict:
    """Sync wrapper for the async agent function."""
    return asyncio.run(run_sales_agent_async(inputs))


# ============================================================
# MAIN EVALUATION LOGIC
# ============================================================

def create_or_update_dataset(client: Client) -> str:
    """Create or update the evaluation dataset."""

    # Check if dataset exists
    datasets = list(client.list_datasets(dataset_name=DATASET_NAME))

    if datasets:
        dataset = datasets[0]
        print(f"[EVAL] Using existing dataset: {dataset.name} (id: {dataset.id})")

        # Delete existing examples to update
        examples = list(client.list_examples(dataset_id=dataset.id))
        for ex in examples:
            client.delete_example(ex.id)
        print(f"[EVAL] Cleared {len(examples)} existing examples")
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description=DATASET_DESCRIPTION
        )
        print(f"[EVAL] Created new dataset: {dataset.name} (id: {dataset.id})")

    # Add test cases
    for i, test_case in enumerate(TEST_CASES):
        client.create_example(
            inputs=test_case["input"],
            outputs=test_case["expected"],
            dataset_id=dataset.id,
            metadata={"category": test_case["expected"].get("category", "general")}
        )

    print(f"[EVAL] Added {len(TEST_CASES)} test cases to dataset")
    return dataset.name


def run_evaluation():
    """Main evaluation function."""
    print("\n" + "="*60)
    print("SALES AGENT EVALUATION")
    print("="*60 + "\n")

    # Check LangSmith config
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        print("[ERROR] LANGCHAIN_API_KEY not set!")
        return

    print(f"[EVAL] LangSmith API Key: {api_key[:20]}...")
    print(f"[EVAL] Project: {os.getenv('LANGCHAIN_PROJECT', 'default')}")

    # Initialize client
    client = Client()

    # Create/update dataset
    print("\n[STEP 1] Setting up dataset...")
    dataset_name = create_or_update_dataset(client)

    # Define evaluators
    print("\n[STEP 2] Configuring evaluators...")
    evaluators = [
        sales_effectiveness_evaluator,
        response_quality_evaluator,
        safety_evaluator,
    ]

    print(f"[EVAL] Using {len(evaluators)} custom evaluators")

    # Run evaluation
    print("\n[STEP 3] Running evaluation...")
    print(f"[EVAL] Dataset: {dataset_name}")
    print(f"[EVAL] Test cases: {len(TEST_CASES)}")
    print("-" * 40)

    experiment_name = f"{EXPERIMENT_PREFIX}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    results = evaluate(
        run_sales_agent,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=experiment_name,
        max_concurrency=2,  # Limit concurrent runs
    )

    # Print summary
    print("\n" + "="*60)
    print("EVALUATION COMPLETE")
    print("="*60)
    print(f"\n[RESULT] Experiment: {experiment_name}")
    print(f"[RESULT] View results at: https://smith.langchain.com")
    print(f"[RESULT] Project: {os.getenv('LANGCHAIN_PROJECT', 'default')}")

    return results


if __name__ == "__main__":
    run_evaluation()
