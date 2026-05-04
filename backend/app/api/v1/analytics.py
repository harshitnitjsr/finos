"""Analytics API — Dashboard KPIs, charts, financial metrics. Redis-cached."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, literal_column, text
from app.core.database import get_db
from app.core.redis_client import cache, TTL_DASHBOARD, TTL_ANALYTICS
from app.models.models import Invoice, Expense, Approval, Vendor, Workflow, AgentLog, Organization
from app.api.deps import get_org_id

from app.core.fx import fx_service

router = APIRouter()

# Removed static CURRENCIES dictionary


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
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    thirty_days_ago = now - timedelta(days=30)
    prev_thirty = now - timedelta(days=60)
    ninety_days_ago = now - timedelta(days=90)

    # Get organization default currency and FX rates
    org_res = await db.execute(select(Organization.default_currency).where(Organization.id == org_id))
    base_currency = org_res.scalar_one_or_none() or "USD"
    rates = await fx_service.get_rates(base_currency)

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

    # Consolidate previous month spend (for trend)
    prev_result = await db.execute(
        select(func.sum(Expense.amount).label("total"), Expense.currency)
        .where(
            Expense.org_id == org_id,
            Expense.transaction_date >= prev_thirty,
            Expense.transaction_date < thirty_days_ago,
        ).group_by(Expense.currency)
    )
    prev_total_base = sum(
        fx_service.convert(float(r.total or 0), r.currency, base_currency, rates)
        for r in prev_result.all()
    )

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
    
    # ── Consolidate and format results ───────────────────────────────────────
    
    # Consolidate monthly spend with trend %
    monthly_data = []
    total_curr_base = 0
    for r in monthly_spend:
        base_val = fx_service.convert(float(r.total or 0), r.currency, base_currency, rates)
        total_curr_base += base_val
        monthly_data.append({"currency": r.currency, "total": float(r.total or 0)})
    
    # Add a pseudo-entry for the base total so frontend knows the consolidated value
    monthly_data.append({"currency": base_currency, "total": total_curr_base, "is_consolidated": True})
    
    # Calculate global trend %
    change_pct = 0
    if prev_total_base > 0:
        change_pct = round(((total_curr_base - prev_total_base) / prev_total_base) * 100, 1)
    
    # Map consolidated entries for charts
    # We add a change_pct to the base currency entry specifically
    for m in monthly_data:
        if m.get("is_consolidated"):
            m["change_pct"] = change_pct

    # Trend: aggregate by day across all currencies
    consolidated_trend = {}
    for r in trend_data:
        d_str = r.day.date().isoformat()
        amt_base = fx_service.convert(float(r.total or 0), r.currency, base_currency, rates)
        consolidated_trend[d_str] = consolidated_trend.get(d_str, 0) + amt_base
    
    formatted_trend = [{"date": d, "amount": amt, "currency": base_currency} for d, amt in sorted(consolidated_trend.items())]

    # Categories: group by category, convert to base
    consolidated_cats = {}
    for r in category_data:
        amt_base = fx_service.convert(float(r.total or 0), r.currency, base_currency, rates)
        consolidated_cats[r.category] = consolidated_cats.get(r.category, 0) + amt_base
    
    formatted_cats = [{"category": c, "amount": amt, "currency": base_currency} for c, amt in consolidated_cats.items()]
    formatted_cats.sort(key=lambda x: x["amount"], reverse=True)

    response = {
        "base_currency": base_currency,
        "kpis": {
            "monthly_spend": monthly_data,
            "pending_approvals": pending_approvals,
            "anomaly_count": anomaly_count,
            "active_workflows": active_workflows,
            "invoice_stats": [{"currency": r.currency, "count": r.total, "value": float(r.total_value or 0)} for r in invoice_stats],
            "invoice_status": invoice_by_status,
        },
        "charts": {
            "expense_trend": formatted_trend,
            "category_breakdown": formatted_cats,
        },
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
    # Get organization default currency and FX rates
    org_res = await db.execute(select(Organization.default_currency).where(Organization.id == org_id))
    base_currency = org_res.scalar_one_or_none() or "USD"
    rates = await fx_service.get_rates(base_currency)

    # Consolidate by day
    consolidated = {}
    for r in result.all():
        d_str = r.day.strftime("%Y-%m-%d") if r.day else None
        if not d_str: continue
        amt_base = fx_service.convert(float(r.total or 0), r.currency, base_currency, rates)
        consolidated[d_str] = consolidated.get(d_str, 0) + amt_base
    
    formatted = [{"date": d, "amount": amt, "currency": base_currency} for d, amt in sorted(consolidated.items())]

    response = {"data": formatted, "days": days, "base_currency": base_currency}
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
    # Get organization default currency and FX rates
    org_res = await db.execute(select(Organization.default_currency).where(Organization.id == org_id))
    base_currency = org_res.scalar_one_or_none() or "USD"
    rates = await fx_service.get_rates(base_currency)

    # Consolidate by vendor
    consolidated = {}
    for r in result.all():
        amt_base = fx_service.convert(float(r.total or 0), r.currency, base_currency, rates)
        if r.vendor_name not in consolidated:
            consolidated[r.vendor_name] = {"name": r.vendor_name, "total": 0, "transactions": 0, "currency": base_currency}
        consolidated[r.vendor_name]["total"] += amt_base
        consolidated[r.vendor_name]["transactions"] += r.transactions
    
    formatted = sorted(consolidated.values(), key=lambda x: x["total"], reverse=True)

    response = {"data": formatted, "days": days, "base_currency": base_currency}
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
    # Get organization default currency and FX rates
    org_res = await db.execute(select(Organization.default_currency).where(Organization.id == org_id))
    base_currency = org_res.scalar_one_or_none() or "USD"
    rates = await fx_service.get_rates(base_currency)

    # Consolidate by category
    consolidated = {}
    for r in result.all():
        amt_base = fx_service.convert(float(r.total or 0), r.currency, base_currency, rates)
        if r.category not in consolidated:
            consolidated[r.category] = {"category": r.category, "total": 0, "count": 0, "currency": base_currency}
        consolidated[r.category]["total"] += amt_base
        consolidated[r.category]["count"] += r.count
    
    formatted = sorted(consolidated.values(), key=lambda x: x["total"], reverse=True)

    response = {"data": formatted, "days": days, "base_currency": base_currency}
    await cache.set("category_breakdown", response, TTL_ANALYTICS, cache_key)
    return response

def format_time_ago(dt: datetime) -> str:
    diff = datetime.utcnow() - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


@router.get("/notifications")
async def get_notifications(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate recent alerts and notifications. Uncached to ensure real-time UI."""
    notifications = []

    # 1. Pending Approvals Summary
    appr_result = await db.execute(
        select(func.count(Approval.id), func.max(Approval.created_at)).where(
            Approval.org_id == org_id, Approval.status == "pending"
        )
    )
    appr_row = appr_result.one_or_none()
    if appr_row and appr_row[0] > 0:
        count, latest_time = appr_row
        notifications.append({
            "id": f"appr-{latest_time.timestamp()}",
            "title": f"Review Required: {count} pending approvals",
            "type": "info",
            "time": format_time_ago(latest_time) if latest_time else "Just now",
            "timestamp": latest_time.timestamp() if latest_time else datetime.utcnow().timestamp()
        })

    # 2. Recent Anomalies
    anomaly_res = await db.execute(
        select(Expense).where(
            Expense.org_id == org_id, Expense.is_anomaly == True
        ).order_by(desc(Expense.created_at)).limit(2)
    )
    # Inline mapping for notifications since it's a simple list
    SYM = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£", "JPY": "¥"}
    for exp in anomaly_res.scalars():
        symbol = SYM.get(exp.currency, exp.currency)
        amount_str = f"{symbol}{exp.amount:,.0f}"
        notifications.append({
            "id": f"anom-{exp.id}",
            "title": f"Policy Alert: {amount_str} — {exp.vendor_name or 'Unknown vendor'}",
            "type": "danger",
            "time": format_time_ago(exp.created_at),
            "timestamp": exp.created_at.timestamp()
        })

    # 3. Recent Agent Logs
    agent_res = await db.execute(
        select(AgentLog).order_by(desc(AgentLog.created_at)).limit(3)
    )
    for log in agent_res.scalars():
        # Clean up agent actions for UI
        action = log.action.replace("_", " ").title()
        notifications.append({
            "id": f"agent-{log.id}",
            "title": f"🤖 {log.agent_name}: {action}",
            "type": "success" if log.status == "success" else "warning",
            "time": format_time_ago(log.created_at),
            "timestamp": log.created_at.timestamp()
        })

    # Sort descending by timestamp and limit to top 5
    notifications.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Strip timestamp before sending to client
    for n in notifications:
        n.pop("timestamp", None)

    return {"notifications": notifications[:5]}
