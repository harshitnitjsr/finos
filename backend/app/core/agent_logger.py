"""
Agent Logger — writes every AI agent invocation to the agent_logs table.
Also updates the Redis heartbeat for live agent status.
"""
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Any
from loguru import logger as _logger

from app.core.redis_client import cache


async def write_agent_log(
    *,
    agent_id: str,
    agent_name: str,
    action: str,
    status: str = "success",
    model_used: Optional[str] = None,
    tokens_used: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    duration_ms: int = 0,
    input_summary: Optional[str] = None,
    output_summary: Optional[str] = None,
    input_data: Optional[dict] = None,
    output_data: Optional[dict] = None,
    confidence: float = 0.0,
    error: Optional[str] = None,
    org_id: str = "org_demo_001",
) -> None:
    """Write an agent log entry to the database and update the Redis heartbeat."""
    from app.core.database import AsyncSessionLocal
    from app.models.models import AgentLog

    try:
        async with AsyncSessionLocal() as db:
            log = AgentLog(
                id=str(uuid.uuid4()),
                org_id=org_id,
                agent_id=agent_id,
                agent_name=agent_name,
                action=action,
                status=status,
                model_used=model_used,
                tokens_used=tokens_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=duration_ms,
                input_summary=input_summary,
                output_summary=output_summary,
                input_data=input_data or {},
                output_data=output_data or {},
                confidence=confidence,
                error=error,
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        _logger.warning(f"AgentLogger: failed to write log for {agent_id}: {e}")

    # Update Redis heartbeat so agent shows as "active"
    try:
        from datetime import datetime
        await cache.set_agent_heartbeat(agent_id, {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "last_action": action,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        _logger.warning(f"AgentLogger: heartbeat update failed for {agent_id}: {e}")


class AgentTimer:
    """Context manager that times execution and auto-logs to agent_logs."""

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        action: str,
        org_id: str = "org_demo_001",
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.action = action
        self.org_id = org_id
        self._start: float = 0
        self.model_used: Optional[str] = None
        self.tokens_used: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.confidence: float = 0.0
        self.input_summary: Optional[str] = None
        self.output_summary: Optional[str] = None
        self.input_data: dict = {}
        self.output_data: dict = {}

    async def __aenter__(self):
        self._start = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self._start) * 1000)
        status = "success" if exc_type is None else "failed"
        error = str(exc_val) if exc_val else None

        await write_agent_log(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            action=self.action,
            status=status,
            model_used=self.model_used,
            tokens_used=self.tokens_used,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            duration_ms=duration_ms,
            input_summary=self.input_summary,
            output_summary=self.output_summary,
            input_data=self.input_data,
            output_data=self.output_data,
            confidence=self.confidence,
            error=error,
            org_id=self.org_id,
        )
        return False  # Don't suppress exceptions
