# Implementing True Agent-to-Agent Coordination 

Moving from **Top-Down Orchestration** (Phase 1) to **True Agent-to-Agent Coordination** (Phase 4) is the leap from workflow automation to autonomous financial operations. 

Currently, AFOS uses **Temporal** as a strict manager. To achieve true coordination, we need to unlock the `backend/langgraph/` directory to create decentralized negotiation networks.

Here is the step-by-step implementation blueprint to build this inside AFOS.

---

## 1. The Architecture Shift

*   **Current State (Temporal):** Linear and Deterministic. `Invoice` -> `OCR` -> `Compliance` -> `Approval`.
*   **Target State (LangGraph + Temporal):** Cyclic and Negotiated. Temporal handles the *reliability* (retries, timeouts, waiting for human inputs), but inside a Temporal Activity, **LangGraph** manages the multi-agent debate.

---

## 2. Step-by-Step Implementation

### Step 1: Define the Shared "Graph State"
Agents need a shared memory space to look at the same problem. In LangGraph, this is the `State`.
Modify `backend/app/langgraph/state.py`:

```python
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage

class FinancialGraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    invoice_id: str
    amount: float
    liquidity_status: str
    negotiation_rounds: int
    final_decision: str # "approved", "rejected", "restructured"
```

### Step 2: Implement the Agents as Nodes
Instead of isolated functions, agents become "Nodes" in a graph that can read the state, append a message, and route to the next agent.

Example (Procurement vs Treasury):

```python
def treasury_node(state: FinancialGraphState):
    # Treasury Agent checks liquidity
    amount = state["amount"]
    if amount > 50000 and state["liquidity_status"] == "low":
        msg = f"Treasury: We cannot pay ${amount} upfront. We need to split this into 4 quarterly payments."
    else:
        msg = f"Treasury: Liquidity is fine. Approved for payment."
    
    return {"messages": [msg], "negotiation_rounds": state["negotiation_rounds"] + 1}

def procurement_node(state: FinancialGraphState):
    # Procurement Agent reads the last message
    last_msg = state["messages"][-1].content
    
    if "split this" in last_msg:
        msg = "Procurement: I will draft an email to the vendor requesting Net-90 terms or 4 installments."
        return {"messages": [msg], "final_decision": "restructured"}
    
    return {"messages": ["Procurement: Proceeding with execution."], "final_decision": "approved"}
```

### Step 3: Map the "Edges" (The Routing Logic)
Agents need to know who to talk to next based on their own logic rather than a hardcoded script.

```python
from langgraph.graph import StateGraph, END

def router(state: FinancialGraphState):
    # If the decision is to restructure, we end the loop and output the draft email
    if state.get("final_decision") == "restructured":
        return END
    # If Treasury pushed back, Procurement must respond
    if state["negotiation_rounds"] < 3:
        return "procurement"
    return END

# Build the Graph
workflow = StateGraph(FinancialGraphState)
workflow.add_node("treasury", treasury_node)
workflow.add_node("procurement", procurement_node)

workflow.add_edge("procurement", "treasury") # Procurement asks Treasury for funds
workflow.add_conditional_edges("treasury", router) # Treasury routes based on logic

agent_network = workflow.compile()
```

---

## 3. Where does this fit in the UI?

In your Next.js dashboard, you would visualize this debate in the **Workflow Monitor**. 
Instead of a straight line showing (Step 1 -> Step 2 -> Step 3), the UI would render a dynamic chat log or a cyclical graph showing:

1.  *Procurement Agent requested $50k.*
2.  *Treasury Agent flagged low liquidity.*
3.  *Procurement Agent generated restructuring email.*
4.  *Requires Human Approval to send.*

By wrapping LangGraph inside a Temporal workflow, AFOS achieves decentralized, intelligent agent negotiation while retaining the enterprise durability required for finance.