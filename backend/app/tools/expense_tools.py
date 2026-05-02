"""
Expense Tools — LangChain tools for the Expense Intelligence Agent.
Each tool queries the real Postgres database.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field


# ── Input schemas ────────────────────────────────────────────────────────────

class QueryExpensesInput(BaseModel):
    days: int = Field(default=30, description="Number of past days to query (e.g. 30, 60, 90)")
    currency: Optional[str] = Field(default=None, description="Filter by currency: USD, INR, EUR, GBP")
    category: Optional[str] = Field(default=None, description="Filter by expense category")
    limit: int = Field(default=20, description="Max rows to return")


class GetAnomaliesInput(BaseModel):
    days: int = Field(default=30, description="Look-back window in days")
    min_score: float = Field(default=0.5, description="Minimum anomaly score 0-1")


class CategorySummaryInput(BaseModel):
    days: int = Field(default=90, description="Look-back window in days")
    currency: Optional[str] = Field(default="USD", description="Currency to aggregate")


class SubscriptionInput(BaseModel):
    days: int = Field(default=90, description="Look-back window for recurring charges")


# ── Tool implementations ──────────────────────────────────────────────────────

@tool("query_expenses", args_schema=QueryExpensesInput)
async def query_expenses(days: int = 30, currency: Optional[str] = None, category: Optional[str] = None, limit: int = 20) -> dict:
    """
    Query recent expense transactions from the database.
    Returns actual expense records with amount, category, vendor, department.
    Use this to answer: 'how much did we spend?', 'show me expenses', 'what did we buy?'
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Expense
    from sqlalchemy import select, desc
    from app.core.context import org_id_var
    ORG_ID = org_id_var.get()

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(days=days)
        q = select(Expense).where(Expense.org_id == ORG_ID, Expense.transaction_date >= since)
        if currency:
            q = q.where(Expense.currency == currency.upper())
        if category:
            q = q.where(Expense.category.ilike(f"%{category}%"))
        q = q.order_by(desc(Expense.amount)).limit(limit)

        result = await db.execute(q)
        expenses = result.scalars().all()

        return {
            "count": len(expenses),
            "period_days": days,
            "expenses": [
                {
                    "id": e.id,
                    "description": e.description,
                    "amount": float(e.amount),
                    "currency": e.currency,
                    "category": e.category,
                    "department": e.department,
                    "vendor": e.vendor_name,
                    "date": e.transaction_date.isoformat() if e.transaction_date else None,
                    "is_anomaly": e.is_anomaly,
                    "is_recurring": e.is_recurring,
                    "status": e.status,
                }
                for e in expenses
            ],
        }


@tool("get_anomalous_expenses", args_schema=GetAnomaliesInput)
async def get_anomalous_expenses(days: int = 30, min_score: float = 0.5) -> dict:
    """
    Retrieve expenses flagged as anomalous by the AI detection system.
    Returns anomalies sorted by severity score (highest first).
    Use this when asked about: unusual spending, fraud, suspicious charges, spend spikes.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Expense
    from sqlalchemy import select, desc
    from app.core.context import org_id_var
    ORG_ID = org_id_var.get()

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(Expense)
            .where(
                Expense.org_id == ORG_ID,
                Expense.is_anomaly == True,
                Expense.transaction_date >= since,
                Expense.anomaly_score >= min_score,
            )
            .order_by(desc(Expense.anomaly_score))
            .limit(20)
        )
        anomalies = result.scalars().all()

        total_flagged_amount = sum(float(a.amount) for a in anomalies)
        return {
            "total_anomalies": len(anomalies),
            "total_flagged_amount": total_flagged_amount,
            "period_days": days,
            "anomalies": [
                {
                    "description": a.description,
                    "amount": float(a.amount),
                    "currency": a.currency,
                    "category": a.category,
                    "vendor": a.vendor_name,
                    "anomaly_score": float(a.anomaly_score or 0),
                    "reason": a.anomaly_reason,
                    "date": a.transaction_date.isoformat() if a.transaction_date else None,
                }
                for a in anomalies
            ],
        }


@tool("get_category_spend_summary", args_schema=CategorySummaryInput)
async def get_category_spend_summary(days: int = 90, currency: Optional[str] = "USD") -> dict:
    """
    Summarize total spending broken down by expense category for a given period.
    Returns category totals, percentages, and trend direction.
    Use this when asked about: category breakdown, top spending areas, where money goes.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Expense
    from sqlalchemy import select, func, desc
    from app.core.context import org_id_var
    ORG_ID = org_id_var.get()

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(days=days)
        q = (
            select(Expense.category, func.sum(Expense.amount).label("total"), func.count(Expense.id).label("cnt"))
            .where(Expense.org_id == ORG_ID, Expense.transaction_date >= since, Expense.category.isnot(None))
        )
        if currency:
            q = q.where(Expense.currency == currency.upper())
        q = q.group_by(Expense.category).order_by(desc(func.sum(Expense.amount)))

        result = await db.execute(q)
        rows = result.all()

        grand_total = sum(float(r.total or 0) for r in rows)
        return {
            "period_days": days,
            "currency": currency,
            "grand_total": grand_total,
            "categories": [
                {
                    "category": r.category,
                    "total": float(r.total or 0),
                    "count": r.cnt,
                    "percentage": round(float(r.total or 0) / grand_total * 100, 1) if grand_total > 0 else 0,
                }
                for r in rows
            ],
        }


@tool("get_recurring_subscriptions", args_schema=SubscriptionInput)
async def get_recurring_subscriptions(days: int = 90) -> dict:
    """
    Find recurring/subscription expenses grouped by vendor.
    Identifies duplicate SaaS tools and total subscription burn.
    Use this when asked about: subscriptions, SaaS spend, recurring costs, duplicates.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Expense
    from sqlalchemy import select, func, desc
    from app.core.context import org_id_var
    ORG_ID = org_id_var.get()

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(
                Expense.vendor_name,
                Expense.category,
                Expense.currency,
                func.count(Expense.id).label("occurrences"),
                func.sum(Expense.amount).label("total"),
                func.avg(Expense.amount).label("avg_charge"),
            )
            .where(Expense.org_id == ORG_ID, Expense.is_recurring == True, Expense.transaction_date >= since)
            .group_by(Expense.vendor_name, Expense.category, Expense.currency)
            .order_by(desc(func.sum(Expense.amount)))
            .limit(25)
        )
        rows = result.all()

        total_recurring = sum(float(r.total or 0) for r in rows if r.currency == "USD")
        return {
            "total_recurring_usd": total_recurring,
            "subscription_count": len(rows),
            "subscriptions": [
                {
                    "vendor": r.vendor_name,
                    "category": r.category,
                    "currency": r.currency,
                    "occurrences": r.occurrences,
                    "total": float(r.total or 0),
                    "avg_charge": round(float(r.avg_charge or 0), 2),
                }
                for r in rows
            ],
        }


# ── Tool registry ─────────────────────────────────────────────────────────────

EXPENSE_TOOLS = [
    query_expenses,
    get_anomalous_expenses,
    get_category_spend_summary,
    get_recurring_subscriptions,
]
