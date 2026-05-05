"""
AFOS — AI Chatbot Workspace API
/api/v1/workspace-chats

Provides full CRUD for workspace conversations and proxies message sends
through the *same* LangGraph supervisor used by the floating widget.

Session isolation:
  - Widget sessions use  session_id = "s_<timestamp>"
  - Workspace sessions   session_id = "ws_<uuid>"
  The "ws_" prefix keeps memory namespaces completely separate.

Persistence:
  - WorkspaceChat       — named conversation (title, timestamps, stats)
  - WorkspaceChatMessage — per-turn log (role, content, agent meta, tools)
"""
import uuid
import json
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update
from langchain_core.messages import HumanMessage
from loguru import logger

from app.core.database import get_db
from app.core.memory import memory_service
from app.core.subscription import require_prompt_quota, increment_prompt_usage
from app.api.deps import get_org_id, get_user_id, get_user_email

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ChatCreateRequest(BaseModel):
    title: Optional[str] = "New Chat"
    model: Optional[str] = "gpt-4o"


class ChatRenameRequest(BaseModel):
    title: str


class SendMessageRequest(BaseModel):
    message: str


class ChatOut(BaseModel):
    id: str
    title: str
    session_id: str
    model: str
    message_count: int
    last_message_preview: Optional[str]
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    agent_name: Optional[str]
    agent_id: Optional[str]
    intent: Optional[str]
    tool_calls: list
    memory_used: bool
    memory_sources: list
    tokens_used: int
    duration_ms: int
    created_at: str


class SendMessageResponse(BaseModel):
    message_id: str
    chat_id: str
    response: str
    agent: str
    agent_id: str
    intent: str
    tool_calls: list
    total_tokens: int
    duration_ms: int
    timestamp: str
    memory_used: bool
    sources: list


# ── Helpers ───────────────────────────────────────────────────────────────────

def _chat_to_out(chat) -> dict:
    return {
        "id": chat.id,
        "title": chat.title,
        "session_id": chat.session_id,
        "model": chat.model,
        "message_count": chat.message_count,
        "last_message_preview": chat.last_message_preview,
        "created_at": chat.created_at.isoformat(),
        "updated_at": chat.updated_at.isoformat(),
    }


def _msg_to_out(msg) -> dict:
    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "agent_name": msg.agent_name,
        "agent_id": msg.agent_id,
        "intent": msg.intent,
        "tool_calls": msg.tool_calls or [],
        "memory_used": msg.memory_used,
        "memory_sources": msg.memory_sources or [],
        "tokens_used": msg.tokens_used,
        "duration_ms": msg.duration_ms,
        "created_at": msg.created_at.isoformat(),
    }


# ── List chats ────────────────────────────────────────────────────────────────

