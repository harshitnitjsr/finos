"""
AFOS Memory Service — 3-tier RAG memory for the chatbot.

Tier 1 — Redis:  Short-term session buffer (last 20 msgs, 24h TTL, O(1) access)
Tier 2 — SQL:    Long-term persistent store (every turn, queryable, auditable)
Tier 3 — Qdrant: Semantic long-term recall (embeddings of past turns, vector search)

Usage:
    context = await memory_service.get_context(session_id, user_query, org_id)
    # inject context string into agent system prompt
    await memory_service.save_turn(session_id, user_msg, ai_msg, metadata, org_id)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from loguru import logger


# ── Embedding helper ──────────────────────────────────────────────────────────

async def _embed(text: str) -> list[float] | None:
    """
    Embed text for semantic memory (Qdrant).
    Uses DO Inference Hub (bge-m3) when DO_INFERENCE_API_KEY is set,
    otherwise falls back to OpenAI text-embedding-3-small.
    """
    try:
        from openai import AsyncOpenAI
        from app.core.config import settings
        if settings.DO_INFERENCE_API_KEY:
            client = AsyncOpenAI(
                api_key=settings.DO_INFERENCE_API_KEY,
                base_url=settings.DO_INFERENCE_BASE_URL,
            )
            model = "bge-m3"
        else:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            model = "text-embedding-3-small"
        resp = await client.embeddings.create(input=text[:8000], model=model)
        return resp.data[0].embedding
    except Exception as e:
        logger.warning(f"Memory embed failed: {e}")
        return None


# ── Redis memory helpers ──────────────────────────────────────────────────────

_REDIS_NS = "afos:memory:session"
_REDIS_TTL = 86400  # 24 hours
_MAX_REDIS_MSGS = 20  # keep last 20 messages per session


async def _redis_append(session_id: str, org_id: str, message: dict) -> None:
    """Push a message to the Redis session list (LPUSH + LTRIM)."""
    import json
    from app.core.redis_client import redis_client
    key = f"{_REDIS_NS}:{org_id}:{session_id}"
    try:
        await redis_client.lpush(key, json.dumps(message, default=str))
        await redis_client.ltrim(key, 0, _MAX_REDIS_MSGS - 1)
        await redis_client.expire(key, _REDIS_TTL)
    except Exception as e:
        logger.warning(f"Redis memory append failed: {e}")


async def _redis_load(session_id: str, org_id: str, limit: int = 10) -> list[dict]:
    """Load last `limit` messages from Redis (LRANGE — newest first, so reverse)."""
    import json
    from app.core.redis_client import redis_client
    key = f"{_REDIS_NS}:{org_id}:{session_id}"
    try:
        raw_list = await redis_client.lrange(key, 0, limit - 1)
        msgs = []
        for raw in reversed(raw_list):  # reverse → chronological order
            try:
                msgs.append(json.loads(raw))
            except Exception:
                pass
        return msgs
    except Exception as e:
        logger.warning(f"Redis memory load failed: {e}")
        return []


async def _redis_clear(session_id: str, org_id: str) -> None:
    from app.core.redis_client import redis_client
    key = f"{_REDIS_NS}:{org_id}:{session_id}"
    try:
        await redis_client.delete(key)
    except Exception:
        pass


# ── SQL memory helpers ────────────────────────────────────────────────────────

async def _sql_save(
    session_id: str,
    org_id: str,
    role: str,
    content: str,
    *,
    agent_name: str = "",
    intent: str = "",
    run_id: str = "",
    tool_calls: list = None,
    tokens_used: int = 0,
    duration_ms: int = 0,
    qdrant_indexed: bool = False,
) -> str:
    """Insert a ConversationMessage row. Returns the new row ID."""
    from app.core.database import AsyncSessionLocal
    from app.models.models import ConversationMessage
    msg_id = str(uuid.uuid4())
    try:
        async with AsyncSessionLocal() as db:
            row = ConversationMessage(
                id=msg_id,
                org_id=org_id,
                session_id=session_id,
                role=role,
                content=content,
                agent_name=agent_name or None,
                intent=intent or None,
                run_id=run_id or None,
                tool_calls=tool_calls or [],
                tokens_used=tokens_used,
                duration_ms=duration_ms,
                qdrant_indexed=qdrant_indexed,
            )
            db.add(row)
            await db.commit()
    except Exception as e:
        logger.warning(f"SQL memory save failed: {e}")
    return msg_id


async def _sql_load_recent(session_id: str, org_id: str, limit: int = 8) -> list[dict]:
    """Load most recent messages for a session from SQL (fallback if Redis miss)."""
    from app.core.database import AsyncSessionLocal
    from app.models.models import ConversationMessage
    from sqlalchemy import select, desc
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ConversationMessage)
                .where(ConversationMessage.org_id == org_id,
                       ConversationMessage.session_id == session_id)
                .order_by(desc(ConversationMessage.created_at))
                .limit(limit)
            )
            rows = result.scalars().all()
            return [
                {
                    "role": r.role,
                    "content": r.content,
                    "agent_name": r.agent_name,
                    "intent": r.intent,
                    "created_at": r.created_at.isoformat(),
                }
                for r in reversed(rows)   # chronological order
            ]
    except Exception as e:
        logger.warning(f"SQL memory load failed: {e}")
        return []


# ── Context builder ───────────────────────────────────────────────────────────

def _format_context(
    recent: list[dict],
    semantic_hits: list[dict],
) -> str:
    """
    Build the memory context string to inject into the agent system prompt.
    Format is deliberately concise to minimize token usage.
    """
    parts: list[str] = []

    if recent:
        parts.append("=== CONVERSATION HISTORY (this session) ===")
        for m in recent[-6:]:   # last 6 messages for brevity
            role_label = "User" if m["role"] == "user" else f"Assistant ({m.get('agent_name', 'AI')})"
            content = m["content"][:400]
            parts.append(f"{role_label}: {content}")
        parts.append("")

    if semantic_hits:
        parts.append("=== RELEVANT PAST CONVERSATIONS (semantic recall) ===")
        for hit in semantic_hits[:3]:
            role_label = "User" if hit["role"] == "user" else f"Assistant ({hit.get('agent_name', 'AI')})"
            content = (hit.get("content") or "")[:300]
            score = hit.get("score", 0)
            parts.append(f"[similarity={score}] {role_label}: {content}")
        parts.append("")

    if not parts:
        return ""

    return "\n".join(parts)


# ── Public API ────────────────────────────────────────────────────────────────

class MemoryService:
    """
    Unified 3-tier memory service for AFOS chatbot.
    Coordinates Redis (hot), SQL (persistent), and Qdrant (semantic).
    """

    async def get_context(
        self,
        session_id: str,
        user_query: str,
        org_id: str,
    ) -> tuple[str, list[dict]]:
        """
        Build enriched memory context for the current query.

        Returns:
            (context_string, lc_history_messages)
            context_string → injected into agent system prompt
            lc_history_messages → LangChain HumanMessage/AIMessage list for conversation
        """
        # 1. Load recent messages (Redis first, SQL fallback)
        recent = await _redis_load(session_id, org_id, limit=10)
        if not recent:
            recent = await _sql_load_recent(session_id, org_id, limit=8)
            # Warm Redis from SQL
            for msg in recent:
                await _redis_append(session_id, org_id, msg)

        # 2. Embed the user query for semantic search
        semantic_hits: list[dict] = []
        query_embedding = await _embed(user_query)
        if query_embedding:
            from app.core.vector_store import vector_store
            semantic_hits = await vector_store.search_similar_turns(
                embedding=query_embedding,
                org_id=org_id,
                limit=4,
                threshold=0.72,
                exclude_session=session_id,  # skip current session (already in recent)
            )

        # 3. Build context string
        context = _format_context(recent, semantic_hits)

        # 4. Build LangChain message list from recent
        from langchain_core.messages import HumanMessage, AIMessage
        lc_msgs = []
        for m in recent[-8:]:
            if m["role"] == "user":
                lc_msgs.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                lc_msgs.append(AIMessage(content=m["content"]))

        logger.debug(
            f"Memory: session={session_id} recent={len(recent)} "
            f"semantic_hits={len(semantic_hits)} context_len={len(context)}"
        )
        return context, lc_msgs

    async def save_turn(
        self,
        session_id: str,
        org_id: str,
        *,
        user_message: str,
        ai_message: str,
        agent_name: str = "",
        intent: str = "",
        run_id: str = "",
        tool_calls: list = None,
        tokens_used: int = 0,
        duration_ms: int = 0,
    ) -> None:
        """
        Persist a completed conversation turn to all 3 memory stores.
        All writes are async fire-and-forget to avoid blocking the response.
        """
        import asyncio

        now = datetime.utcnow().isoformat()
        user_msg_dict = {"role": "user", "content": user_message, "created_at": now}
        asst_msg_dict = {
            "role": "assistant",
            "content": ai_message,
            "agent_name": agent_name,
            "intent": intent,
            "created_at": now,
        }

        # ── Redis (always fast) ──
        await _redis_append(session_id, org_id, user_msg_dict)
        await _redis_append(session_id, org_id, asst_msg_dict)

        # ── SQL + Qdrant (schedule as tasks) ──
        asyncio.get_event_loop().create_task(
            self._persist_to_sql_and_qdrant(
                session_id=session_id,
                org_id=org_id,
                user_message=user_message,
                ai_message=ai_message,
                agent_name=agent_name,
                intent=intent,
                run_id=run_id,
                tool_calls=tool_calls or [],
                tokens_used=tokens_used,
                duration_ms=duration_ms,
                now=now,
            )
        )

    async def _persist_to_sql_and_qdrant(
        self,
        *,
        session_id: str,
        org_id: str,
        user_message: str,
        ai_message: str,
        agent_name: str,
        intent: str,
        run_id: str,
        tool_calls: list,
        tokens_used: int,
        duration_ms: int,
        now: str,
    ) -> None:
        """Background task: write to SQL then embed + upsert to Qdrant."""
        from app.core.vector_store import vector_store

        # SQL: user message
        user_id = await _sql_save(
            session_id, org_id, "user", user_message
        )

        # SQL: assistant message
        asst_id = await _sql_save(
            session_id, org_id, "assistant", ai_message,
            agent_name=agent_name,
            intent=intent,
            run_id=run_id,
            tool_calls=tool_calls,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )

        # Qdrant: embed combined turn text (question + answer)
        combined = f"User: {user_message}\nAssistant ({agent_name}): {ai_message}"
        embedding = await _embed(combined)
        if embedding:
            # Upsert user turn
            await vector_store.upsert_conversation_turn(
                turn_id=user_id,
                embedding=embedding,
                payload={
                    "org_id": org_id,
                    "session_id": session_id,
                    "role": "user",
                    "content": user_message,
                    "agent_name": "",
                    "intent": intent,
                    "created_at": now,
                },
            )
            # Upsert assistant turn (richer payload)
            await vector_store.upsert_conversation_turn(
                turn_id=asst_id,
                embedding=embedding,
                payload={
                    "org_id": org_id,
                    "session_id": session_id,
                    "role": "assistant",
                    "content": ai_message,
                    "agent_name": agent_name,
                    "intent": intent,
                    "created_at": now,
                },
            )
            logger.debug(f"Memory: Qdrant indexed turn {asst_id[:8]}... for session {session_id}")

    async def clear_session(self, session_id: str, org_id: str) -> None:
        """Clear Redis session memory (SQL/Qdrant data is retained for audit)."""
        await _redis_clear(session_id, org_id)

    async def get_session_history(
        self, session_id: str, org_id: str, limit: int = 50
    ) -> list[dict]:
        """Load full session history from SQL (authoritative source)."""
        return await _sql_load_recent(session_id, org_id, limit=limit)


# Singleton
memory_service = MemoryService()
