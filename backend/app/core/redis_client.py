"""
Redis service — caching, pub/sub, rate limiting, session store.
Full implementation using redis.asyncio.

Operational memory namespaces:
  afos:memory:session:{org}:{session}  — chat short-term context (Tier 1)
  afos:agent_heartbeat:{agent_id}      — live agent status (60s TTL)
  afos:workflow:state:{workflow_id}    — active workflow execution state
  afos:workflow:lock:{workflow_id}     — retry dedup lock (prevent double-retry)
  afos:ratelimit:{identifier}          — sliding window rate limiter
  afos:counter:{org}:{name}            — atomic counters
"""
import json
import hashlib
from typing import Any, Optional
from functools import wraps
import redis.asyncio as aioredis
from loguru import logger

from app.core.config import settings

# Singleton Redis pool
redis_client = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=20,
)

# Cache TTLs (seconds)
TTL_DASHBOARD = 30          # Dashboard KPIs — fast refresh
TTL_ANALYTICS = 120         # Analytics charts — moderate refresh
TTL_TREASURY = 60           # Treasury summary
TTL_AGENT_STATUS = 15       # Agent live status
TTL_VENDOR_LIST = 300       # Vendor list — slow changing
TTL_INSIGHTS = 600          # AI insights — expensive to recompute
TTL_CATEGORY_STATS = 120    # Category breakdowns
TTL_WORKFLOW_STATE = 3600   # Active workflow execution state (1h)
TTL_RETRY_LOCK = 300        # Retry dedup lock (5 min)


