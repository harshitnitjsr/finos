"""
AFOS LangGraph Supervisor — the main StateGraph that routes queries
to specialized financial agents, each backed by real LangChain tools.

Flow:
  classify_intent → [route] → agent_node → synthesize → END

Each agent node uses ChatOpenAI.bind_tools() for function calling.
Every tool call is logged to agent_tool_logs via tool_logger.wrap_tools().
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Literal

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from loguru import logger

from app.langgraph.state import AFOSState
from app.langgraph.tool_logger import call_tool_with_logging
from app.core.config import settings

# ── Tool imports ──────────────────────────────────────────────────────────────
from app.tools.expense_tools import EXPENSE_TOOLS
from app.tools.invoice_tools import INVOICE_TOOLS
from app.tools.treasury_tools import TREASURY_TOOLS
from app.tools.vendor_tools import VENDOR_TOOLS
from app.tools.compliance_tools import COMPLIANCE_TOOLS
from app.tools.forecasting_tools import FORECASTING_TOOLS

# ── Agent registry ────────────────────────────────────────────────────────────

AGENT_REGISTRY = {
    "expense_agent": {
        "id": "expense-agent",
        "name": "Expense Intelligence",
        "tools": EXPENSE_TOOLS,
        "system": """You are the Expense Intelligence Agent for AFOS — an AI Financial Operating System.
You specialize in: expense analysis, anomaly detection, category breakdowns, and subscription optimization.

ALWAYS use your tools to fetch real data before answering. Never guess numbers.
Be specific and cite actual figures from tool results.
Format currency values clearly (e.g. $12,450 or ₹8,50,000).""",
    },
    "invoice_agent": {
        "id": "invoice-agent",
        "name": "Invoice Intelligence",
        "tools": INVOICE_TOOLS,
        "system": """You are the Invoice Intelligence Agent for AFOS.
You specialize in: invoice tracking, vendor payment history, overdue invoices, and pipeline management.

ALWAYS use your tools to fetch real data. Never fabricate invoice numbers or amounts.
Highlight overdue or high-risk items prominently.""",
    },
    "treasury_agent": {
        "id": "treasury-agent",
        "name": "Treasury Agent",
        "tools": TREASURY_TOOLS,
        "system": """You are the Treasury Agent for AFOS.
You specialize in: burn rate analysis, cash flow, runway forecasting, and payment scheduling.

ALWAYS use your tools to calculate real burn rates and runway.
Present financial health status clearly (excellent/healthy/warning/critical).""",
    },
    "vendor_agent": {
        "id": "vendor-agent",
        "name": "Vendor Intelligence",
        "tools": VENDOR_TOOLS,
        "system": """You are the Vendor Intelligence Agent for AFOS.
You specialize in: vendor risk scoring, spend distribution, supplier analysis, and vendor search.

ALWAYS use your tools to fetch real vendor data.
Flag high-risk or unverified vendors clearly.""",
    },
    "compliance_agent": {
        "id": "compliance-agent",
        "name": "Compliance Agent",
        "tools": COMPLIANCE_TOOLS,
        "system": """You are the Compliance Agent for AFOS.
You specialize in: policy enforcement, approval routing, risk assessment, and high-risk item detection.

ALWAYS use your tools to evaluate policy rules and fetch pending approvals.
Be explicit about which policy rules apply.""",
    },
    "approval_agent": {
        "id": "approval-agent",
        "name": "Approval Agent",
        "tools": COMPLIANCE_TOOLS,   # reuses compliance tools
        "system": """You are the Approval Agent for AFOS.
You specialize in: approval queue management, routing decisions, and escalation assessment.

ALWAYS use get_pending_approvals first to see what needs attention.
Provide clear approve/reject recommendations with reasoning.""",
    },
    "forecasting_agent": {
        "id": "forecasting-agent",
        "name": "Forecasting Agent",
        "tools": FORECASTING_TOOLS,
        "system": """You are the Forecasting Agent for AFOS.
You specialize in: spend forecasting, category trend analysis, budget projections, and historical analysis.

ALWAYS use your tools to fetch real historical data before making projections.
Show trend direction (growing/stable/declining) and quantify changes.""",
    },
    "insight_agent": {
        "id": "insight-agent",
        "name": "Insight Agent",
        "tools": FORECASTING_TOOLS,  # has dashboard_snapshot and agent_activity
        "system": """You are the Insight Agent for AFOS — the general financial intelligence hub.
You specialize in: executive summaries, cross-domain insights, recommendations, and financial health overviews.

