"""
Forecasting & Insight Tools — LangChain tools for Forecasting and Insight Agents.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class HistoricalSpendInput(BaseModel):
    months: int = Field(default=6, description="Number of past months of data")
    group_by: str = Field(default="month", description="Group by: month or category")


class CategoryTrendInput(BaseModel):
    category: str = Field(description="Expense category to analyze trend for")
    months: int = Field(default=6, description="Number of months to analyze")


class DashboardSummaryInput(BaseModel):
    days: int = Field(default=30, description="Summary period in days")


class AgentActivityInput(BaseModel):
    hours: int = Field(default=24, description="Look-back window in hours")
    limit: int = Field(default=50, description="Max log entries")


@tool("get_historical_spend_data", args_schema=HistoricalSpendInput)
async def get_historical_spend_data(months: int = 6, group_by: str = "month") -> dict:
    """
    Pull historical spending data from the database for forecasting and trend analysis.
    Returns month-by-month or category-level spending data.
    Use for: 'spending history', 'historical data', 'past spend', 'trend analysis'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Expense
    from sqlalchemy import select, func, text
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(days=months * 31)

        if group_by == "category":
            result = await db.execute(
                select(Expense.category, func.sum(Expense.amount).label("total"), func.count(Expense.id).label("cnt"), Expense.currency)
                .where(Expense.org_id == ORG_ID, Expense.transaction_date >= since, Expense.category.isnot(None))
                .group_by(Expense.category, Expense.currency)
                .order_by(text("total DESC"))
            )
            rows = result.all()
            return {
                "group_by": "category",
                "months": months,
                "data": [{"category": r.category, "currency": r.currency, "total": float(r.total or 0), "count": r.cnt} for r in rows],
            }
        else:
            result = await db.execute(
                select(func.date_trunc("month", Expense.transaction_date).label("month"), func.sum(Expense.amount).label("total"), Expense.currency)
                .where(Expense.org_id == ORG_ID, Expense.transaction_date >= since)
                .group_by(text("month"), Expense.currency)
                .order_by(text("month"))
            )
            rows = result.all()
            return {
                "group_by": "month",
                "months": months,
                "data": [{"month": r.month.strftime("%Y-%m") if r.month else "Unknown", "currency": r.currency, "total": float(r.total or 0)} for r in rows],
            }


