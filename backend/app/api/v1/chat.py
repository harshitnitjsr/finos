"""
AFOS Chat API — powered by LangGraph multi-agent supervisor + 3-tier memory.

Memory pipeline per request:
  1. Load context:  Redis (hot session) + Qdrant (semantic recall) → injected into system prompt
  2. Run graph:     classify intent → specialized agent → tool calls → real DB data
  3. Save turn:     Redis append + SQL persist + Qdrant embed (async background)
"""
import uuid
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage
from loguru import logger

from app.core.database import get_db
from app.core.memory import memory_service

router = APIRouter()
ORG_ID = "org_demo_001"


# ── Request / Response schemas ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    message: str
    agent: str
    agent_id: str
    intent: str
    tool_calls: list[dict]
    total_tokens: int
    duration_ms: int
    session_id: str
    timestamp: str
    memory_used: bool       # did memory context influence this response?
    sources: list[str]      # which memory stores were used


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Multi-agent chat with 3-tier memory-augmented RAG.

    Memory flow:
      GET:  Redis (recent session) + Qdrant (semantic past turns) → context string
      RUN:  LangGraph supervisor → agent → live SQL tool calls
      PUT:  Redis append + SQL INSERT + Qdrant embed (background task)
    """
    from app.langgraph.supervisor import supervisor_graph
    start = time.time()
    run_id = str(uuid.uuid4())

    # ── 1. Retrieve memory context ──────────────────────────────────────────
    memory_context, lc_history = await memory_service.get_context(
        session_id=request.session_id,
        user_query=request.message,
        org_id=ORG_ID,
    )
    memory_used = bool(memory_context)
    sources = []
    if lc_history:
        sources.append("redis")
        sources.append("postgresql")
    if "semantic recall" in memory_context.lower():
        sources.append("qdrant")

    # ── 2. Build LangGraph initial state ────────────────────────────────────
    initial_state = {
        "messages": lc_history + [HumanMessage(content=request.message)],
        "intent": "",
        "agent_id": "",
        "agent_name": "",
        "run_id": run_id,
        "org_id": ORG_ID,
        "session_id": request.session_id,
        "tool_calls": [],
        "final_response": None,
        "memory_context": memory_context,
        "total_tokens": 0,
        "total_duration_ms": 0,
    }

    # ── 3. Run supervisor graph ──────────────────────────────────────────────
    try:
        final_state = await supervisor_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"LangGraph supervisor error: {e}")
        final_state = {
            **initial_state,
            "final_response": f"⚠️ Agent error: {str(e)[:200]}. Please try again.",
            "intent": "error",
            "agent_id": "system",
            "agent_name": "System",
            "tool_calls": [],
            "total_tokens": 0,
            "total_duration_ms": int((time.time() - start) * 1000),
        }

    response_text = final_state.get("final_response") or "I was unable to generate a response. Please try again."
    tool_calls = final_state.get("tool_calls", [])
    total_tokens = final_state.get("total_tokens", 0)
    duration_ms = int((time.time() - start) * 1000)
    agent_name = final_state.get("agent_name", "AI Agent")
    agent_id = final_state.get("agent_id", "")
    intent = final_state.get("intent", "")

    # ── 4. Save turn to all 3 memory stores (async background) ──────────────
    await memory_service.save_turn(
        session_id=request.session_id,
        org_id=ORG_ID,
        user_message=request.message,
        ai_message=response_text,
        agent_name=agent_name,
        intent=intent,
        run_id=run_id,
        tool_calls=tool_calls,
        tokens_used=total_tokens,
        duration_ms=duration_ms,
    )

    logger.info(
        f"Chat: session={request.session_id} intent={intent} "
        f"agent={agent_name} tools={len(tool_calls)} "
        f"tokens={total_tokens} {duration_ms}ms memory={memory_used}"
    )

    return ChatResponse(
        message=response_text,
        agent=agent_name,
        agent_id=agent_id,
        intent=intent,
        tool_calls=tool_calls,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        session_id=request.session_id,
        timestamp=datetime.utcnow().isoformat(),
        memory_used=memory_used,
        sources=list(set(sources)),
    )


# ── Session management ────────────────────────────────────────────────────────

@router.delete("/{session_id}")
async def clear_session(session_id: str):
    """Clear Redis session buffer (SQL + Qdrant history is retained for audit)."""
    await memory_service.clear_session(session_id, ORG_ID)
    return {"message": f"Session '{session_id}' cleared from Redis cache"}


@router.get("/history/{session_id}")
async def get_history(session_id: str, limit: int = 50):
    """
    Full session history from PostgreSQL (authoritative, persistent).
    Includes agent metadata, tool calls, and token usage per turn.
    """
    messages = await memory_service.get_session_history(session_id, ORG_ID, limit=limit)
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
        "source": "postgresql",
    }


@router.get("/sessions")
async def list_sessions(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """List all chat sessions with message counts and last activity."""
    from app.models.models import ConversationMessage
    from sqlalchemy import select, func, desc
    result = await db.execute(
        select(
            ConversationMessage.session_id,
            func.count(ConversationMessage.id).label("message_count"),
            func.max(ConversationMessage.created_at).label("last_active"),
        )
        .where(ConversationMessage.org_id == ORG_ID)
        .group_by(ConversationMessage.session_id)
        .order_by(desc(func.max(ConversationMessage.created_at)))
        .limit(limit)
    )
    rows = result.all()
    return {
        "sessions": [
            {
                "session_id": r.session_id,
                "message_count": r.message_count,
                "last_active": r.last_active.isoformat() if r.last_active else None,
            }
            for r in rows
        ]
    }


@router.get("/tool-logs")
async def get_tool_logs(limit: int = 50, agent_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Get recent tool call logs across all agents."""
    from app.models.models import AgentToolLog
    from sqlalchemy import select, desc
    q = select(AgentToolLog).where(AgentToolLog.org_id == ORG_ID)
    if agent_id:
        q = q.where(AgentToolLog.agent_id == agent_id)
    q = q.order_by(desc(AgentToolLog.created_at)).limit(min(limit, 200))
    result = await db.execute(q)
    logs = result.scalars().all()
    return {
        "total": len(logs),
        "tool_logs": [
            {
                "id": l.id,
                "agent_id": l.agent_id,
                "agent_name": l.agent_name,
                "run_id": l.run_id,
                "tool_name": l.tool_name,
                "input_data": l.input_data,
                "output_data": l.output_data,
                "input_summary": l.input_summary,
                "output_summary": l.output_summary,
                "duration_ms": l.duration_ms,
                "status": l.status,
                "error": l.error,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ],
    }