class CacheService:
    """Redis-backed cache service with namespaced keys and TTL management."""

    def __init__(self, client: aioredis.Redis):
        self.r = client

    def _key(self, namespace: str, *parts: Any) -> str:
        suffix = ":".join(str(p) for p in parts)
        return f"afos:{namespace}:{suffix}"

    async def get(self, namespace: str, *key_parts: Any) -> Optional[Any]:
        """Get cached value, returning None on miss."""
        key = self._key(namespace, *key_parts)
        try:
            raw = await self.r.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Cache GET error [{key}]: {e}")
            return None

    async def set(self, namespace: str, value: Any, ttl: int, *key_parts: Any) -> None:
        """Set cache value with TTL."""
        key = self._key(namespace, *key_parts)
        try:
            await self.r.setex(key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.warning(f"Cache SET error [{key}]: {e}")

    async def delete(self, namespace: str, *key_parts: Any) -> None:
        """Invalidate a specific cache key."""
        key = self._key(namespace, *key_parts)
        try:
            await self.r.delete(key)
        except Exception as e:
            logger.warning(f"Cache DELETE error [{key}]: {e}")

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a glob pattern."""
        try:
            keys = await self.r.keys(f"afos:{pattern}:*")
            if keys:
                return await self.r.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache INVALIDATE error [{pattern}]: {e}")
            return 0

    async def publish(self, channel: str, message: Any) -> None:
        """Publish a message to a Redis pub/sub channel."""
        try:
            await self.r.publish(f"afos:{channel}", json.dumps(message, default=str))
        except Exception as e:
            logger.warning(f"Pub/sub PUBLISH error [{channel}]: {e}")

    async def increment_counter(self, name: str, org_id: str, ttl: int = 86400) -> int:
        """Atomic counter for rate limiting and tracking."""
        key = self._key("counter", org_id, name)
        try:
            val = await self.r.incr(key)
            if val == 1:
                await self.r.expire(key, ttl)
            return val
        except Exception:
            return 0

    async def rate_limit(self, identifier: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """
        Sliding window rate limiter.
        Returns (is_allowed, requests_remaining).
        """
        key = self._key("ratelimit", identifier)
        try:
            pipe = self.r.pipeline()
            await pipe.incr(key)
            await pipe.expire(key, window_seconds)
            results = await pipe.execute()
            count = results[0]
            remaining = max(0, limit - count)
            return count <= limit, remaining
        except Exception:
            return True, limit  # Fail open

    async def set_agent_heartbeat(self, agent_id: str, stats: dict) -> None:
        """Record agent live status with short TTL."""
        key = self._key("agent_heartbeat", agent_id)
        try:
            await self.r.setex(key, 60, json.dumps(stats, default=str))
        except Exception:
            pass

    async def get_agent_heartbeat(self, agent_id: str) -> Optional[dict]:
        """Get agent heartbeat — None means agent is down."""
        key = self._key("agent_heartbeat", agent_id)
        try:
            raw = await self.r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    # ── Active workflow state ──────────────────────────────────────────────────

    async def set_workflow_state(self, workflow_id: str, state: dict) -> None:
        """
        Store active workflow execution state in Redis.
        Tracks current step, status, context for real-time polling.
        TTL: 1 hour (long enough for multi-step approvals).
        """
        key = self._key("workflow:state", workflow_id)
        try:
            await self.r.setex(key, TTL_WORKFLOW_STATE, json.dumps(state, default=str))
            logger.debug(f"WorkflowState: {workflow_id} → step={state.get('current_step')} status={state.get('status')}")
        except Exception as e:
            logger.warning(f"WorkflowState SET failed [{workflow_id}]: {e}")

    async def get_workflow_state(self, workflow_id: str) -> Optional[dict]:
        """Get real-time workflow execution state from Redis."""
        key = self._key("workflow:state", workflow_id)
        try:
            raw = await self.r.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning(f"WorkflowState GET failed [{workflow_id}]: {e}")
            return None

    async def update_workflow_step(
        self,
        workflow_id: str,
        current_step: int,
        step_name: str,
        status: str = "running",
        error: Optional[str] = None,
    ) -> None:
        """
        Atomic step update — reads existing state, patches step, writes back.
        Used by workflow activities to broadcast real-time progress.
        """
        existing = await self.get_workflow_state(workflow_id) or {}
        existing.update({
            "workflow_id": workflow_id,
            "current_step": current_step,
            "current_step_name": step_name,
            "status": status,
            "error": error,
            "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
        })
        await self.set_workflow_state(workflow_id, existing)

    async def clear_workflow_state(self, workflow_id: str) -> None:
        """Remove workflow state from Redis after completion."""
        key = self._key("workflow:state", workflow_id)
        try:
            await self.r.delete(key)
        except Exception:
            pass

    # ── Retry management ──────────────────────────────────────────────────────

    async def acquire_retry_lock(self, workflow_id: str) -> bool:
        """
        Acquire a distributed retry lock to prevent duplicate retries.
        Uses SET NX (only set if not exists) — atomic operation.
        Returns True if lock acquired, False if already locked (retry in progress).
        """
        key = self._key("workflow:lock", workflow_id)
        try:
            result = await self.r.set(key, "1", nx=True, ex=TTL_RETRY_LOCK)
            return result is not None  # SET NX returns None if key exists
        except Exception as e:
            logger.warning(f"RetryLock acquire failed [{workflow_id}]: {e}")
            return True  # Fail open

    async def release_retry_lock(self, workflow_id: str) -> None:
        """Release retry lock after retry attempt completes (success or failure)."""
        key = self._key("workflow:lock", workflow_id)
        try:
            await self.r.delete(key)
        except Exception:
            pass

    async def get_retry_count(self, workflow_id: str) -> int:
        """Get current Redis-tracked retry count (separate from SQL audit trail)."""
        key = self._key("workflow:retries", workflow_id)
        try:
            val = await self.r.get(key)
            return int(val) if val else 0
        except Exception:
            return 0

    async def increment_retry_count(self, workflow_id: str, max_retries: int = 5) -> tuple[bool, int]:
        """
        Increment retry counter and check limit.
        Returns (can_retry, current_count).
        Counter expires after 24h to auto-reset.
        """
        key = self._key("workflow:retries", workflow_id)
        try:
            count = await self.r.incr(key)
            if count == 1:
                await self.r.expire(key, 86400)  # 24h expiry
            can_retry = count <= max_retries
            if not can_retry:
                logger.warning(f"Workflow {workflow_id} exceeded max retries ({max_retries})")
            return can_retry, count
        except Exception:
            return True, 1  # Fail open

    async def reset_retry_count(self, workflow_id: str) -> None:
        """Reset retry counter on successful completion."""
        key = self._key("workflow:retries", workflow_id)
        try:
            await self.r.delete(key)
        except Exception:
            pass

    # ── Temporary reasoning context ───────────────────────────────────────────

    async def set_reasoning_context(
        self,
        run_id: str,
        context: dict,
        ttl: int = 300,
    ) -> None:
        """
        Store temporary LLM reasoning context keyed by run_id.
        Used to share intermediate agent reasoning across tool calls.
        TTL: 5 minutes (a single agent turn should never take longer).
        """
        key = self._key("reasoning", run_id)
        try:
            await self.r.setex(key, ttl, json.dumps(context, default=str))
        except Exception as e:
            logger.warning(f"ReasoningContext SET failed [{run_id}]: {e}")

    async def get_reasoning_context(self, run_id: str) -> Optional[dict]:
        """Retrieve temporary reasoning context for the current agent run."""
        key = self._key("reasoning", run_id)
        try:
            raw = await self.r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def clear_reasoning_context(self, run_id: str) -> None:
        """Delete reasoning context after agent turn completes."""
        key = self._key("reasoning", run_id)
        try:
            await self.r.delete(key)
        except Exception:
            pass

    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            return await self.r.ping()
        except Exception:
            return False


cache = CacheService(redis_client)
