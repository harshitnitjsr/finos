"""
AFOS Streaming Response Engine
───────────────────────────────
Runs the same classify_intent → agent pipeline as the supervisor graph
but streams the final LLM response token-by-token via SSE.

SSE event types emitted (newline-delimited, each prefixed with "data: "):
  {"type": "agent",     "agent": "...", "agent_id": "...", "intent": "..."}
  {"type": "tool_call", "tool": "...",  "args": {...},     "turn": 0}
  {"type": "token",     "content": "..."}
  {"type": "done",      "session_id":"...", "total_tokens":0,
                         "duration_ms":0, "memory_used":true, "sources":[...]}
  {"type": "error",     "message": "..."}

Design notes:
- classify_intent uses llama3.3-70b-instruct on DO Tier 1 (gpt-4o-mini when OpenAI direct)
- Agent tool-calls are NOT streamed (they hit live DB; emit a tool_call event each)
- Only the FINAL LLM response (synthesis turn after all tools complete) is streamed
- Everything after streaming ends is saved via memory_service.save_turn() as normal
"""
from __future__ import annotations

import json
import time
import uuid
from typing import AsyncGenerator

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from app.langgraph.supervisor import AGENT_REGISTRY, INTENT_TO_AGENT, CLASSIFY_PROMPT, _make_llm
from app.core.config import settings
from app.core.prompt_guard import scan as guard_scan, wrap_user_message, sanitise_tool_output, build_hardened_system_prompt
from app.langgraph.tool_logger import call_tool_with_logging
from app.core.redis_client import cache as _cache


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