@tool("analyze_category_trend", args_schema=CategoryTrendInput)
async def analyze_category_trend(category: str, months: int = 6) -> dict:
    """
    Analyze the spending trend for a specific expense category over time.
    Shows month-by-month change and whether spending is growing or declining.
    Use for: 'is cloud spend growing?', 'SaaS trend', 'category forecast', 'category growth rate'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Expense
    from sqlalchemy import select, func, text
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(days=months * 31)
        result = await db.execute(
            select(func.date_trunc("month", Expense.transaction_date).label("month"), func.sum(Expense.amount).label("total"), func.count(Expense.id).label("cnt"))
            .where(Expense.org_id == ORG_ID, Expense.transaction_date >= since, Expense.category.ilike(f"%{category}%"))
            .group_by(text("month"))
            .order_by(text("month"))
        )
        rows = result.all()
        trend = [{"month": r.month.strftime("%Y-%m") if r.month else "Unknown", "total": float(r.total or 0), "count": r.cnt} for r in rows]

        # Calculate growth
        if len(trend) >= 2:
            first_val = trend[0]["total"]
            last_val = trend[-1]["total"]
            total_growth = ((last_val - first_val) / max(first_val, 1)) * 100
            trend_direction = "growing" if total_growth > 5 else "declining" if total_growth < -5 else "stable"
        else:
            total_growth = 0
            trend_direction = "insufficient_data"

        return {
            "category": category,
            "months": months,
            "trend_direction": trend_direction,
            "total_growth_pct": round(total_growth, 1),
            "monthly_data": trend,
            "avg_monthly_spend": round(sum(d["total"] for d in trend) / max(len(trend), 1), 2),
        }


@tool("get_financial_dashboard_snapshot", args_schema=DashboardSummaryInput)
async def get_financial_dashboard_snapshot(days: int = 30) -> dict:
    """
    Get a comprehensive financial snapshot combining expenses, invoices, approvals, and anomalies.
    Perfect for executive summaries and financial health assessments.
    Use for: 'financial summary', 'dashboard overview', 'how is the company doing?', 'health check'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Expense, Invoice, Approval, Vendor
    from sqlalchemy import select, func
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(days=days)

        # Spend summary
        spend = await db.execute(
            select(Expense.currency, func.sum(Expense.amount).label("total_amt"), func.count(Expense.id).label("cnt"))
            .where(Expense.org_id == ORG_ID, Expense.transaction_date >= since)
            .group_by(Expense.currency)
        )
        spend_by_currency = [{"currency": r.currency, "total": float(r.total_amt or 0), "count": r.cnt} for r in spend.all()]

        # Anomalies
        anomaly_cnt = (await db.execute(select(func.count(Expense.id)).where(Expense.org_id == ORG_ID, Expense.is_anomaly == True, Expense.transaction_date >= since))).scalar_one_or_none() or 0

        # Pending approvals
        pending_cnt = (await db.execute(select(func.count(Approval.id)).where(Approval.org_id == ORG_ID, Approval.status == "pending"))).scalar_one_or_none() or 0

        # Invoice counts
        inv_result = await db.execute(
            select(Invoice.status, func.count(Invoice.id).label("c"))
            .where(Invoice.org_id == ORG_ID)
            .group_by(Invoice.status)
        )
        invoices_by_status = {r.status: r.c for r in inv_result.all()}

        # High-risk vendors
        hr_vendors = (await db.execute(select(func.count(Vendor.id)).where(Vendor.org_id == ORG_ID, Vendor.risk_level.in_(["high", "critical"])))).scalar_one_or_none() or 0

        return {
            "period_days": days,
            "spend_by_currency": spend_by_currency,
            "anomaly_count": anomaly_cnt,
            "pending_approvals": pending_cnt,
            "invoices_by_status": invoices_by_status,
            "high_risk_vendors": hr_vendors,
            "snapshot_time": datetime.utcnow().isoformat(),
        }


@tool("get_agent_activity_logs", args_schema=AgentActivityInput)
async def get_agent_activity_logs(hours: int = 24, limit: int = 50) -> dict:
    """
    Get recent AI agent activity logs showing what agents have been doing.
    Returns tool calls, models used, and performance metrics.
    Use for: 'agent activity', 'what have agents done?', 'AI logs', 'system activity'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import AgentLog, AgentToolLog
    from sqlalchemy import select, desc
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(hours=hours)

        logs_result = await db.execute(
            select(AgentLog).where(AgentLog.org_id == ORG_ID, AgentLog.created_at >= since)
            .order_by(desc(AgentLog.created_at)).limit(limit)
        )
        logs = logs_result.scalars().all()

        tool_logs_result = await db.execute(
            select(AgentToolLog).where(AgentToolLog.org_id == ORG_ID, AgentToolLog.created_at >= since)
            .order_by(desc(AgentToolLog.created_at)).limit(limit)
        )
        tool_logs = tool_logs_result.scalars().all()

        return {
            "period_hours": hours,
            "agent_invocations": len(logs),
            "tool_calls": len(tool_logs),
            "agent_logs": [
                {"agent": l.agent_name, "action": l.action, "status": l.status, "duration_ms": l.duration_ms, "tokens": l.tokens_used, "time": l.created_at.isoformat()}
                for l in logs
            ],
            "tool_call_logs": [
                {"agent": t.agent_name, "tool": t.tool_name, "status": t.status, "duration_ms": t.duration_ms, "time": t.created_at.isoformat(), "input": t.input_summary, "output": t.output_summary}
                for t in tool_logs
            ],
        }


FORECASTING_TOOLS = [get_historical_spend_data, analyze_category_trend, get_financial_dashboard_snapshot, get_agent_activity_logs]
