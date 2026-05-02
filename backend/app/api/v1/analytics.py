"""Analytics API — Dashboard KPIs, charts, financial metrics. Redis-cached."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, literal_column, text
from app.core.database import get_db
from app.core.redis_client import cache, TTL_DASHBOARD, TTL_ANALYTICS
from app.models.models import Invoice, Expense, Approval, Vendor, Workflow
from app.api.deps import get_org_id

router = APIRouter()

CURRENCIES = {
    "USD": {"symbol": "$", "rate": 1.0},
    "INR": {"symbol": "₹", "rate": 83.5},
    "EUR": {"symbol": "€", "rate": 0.92},
    "GBP": {"symbol": "£", "rate": 0.79},
    "JPY": {"symbol": "¥", "rate": 149.5},
}


@router.get("/dashboard")
async def dashboard_metrics(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Core dashboard KPIs — cached 30s."""
    cached = await cache.get("dashboard", org_id)
    if cached:
        return cached

    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    prev_thirty = now - timedelta(days=60)
    ninety_days_ago = now - timedelta(days=90)

    # Invoice stats by currency
    inv_result = await db.execute(
        select(
            func.count(Invoice.id).label("total"),
            func.sum(Invoice.total_amount).label("total_value"),
            Invoice.currency,
        ).where(Invoice.org_id == org_id).group_by(Invoice.currency)
    )
    invoice_stats = inv_result.all()

    # Pending approvals
    appr_result = await db.execute(
        select(func.count(Approval.id)).where(
            Approval.org_id == org_id, Approval.status == "pending"
        )
    )
    pending_approvals = appr_result.scalar_one_or_none() or 0

    # Current month spend
    monthly_result = await db.execute(
        select(
            func.sum(Expense.amount).label("total"),
            Expense.currency,
        ).where(
            Expense.org_id == org_id,
            Expense.transaction_date >= thirty_days_ago,
        ).group_by(Expense.currency)
    )
    monthly_spend = monthly_result.all()

    # Previous month spend (for trend)
    prev_result = await db.execute(
        select(func.sum(Expense.amount).label("total"), Expense.currency)
        .where(
            Expense.org_id == org_id,
            Expense.transaction_date >= prev_thirty,
            Expense.transaction_date < thirty_days_ago,
        ).group_by(Expense.currency)
    )
    prev_spend = {r.currency: float(r.total or 0) for r in prev_result.all()}

    # Anomalies
    anomaly_result = await db.execute(
        select(func.count(Expense.id)).where(
            Expense.org_id == org_id,
            Expense.is_anomaly == True,
            Expense.transaction_date >= thirty_days_ago,
        )
    )
    anomaly_count = anomaly_result.scalar_one_or_none() or 0

    # 30-day daily expense trend
    from sqlalchemy import text as sa_text
    trend_stmt = sa_text("""
        SELECT date_trunc('day', transaction_date) AS day,
               SUM(amount) AS total,
               currency
        FROM expenses
        WHERE org_id = :org_id
          AND transaction_date >= :since
        GROUP BY date_trunc('day', transaction_date), currency
        ORDER BY date_trunc('day', transaction_date)
    """)
    trend_result = await db.execute(trend_stmt, {"org_id": org_id, "since": thirty_days_ago})
    trend_data = trend_result.all()

    # Category breakdown (90 days)
    cat_result = await db.execute(
        select(
            Expense.category,
            func.sum(Expense.amount).label("total"),
            Expense.currency,
        ).where(
            Expense.org_id == org_id,
            Expense.category.isnot(None),
            Expense.transaction_date >= ninety_days_ago,
        ).group_by(Expense.category, Expense.currency)
        .order_by(desc(func.sum(Expense.amount)))
        .limit(8)
    )
    category_data = cat_result.all()

    # Active workflows
    wf_result = await db.execute(
        select(func.count(Workflow.id)).where(
            Workflow.org_id == org_id,
            Workflow.status.in_(["running", "pending"]),
        )
    )
    active_workflows = wf_result.scalar_one_or_none() or 0

    # Invoices by status
    inv_status_result = await db.execute(
        select(Invoice.status, func.count(Invoice.id).label("count"))
        .where(Invoice.org_id == org_id)
        .group_by(Invoice.status)
    )
    invoice_by_status = {r.status: r.count for r in inv_status_result.all()}

    # Top vendors by spend (30 days)
    vendor_spend_result = await db.execute(
        select(
            Expense.vendor_name,
            func.sum(Expense.amount).label("total"),
            Expense.currency,
        ).where(
            Expense.org_id == org_id,
            Expense.vendor_name.isnot(None),
            Expense.transaction_date >= thirty_days_ago,
        ).group_by(Expense.vendor_name, Expense.currency)
        .order_by(desc(func.sum(Expense.amount)))
        .limit(10)
    )
    vendor_spend = vendor_spend_result.all()

    response = {
        "kpis": {
            "total_invoices": sum(r.total for r in invoice_stats),
            "total_invoice_value": [
                {"currency": r.currency, "total": float(r.total_value or 0)}
                for r in invoice_stats
            ],
            "pending_approvals": pending_approvals,
            "monthly_spend": [
                {
                    "currency": r.currency,
                    "total": float(r.total or 0),
                    "prev_total": prev_spend.get(r.currency, 0),
                    "change_pct": (
                        round(
                            ((float(r.total or 0) - prev_spend.get(r.currency, 0))
                             / max(prev_spend.get(r.currency, 1), 1)) * 100,
                            1,
                        )
                        if prev_spend.get(r.currency, 0) > 0 else 0
                    ),
                }
                for r in monthly_spend
            ],
            "anomaly_count": anomaly_count,
            "active_workflows": active_workflows,
            "invoice_by_status": invoice_by_status,
        },
        "charts": {
            "expense_trend": [
                {
                    "date": r.day.strftime("%Y-%m-%d") if r.day else None,
                    "amount": float(r.total or 0),
                    "currency": r.currency,
                }
                for r in trend_data
            ],
            "category_breakdown": [
                {
                    "category": r.category or "Uncategorized",
                    "amount": float(r.total or 0),
                    "currency": r.currency,
                }
                for r in category_data
            ],
            "vendor_spend": [
                {
                    "name": r.vendor_name,
                    "total": float(r.total or 0),
                    "currency": r.currency,
                }
                for r in vendor_spend
            ],
        },
        "currencies": CURRENCIES,
        "generated_at": now.isoformat(),
    }

    await cache.set("dashboard", response, TTL_DASHBOARD, org_id)
    return response