async def stream_agent_response(
    *,
    message: str,
    session_id: str,
    org_id: str,
    memory_context: str,
    lc_history: list,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE strings.
    Caller wraps this in a FastAPI StreamingResponse.
    """
    from app.core.context import org_id_var
    org_id_var.set(org_id)

    run_id = str(uuid.uuid4())
    start = time.time()
    total_tokens = 0

    # ── 0. Prompt injection guard on raw user message ────────────────────────
    guard_result = guard_scan(message)
    if guard_result.flagged:
        logger.warning(
            f"PromptGuard: threats={guard_result.threats} org={org_id} "
            f"session={session_id} msg_preview={message[:80]!r}"
        )
    # Use sanitised text for all LLM calls; wrap in XML tags to enforce boundary
    safe_message = wrap_user_message(guard_result.text)

    # ── 1. Classify intent (non-streamed, fast) ──────────────────────────────
    try:
        classifier_llm = _make_llm("gpt-4o-mini", temperature=0)
        classification = await classifier_llm.ainvoke([
            SystemMessage(content=CLASSIFY_PROMPT),
            HumanMessage(content=safe_message),
        ])
        intent = classification.content.strip().lower()
        if intent not in INTENT_TO_AGENT:
            intent = "general_finance"
    except Exception as e:
        logger.error(f"Streaming: intent classification failed: {e}")
        intent = "general_finance"

    agent_key = INTENT_TO_AGENT[intent]
    cfg = AGENT_REGISTRY[agent_key]
    agent_id = cfg["id"]
    agent_name = cfg["name"]

    # ── Store initial reasoning context in Redis (5min TTL) ───────────────
    await _cache.set_reasoning_context(run_id, {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "intent": intent,
        "org_id": org_id,
        "session_id": session_id,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
        "tool_calls": [],
        "status": "running",
    })

    # Emit agent metadata so the UI can show "Expense Intelligence · expense_query"
    yield _sse({"type": "agent", "agent": agent_name, "agent_id": agent_id, "intent": intent, "run_id": run_id})

    # ── 2. Set up agent tools ─────────────────────────────────────────────────
    raw_tools = cfg["tools"]
    tool_map = {t.name: t for t in raw_tools}

    # Harden system prompt with injection-resistance preamble
    system_text = build_hardened_system_prompt(cfg["system"])
    if memory_context:
        system_text = f"{system_text}\n\n{memory_context}"

    system = SystemMessage(content=system_text)
    conversation = [system] + list(lc_history) + [HumanMessage(content=safe_message)]

    tool_call_records: list[dict] = []
    final_text = ""

    # LLM for tool-calling turns - routed via DO Inference Hub when key is set
    tool_llm = _make_llm("gpt-4o", temperature=0.3).bind_tools(raw_tools)

    # LLM for final streaming synthesis - routed via DO Inference Hub
    stream_llm = _make_llm("gpt-4o", temperature=0.3)

    # ── 3. Agentic tool-calling loop (non-streamed) ───────────────────────────
    MAX_TURNS = 6
    try:
        for turn in range(MAX_TURNS):
            response = await tool_llm.ainvoke(conversation)

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                total_tokens += response.usage_metadata.get("total_tokens", 0)

            conversation.append(response)

            # No tool calls → this is the final answer; stream it instead
            if not response.tool_calls:
                # Pop the non-streamed final answer and re-generate via stream
                conversation.pop()  # remove the non-streamed AIMessage
                break

            # Execute each tool
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})
                tool_id = tc.get("id", str(uuid.uuid4()))

                record = {"tool": tool_name, "args": tool_args, "turn": turn}
                tool_call_records.append(record)
                yield _sse({"type": "tool_call", **record})

                # ── Update reasoning context with live tool progress ─────────
                await _cache.set_reasoning_context(run_id, {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "intent": intent,
                    "org_id": org_id,
                    "session_id": session_id,
                    "status": "calling_tool",
                    "current_tool": tool_name,
                    "current_turn": turn,
                    "tool_calls": tool_call_records,
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
                        raw_str = json.dumps(raw_result, default=str)[:4000]
                        # Sanitise tool output (indirect injection from DB/OCR data)
                        tool_result_content = sanitise_tool_output(tool_name, raw_str)
                    except Exception as exc:
                        tool_result_content = f"Tool error: {exc}"
                        logger.error(f"Streaming tool {tool_name} failed: {exc}")

                conversation.append(ToolMessage(
                    content=tool_result_content,
                    tool_call_id=tool_id,
                    name=tool_name,
                ))

        # ── 4. Stream final synthesis ─────────────────────────────────────────
        # conversation now ends with the last ToolMessage (or the user message
        # if no tools were called). Ask the stream_llm to synthesize.
        async for chunk in stream_llm.astream(conversation):
            if hasattr(chunk, "content") and chunk.content:
                token_text = chunk.content if isinstance(chunk.content, str) else ""
                if token_text:
                    final_text += token_text
                    yield _sse({"type": "token", "content": token_text})
            # accumulate usage if available in final chunk
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                total_tokens += chunk.usage_metadata.get("total_tokens", 0)

    except Exception as e:
        logger.error(f"Streaming agent error: {e}")
        yield _sse({"type": "error", "message": str(e)[:300]})
        return

    duration_ms = int((time.time() - start) * 1000)

    logger.info(
        f"Stream: {agent_name} intent={intent} tools={len(tool_call_records)} "
        f"tokens={total_tokens} {duration_ms}ms session={session_id}"
    )

    # ── 5. Emit done event with full metadata ─────────────────────────────────
    yield _sse({
        "type": "done",
        "session_id": session_id,
        "run_id": run_id,
        "agent": agent_name,
        "agent_id": agent_id,
        "intent": intent,
        "tool_calls": tool_call_records,
        "total_tokens": total_tokens,
        "duration_ms": duration_ms,
    })

    # ── 6. Mark reasoning context done and schedule cleanup ────────────────
    await _cache.set_reasoning_context(run_id, {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "intent": intent,
        "org_id": org_id,
        "session_id": session_id,
        "status": "done",
        "tool_calls": tool_call_records,
        "total_tokens": total_tokens,
        "duration_ms": duration_ms,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    import asyncio
    asyncio.get_event_loop().call_later(2, lambda: asyncio.ensure_future(
        _cache.clear_reasoning_context(run_id)
    ))