@router.get("")
async def list_chats(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Return workspace chats sorted by most-recently-updated."""
    from app.models.models import WorkspaceChat

    q = (
        select(WorkspaceChat)
        .where(WorkspaceChat.org_id == org_id, WorkspaceChat.is_archived.is_(False))
        .order_by(desc(WorkspaceChat.updated_at))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(q)
    chats = result.scalars().all()

    total_q = await db.execute(
        select(func.count()).select_from(WorkspaceChat)
        .where(WorkspaceChat.org_id == org_id, WorkspaceChat.is_archived.is_(False))
    )
    total = total_q.scalar() or 0

    return {
        "chats": [_chat_to_out(c) for c in chats],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


# ── Create chat ───────────────────────────────────────────────────────────────

@router.post("", response_model=ChatOut)
async def create_chat(
    body: ChatCreateRequest,
    org_id: str = Depends(get_org_id),
    user_id: str = Depends(get_user_id),
    user_email: str = Depends(get_user_email),
    db: AsyncSession = Depends(get_db),
):
    """Create a new empty workspace chat with a ws_-prefixed session_id."""
    from app.models.models import WorkspaceChat

    chat = WorkspaceChat(
        id=str(uuid.uuid4()),
        org_id=org_id,
        user_id=user_id or None,
        user_email=user_email or None,
        title=body.title or "New Chat",
        session_id=f"ws_{uuid.uuid4().hex}",
        model=body.model or "gpt-4o",
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    logger.info(f"WorkspaceChat created: {chat.id} session={chat.session_id}")
    return _chat_to_out(chat)


# ── Get chat ──────────────────────────────────────────────────────────────────

@router.get("/{chat_id}")
async def get_chat(
    chat_id: str,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    from app.models.models import WorkspaceChat

    result = await db.execute(
        select(WorkspaceChat)
        .where(WorkspaceChat.id == chat_id, WorkspaceChat.org_id == org_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return _chat_to_out(chat)


# ── Rename chat ───────────────────────────────────────────────────────────────

@router.patch("/{chat_id}")
async def rename_chat(
    chat_id: str,
    body: ChatRenameRequest,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    from app.models.models import WorkspaceChat

    result = await db.execute(
        select(WorkspaceChat)
        .where(WorkspaceChat.id == chat_id, WorkspaceChat.org_id == org_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    chat.title = body.title[:255]
    await db.commit()
    await db.refresh(chat)
    return _chat_to_out(chat)


# ── Delete (soft archive) chat ────────────────────────────────────────────────

@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    from app.models.models import WorkspaceChat

    result = await db.execute(
        select(WorkspaceChat)
        .where(WorkspaceChat.id == chat_id, WorkspaceChat.org_id == org_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    chat.is_archived = True
    await db.commit()
    # Also clear Redis session cache so memory doesn't leak
    try:
        await memory_service.clear_session(chat.session_id, org_id)
    except Exception:
        pass
    return {"message": "Chat archived", "chat_id": chat_id}


# ── Get messages ──────────────────────────────────────────────────────────────

@router.get("/{chat_id}/messages")
async def get_messages(
    chat_id: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    from app.models.models import WorkspaceChat, WorkspaceChatMessage

    # Verify ownership
    chat_q = await db.execute(
        select(WorkspaceChat)
        .where(WorkspaceChat.id == chat_id, WorkspaceChat.org_id == org_id)
    )
    chat = chat_q.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    msgs_q = (
        select(WorkspaceChatMessage)
        .where(WorkspaceChatMessage.chat_id == chat_id)
        .order_by(WorkspaceChatMessage.created_at)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(msgs_q)
    msgs = result.scalars().all()

    return {
        "chat_id": chat_id,
        "messages": [_msg_to_out(m) for m in msgs],
        "count": len(msgs),
    }


# ── Send message ──────────────────────────────────────────────────────────────

@router.post("/{chat_id}/messages", response_model=SendMessageResponse)
async def send_message(
    chat_id: str,
    body: SendMessageRequest,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
    _sub: dict = Depends(require_prompt_quota),   # 402 if prompt limit hit
):
    """
    Send a user message → run LangGraph supervisor → persist both turns
    to WorkspaceChatMessage → update WorkspaceChat stats.

    Reuses the exact same supervisor_graph and memory_service as the widget.
    """
    from app.models.models import WorkspaceChat, WorkspaceChatMessage
    from app.langgraph.supervisor import supervisor_graph

    # ── Verify & load chat ───────────────────────────────────────────────────
    chat_q = await db.execute(
        select(WorkspaceChat)
        .where(WorkspaceChat.id == chat_id, WorkspaceChat.org_id == org_id)
    )
    chat = chat_q.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    start = time.time()
    run_id = str(uuid.uuid4())
    session_id = chat.session_id

    # ── 1. Persist user message ──────────────────────────────────────────────
    user_msg = WorkspaceChatMessage(
        id=str(uuid.uuid4()),
        org_id=org_id,
        chat_id=chat_id,
        session_id=session_id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)

    # ── 2. Load memory context ───────────────────────────────────────────────
    memory_context, lc_history = await memory_service.get_context(
        session_id=session_id,
        user_query=body.message,
        org_id=org_id,
    )
    memory_used = bool(memory_context)
    sources: list[str] = []
    if lc_history:
        sources += ["redis", "postgresql"]
    if "semantic recall" in memory_context.lower():
        sources.append("qdrant")

    # ── 3. Run LangGraph supervisor ──────────────────────────────────────────
    initial_state = {
        "messages": lc_history + [HumanMessage(content=body.message)],
        "intent": "",
        "agent_id": "",
        "agent_name": "",
        "run_id": run_id,
        "org_id": org_id,
        "session_id": session_id,
        "tool_calls": [],
        "final_response": None,
        "memory_context": memory_context,
        "total_tokens": 0,
        "total_duration_ms": 0,
    }

    try:
        final_state = await supervisor_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"WorkspaceChat supervisor error: {e}")
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

    response_text = (
        final_state.get("final_response")
        or "I was unable to generate a response. Please try again."
    )
    tool_calls   = final_state.get("tool_calls", [])
    total_tokens = final_state.get("total_tokens", 0)
    duration_ms  = int((time.time() - start) * 1000)
    agent_name   = final_state.get("agent_name", "AI Agent")
    agent_id     = final_state.get("agent_id", "")
    intent       = final_state.get("intent", "")

    # ── 4. Persist assistant message ─────────────────────────────────────────
    asst_msg = WorkspaceChatMessage(
        id=str(uuid.uuid4()),
        org_id=org_id,
        chat_id=chat_id,
        session_id=session_id,
        role="assistant",
        content=response_text,
        agent_name=agent_name,
        agent_id=agent_id,
        intent=intent,
        run_id=run_id,
        tool_calls=tool_calls,
        memory_used=memory_used,
        memory_sources=list(set(sources)),
        tokens_used=total_tokens,
        duration_ms=duration_ms,
    )
    db.add(asst_msg)

    # ── 5. Update WorkspaceChat stats ────────────────────────────────────────
    preview = response_text[:280].replace("\n", " ")
    # Auto-title from first user message (only when it was "New Chat")
    if chat.title == "New Chat" and chat.message_count == 0:
        chat.title = body.message[:80]
    chat.message_count = (chat.message_count or 0) + 2
    chat.last_message_preview = preview
    chat.updated_at = datetime.utcnow()

    await db.commit()

    # ── 6. Persist turn in shared memory stores (Redis + SQL + Qdrant) ───────
    await memory_service.save_turn(
        session_id=session_id,
        org_id=org_id,
        user_message=body.message,
        ai_message=response_text,
        agent_name=agent_name,
        intent=intent,
        run_id=run_id,
        tool_calls=tool_calls,
        tokens_used=total_tokens,
        duration_ms=duration_ms,
    )

    # ── 7. Increment prompt usage counter ───────────────────────────────────
    await increment_prompt_usage(org_id, db)

    logger.info(
        f"WorkspaceChat: chat={chat_id} session={session_id} "
        f"intent={intent} agent={agent_name} tools={len(tool_calls)} "
        f"tokens={total_tokens} {duration_ms}ms"
    )

    return SendMessageResponse(
        message_id=asst_msg.id,
        chat_id=chat_id,
        response=response_text,
        agent=agent_name,
        agent_id=agent_id,
        intent=intent,
        tool_calls=tool_calls,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        timestamp=datetime.utcnow().isoformat(),
        memory_used=memory_used,
        sources=list(set(sources)),
    )


# ── Streaming message endpoint ────────────────────────────────────────────────

@router.post("/{chat_id}/messages/stream")
async def send_message_stream(
    chat_id: str,
    body: SendMessageRequest,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
    _sub: dict = Depends(require_prompt_quota),   # 402 if prompt limit hit
):
    """
    SSE streaming variant of send_message.
    Streams tokens as they are generated, then persists both turns to
    workspace_chats / workspace_messages tables after the stream ends.

    SSE event types:
      data: {"type":"agent",     "agent":"...", "agent_id":"...", "intent":"..."}
      data: {"type":"tool_call", "tool":"...",  "args":{},        "turn":0}
      data: {"type":"token",     "content":"..."}
      data: {"type":"done",      "chat_id":"...", "message_id":"...", ...}
      data: {"type":"error",     "message":"..."}
    """
    from app.models.models import WorkspaceChat, WorkspaceChatMessage
    from app.langgraph.streaming import stream_agent_response

    # Verify ownership & get chat
    chat_q = await db.execute(
        select(WorkspaceChat)
        .where(WorkspaceChat.id == chat_id, WorkspaceChat.org_id == org_id)
    )
    chat = chat_q.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    session_id = chat.session_id

    # Load memory before streaming
    memory_context, lc_history = await memory_service.get_context(
        session_id=session_id,
        user_query=body.message,
        org_id=org_id,
    )
    memory_used = bool(memory_context)
    sources: list[str] = []
    if lc_history:
        sources += ["redis", "postgresql"]
    if "semantic recall" in memory_context.lower():
        sources.append("qdrant")

    # Persist user message immediately (before streaming starts)
    user_msg_id = str(uuid.uuid4())
    user_msg = WorkspaceChatMessage(
        id=user_msg_id,
        org_id=org_id,
        chat_id=chat_id,
        session_id=session_id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    await db.commit()

    # Increment prompt counter before the generator starts
    # (we can't safely use db inside the async generator)
    await increment_prompt_usage(org_id, db)

    # Accumulated state (built from SSE events during streaming)
    acc: dict = {
        "final_text": "",
        "tool_calls": [],
        "total_tokens": 0,
        "duration_ms": 0,
        "agent_name": "AI Agent",
        "agent_id": "",
        "intent": "",
        "run_id": "",
        "asst_msg_id": str(uuid.uuid4()),
    }

    async def event_stream():
        asst_msg_id = acc["asst_msg_id"]

        try:
            async for chunk in stream_agent_response(
                message=body.message,
                session_id=session_id,
                org_id=org_id,
                memory_context=memory_context,
                lc_history=lc_history,
            ):
                yield chunk

                # Parse to build accumulated metadata
                if chunk.startswith("data: "):
                    try:
                        evt = json.loads(chunk[6:])
                        t = evt.get("type")
                        if t == "token":
                            acc["final_text"] += evt.get("content", "")
                        elif t == "agent":
                            acc["agent_name"] = evt.get("agent", "AI Agent")
                            acc["agent_id"]   = evt.get("agent_id", "")
                            acc["intent"]     = evt.get("intent", "")
                        elif t == "done":
                            acc["tool_calls"]   = evt.get("tool_calls", [])
                            acc["total_tokens"] = evt.get("total_tokens", 0)
                            acc["duration_ms"]  = evt.get("duration_ms", 0)
                            acc["run_id"]       = evt.get("run_id", "")
                    except Exception:
                        pass

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"
            return

        # ── Persist assistant message after stream ends ────────────────────
        try:
            # Need a fresh DB session since we're in an async generator
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                asst_msg = WorkspaceChatMessage(
                    id=asst_msg_id,
                    org_id=org_id,
                    chat_id=chat_id,
                    session_id=session_id,
                    role="assistant",
                    content=acc["final_text"] or "No response generated.",
                    agent_name=acc["agent_name"],
                    agent_id=acc["agent_id"],
                    intent=acc["intent"],
                    run_id=acc["run_id"],
                    tool_calls=acc["tool_calls"],
                    memory_used=memory_used,
                    memory_sources=list(set(sources)),
                    tokens_used=acc["total_tokens"],
                    duration_ms=acc["duration_ms"],
                )
                session.add(asst_msg)

                # Update WorkspaceChat stats
                chat_upd = await session.execute(
                    select(WorkspaceChat).where(WorkspaceChat.id == chat_id)
                )
                chat_obj = chat_upd.scalar_one_or_none()
                if chat_obj:
                    if chat_obj.title == "New Chat" and chat_obj.message_count == 0:
                        chat_obj.title = body.message[:80]
                    chat_obj.message_count = (chat_obj.message_count or 0) + 2
                    chat_obj.last_message_preview = (acc["final_text"] or "")[:280].replace("\n", " ")
                    chat_obj.updated_at = datetime.utcnow()

                await session.commit()

            # Persist to 3-tier memory
            await memory_service.save_turn(
                session_id=session_id,
                org_id=org_id,
                user_message=body.message,
                ai_message=acc["final_text"],
                agent_name=acc["agent_name"],
                intent=acc["intent"],
                run_id=acc["run_id"],
                tool_calls=acc["tool_calls"],
                tokens_used=acc["total_tokens"],
                duration_ms=acc["duration_ms"],
            )

            logger.info(
                f"WorkspaceStream: chat={chat_id} agent={acc['agent_name']} "
                f"tools={len(acc['tool_calls'])} tokens={acc['total_tokens']} "
                f"{acc['duration_ms']}ms"
            )

        except Exception as e:
            logger.error(f"WorkspaceStream post-persist error: {e}")

        # Emit enriched done event with workspace-specific fields
        yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id, 'message_id': asst_msg_id, 'agent': acc['agent_name'], 'agent_id': acc['agent_id'], 'intent': acc['intent'], 'tool_calls': acc['tool_calls'], 'total_tokens': acc['total_tokens'], 'duration_ms': acc['duration_ms'], 'memory_used': memory_used, 'sources': list(set(sources))})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
