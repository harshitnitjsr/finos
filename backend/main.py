"""
AFOS — AI Financial Operating System
FastAPI Backend — Main Application Entry Point
"""
import asyncio
import hmac
import hashlib
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import os

from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis_client import redis_client, cache
from app.core.vector_store import vector_store
from app.core.temporal import temporal_manager
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

    # Initialize Temporal Client
    try:
        await temporal_manager.connect()
        logger.info("✅ Temporal client connected")
    except Exception as e:
        logger.error(f"⚠️ Temporal connection failed (workflows unavailable): {e}")

    # Seed demo data if empty
    await seed_demo_data()
    logger.info("✅ Demo data seeded")

    yield

    # Cleanup
    await redis_client.aclose()
    await engine.dispose()
    logger.info("🛑 AFOS shutdown complete")


# ── Internal proxy authentication middleware ─────────────────────────────────
# Every request to /api/v1/* MUST carry X-Internal-Token matching
# BACKEND_API_SECRET. This prevents direct access bypassing the Next.js proxy.
#
# Public routes (no token needed):
#   GET /health
#   GET /api/docs, /api/redoc, /openapi.json

PUBLIC_PREFIXES = (
    "/health",
    "/api/docs",
    "/api/redoc",
    "/openapi.json",
    # Webhook endpoints — called by external services (Razorpay, Stripe, etc.)
    # that cannot send our internal X-Internal-Token header
    "/api/v1/payments/webhook/",
    "/api/v1/payments/razorpay-webhook",
    "/api/v1/payments/stripe-webhook",
    # Razorpay subscription lifecycle webhooks
    "/api/v1/subscriptions/webhook",
)


class InternalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Allow public routes through without a token
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # Only enforce on /api/v1/* routes
        if not path.startswith("/api/v1"):
            return await call_next(request)

        # CORS preflight — browser strips all custom headers from OPTIONS requests,
        # so there is no X-Internal-Token to validate. Let CORS middleware handle it.
        if request.method == "OPTIONS":
            return await call_next(request)

        # In development mode, skip enforcement if secret is the placeholder
        secret = settings.BACKEND_API_SECRET
        if secret == "change_me_in_production" and settings.ENVIRONMENT == "development":
            return await call_next(request)

        # Validate the X-Internal-Token header using constant-time comparison
        token = request.headers.get("x-internal-token", "")
        expected = secret
        if not hmac.compare_digest(token.encode(), expected.encode()):
            logger.warning(f"Auth failed! Token received: {repr(token)}, Expected: {repr(expected)}")
            logger.warning(f"Request Headers: {dict(request.headers)}")
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized — direct backend access is not allowed"},
            )

        return await call_next(request)



app = FastAPI(
    title="AFOS — AI Financial Operating System",
    description="Autonomous Financial Operating System API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Middleware — order matters: outermost runs first on request, last on response
# Note: GZipMiddleware is intentionally omitted as it buffers small chunks
# and completely breaks Server-Sent Events (SSE) streaming.
app.add_middleware(
    CORSMiddleware,
    # Only accept requests from the Next.js frontend origin
    allow_origins=[settings.NEXTJS_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
# InternalAuthMiddleware must be added AFTER CORS so OPTIONS preflight is allowed
app.add_middleware(InternalAuthMiddleware)

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
    qdrant_stats = {}
    if qdrant_ok:
        try:
            qdrant_stats = await vector_store.get_collection_stats()
        except Exception:
            qdrant_stats = {}
    return {
        "status": "healthy",
        "service": "AFOS API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "services": {
            "redis": "connected" if redis_ok else "unavailable",
            "qdrant": "connected" if qdrant_ok else "unavailable",
        },
        "qdrant_collections": qdrant_stats,
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
