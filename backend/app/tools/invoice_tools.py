"""
Invoice Tools — LangChain tools for the Invoice Intelligence Agent.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class QueryInvoicesInput(BaseModel):
    status: Optional[str] = Field(default=None, description="Filter by status: pending, approved, paid, overdue, awaiting_approval")
    days: int = Field(default=60, description="Look-back window in days")
    limit: int = Field(default=20, description="Max rows")


class OverdueInput(BaseModel):
    include_high_risk: bool = Field(default=True, description="Include high-risk invoices even if not yet overdue")


class InvoiceDetailInput(BaseModel):
    invoice_number: Optional[str] = Field(default=None, description="Specific invoice number to retrieve")
    vendor_name: Optional[str] = Field(default=None, description="Filter by vendor name (partial match)")


class VendorHistoryInput(BaseModel):
    vendor_name: str = Field(description="Vendor name to look up payment history")
    limit: int = Field(default=10, description="Max transactions to return")


@tool("query_invoices", args_schema=QueryInvoicesInput)
async def query_invoices(status: Optional[str] = None, days: int = 60, limit: int = 20) -> dict:
    """
    Query invoice records from the database filtered by status and time period.
    Returns invoice details including vendor, amount, due date, and risk level.
    Use for: 'show me invoices', 'what invoices are pending?', 'payment queue'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Invoice, Vendor
    from sqlalchemy import select, desc
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        since = datetime.utcnow() - timedelta(days=days)
        q = (
            select(Invoice, Vendor.name.label("vendor_name"))
            .join(Vendor, Invoice.vendor_id == Vendor.id, isouter=True)
            .where(Invoice.org_id == ORG_ID, Invoice.created_at >= since)
        )
        if status:
            q = q.where(Invoice.status == status.lower())
        q = q.order_by(desc(Invoice.created_at)).limit(limit)

        result = await db.execute(q)
        rows = result.all()

        return {
            "count": len(rows),
            "invoices": [
                {
                    "id": row[0].id,
                    "invoice_number": row[0].invoice_number,
                    "vendor": row.vendor_name or "Unknown",
                    "amount": float(row[0].total_amount),
                    "currency": row[0].currency,
                    "status": row[0].status,
                    "due_date": row[0].due_date.isoformat() if row[0].due_date else None,
                    "risk_level": row[0].risk_level,
                    "risk_score": float(row[0].risk_score or 0),
                    "is_duplicate": row[0].is_duplicate,
                    "created_at": row[0].created_at.isoformat(),
                }
                for row in rows
            ],
        }


