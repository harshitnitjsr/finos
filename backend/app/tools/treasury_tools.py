"""
Treasury Tools — LangChain tools for the Treasury Agent.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class BurnRateInput(BaseModel):
    days: int = Field(default=30, description="Window to calculate burn rate (30, 60, 90)")
    currency: str = Field(default="USD", description="Currency for burn calculation")


class UpcomingPaymentsInput(BaseModel):
    days_ahead: int = Field(default=30, description="How many days forward to look")


class MonthlyTrendInput(BaseModel):
    months: int = Field(default=6, description="Number of past months for trend data")
    currency: str = Field(default="USD", description="Currency to aggregate")


class RunwayInput(BaseModel):
    cash_on_hand: float = Field(default=1200000.0, description="Current cash balance in USD")


@tool("get_burn_rate", args_schema=BurnRateInput)
async def get_burn_rate(days: int = 30, currency: str = "USD") -> dict:
    """
    Calculate the company's actual burn rate from real expense data.
    Returns daily, monthly, and annualized burn rate with top burning categories.
    Use for: 'burn rate', 'how fast are we spending?', 'monthly spend', 'cash burn'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Expense
    from sqlalchemy import select, func, desc
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(days=days)
        total_result = await db.execute(
            select(func.sum(Expense.amount).label("total"), func.count(Expense.id).label("cnt"))
            .where(Expense.org_id == ORG_ID, Expense.transaction_date >= since, Expense.currency == currency.upper())
        )
        row = total_result.one()
        total = float(row.total or 0)
        cnt = int(row.cnt or 0)

        # Top categories
        cat_result = await db.execute(
            select(Expense.category, func.sum(Expense.amount).label("total"))
            .where(Expense.org_id == ORG_ID, Expense.transaction_date >= since, Expense.currency == currency.upper(), Expense.category.isnot(None))
            .group_by(Expense.category).order_by(desc(func.sum(Expense.amount))).limit(5)
        )
        top_cats = [{"category": r.category, "total": float(r.total or 0)} for r in cat_result.all()]

        daily_burn = total / max(days, 1)
        monthly_burn = daily_burn * 30

        return {
            "currency": currency.upper(),
            "period_days": days,
            "total_spend": total,
            "transaction_count": cnt,
            "daily_burn_rate": round(daily_burn, 2),
            "monthly_burn_rate": round(monthly_burn, 2),
            "annualized_burn_rate": round(daily_burn * 365, 2),
            "top_burn_categories": top_cats,
        }


@tool("get_upcoming_payments", args_schema=UpcomingPaymentsInput)
async def get_upcoming_payments(days_ahead: int = 30) -> dict:
    """
    Get all invoices due for payment in the next N days.
    Shows total cash required and prioritized payment schedule.
    Use for: 'upcoming payments', 'what do we owe?', 'cash requirements', 'payment schedule'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Invoice, Vendor
    from sqlalchemy import select, desc
    ORG_ID = "org_demo_001"

    now = datetime.utcnow()
    deadline = now + timedelta(days=days_ahead)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Invoice, Vendor.name.label("vendor_name"))
            .join(Vendor, Invoice.vendor_id == Vendor.id, isouter=True)
            .where(
                Invoice.org_id == ORG_ID,
                Invoice.due_date.isnot(None),
                Invoice.due_date <= deadline,
                Invoice.status.notin_(["paid", "rejected"]),
            )
            .order_by(Invoice.due_date)
            .limit(20)
        )
        rows = result.all()

        by_currency: dict = {}
        for r in rows:
            cur = r[0].currency
            amt = float(r[0].total_amount)
            by_currency[cur] = by_currency.get(cur, 0) + amt

        return {
            "period_days": days_ahead,
            "payment_count": len(rows),
            "total_by_currency": by_currency,
            "payments": [
                {
                    "invoice_number": r[0].invoice_number,
                    "vendor": r.vendor_name or "Unknown",
                    "amount": float(r[0].total_amount),
                    "currency": r[0].currency,
                    "due_date": r[0].due_date.isoformat() if r[0].due_date else None,
                    "days_until_due": (r[0].due_date - now).days if r[0].due_date else None,
                    "status": r[0].status,
                    "risk_level": r[0].risk_level,
                    "priority": "HIGH" if (r[0].due_date and (r[0].due_date - now).days <= 3) else "MEDIUM" if (r[0].due_date and (r[0].due_date - now).days <= 7) else "NORMAL",
                }
                for r in rows
            ],
        }


@tool("get_monthly_spend_trend", args_schema=MonthlyTrendInput)
async def get_monthly_spend_trend(months: int = 6, currency: str = "USD") -> dict:
    """
    Get month-by-month spending trend for the past N months.
    Useful for identifying growth patterns, seasonal effects, and forecasting.
    Use for: 'spending trend', 'monthly history', 'are we spending more?', 'growth rate'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Expense
    from sqlalchemy import select, func, text
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(days=months * 31)
        result = await db.execute(
            select(
                func.date_trunc("month", Expense.transaction_date).label("month"),
                func.sum(Expense.amount).label("total"),
                func.count(Expense.id).label("cnt"),
            )
            .where(Expense.org_id == ORG_ID, Expense.transaction_date >= since, Expense.currency == currency.upper())
            .group_by(text("month"))
            .order_by(text("month"))
        )
        rows = result.all()

        trend_data = [
            {"month": r.month.strftime("%Y-%m") if r.month else "Unknown", "total": float(r.total or 0), "count": r.cnt}
            for r in rows
        ]

        # Calculate MoM growth
        for i in range(1, len(trend_data)):
            prev = trend_data[i - 1]["total"]
            curr = trend_data[i]["total"]
            trend_data[i]["mom_change_pct"] = round((curr - prev) / max(prev, 1) * 100, 1)

        avg_monthly = sum(d["total"] for d in trend_data) / max(len(trend_data), 1)
        return {"currency": currency.upper(), "months": months, "average_monthly": round(avg_monthly, 2), "trend": trend_data}


@tool("calculate_runway", args_schema=RunwayInput)
async def calculate_runway(cash_on_hand: float = 1200000.0) -> dict:
    """
    Calculate company runway based on current burn rate and cash on hand.
    Returns months of runway and key risk milestones.
    Use for: 'how long is our runway?', 'when do we run out of money?', 'cash runway'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Expense
    from sqlalchemy import select, func
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        # 3-month average burn
        since_3m = datetime.utcnow() - timedelta(days=90)
        result = await db.execute(
            select(func.sum(Expense.amount).label("total"))
            .where(Expense.org_id == ORG_ID, Expense.transaction_date >= since_3m, Expense.currency == "USD")
        )
        total_3m = float((result.scalar_one_or_none()) or 0)
        monthly_burn = total_3m / 3

        runway_months = cash_on_hand / max(monthly_burn, 1)
        runway_days = int(runway_months * 30)
        runway_date = datetime.utcnow() + timedelta(days=runway_days)

        return {
            "cash_on_hand_usd": cash_on_hand,
            "monthly_burn_rate_usd": round(monthly_burn, 2),
            "runway_months": round(runway_months, 1),
            "runway_days": runway_days,
            "projected_zero_date": runway_date.strftime("%Y-%m-%d"),
            "health": "excellent" if runway_months > 18 else "healthy" if runway_months > 12 else "warning" if runway_months > 6 else "critical",
            "milestones": {
                "6_months": (datetime.utcnow() + timedelta(days=180)).strftime("%Y-%m-%d"),
                "12_months": (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d"),
            },
        }


TREASURY_TOOLS = [get_burn_rate, get_upcoming_payments, get_monthly_spend_trend, calculate_runway]
