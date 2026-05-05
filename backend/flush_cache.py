import asyncio
from app.core.redis_client import cache

async def flush():
    await cache.invalidate_pattern("vendors")
    await cache.invalidate_pattern("dashboard")
    await cache.invalidate_pattern("analytics")
    print("Cache cleared for vendors, dashboard, analytics.")

if __name__ == "__main__":
    asyncio.run(flush())
