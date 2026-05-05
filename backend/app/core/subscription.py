"""
Subscription enforcement helpers for AFOS.

Usage in route handlers:
    from app.core.subscription import require_invoice_quota, require_prompt_quota

    @router.post("/invoices")
    async def create_invoice(..., _=Depends(require_invoice_quota)):
        ...

Design:
  - Subscription state is cached in Redis for 60 s to avoid per-request DB hits.
  - On limit exceeded we return HTTP 402 with a machine-readable body so the
    frontend can show the correct upgrade prompt.
  - Unlimited plans have max_* == -1 which bypasses all checks.
"""
import json
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_org_id
from app.core.database import get_db
from app.core.redis_client import cache
from app.models.models import OrganizationSubscription, SubscriptionPlan, SubscriptionStatus


# ── Cache helpers ────────────────────────────────────────────────────────────

_CACHE_TTL = 60  # seconds


async def _get_subscription(org_id: str, db: AsyncSession) -> dict:
    """Return subscription info dict, creating a Free record if missing."""
    cache_key = f"sub:{org_id}"
    cached = await cache.get("subscriptions", cache_key)
    if cached:
        return cached

    result = await db.execute(
        select(OrganizationSubscription, SubscriptionPlan)
        .join(SubscriptionPlan, OrganizationSubscription.plan_id == SubscriptionPlan.id)
        .where(OrganizationSubscription.org_id == org_id)
        .limit(1)
    )
    row = result.first()

    if not row:
        # First time: auto-create a Free subscription
        sub_info = await _create_free_subscription(org_id, db)
    else:
        sub, plan = row

        # If free plan has no expiry set yet, backfill it (created_at + 30 days)
        if plan.slug == "free" and sub.current_period_end is None:
            sub.current_period_end = sub.created_at + timedelta(days=30)
            sub.current_period_start = sub.created_at
            sub.updated_at = datetime.utcnow()
            await db.commit()

        sub_info = {
            "subscription_id": sub.id,
            "status": sub.status,
            "plan_slug": plan.slug,
            "plan_name": plan.name,
            "price_monthly_inr": plan.price_monthly_inr,
            "max_invoices": plan.max_invoices_per_month,
            "max_prompts": plan.max_prompts_per_month,
            "invoices_used": sub.invoices_used,
            "prompts_used": sub.prompts_used,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        }

    await cache.set("subscriptions", sub_info, _CACHE_TTL, cache_key)
    return sub_info


async def _create_free_subscription(org_id: str, db: AsyncSession) -> dict:
    """Bootstrap a Free tier subscription for a new org."""
    # Find the free plan
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.slug == "free").limit(1)
    )
    free_plan = result.scalar_one_or_none()

    if not free_plan:
        logger.warning("No 'free' plan found in DB — skipping subscription bootstrap")
        # Return permissive defaults so the app doesn't crash
        return {
            "subscription_id": None,
            "status": SubscriptionStatus.FREE,
            "plan_slug": "free",
            "plan_name": "Free",
            "price_monthly_inr": 0,
            "max_invoices": 5,
            "max_prompts": 10,
            "invoices_used": 0,
            "prompts_used": 0,
            "current_period_end": None,
        }

    now = datetime.utcnow()
    free_expires = now + timedelta(days=30)
    sub = OrganizationSubscription(
        org_id=org_id,
        plan_id=free_plan.id,
        status=SubscriptionStatus.FREE,
        current_period_start=now,
        current_period_end=free_expires,   # Free plan expires 30 days after signup
    )
    db.add(sub)
    await db.commit()
    logger.info(f"Created Free subscription for org {org_id} — expires {free_expires.date()}")

    return {
        "subscription_id": sub.id,
        "status": sub.status,
        "plan_slug": free_plan.slug,
        "plan_name": free_plan.name,
        "price_monthly_inr": free_plan.price_monthly_inr,
        "max_invoices": free_plan.max_invoices_per_month,
        "max_prompts": free_plan.max_prompts_per_month,
        "invoices_used": 0,
        "prompts_used": 0,
        "current_period_end": free_expires.isoformat(),
    }


