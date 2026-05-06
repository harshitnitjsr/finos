"""
Subscriptions API — Razorpay-powered billing for AFOS.

Routes:
  GET  /subscriptions/plans           List all available plans (includes INR + USD pricing)
  GET  /subscriptions/current         Current org's subscription + usage
  POST /subscriptions/create          Create a Razorpay subscription & get payment link
                                      Body: { plan_slug, currency: "INR" | "USD" }
  POST /subscriptions/verify          Verify payment signature after checkout
  POST /subscriptions/cancel          Cancel the active subscription (downgrades to Free)
  POST /subscriptions/webhook         Razorpay webhook handler (public — no internal token)

Currency routing:
  India users    → currency="INR" → uses plan.razorpay_plan_id     (INR Razorpay plan)
  International  → currency="USD" → uses plan.razorpay_plan_id_usd (USD Razorpay plan)
  Razorpay handles multi-currency checkout transparently for 135+ currencies / 180+ countries.

Razorpay Subscription flow:
  1. Frontend calls POST /subscriptions/create with { plan_slug, currency }
  2. Backend creates a Razorpay Subscription and returns a short_url
  3. User pays on Razorpay-hosted page
  4. Razorpay fires subscription.activated webhook → we activate
  5. Monthly auto-charge: invoice.paid webhook → we reset usage counters
  6. Cancel/failure: subscription.cancelled webhook → downgrade to free
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional

import httpx
import razorpay
from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_org_id
from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import cache
from app.core.subscription import get_subscription_info, _get_subscription
from app.models.models import (
    Organization, OrganizationSubscription, SubscriptionPlan, SubscriptionStatus,
)

router = APIRouter()


# ── Razorpay client ──────────────────────────────────────────────────────────

def _rz_client() -> razorpay.Client:
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Razorpay is not configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.",
        )
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _plan_to_dict(p: SubscriptionPlan) -> dict:
    return {
        "id": p.id,
        "slug": p.slug,
        "name": p.name,
        "description": p.description,
        "price_monthly_inr": p.price_monthly_inr,
        "price_monthly_usd": getattr(p, "price_monthly_usd", 0) or 0,
        "display_price": f"₹{p.price_monthly_inr:,}" if p.price_monthly_inr > 0 else "Free",
        "display_price_usd": f"${getattr(p, 'price_monthly_usd', 0)}" if (getattr(p, 'price_monthly_usd', 0) or 0) > 0 else "Free",
        "razorpay_plan_id": p.razorpay_plan_id,
        "razorpay_plan_id_usd": getattr(p, "razorpay_plan_id_usd", None),
        "max_invoices_per_month": p.max_invoices_per_month,
        "max_prompts_per_month": p.max_prompts_per_month,
        "is_active": p.is_active,
        "sort_order": p.sort_order,
    }


def _sub_to_dict(sub: OrganizationSubscription, plan: SubscriptionPlan) -> dict:
    return {
        "id": sub.id,
        "org_id": sub.org_id,
        "status": sub.status,
        "plan": _plan_to_dict(plan),
        "razorpay_subscription_id": sub.razorpay_subscription_id,
        "billing_currency": getattr(sub, "billing_currency", "INR") or "INR",
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "invoices_used": sub.invoices_used,
        "prompts_used": sub.prompts_used,
        "created_at": sub.created_at.isoformat(),
    }


async def _detect_currency_from_ip(request: Request) -> str:
    """
    Detect billing currency from the caller's IP address.
    Returns "INR" for India, "USD" for every other country.

    - Production: uses the real client IP from request headers
    - Local dev / localhost: calls ip-api.com without an IP param so it
      detects the SERVER's own outbound IP — which reflects VPN if active.
    """
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.headers.get("X-Real-IP", "")
        or (request.client.host if request.client else "")
    )

    is_local = client_ip in ("127.0.0.1", "::1", "localhost", "")

    # Primary: ipinfo.io (HTTPS, reliable)  |  Fallback: ip-api.com (HTTP)
    primary_url  = "https://ipinfo.io/json"       if is_local else f"https://ipinfo.io/{client_ip}/json"
    fallback_url = "http://ip-api.com/json/"      if is_local else f"http://ip-api.com/json/{client_ip}"

    async with httpx.AsyncClient(timeout=4.0) as client:

        # ── Primary: ipinfo.io ───────────────────────────────────────────
        try:
            resp = await client.get(primary_url)
            resp.raise_for_status()
            country_code = resp.json().get("country", "")
            if country_code:
                currency = "INR" if country_code == "IN" else "USD"
                logger.debug(f"[geo/primary] {client_ip or 'server'} → {country_code} → {currency}")
                return currency
        except Exception as exc:
            logger.warning(
                f"[geo/primary] ipinfo.io failed ({type(exc).__name__}: {exc}), trying fallback..."
            )

        # ── Fallback: ip-api.com ─────────────────────────────────────────
        try:
            resp = await client.get(fallback_url, params={"fields": "countryCode"})
            resp.raise_for_status()
            country_code = resp.json().get("countryCode", "")
            if country_code:
                currency = "INR" if country_code == "IN" else "USD"
                logger.debug(f"[geo/fallback] {client_ip or 'server'} → {country_code} → {currency}")
                return currency
        except Exception as exc:
            logger.warning(
                f"[geo/fallback] ip-api.com failed ({type(exc).__name__}: {exc}) — defaulting to INR"
            )

    return "INR"




async def _get_or_create_sub(org_id: str, db: AsyncSession):
    """Return (OrganizationSubscription, SubscriptionPlan) for org, creating Free if missing."""
    result = await db.execute(
        select(OrganizationSubscription, SubscriptionPlan)
        .join(SubscriptionPlan, OrganizationSubscription.plan_id == SubscriptionPlan.id)
        .where(OrganizationSubscription.org_id == org_id)
        .limit(1)
    )
    row = result.first()
    if row:
        return row[0], row[1]

    # Auto-create free subscription
    free_plan_result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.slug == "free").limit(1)
    )
    free_plan = free_plan_result.scalar_one_or_none()
    if not free_plan:
        raise HTTPException(status_code=500, detail="Free plan not found in DB. Run seed.")

    sub = OrganizationSubscription(
        org_id=org_id,
        plan_id=free_plan.id,
        status=SubscriptionStatus.FREE,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub, free_plan


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Return all active subscription plans + detected billing currency for this caller.
    Plans are cached; currency is detected fresh per-request from the caller's IP.
    """
    # Detect currency from IP (per-request, never cached — each caller has a different IP)
    detected_currency = await _detect_currency_from_ip(request)

    # Plans list itself can be cached (same for everyone)
    cached_plans = await cache.get("subscriptions", "all_plans_v2")
    if not cached_plans:
        result = await db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active == True)  # noqa: E712
            .order_by(SubscriptionPlan.sort_order)
        )
        plans = result.scalars().all()
        cached_plans = [_plan_to_dict(p) for p in plans]
        await cache.set("subscriptions", cached_plans, 300, "all_plans_v2")

    return {
        "plans": cached_plans,
        "detected_currency": detected_currency,  # "INR" or "USD"
    }


