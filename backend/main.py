"""
AFOS — AI Financial Operating System
FastAPI Backend — Main Application Entry Point
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from loguru import logger
import os

from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis_client import redis_client, cache
from app.core.vector_store import vector_store
from app.api.v1.router import api_router
from app.core.seed import seed_demo_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("🚀 Starting AFOS — AI Financial Operating System")

    # Create upload directory
    os.makedirs(settings.STORAGE_LOCAL_PATH, exist_ok=True)

    # Initialize database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables created")

    # Verify Redis
    redis_ok = await cache.ping()
    if redis_ok:
        logger.info("✅ Redis connected")
    else:
        logger.warning("⚠️  Redis unavailable — caching disabled")

    # Initialize Qdrant vector store (create collections)
    await vector_store.initialize()

    # Seed demo data if empty
    await seed_demo_data()
    logger.info("✅ Demo data seeded")

    yield

    # Cleanup
    await redis_client.aclose()
    await engine.dispose()
    logger.info("🛑 AFOS shutdown complete")


app = FastAPI(
    title="AFOS — AI Financial Operating System",
    description="Autonomous Financial Operating System API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for uploads (auto-create if missing)
import os as _os
_os.makedirs(settings.STORAGE_LOCAL_PATH, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.STORAGE_LOCAL_PATH), name="uploads")

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    redis_ok = await cache.ping()
    qdrant_ok = await vector_store.ping()
    return {
        "status": "healthy",
        "service": "AFOS API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "services": {
            "redis": "connected" if redis_ok else "unavailable",
            "qdrant": "connected" if qdrant_ok else "unavailable",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
