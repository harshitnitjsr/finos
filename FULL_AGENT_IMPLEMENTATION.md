# Full AFOS Multi-Agent Implementation Guide (Using Existing Agents)

This guide details how to transition AFOS from a Chat-based Intent Router (your current `supervisor.py`) to a **True Autonomous Financial Pipeline** by reusing the exact same Python agents and tools you have already built.

---

## 1. The Architecture Shift

You already have `AGENT_REGISTRY` in `app/langgraph/supervisor.py` spanning 8 highly capable agents powered by `EXPENSE_TOOLS`, `INVOICE_TOOLS`, `COMPLIANCE_TOOLS`, etc.

Right now, an incoming human message is routed to **one** agent via `classify_intent_node` and then ends.

To achieve Phase 4 autonomy, we will build a **Sequential StateGraph** where a new document triggers a relay race through your *existing* agents.

---

## 2. Step 1: Define the Shared Autonomous State

In `app/langgraph/state.py`, expand your state to hold financial processing metadata alongside the standard `AFOSState`:

```python
from typing import TypedDict, Annotated, Sequence, Optional
import operator
from langchain_core.messages import BaseMessage

class AutonomousPipeline_State(TypedDict):
    # Core graph requirements
    messages: Annotated[Sequence[BaseMessage], operator.add]
    run_id: str
    org_id: str
    
    # Context flowing downstream
    document_uri: str
    extracted_vendor: Optional[str]
    amount: float
    liquidity_status: str
    policy_status: str     # 'pass' | 'fail'
    final_decision: str    # 'approved' | 'escalated'
```

---

## 3. Step 2: Use Existing Agents as Graph Nodes

You do **not** need to rewrite your agents. We simply use the `make_agent_node(agent_key)` function from `supervisor.py` to stamp out nodes. 

To bridge the gap between autonomous document processing and chat agents, we just inject programmatic prompt messages (System commands disguised as Human instructions) driving them to use their tools on the document.

In `app/langgraph/pipeline.py`:

```python
from app.langgraph.supervisor import make_agent_node
from langchain_core.messages import HumanMessage

# 1. Grab the existing LangChain agents wrapper from your supervisor
invoice_agent_node = make_agent_node("invoice_agent")
vendor_agent_node = make_agent_node("vendor_agent")
compliance_agent_node = make_agent_node("compliance_agent")
treasury_agent_node = make_agent_node("treasury_agent")
approval_agent_node = make_agent_node("approval_agent")

def invoice_step(state: AutonomousPipeline_State):
    """Programs the Invoice Agent to extract the data."""
    # Programmatic prompt commanding the existing tool-backed agent
    prompt = f"Please extract all data from this document: {state['document_uri']} and summarize the vendor and amount."
    state["messages"].append(HumanMessage(content=prompt))
    return invoice_agent_node(state)

def vendor_step(state: AutonomousPipeline_State):
    """Programs the Vendor Agent to verify if it's shadow IT."""
    prompt = "Given the last extraction, use your tools to analyze this vendor risk and check for duplicate software (shadow IT)."
    state["messages"].append(HumanMessage(content=prompt))
    return vendor_agent_node(state)

def compliance_step(state: AutonomousPipeline_State):
    """Programs the Compliance Agent to evaluate OPA rules."""
    prompt = "Evaluate the current transaction context against OPA policies using your compliance tools. State if it passes or is blocked."
    state["messages"].append(HumanMessage(content=prompt))
    return compliance_agent_node(state)

def treasury_step(state: AutonomousPipeline_State):
    """Programs the Treasury Agent to determine funding."""
    prompt = "Use your forecasting tools to determine if we have cash to afford this today."
    state["messages"].append(HumanMessage(content=prompt))
    return treasury_agent_node(state)
```

---

## 4. Step 3: Connect the AI Nodes with Conditional Logic

Now, wire them together with routing edges based on the messages produced.

```python
from langgraph.graph import StateGraph, END

def route_after_compliance(state: AutonomousPipeline_State):
    last_msg = state["messages"][-1].content.lower()
    if "violation" in last_msg or "blocked" in last_msg:
        # Move directly to the Approval Agent bypassing treasury
        return "approval_step"
    return "treasury_step"

def route_after_treasury(state: AutonomousPipeline_State):
    last_msg = state["messages"][-1].content.lower()
    if "insufficient" in last_msg or "warning" in last_msg:
        return "approval_step"
    return END

# Build the Graph
pipeline = StateGraph(AutonomousPipeline_State)

# Add your existing agent wrappers
pipeline.add_node("invoice_step", invoice_step)
pipeline.add_node("vendor_step", vendor_step)
pipeline.add_node("compliance_step", compliance_step)
pipeline.add_node("treasury_step", treasury_step)
pipeline.add_node("approval_step", approval_agent_node) # Wraps directly

# Sequential chain
pipeline.set_entry_point("invoice_step")
pipeline.add_edge("invoice_step", "vendor_step")
pipeline.add_edge("vendor_step", "compliance_step")

# Decision Branches
pipeline.add_conditional_edges("compliance_step", route_after_compliance)
pipeline.add_conditional_edges("treasury_step", route_after_treasury)
pipeline.add_edge("approval_step", END)

# Compile
autonomous_financial_pipeline = pipeline.compile()
```

---

## 5. Step 4: Wrapping it in Temporal

Now, inside `app/workflows/invoice_workflows.py`, your Temporal engine calls this massive AI pipeline as a single distributed execution step.

```python
from temporalio import activity, workflow
from app.langgraph.pipeline import autonomous_financial_pipeline

@activity.defn
async def run_autonomous_agents(document_uri: str) -> dict:
    state = {"document_uri": document_uri, "messages": []}
    
    # Executes the full intelligence graph relying on your existing backend tools
    final_output = await autonomous_financial_pipeline.ainvoke(state)
    return final_output

@workflow.defn
class InvoiceWorkflow:
    @workflow.run
    async def process_invoice(self, document_uri: str):
        # Trigger the 8-agent negotiation
        final_state = await workflow.execute_activity(
            run_autonomous_agents,
            document_uri,
            schedule_to_close_timeout=timedelta(minutes=15)
        )
        
        last_msg = final_state["messages"][-1].content
        if "escalated" in last_msg.lower() or "approval queue" in last_msg.lower():
            # Temporal handles the blocking wait state
            await workflow.wait_condition(...) 

        return "Payment Executed"
```

### Why this is powerful:
You didn't write any new agent prompt logic. You took the `model_router.bind_tools(...)` AI configurations you previously wrote in `supervisor.py`, and you just stitched them linearly (Invoice -> Vendor -> Compliance -> Treasury). They inherently know what to do because they are supplied with `INVOICE_TOOLS`, `VENDOR_TOOLS`, etc.