ALWAYS use get_financial_dashboard_snapshot as your first tool to ground your response in real data.
Then use other tools if needed for deeper analysis. Be executive-level concise.""",
    },
}

# Intent → agent mapping
INTENT_TO_AGENT = {
    "expense_query":    "expense_agent",
    "anomaly_query":    "expense_agent",
    "invoice_query":    "invoice_agent",
    "treasury_query":   "treasury_agent",
    "cashflow_query":   "treasury_agent",
    "vendor_query":     "vendor_agent",
    "compliance_query": "compliance_agent",
    "approval_query":   "approval_agent",
    "forecast_query":   "forecasting_agent",
    "general_finance":  "insight_agent",
}

# ── Intent classifier ─────────────────────────────────────────────────────────

CLASSIFY_PROMPT = """Classify this financial query into exactly one of these intents:
- expense_query: spending, expenses, transactions, costs, purchases
- anomaly_query: unusual spending, fraud, suspicious charges, anomalies, flagged
- invoice_query: invoices, bills, vendor payments, payment status, due dates
- treasury_query: burn rate, cash flow, cash position, runway, liquidity
- cashflow_query: cash projection, cash forecast, incoming/outgoing
- vendor_query: vendors, suppliers, vendor risk, vendor search, who we pay
- compliance_query: policy violations, compliance, rules, blocked payments
- approval_query: approvals, pending review, who needs to approve, approval queue
- forecast_query: forecast, prediction, budget, trend, projection, growth
- general_finance: general questions, executive summary, financial health, overview

Return ONLY the intent label. No explanation."""


async def classify_intent_node(state: AFOSState) -> dict:
    """Node: classify the user's intent to route to the right agent."""
    messages = state["messages"]
    user_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")

    llm = ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY, temperature=0)
    response = await llm.ainvoke([
        SystemMessage(content=CLASSIFY_PROMPT),
        HumanMessage(content=user_msg),
    ])
    intent = response.content.strip().lower()
    if intent not in INTENT_TO_AGENT:
        intent = "general_finance"

    agent_key = INTENT_TO_AGENT[intent]
    cfg = AGENT_REGISTRY[agent_key]

    logger.info(f"LangGraph: classified '{user_msg[:60]}' → intent={intent} → agent={cfg['name']}")

    return {
        "intent": intent,
        "agent_id": cfg["id"],
        "agent_name": cfg["name"],
        "tool_calls": [],
    }


# ── Generic agent node factory ────────────────────────────────────────────────

