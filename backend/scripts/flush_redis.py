import asyncio
import os
from dotenv import load_dotenv

# Load .env from backend directory
load_dotenv("backend/.env")

from app.core.redis_client import redis_client

async def flush_redis():
    print(f"Connecting to Redis at {os.getenv('REDIS_URL')}...")
    # Re-initialize client if URL changed in env
    from app.core.config import settings
    print(f"Settings REDIS_URL: {settings.REDIS_URL}")
    
    await redis_client.flushall()
    print("Redis flushed successfully.")

if __name__ == "__main__":
    asyncio.run(flush_redis())
