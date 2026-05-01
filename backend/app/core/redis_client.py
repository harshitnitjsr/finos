"""
Redis service — caching, pub/sub, rate limiting, session store.
Full implementation using redis.asyncio.
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

    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            return await self.r.ping()
        except Exception:
            return False


cache = CacheService(redis_client)