def make_agent_node(agent_key: str):
    """
    Creates a LangGraph node for a given agent.
    Uses ChatOpenAI + bind_tools() for function calling.
    Tools are invoked directly via ainvoke() (not ToolNode) to ensure
    proper async execution and accurate timing logs.
    """
    cfg = AGENT_REGISTRY[agent_key]

    async def agent_node(state: AFOSState) -> dict:
        run_id = state.get("run_id", str(uuid.uuid4()))
        org_id = state.get("org_id")

        from app.core.context import org_id_var
        org_id_var.set(org_id)

        from app.core.redis_client import cache as _cache

        agent_id = cfg["id"]
        agent_name = cfg["name"]

        # ── Store initial reasoning context in Redis (5min TTL) ───────────
        await _cache.set_reasoning_context(run_id, {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "intent": state.get("intent", "unknown"),
            "org_id": org_id,
            "started_at": datetime.utcnow().isoformat(),
            "tool_calls": [],
            "status": "running",
        })

        # Tool registry — raw tools for LLM binding + direct async invocation
        raw_tools = cfg["tools"]
        tool_map = {t.name: t for t in raw_tools}

        # LLM with tool schema bound for OpenAI function calling
        llm = ChatOpenAI(
            model="gpt-4o",
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
        ).bind_tools(raw_tools)

        system_text = cfg["system"]

        # Prepend memory context if available (Redis recent + Qdrant semantic)
        memory_context = state.get("memory_context", "")
        if memory_context:
            system_text = f"{system_text}\n\n{memory_context}"

        system = SystemMessage(content=system_text)
        conversation = [system] + list(state["messages"])

        start = time.time()
        tool_call_records: list[dict] = []
        total_tokens = 0

        # Agentic loop: LLM decides which tools to call
        MAX_TURNS = 6
        for turn in range(MAX_TURNS):
            response = await llm.ainvoke(conversation)

            # Accumulate token usage
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                total_tokens += response.usage_metadata.get("total_tokens", 0)

            conversation.append(response)

            # No more tool calls → final answer
            if not response.tool_calls:
                break

            # Execute each tool call via call_tool_with_logging (direct coroutine)
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})
                tool_id = tc.get("id", str(uuid.uuid4()))

                tool_call_records.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "turn": turn,
                })

                # ── Update reasoning context with live tool call progress ─────
                await _cache.set_reasoning_context(run_id, {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "intent": state.get("intent", "unknown"),
                    "org_id": org_id,
                    "status": "calling_tool",
                    "current_tool": tool_name,
                    "current_turn": turn,
                    "tool_calls": tool_call_records,
                    "updated_at": datetime.utcnow().isoformat(),
                })

                tool_obj = tool_map.get(tool_name)
                if tool_obj is None:
                    tool_result_content = f"Error: tool '{tool_name}' not found"
                else:
                    try:
                        raw_result = await call_tool_with_logging(
                            tool_obj, tool_args,
                            agent_id=agent_id,
                            agent_name=agent_name,
                            run_id=run_id,
                            org_id=org_id,
                        )
                        tool_result_content = json.dumps(raw_result, default=str)[:4000]
                    except Exception as exc:
                        tool_result_content = f"Tool error: {exc}"
                        logger.error(f"Tool {tool_name} failed: {exc}")

                # Add ToolMessage so LLM sees the result
                conversation.append(ToolMessage(
                    content=tool_result_content,
                    tool_call_id=tool_id,
                    name=tool_name,
                ))

        # Extract last AIMessage with text content
        final_text = ""
        for msg in reversed(conversation):
            if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                final_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        duration_ms = int((time.time() - start) * 1000)

        # Persist to agent_logs for the agents dashboard
        from app.core.agent_logger import write_agent_log
        user_input = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")
        await write_agent_log(
            agent_id=agent_id,
            agent_name=agent_name,
            action=f"langgraph:{state.get('intent', 'general')}",
            status="success",
            model_used="gpt-4o",
            tokens_used=total_tokens,
            duration_ms=duration_ms,
            input_summary=str(user_input)[:200],
            output_summary=final_text[:200],
            confidence=0.9,
            org_id=org_id,
        )

        logger.info(
            f"LangGraph: {agent_name} done in {duration_ms}ms | "
            f"{len(tool_call_records)} tools | {total_tokens} tokens"
        )

        # ── Mark reasoning context complete + clear from Redis ─────────────────
        await _cache.set_reasoning_context(run_id, {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "intent": state.get("intent", "unknown"),
            "org_id": org_id,
            "status": "done",
            "tool_calls": tool_call_records,
            "total_tokens": total_tokens,
            "duration_ms": duration_ms,
            "completed_at": datetime.utcnow().isoformat(),
        })
        # Give clients one last chance to read it (1s window), then clear
        import asyncio
        asyncio.get_event_loop().call_later(2, lambda: asyncio.ensure_future(
            _cache.clear_reasoning_context(run_id)
        ))

        return {
            "messages": [AIMessage(content=final_text)],
            "final_response": final_text,
            "tool_calls": tool_call_records,
            "total_tokens": state.get("total_tokens", 0) + total_tokens,
            "total_duration_ms": state.get("total_duration_ms", 0) + duration_ms,
        }

    agent_node.__name__ = f"{agent_key}_node"
    return agent_node



# ── Router function ───────────────────────────────────────────────────────────

def route_to_agent(state: AFOSState) -> str:
    """Route from classifier to the right agent node."""
    intent = state.get("intent", "general_finance")
    return INTENT_TO_AGENT.get(intent, "insight_agent")


# ── Build the StateGraph ──────────────────────────────────────────────────────

def build_supervisor_graph() -> StateGraph:
    """Build and compile the AFOS LangGraph supervisor."""
    graph = StateGraph(AFOSState)

    # Add classifier node
    graph.add_node("classify_intent", classify_intent_node)

    # Add all agent nodes
    for agent_key in AGENT_REGISTRY:
        graph.add_node(agent_key, make_agent_node(agent_key))

    # Entry point
    graph.set_entry_point("classify_intent")

    # Conditional routing from classifier
    graph.add_conditional_edges(
        "classify_intent",
        route_to_agent,
        {agent_key: agent_key for agent_key in AGENT_REGISTRY},
    )

    # All agents lead to END
    for agent_key in AGENT_REGISTRY:
        graph.add_edge(agent_key, END)

    return graph.compile()


# Singleton — compiled once at module load
supervisor_graph = build_supervisor_graph()
