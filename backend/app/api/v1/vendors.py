"""
Vendors API — full CRUD with Qdrant semantic indexing on create/update.
Redis-cached list endpoint.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.redis_client import cache, TTL_VENDOR_LIST
from app.core.vector_store import vector_store
from app.core.fx import fx_service
from app.models.models import Vendor, Invoice, Expense, Organization
from app.api.deps import get_org_id
from app.agents.vendor_agent import vendor_agent
from app.agents.insight_agent import insight_agent

router = APIRouter()


class VendorCreate(BaseModel):
    name: str
    email: Optional[str] = None
    category: Optional[str] = None
    website: Optional[str] = None
    payment_currency: str = "USD"


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    category: Optional[str] = None
    is_verified: Optional[bool] = None
    risk_level: Optional[str] = None


@router.get("/")
async def list_vendors(
    category: Optional[str] = None,
    risk_level: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """List all vendors. Cached 5 min."""
    cache_key = f"{org_id}:{category}:{risk_level}:{limit}"
    cached = await cache.get("vendors", cache_key)
    if cached:
        return cached

    # Get organization default currency and FX rates
    org_res = await db.execute(select(Organization.default_currency).where(Organization.id == org_id))
    base_currency = org_res.scalar_one_or_none() or "USD"
    rates = await fx_service.get_rates(base_currency)

    # Get base vendor list
    q = select(Vendor).where(Vendor.org_id == org_id).limit(limit)
    if category:
        q = q.where(Vendor.category == category)
    if risk_level:
        q = q.where(Vendor.risk_level == risk_level)
    
    result = await db.execute(q)
    rows = result.scalars().all()

    # 1. Invoices
    q_inv = (
        select(Vendor.id, Invoice.currency, func.sum(Invoice.total_amount).label("curr_total"))
        .join(Invoice, Invoice.vendor_id == Vendor.id)
        .where(Vendor.org_id == org_id, Invoice.status == "paid")
        .group_by(Vendor.id, Invoice.currency)
    )
    res_inv = await db.execute(q_inv)
    
    # 2. Expenses — exclude auto-created payment audit records (already counted as invoices)
    from sqlalchemy import or_
    q_exp = (
        select(Vendor.id, Expense.currency, func.sum(Expense.amount).label("curr_total"))
        .join(Expense, Expense.vendor_id == Vendor.id)
        .where(
            Expense.org_id == org_id,
            ~Expense.description.ilike("Paid via Payment Link%"),
            ~Expense.description.ilike("Paid Invoice:%"),
        )
        .group_by(Vendor.id, Expense.currency)
    )
    res_exp = await db.execute(q_exp)
    
    vendor_currency_map = {} # vendor_id -> consolidated_total_base
    
    for v_id, curr, total in res_inv.all():
        amt_base = fx_service.convert(float(total or 0), curr, base_currency, rates)
        vendor_currency_map[v_id] = vendor_currency_map.get(v_id, 0) + amt_base

    for v_id, curr, total in res_exp.all():
        amt_base = fx_service.convert(float(total or 0), curr, base_currency, rates)
        vendor_currency_map[v_id] = vendor_currency_map.get(v_id, 0) + amt_base

    vendors = []
    for vendor in rows:
        v_dict = _vendor_to_dict(vendor)
        if vendor.id in vendor_currency_map:
            v_dict["total_paid"] = vendor_currency_map[vendor.id]
        else:
            v_dict["total_paid"] = fx_service.convert(float(vendor.total_paid or 0), vendor.payment_currency, base_currency, rates)
        vendors.append(v_dict)
    
    # Sort by total_paid desc
    vendors.sort(key=lambda x: x["total_paid"], reverse=True)

    # Get organization default currency
    org_res = await db.execute(select(Organization.default_currency).where(Organization.id == org_id))
    base_currency = org_res.scalar_one_or_none() or "USD"

    response = {
        "vendors": vendors,
        "total": len(vendors),
        "base_currency": base_currency,
    }
    await cache.set("vendors", response, TTL_VENDOR_LIST, cache_key)
    return response


@router.post("/")
async def create_vendor(
    body: VendorCreate,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Create vendor or return existing one if name already exists (dedup)."""
    from app.core.vendor_utils import find_or_create_vendor

    vendor, created = await find_or_create_vendor(
        db=db,
        org_id=org_id,
        name=body.name,
        email=body.email,
        category=body.category,
        payment_currency=body.payment_currency or "USD",
        website=body.website,
    )
    await db.commit()

    if not created:
        await cache.invalidate_pattern("vendors")
        return {**_vendor_to_dict(vendor), "_existing": True, "_message": f"Vendor '{vendor.name}' already exists — returned existing record."}

    await cache.invalidate_pattern("vendors")
    return _vendor_to_dict(vendor)