@router.get("/current")
async def get_current_subscription(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Return the current subscription state + usage for the caller's org."""
    sub, plan = await _get_or_create_sub(org_id, db)
    return _sub_to_dict(sub, plan)


class CreateSubscriptionBody(BaseModel):
    plan_slug: str            # starter | pro | enterprise
    currency:  str = "INR"   # "INR" (India) or "USD" (international)


@router.post("/create")
async def create_subscription(
    body: CreateSubscriptionBody,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Razorpay Subscription for the given plan and return a payment link.

    Flow:
      1. Validate plan exists and has a Razorpay plan_id configured
      2. Get/create org's subscription record
      3. Create Razorpay Subscription via API
      4. Save razorpay_subscription_id to DB (status stays free until webhook confirms)
      5. Return {short_url, subscription_id} so frontend can redirect user
    """
    if body.plan_slug == "free":
        raise HTTPException(status_code=400, detail="Cannot 'subscribe' to the Free plan.")

    # Validate currency
    billing_currency = body.currency.upper()
    if billing_currency not in ("INR", "USD"):
        raise HTTPException(status_code=400, detail="currency must be 'INR' or 'USD'.")

    # Fetch plan
    plan_result = await db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.slug == body.plan_slug, SubscriptionPlan.is_active == True)  # noqa: E712
        .limit(1)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{body.plan_slug}' not found.")

    # Pick the correct Razorpay plan ID based on currency
    if billing_currency == "USD":
        razorpay_plan_id = getattr(plan, "razorpay_plan_id_usd", None)
        if not razorpay_plan_id:
            raise HTTPException(
                status_code=503,
                detail=f"USD Razorpay Plan ID not configured for '{body.plan_slug}'. "
                       f"Set RAZORPAY_PLAN_ID_{body.plan_slug.upper()}_USD in .env.",
            )
    else:
        razorpay_plan_id = plan.razorpay_plan_id
        if not razorpay_plan_id:
            raise HTTPException(
                status_code=503,
                detail=f"INR Razorpay Plan ID not configured for '{body.plan_slug}'. "
                       f"Set RAZORPAY_PLAN_ID_{body.plan_slug.upper()} in .env.",
            )

    # Get org details for Razorpay customer
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    sub, _ = await _get_or_create_sub(org_id, db)

    # If already on this plan and active, return existing link
    if sub.status == SubscriptionStatus.ACTIVE and sub.plan_id == plan.id:
        raise HTTPException(status_code=400, detail="Already subscribed to this plan.")

    rz = _rz_client()

    # Create Razorpay subscription
    try:
        rz_sub = rz.subscription.create({
            "plan_id": razorpay_plan_id,
            "total_count": 12,          # 12 billing cycles (1 year)
            "quantity": 1,
            "customer_notify": 1,
            "notes": {
                "org_id": org_id,
                "org_name": org.name,
                "plan_slug": plan.slug,
                "currency": billing_currency,
            },
        })
    except Exception as e:
        logger.error(f"Razorpay subscription create failed: {e}")
        raise HTTPException(status_code=502, detail=f"Razorpay error: {e}")

    # Save pending subscription — plan_id stays as FREE until payment confirmed
    # Plan is activated in /verify (after HMAC check) or subscription.activated webhook
    sub.razorpay_subscription_id = rz_sub["id"]
    sub.billing_currency = billing_currency
    sub.updated_at       = datetime.utcnow()
    await db.commit()

    # Store pending plan slug in Redis (24h) so verify/webhook can activate it
    await cache.set("subscriptions", plan.slug, 86400, f"pending_plan:{rz_sub['id']}")

    # Bust cache
    await cache.invalidate_pattern(f"subscriptions:sub:{org_id}")

    logger.info(f"Created Razorpay subscription {rz_sub['id']} for org {org_id} plan {plan.slug} (PENDING payment)")

    return {
        "razorpay_subscription_id": rz_sub["id"],
        "short_url": rz_sub.get("short_url"),
        "plan": _plan_to_dict(plan),
        "key_id": settings.RAZORPAY_KEY_ID,
    }


class VerifyPaymentBody(BaseModel):
    razorpay_payment_id: str
    razorpay_subscription_id: str
    razorpay_signature: str


@router.post("/verify")
async def verify_subscription_payment(
    body: VerifyPaymentBody,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify Razorpay signature after user completes checkout on Razorpay's page.
    Activates the subscription immediately (doesn't wait for webhook).
    """
    # Verify HMAC signature
    expected_sig = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{body.razorpay_payment_id}|{body.razorpay_subscription_id}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, body.razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid payment signature.")

    # Fetch and activate
    result = await db.execute(
        select(OrganizationSubscription)
        .where(
            OrganizationSubscription.org_id == org_id,
            OrganizationSubscription.razorpay_subscription_id == body.razorpay_subscription_id,
        )
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found.")

    # Activate plan — look up from Redis pending store
    pending_slug = await cache.get("subscriptions", f"pending_plan:{body.razorpay_subscription_id}")
    if pending_slug:
        plan_result = await db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.slug == pending_slug, SubscriptionPlan.is_active == True)  # noqa: E712
            .limit(1)
        )
        paid_plan = plan_result.scalar_one_or_none()
        if paid_plan:
            sub.plan_id = paid_plan.id
            logger.info(f"Verify: activated plan '{pending_slug}' for org {org_id}")

    sub.status = SubscriptionStatus.ACTIVE
    sub.updated_at = datetime.utcnow()
    await db.commit()
    await cache.invalidate_pattern(f"subscriptions:sub:{org_id}")

    return {"status": "activated", "subscription_id": sub.razorpay_subscription_id}


@router.post("/cancel")
async def cancel_subscription(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Cancel the active subscription at Razorpay and downgrade org to Free plan."""
    sub, plan = await _get_or_create_sub(org_id, db)

    if sub.status != SubscriptionStatus.ACTIVE or not sub.razorpay_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription to cancel.")

    rz = _rz_client()
    try:
        rz.subscription.cancel(sub.razorpay_subscription_id, {"cancel_at_cycle_end": 1})
    except Exception as e:
        logger.error(f"Razorpay cancel failed: {e}")
        raise HTTPException(status_code=502, detail=f"Razorpay cancel error: {e}")

    sub.status = SubscriptionStatus.CANCELLED
    sub.updated_at = datetime.utcnow()
    await db.commit()
    await cache.invalidate_pattern(f"subscriptions:sub:{org_id}")

    return {"status": "cancelled"}


# ── Webhook (public — no InternalAuthMiddleware token) ───────────────────────

@router.post("/webhook")
async def razorpay_subscription_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Razorpay subscription lifecycle webhooks.

    Events handled:
      subscription.activated  → mark subscription ACTIVE
      subscription.charged    → reset monthly usage counters (new billing period)
      subscription.cancelled  → downgrade to Free plan
      subscription.paused     → mark PAUSED
      subscription.resumed    → mark ACTIVE
    """
    payload_bytes = await request.body()
    sig_header = request.headers.get("x-razorpay-signature", "")
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET

    # Verify signature if secret is configured
    if webhook_secret:
        expected = hmac.new(
            webhook_secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, sig_header):
            logger.warning("Razorpay subscription webhook: invalid signature")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        event = json.loads(payload_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type: str = event.get("event", "")
    payload = event.get("payload", {})
    sub_entity = payload.get("subscription", {}).get("entity", {})
    rz_sub_id: str = sub_entity.get("id", "")

    if not rz_sub_id:
        return {"received": True}

    # Fetch our subscription record
    result = await db.execute(
        select(OrganizationSubscription)
        .where(OrganizationSubscription.razorpay_subscription_id == rz_sub_id)
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning(f"Webhook: subscription {rz_sub_id} not found in DB")
        return {"received": True}

    # Append event to log (keep last 20)
    events_log = list(sub.webhook_events or [])
    events_log.append({"event": event_type, "at": datetime.utcnow().isoformat()})
    sub.webhook_events = events_log[-20:]

    if event_type == "subscription.activated":
        # Look up pending plan from notes (set at /create time)
        notes = sub_entity.get("notes", {})
        plan_slug = notes.get("plan_slug") if isinstance(notes, dict) else None
        if plan_slug:
            plan_result = await db.execute(
                select(SubscriptionPlan)
                .where(SubscriptionPlan.slug == plan_slug, SubscriptionPlan.is_active == True)  # noqa: E712
                .limit(1)
            )
            paid_plan = plan_result.scalar_one_or_none()
            if paid_plan:
                sub.plan_id = paid_plan.id
                logger.info(f"Webhook: activated plan '{plan_slug}' for org {sub.org_id}")
        sub.status = SubscriptionStatus.ACTIVE
        logger.info(f"Subscription {rz_sub_id} activated for org {sub.org_id}")

    elif event_type == "subscription.charged":
        # New billing period — reset usage counters
        sub.invoices_used = 0
        sub.prompts_used = 0
        sub.status = SubscriptionStatus.ACTIVE
        # Update period dates from webhook
        current_start = sub_entity.get("current_start")
        current_end = sub_entity.get("current_end")
        if current_start:
            sub.current_period_start = datetime.fromtimestamp(current_start, tz=timezone.utc)
        if current_end:
            sub.current_period_end = datetime.fromtimestamp(current_end, tz=timezone.utc)
        logger.info(f"Subscription {rz_sub_id} charged — usage counters reset for org {sub.org_id}")

    elif event_type == "subscription.cancelled":
        # Downgrade to free plan
        free_result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.slug == "free").limit(1)
        )
        free_plan = free_result.scalar_one_or_none()
        if free_plan:
            sub.plan_id = free_plan.id
        sub.status = SubscriptionStatus.CANCELLED
        sub.razorpay_subscription_id = None
        logger.info(f"Subscription cancelled — org {sub.org_id} downgraded to Free")

    elif event_type == "subscription.paused":
        sub.status = SubscriptionStatus.PAUSED

    elif event_type == "subscription.resumed":
        sub.status = SubscriptionStatus.ACTIVE

    elif event_type == "subscription.pending":
        sub.status = SubscriptionStatus.PAST_DUE

    sub.updated_at = datetime.utcnow()
    await db.commit()
    await cache.invalidate_pattern(f"subscriptions:sub:{sub.org_id}")

    return {"received": True}
