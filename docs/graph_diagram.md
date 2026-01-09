# Sales Agent Graph - LangGraph Architecture

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	context_injector(context_injector)
	supervisor(supervisor)
	orchestrator(orchestrator)
	sales_agent(sales_agent)
	reverse_logistics_agent(reverse_logistics_agent)
	human_node(human_node)
	memory_optimizer(memory_optimizer)
	__end__([<p>__end__</p>]):::last
	__start__ --> context_injector;
	context_injector --> supervisor;
	human_node -.-> memory_optimizer;
	human_node -.-> reverse_logistics_agent;
	human_node -.-> sales_agent;
	orchestrator -.-> reverse_logistics_agent;
	orchestrator -.-> sales_agent;
	reverse_logistics_agent -.-> human_node;
	reverse_logistics_agent -.-> memory_optimizer;
	sales_agent -.-> human_node;
	sales_agent -.-> memory_optimizer;
	supervisor -.-> human_node;
	supervisor -.-> orchestrator;
	memory_optimizer --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc

```

## Nodes Description

| Node | Description |
|------|-------------|
| **context_injector** | Loads user profile and context |
| **supervisor** | Classifies messages (SAFE/UNSAFE) |
| **orchestrator** | Analyzes conversation stage, detects hesitation |
| **sales_agent** | Main sales conversation handler |
| **reverse_logistics_agent** | Handles returns/exchanges |
| **human_node** | Human-in-the-loop intervention |
| **memory_optimizer** | Summarizes long conversations |