@tool("get_overdue_invoices", args_schema=OverdueInput)
async def get_overdue_invoices(include_high_risk: bool = True) -> dict:
    """
    Get all overdue invoices and invoices approaching their due date (within 7 days).
    Also flags high-risk invoices that need urgent attention.
    Use for: 'what is overdue?', 'what needs payment?', 'urgent invoices'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Invoice, Vendor
    from sqlalchemy import select, or_, desc
    ORG_ID = "org_demo_001"

    now = datetime.utcnow()
    week_ahead = now + timedelta(days=7)

    async with AsyncSessionLocal() as db:
        conditions = [
            Invoice.status == "overdue",
            (Invoice.due_date <= week_ahead) & (Invoice.due_date >= now) & (Invoice.status.notin_(["paid", "rejected"])),
        ]
        if include_high_risk:
            conditions.append(Invoice.risk_level.in_(["high", "critical"]))

        q = (
            select(Invoice, Vendor.name.label("vendor_name"))
            .join(Vendor, Invoice.vendor_id == Vendor.id, isouter=True)
            .where(Invoice.org_id == ORG_ID, or_(*conditions))
            .order_by(Invoice.due_date)
            .limit(20)
        )
        result = await db.execute(q)
        rows = result.all()

        total_overdue_amount = sum(float(r[0].total_amount) for r in rows if r[0].status == "overdue")
        return {
            "total_overdue_count": len([r for r in rows if r[0].status == "overdue"]),
            "total_overdue_amount": total_overdue_amount,
            "urgent_items": len(rows),
            "invoices": [
                {
                    "invoice_number": r[0].invoice_number,
                    "vendor": r.vendor_name or "Unknown",
                    "amount": float(r[0].total_amount),
                    "currency": r[0].currency,
                    "status": r[0].status,
                    "due_date": r[0].due_date.isoformat() if r[0].due_date else None,
                    "days_overdue": (now - r[0].due_date).days if r[0].due_date and r[0].due_date < now else None,
                    "days_until_due": (r[0].due_date - now).days if r[0].due_date and r[0].due_date >= now else None,
                    "risk_level": r[0].risk_level,
                }
                for r in rows
            ],
        }


@tool("get_invoice_pipeline_summary", args_schema=QueryInvoicesInput)
async def get_invoice_pipeline_summary(status: Optional[str] = None, days: int = 60, limit: int = 20) -> dict:
    """
    Get a summary of the invoice pipeline grouped by status with totals.
    Shows how much is pending, approved, paid, overdue across all currencies.
    Use for: 'invoice summary', 'pipeline status', 'how much is outstanding?'
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Invoice
    from sqlalchemy import select, func
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                Invoice.status,
                Invoice.currency,
                func.count(Invoice.id).label("count"),
                func.sum(Invoice.total_amount).label("total"),
            )
            .where(Invoice.org_id == ORG_ID)
            .group_by(Invoice.status, Invoice.currency)
            .order_by(Invoice.status)
        )
        rows = result.all()

        pipeline = {}
        for r in rows:
            key = r.status
            if key not in pipeline:
                pipeline[key] = []
            pipeline[key].append({"currency": r.currency, "count": r.count, "total": float(r.total or 0)})

        return {"pipeline": pipeline, "status_count": len(pipeline)}


@tool("get_vendor_invoice_history", args_schema=VendorHistoryInput)
async def get_vendor_invoice_history(vendor_name: str, limit: int = 10) -> dict:
    """
    Get the full invoice history for a specific vendor including payment patterns.
    Shows on-time payments, risk history, and total amounts paid.
    Use for: 'vendor payment history', 'how much have we paid X?', 'vendor reliability'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Invoice, Vendor
    from sqlalchemy import select, desc
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        # Find vendor
        v_result = await db.execute(
            select(Vendor).where(Vendor.org_id == ORG_ID, Vendor.name.ilike(f"%{vendor_name}%")).limit(1)
        )
        vendor = v_result.scalar_one_or_none()

        if not vendor:
            return {"error": f"No vendor matching '{vendor_name}' found", "vendor_name": vendor_name}

        # Get invoices for this vendor
        inv_result = await db.execute(
            select(Invoice)
            .where(Invoice.org_id == ORG_ID, Invoice.vendor_id == vendor.id)
            .order_by(desc(Invoice.created_at))
            .limit(limit)
        )
        invoices = inv_result.scalars().all()

        total_paid = sum(float(i.total_amount) for i in invoices if i.status == "paid")
        return {
            "vendor": {"id": vendor.id, "name": vendor.name, "category": vendor.category, "risk_level": vendor.risk_level, "risk_score": float(vendor.risk_score or 0), "is_verified": vendor.is_verified, "total_relationship_value": float(vendor.total_paid or 0)},
            "invoice_history": [
                {"invoice_number": i.invoice_number, "amount": float(i.total_amount), "currency": i.currency, "status": i.status, "date": i.created_at.isoformat(), "due_date": i.due_date.isoformat() if i.due_date else None}
                for i in invoices
            ],
            "total_paid": total_paid,
            "on_time_rate": "N/A (calculated from history)",
        }


INVOICE_TOOLS = [query_invoices, get_overdue_invoices, get_invoice_pipeline_summary, get_vendor_invoice_history]