@router.get("/{vendor_id}")
async def get_vendor(
    vendor_id: str,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
    health_check: bool = False,
):
    vendor = await db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Invoice history (paid invoices only)
    inv_result = await db.execute(
        select(func.count(Invoice.id), func.sum(Invoice.total_amount), Invoice.currency)
        .where(Invoice.vendor_id == vendor_id, Invoice.status == "paid")
        .group_by(Invoice.currency)
    )
    invoice_stats = [
        {"currency": r[2], "count": r[0], "total": float(r[1] or 0)}
        for r in inv_result.all()
    ]

    result = {**_vendor_to_dict(vendor), "invoice_stats": invoice_stats}

    if health_check:
        # ── vendor_agent.assess_vendor_health() + insight_agent.analyze_vendor_health() ──
        try:
            exp_result = await db.execute(
                select(Invoice.total_amount, Invoice.currency, Invoice.status, Invoice.created_at)
                .where(Invoice.vendor_id == vendor_id)
                .order_by(Invoice.created_at.desc())
                .limit(20)
            )
            tx_history = [
                {"amount": float(r[0] or 0), "currency": r[1], "status": r[2]}
                for r in exp_result.all()
            ]
            vendor_data = _vendor_to_dict(vendor)

            # vendor_agent health (rule-based + AI scoring)
            health = await vendor_agent.assess_vendor_health(vendor_data, tx_history)
            result["vendor_health"] = health

            # insight_agent deep analysis
            deep = await insight_agent.analyze_vendor_health(vendor_data, tx_history)
            result["health_analysis"] = deep
        except Exception:
            result["vendor_health"] = None
            result["health_analysis"] = None

    return result


@router.patch("/{vendor_id}")
async def update_vendor(vendor_id: str, body: VendorUpdate, db: AsyncSession = Depends(get_db)):
    vendor = await db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(vendor, field, value)
    vendor.updated_at = datetime.utcnow()
    await db.commit()
    await cache.invalidate_pattern("vendors")
    return _vendor_to_dict(vendor)


@router.get("/search/semantic")
async def semantic_vendor_search(
    q: str,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Semantic vendor search via Qdrant embeddings."""
    embedding = await model_router.embed(q)
    matches = await vector_store.find_similar_vendors(
        embedding=embedding,
        org_id=org_id,
        threshold=0.25,
        limit=10,
    )
    return {"query": q, "matches": matches}


def _vendor_to_dict(v: Vendor) -> dict:
    meta: dict = v.extra_metadata or {}
    return {
        "id": v.id,
        "name": v.name,
        "email": v.email,
        "category": v.category,
        "website": meta.get("website"),
        "risk_level": v.risk_level,
        "risk_score": float(v.risk_score or 0),
        "is_verified": v.is_verified,
        "is_active": v.is_active,
        "total_paid": float(v.total_paid or 0),
        "payment_currency": v.payment_currency,
        "created_at": v.created_at.isoformat(),
        # Bank details saved during approval modal
        "bank_details": {
            "account_name": meta.get("bank_account_name"),
            "account_number": meta.get("bank_account_number"),
            "ifsc_code": meta.get("bank_ifsc_code"),
        } if any([meta.get("bank_account_name"), meta.get("bank_account_number"), meta.get("bank_ifsc_code")]) else None,
    }
