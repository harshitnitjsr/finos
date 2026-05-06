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
    QDRANT_API_KEY: Optional[str] = None
    
    # OPA (Open Policy Agent)
    OPA_URL: str = "http://localhost:8181/v1/data/finance"
    
    # Temporal
    TEMPORAL_HOST: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "afos-task-queue"
    
    # OpenAI (fallback — only used when DO_INFERENCE_API_KEY is not set)
    OPENAI_API_KEY: str = ""

    # DigitalOcean Inference Hub — OpenAI-compatible, billed from DO credits
    # Get key: DO Control Panel → Inference → API Keys → Generate
    DO_INFERENCE_API_KEY: str = ""
    DO_INFERENCE_BASE_URL: str = "https://inference.do-ai.run/v1"
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""  # whsec_... for signature verification
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_CLIENT_ID: str = ""  # ca_... for Stripe Connect OAuth

    # Razorpay / RazorpayX
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAYX_ACCOUNT_NUMBER: str = ""  # Virtual account for payouts
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RAZORPAY_CLIENT_ID: str = ""  # Partner OAuth
    RAZORPAY_CLIENT_SECRET: str = ""

    # Razorpay Subscription Plan IDs — INR (India) plans
    # Create in: Razorpay Dashboard → Products → Plans (currency = INR)
    RAZORPAY_PLAN_ID_STARTER:    str = ""   # e.g. plan_xxxx
    RAZORPAY_PLAN_ID_PRO:        str = ""   # e.g. plan_yyyy
    RAZORPAY_PLAN_ID_ENTERPRISE: str = ""   # e.g. plan_zzzz

    # Razorpay Subscription Plan IDs — USD (International) plans
    # Create in: Razorpay Dashboard → Products → Plans (currency = USD)
    RAZORPAY_PLAN_ID_STARTER_USD:    str = ""   # e.g. plan_aaaa
    RAZORPAY_PLAN_ID_PRO_USD:        str = ""   # e.g. plan_bbbb
    RAZORPAY_PLAN_ID_ENTERPRISE_USD: str = ""   # e.g. plan_cccc

    # Frontend base URL for redirects after payment
    APP_BASE_URL: str = "http://localhost:3000"

    # Platform commission charged on top of invoice amount (e.g. 2.0 = 2%)
    PLATFORM_COMMISSION_PERCENT: float = 0.0

    # Payment system
    PAYMENT_BASE_URL: str = "http://localhost:8000"  # For webhook registration
    
    # Model Router — OpenAI names used when DO key is NOT set (direct OpenAI billing)
    # When DO_INFERENCE_API_KEY is set, model_router.py overrides these with:
    #   chat tasks  → llama3.3-70b-instruct  (free, DO Tier 1, tool-calling capable)
    #   embeddings  → bge-m3                 (free, DO Tier 1, 1024-dim)
    MODEL_ROUTER_REASONING: str = "llama3.3-70b-instruct"
    MODEL_ROUTER_EXTRACTION: str = "llama3.3-70b-instruct"
    MODEL_ROUTER_CLASSIFICATION: str = "llama3.3-70b-instruct"
    MODEL_ROUTER_EMBEDDING: str = "bge-m3"
    MODEL_ROUTER_FORECAST: str = "llama3.3-70b-instruct"
    MODEL_ROUTER_COMPLIANCE: str = "llama3.3-70b-instruct"
    
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
    AWS_REGION: str = "us-east-1"
    
    # Email Settings
    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@afos.io"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
