"""
Insights API — GPT-4o powered executive summaries + recommendations.
Pulls real metrics from DB; results cached in Redis for 10 min.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.core.database import get_db
from app.core.redis_client import cache, TTL_INSIGHTS
from app.models.models import Expense, Invoice, Approval, Vendor
from app.agents.insight_agent import insight_agent

from app.api.deps import get_org_id

router = APIRouter()

@router.get("/executive-summary")
async def executive_summary(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    GPT-4o executive financial summary with real data context.
    Expensive — cached 10 minutes in Redis.
    """
    cached = await cache.get("executive_summary", org_id)
    if cached:
        return cached

    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    # Gather real context data
    monthly_spend = await db.execute(
        select(func.sum(Expense.amount).label("total"), Expense.currency)
        .where(Expense.org_id == org_id, Expense.transaction_date >= thirty_days_ago)
        .group_by(Expense.currency)
    )
    spend_by_currency = [{"currency": r.currency, "total": float(r.total or 0)} for r in monthly_spend.all()]

    anomaly_count = (await db.execute(
        select(func.count(Expense.id))
        .where(Expense.org_id == org_id, Expense.is_anomaly == True, Expense.transaction_date >= thirty_days_ago)
    )).scalar_one_or_none() or 0

    pending_approvals = (await db.execute(
        select(func.count(Approval.id))
        .where(Approval.org_id == org_id, Approval.status == "pending")
    )).scalar_one_or_none() or 0

    high_risk_count = (await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.org_id == org_id, Invoice.risk_level.in_(["high", "critical"]))
    )).scalar_one_or_none() or 0

    top_categories = await db.execute(
        select(Expense.category, func.sum(Expense.amount).label("total"))
        .where(Expense.org_id == org_id, Expense.transaction_date >= thirty_days_ago, Expense.category.isnot(None))
        .group_by(Expense.category)
        .order_by(desc(func.sum(Expense.amount)))
        .limit(5)
    )
    categories = [{"category": r.category, "total": float(r.total or 0)} for r in top_categories.all()]

    financial_context = {
        "monthly_spend": spend_by_currency,
        "anomaly_count": anomaly_count,
        "pending_approvals": pending_approvals,
        "high_risk_invoices": high_risk_count,
        "top_spend_categories": categories,
        "period": "last 30 days",
    }

    summary = await insight_agent.generate_executive_summary(financial_context)

    response = {
        **summary,
        "financial_context": financial_context,
        "generated_at": now.isoformat(),
        "cache_ttl_seconds": TTL_INSIGHTS,
    }

    await cache.set("executive_summary", response, TTL_INSIGHTS, org_id)
    return response


@router.get("/recommendations")
async def recommendations(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    AI-generated cost optimization recommendations from real spend data.
    Cached 10 minutes.
    """
    cached = await cache.get("recommendations", org_id)
    if cached:
        return cached

    now = datetime.utcnow()
    ninety_days_ago = now - timedelta(days=90)

    # Recurring SaaS expenses — detect potential duplicates
    recurring = await db.execute(
        select(Expense.vendor_name, func.count(Expense.id).label("cnt"), func.sum(Expense.amount).label("total"), Expense.currency)
        .where(Expense.org_id == org_id, Expense.is_recurring == True)
        .group_by(Expense.vendor_name, Expense.currency)
        .order_by(desc(func.sum(Expense.amount)))
        .limit(20)
    )
    recurring_expenses = [
        {"vendor": r.vendor_name, "occurrences": r.cnt, "total": float(r.total or 0), "currency": r.currency}
        for r in recurring.all()
    ]

    # High anomaly categories
    anomaly_categories = await db.execute(
        select(Expense.category, func.count(Expense.id).label("cnt"), func.sum(Expense.amount).label("total"))
        .where(Expense.org_id == org_id, Expense.is_anomaly == True, Expense.transaction_date >= ninety_days_ago)
        .group_by(Expense.category)
        .order_by(desc(func.count(Expense.id)))
        .limit(5)
    )
    anomaly_cats = [{"category": r.category, "count": r.cnt, "total": float(r.total or 0)} for r in anomaly_categories.all()]

    context = {
        "recurring_expenses": recurring_expenses,
        "anomaly_categories": anomaly_cats,
        "period": "90 days",
    }

    recs = await insight_agent.generate_recommendations(context)

    response = {
        "recommendations": recs,
        "context": context,
        "generated_at": now.isoformat(),
    }
    await cache.set("recommendations", response, TTL_INSIGHTS, org_id)
    return response


@router.post("/invalidate-cache")
async def invalidate_insight_cache():
    """Force-refresh insight cache (admin action)."""
    await cache.invalidate_pattern("executive_summary")
    await cache.invalidate_pattern("recommendations")
    return {"message": "Insight cache cleared"}