def _limit_error(resource: str, used: int, limit: int, plan_name: str, is_free: bool = False) -> HTTPException:
    period = "lifetime quota" if is_free else "this month"
    return HTTPException(
        status_code=402,
        detail={
            "error": "subscription_limit_exceeded",
            "resource": resource,
            "used": used,
            "limit": limit,
            "plan": plan_name,
            "message": (
                f"You have used {used}/{limit} {resource} ({period}) on the {plan_name} plan. "
                f"Upgrade your plan to continue."
            ),
        },
    )


def _expired_error(expires_at: str) -> HTTPException:
    """Raised when the 30-day Free plan has expired regardless of usage."""
    return HTTPException(
        status_code=402,
        detail={
            "error": "free_plan_expired",
            "expired_at": expires_at,
            "message": (
                f"Your free trial expired on {expires_at[:10]}. "
                f"Upgrade to a paid plan to continue using AFOS."
            ),
        },
    )

def _check_access_allowed(info: dict) -> None:
    """
    Central access check — called by all quota dependencies.
    Raises 402 when:
      - Free plan trial has expired (time-based)
      - Paid subscription is cancelled / past_due / paused
    """
    is_free = info["plan_slug"] == "free"

    if is_free and info["current_period_end"]:
        expires = datetime.fromisoformat(info["current_period_end"])
        if datetime.utcnow() > expires:
            raise _expired_error(info["current_period_end"])

    if not is_free and info["status"] in ("cancelled", "past_due", "paused"):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "subscription_inactive",
                "status": info["status"],
                "message": (
                    f"Your {info['plan_name']} subscription is {info['status']}. "
                    f"Please renew your plan to continue using AI features."
                ),
            },
        )


# ── Public dependencies ──────────────────────────────────────────────────────

async def require_invoice_quota(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Raises 402 if: free trial expired, paid sub inactive, or invoice limit reached."""
    info = await _get_subscription(org_id, db)
    _check_access_allowed(info)

    is_free = info["plan_slug"] == "free"
    max_inv = info["max_invoices"]
    used = info["invoices_used"]
    if max_inv != -1 and used >= max_inv:
        raise _limit_error("invoices", used, max_inv, info["plan_name"], is_free=is_free)

    return info


async def require_prompt_quota(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Raises 402 if: free trial expired, paid sub inactive, or prompt limit reached."""
    info = await _get_subscription(org_id, db)
    _check_access_allowed(info)

    is_free = info["plan_slug"] == "free"
    max_p = info["max_prompts"]
    used = info["prompts_used"]
    if max_p != -1 and used >= max_p:
        raise _limit_error("AI prompts", used, max_p, info["plan_name"], is_free=is_free)

    return info


async def get_subscription_info(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Non-blocking dependency — returns subscription info without enforcing limits."""
    return await _get_subscription(org_id, db)


async def require_active_subscription(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    General-purpose gate for ANY AI feature (insights, agents, etc.).
    Raises 402 when free trial expires or paid subscription is inactive.
    Does NOT enforce per-resource quotas — use require_invoice/prompt_quota for that.
    """
    info = await _get_subscription(org_id, db)
    _check_access_allowed(info)
    return info


# ── Usage counter helpers (called after successful operations) ────────────────

async def increment_invoice_usage(org_id: str, db: AsyncSession) -> None:
    """Increment invoices_used counter and bust cache."""
    result = await db.execute(
        select(OrganizationSubscription)
        .where(OrganizationSubscription.org_id == org_id)
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.invoices_used = (sub.invoices_used or 0) + 1
        sub.updated_at = datetime.utcnow()
        await db.commit()
        await cache.invalidate_pattern(f"subscriptions:sub:{org_id}")


async def increment_prompt_usage(org_id: str, db: AsyncSession) -> None:
    """Increment prompts_used counter and bust cache."""
    result = await db.execute(
        select(OrganizationSubscription)
        .where(OrganizationSubscription.org_id == org_id)
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.prompts_used = (sub.prompts_used or 0) + 1
        sub.updated_at = datetime.utcnow()
        await db.commit()
        await cache.invalidate_pattern(f"subscriptions:sub:{org_id}")
