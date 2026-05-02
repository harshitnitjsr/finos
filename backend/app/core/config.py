"""Application configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://afos:afos_password@localhost:5432/afos_db"
    ASYNC_DATABASE_URL: str = "postgresql+asyncpg://afos:afos_password@localhost:5432/afos_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    
    # Temporal
    TEMPORAL_HOST: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "afos-task-queue"
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    
    # Model Router
    MODEL_ROUTER_REASONING: str = "gpt-4o"
    MODEL_ROUTER_EXTRACTION: str = "gpt-4o-mini"
    MODEL_ROUTER_CLASSIFICATION: str = "gpt-4o-mini"
    MODEL_ROUTER_EMBEDDING: str = "text-embedding-3-small"
    MODEL_ROUTER_FORECAST: str = "gpt-4o"
    MODEL_ROUTER_COMPLIANCE: str = "gpt-4o"
    
    # Auth — internal proxy secret (must match BACKEND_API_SECRET in Next.js .env.local)
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    BACKEND_API_SECRET: str = "change_me_in_production"
    APP_SECRET_KEY: str = "change_me_in_production"

    # Allowed origin for CORS (Next.js frontend)
    NEXTJS_ORIGIN: str = "http://localhost:3000"
    
    # App
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # Storage
    STORAGE_TYPE: str = "local"
    STORAGE_LOCAL_PATH: str = "./uploads"
    
    # AWS (optional)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