@router.get("/spend-trend")
async def spend_trend(
    days: int = Query(30, ge=7, le=365),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Daily spend trend. Cached 120s."""
    cache_key = f"{org_id}:{days}"
    cached = await cache.get("spend_trend", cache_key)
    if cached:
        return cached

    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            func.date_trunc("day", Expense.transaction_date).label("day"),
            func.sum(Expense.amount).label("total"),
            Expense.currency,
        ).where(
            Expense.org_id == org_id,
            Expense.transaction_date >= since,
        ).group_by("day", Expense.currency)
        .order_by("day")
    )
    data = [
        {"date": r.day.strftime("%Y-%m-%d") if r.day else None, "amount": float(r.total or 0), "currency": r.currency}
        for r in result.all()
    ]
    response = {"data": data, "days": days}
    await cache.set("spend_trend", response, TTL_ANALYTICS, cache_key)
    return response


@router.get("/vendor-breakdown")
async def vendor_breakdown(
    days: int = Query(90, ge=7, le=365),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Top vendor spend breakdown. Cached 120s."""
    cache_key = f"{org_id}:{days}"
    cached = await cache.get("vendor_breakdown", cache_key)
    if cached:
        return cached

    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            Expense.vendor_name,
            func.sum(Expense.amount).label("total"),
            Expense.currency,
            func.count(Expense.id).label("transactions"),
        ).where(
            Expense.org_id == org_id,
            Expense.vendor_name.isnot(None),
            Expense.transaction_date >= since,
        ).group_by(Expense.vendor_name, Expense.currency)
        .order_by(desc(func.sum(Expense.amount)))
        .limit(15)
    )
    data = [
        {
            "name": r.vendor_name,
            "total": float(r.total or 0),
            "currency": r.currency,
            "transactions": r.transactions,
        }
        for r in result.all()
    ]
    response = {"data": data}
    await cache.set("vendor_breakdown", response, TTL_ANALYTICS, cache_key)
    return response


@router.get("/category-breakdown")
async def category_breakdown(
    days: int = Query(90, ge=7, le=365),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Expense category breakdown. Cached 120s."""
    cache_key = f"{org_id}:{days}"
    cached = await cache.get("category_breakdown", cache_key)
    if cached:
        return cached

    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            Expense.category,
            Expense.currency,
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count"),
            func.avg(Expense.amount).label("avg"),
        ).where(
            Expense.org_id == org_id,
            Expense.category.isnot(None),
            Expense.transaction_date >= since,
        ).group_by(Expense.category, Expense.currency)
        .order_by(desc(func.sum(Expense.amount)))
    )
    data = [
        {
            "category": r.category,
            "currency": r.currency,
            "total": float(r.total or 0),
            "count": r.count,
            "avg": float(r.avg or 0),
        }
        for r in result.all()
    ]
    response = {"data": data}
    await cache.set("category_breakdown", response, TTL_ANALYTICS, cache_key)
    return response
