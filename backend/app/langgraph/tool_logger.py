"""
Tool Logger — logs every LangChain tool invocation to agent_tool_logs.

DESIGN: Instead of hooking _arun (which breaks with LangChain 0.3's
StructuredTool config kwarg requirement), we expose call_tool_with_logging()
which calls the tool's underlying coroutine directly and wraps it with timing.
"""
from __future__ import annotations
import time
import uuid
import json
from typing import Any
from loguru import logger
from langchain_core.tools import BaseTool


def _safe_json(obj: Any) -> dict:
    """Convert any value to a safe JSON-serializable dict."""
    try:
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, str):
            return {"result": obj}
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return {"result": str(obj)[:1000]}


async def _write_tool_log(
    *,
    org_id: str,
    agent_id: str,
    agent_name: str,
    run_id: str,
    tool_name: str,
    tool_description: str,
    input_data: dict,
    output_data: dict,
    duration_ms: int,
    status: str,
    error: str | None = None,
) -> None:
    """Persist a tool call record to agent_tool_logs table."""
    from app.core.database import AsyncSessionLocal
    from app.models.models import AgentToolLog

    input_summary = str(input_data)[:450]
    output_summary = str(output_data)[:450]

    try:
        async with AsyncSessionLocal() as db:
            record = AgentToolLog(
                id=str(uuid.uuid4()),
                org_id=org_id,
                agent_id=agent_id,
                agent_name=agent_name,
                run_id=run_id,
                tool_name=tool_name,
                tool_description=(tool_description or "")[:500],
                input_data=input_data,
                output_data=output_data,
                input_summary=input_summary,
                output_summary=output_summary,
                duration_ms=duration_ms,
                status=status,
                error=error,
            )
            db.add(record)
            await db.commit()
            logger.debug(f"ToolLog [{status}] {tool_name} -> {duration_ms}ms")
    except Exception as e:
        logger.warning(f"ToolLogger: failed to persist [{tool_name}]: {e}")


async def call_tool_with_logging(
    tool: BaseTool,
    tool_args: dict,
    *,
    agent_id: str,
    agent_name: str,
    run_id: str,
    org_id: str,
) -> Any:
    """
    Call a LangChain StructuredTool's underlying coroutine directly,
    bypassing the arun/config kwarg chain that breaks in LangChain 0.3.
    Logs the invocation (input, output, duration, status) to agent_tool_logs.

    Returns the raw tool result (dict/str).
    """
    tool_name = tool.name
    tool_desc = tool.description or ""

    start = time.perf_counter()
    status = "success"
    error_msg: str | None = None
    result: Any = None

    input_data = _safe_json({k: str(v)[:300] for k, v in tool_args.items()})

    try:
        # Use the coroutine directly — avoids LangChain's arun/config chain
        if hasattr(tool, "coroutine") and tool.coroutine is not None:
            result = await tool.coroutine(**tool_args)
        elif hasattr(tool, "afunc"):
            result = await tool.afunc(**tool_args)
        else:
            # Fallback: call via invoke (sync tools)
            import asyncio
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: tool.run(tool_args)
            )
        return result

    except Exception as exc:
        status = "error"
        error_msg = str(exc)[:500]
        logger.error(f"Tool {tool_name} raised: {exc}")
        raise

    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        output_data = _safe_json(result) if result is not None else {}

        import asyncio
        try:
            asyncio.get_event_loop().create_task(_write_tool_log(
                org_id=org_id,
                agent_id=agent_id,
                agent_name=agent_name,
                run_id=run_id,
                tool_name=tool_name,
                tool_description=tool_desc,
                input_data=input_data,
                output_data=output_data,
                duration_ms=duration_ms,
                status=status,
                error=error_msg,
            ))
        except RuntimeError:
            pass  # No event loop in test context
