"""
Vendor Tools — LangChain tools for the Vendor Intelligence Agent.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class VendorQueryInput(BaseModel):
    risk_level: Optional[str] = Field(default=None, description="Filter by risk: low, medium, high, critical")
    category: Optional[str] = Field(default=None, description="Filter by vendor category")
    limit: int = Field(default=20, description="Max results")


class VendorSearchInput(BaseModel):
    name: str = Field(description="Vendor name to search (partial match supported)")


class VendorRiskInput(BaseModel):
    min_risk_score: float = Field(default=50.0, description="Minimum risk score threshold (0-100)")


@tool("query_vendors", args_schema=VendorQueryInput)
async def query_vendors(risk_level: Optional[str] = None, category: Optional[str] = None, limit: int = 20) -> dict:
    """
    Query vendors from the database with optional filters.
    Returns vendor profiles with risk scores, categories, and payment totals.
    Use for: 'list vendors', 'show suppliers', 'who do we pay?', 'vendor list'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Vendor
    from sqlalchemy import select, desc
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        q = select(Vendor).where(Vendor.org_id == ORG_ID, Vendor.is_active == True)
        if risk_level:
            q = q.where(Vendor.risk_level == risk_level.lower())
        if category:
            q = q.where(Vendor.category.ilike(f"%{category}%"))
        q = q.order_by(desc(Vendor.total_paid)).limit(limit)

        result = await db.execute(q)
        vendors = result.scalars().all()

        return {
            "count": len(vendors),
            "vendors": [
                {
                    "id": v.id,
                    "name": v.name,
                    "category": v.category,
                    "risk_level": v.risk_level,
                    "risk_score": float(v.risk_score or 0),
                    "total_paid": float(v.total_paid or 0),
                    "currency": v.payment_currency,
                    "is_verified": v.is_verified,
                }
                for v in vendors
            ],
        }


@tool("search_vendor", args_schema=VendorSearchInput)
async def search_vendor(name: str) -> dict:
    """
    Search for a specific vendor by name (supports partial matching).
    Returns full vendor profile including risk assessment and payment history.
    Use for: 'find vendor X', 'tell me about AWS', 'is Stripe verified?'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Vendor, Invoice
    from sqlalchemy import select, func, desc
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Vendor).where(Vendor.org_id == ORG_ID, Vendor.name.ilike(f"%{name}%")).limit(5)
        )
        vendors = result.scalars().all()

        if not vendors:
            return {"found": False, "search_term": name, "message": f"No vendor matching '{name}'"}

        vendor_profiles = []
        for v in vendors:
            # Get invoice count for this vendor
            inv_count = (await db.execute(
                select(func.count(Invoice.id)).where(Invoice.vendor_id == v.id)
            )).scalar_one_or_none() or 0

            vendor_profiles.append({
                "id": v.id,
                "name": v.name,
                "category": v.category,
                "risk_level": v.risk_level,
                "risk_score": float(v.risk_score or 0),
                "total_paid": float(v.total_paid or 0),
                "currency": v.payment_currency,
                "is_verified": v.is_verified,
                "is_active": v.is_active,
                "invoice_count": inv_count,
                "created_at": v.created_at.isoformat(),
            })

        return {"found": True, "count": len(vendor_profiles), "vendors": vendor_profiles}


@tool("get_high_risk_vendors", args_schema=VendorRiskInput)
async def get_high_risk_vendors(min_risk_score: float = 50.0) -> dict:
    """
    Get vendors with high risk scores that require attention or review.
    Also returns unverified vendors receiving payments above thresholds.
    Use for: 'risky vendors', 'unverified suppliers', 'vendor risk', 'dangerous vendors'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Vendor
    from sqlalchemy import select, desc
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Vendor)
            .where(Vendor.org_id == ORG_ID, Vendor.risk_score >= min_risk_score)
            .order_by(desc(Vendor.risk_score))
            .limit(20)
        )
        vendors = result.scalars().all()

        unverified_result = await db.execute(
            select(Vendor)
            .where(Vendor.org_id == ORG_ID, Vendor.is_verified == False, Vendor.total_paid > 10000)
            .order_by(desc(Vendor.total_paid))
            .limit(10)
        )
        unverified = unverified_result.scalars().all()

        return {
            "high_risk_count": len(vendors),
            "unverified_high_value_count": len(unverified),
            "high_risk_vendors": [
                {"name": v.name, "risk_score": float(v.risk_score or 0), "risk_level": v.risk_level, "total_paid": float(v.total_paid or 0), "is_verified": v.is_verified}
                for v in vendors
            ],
            "unverified_high_value": [
                {"name": v.name, "total_paid": float(v.total_paid or 0), "currency": v.payment_currency, "risk_score": float(v.risk_score or 0)}
                for v in unverified
            ],
        }


@tool("get_vendor_spend_distribution", args_schema=VendorQueryInput)
async def get_vendor_spend_distribution(risk_level: Optional[str] = None, category: Optional[str] = None, limit: int = 20) -> dict:
    """
    Get spending distribution across vendors — concentration risk analysis.
    Shows top vendors by total spend and what percentage of budget they represent.
    Use for: 'vendor concentration', 'top vendors by spend', 'where does money go by vendor'.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.models import Vendor
    from sqlalchemy import select, desc
    ORG_ID = "org_demo_001"

    async with AsyncSessionLocal() as db:
        q = select(Vendor).where(Vendor.org_id == ORG_ID, Vendor.is_active == True, Vendor.total_paid > 0)
        if category:
            q = q.where(Vendor.category.ilike(f"%{category}%"))
        q = q.order_by(desc(Vendor.total_paid)).limit(limit)

        result = await db.execute(q)
        vendors = result.scalars().all()

        total_spend = sum(float(v.total_paid or 0) for v in vendors)
        return {
            "total_vendor_spend": total_spend,
            "vendor_count": len(vendors),
            "distribution": [
                {
                    "name": v.name,
                    "category": v.category,
                    "total_paid": float(v.total_paid or 0),
                    "currency": v.payment_currency,
                    "share_pct": round(float(v.total_paid or 0) / max(total_spend, 1) * 100, 1),
                    "risk_level": v.risk_level,
                }
                for v in vendors
            ],
        }


VENDOR_TOOLS = [query_vendors, search_vendor, get_high_risk_vendors, get_vendor_spend_distribution]
