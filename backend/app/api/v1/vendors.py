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
from app.core.model_router import model_router
from app.models.models import Vendor, Invoice, Expense
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

    q = (
        select(Vendor)
        .where(Vendor.org_id == org_id)
        .order_by(desc(Vendor.total_paid))
        .limit(limit)
    )
    if category:
        q = q.where(Vendor.category == category)
    if risk_level:
        q = q.where(Vendor.risk_level == risk_level)

    result = await db.execute(q)
    vendors = result.scalars().all()

    response = {
        "vendors": [_vendor_to_dict(v) for v in vendors],
        "total": len(vendors),
    }
    await cache.set("vendors", response, TTL_VENDOR_LIST, cache_key)
    return response


@router.post("/")
async def create_vendor(
    body: VendorCreate,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Create vendor and index in Qdrant."""
    vendor = Vendor(
        org_id=org_id,
        name=body.name,
        email=body.email,
        category=body.category,
        payment_currency=body.payment_currency,
        risk_level="low",
        risk_score=10.0,
        is_active=True,
        extra_metadata={"website": body.website} if body.website else {},
    )
    db.add(vendor)
    await db.flush()

    embed_text = f"{body.name} {body.category or ''} {body.payment_currency}"
    embedding = await model_router.embed(embed_text)
    await vector_store.upsert_vendor(
        vendor_id=str(vendor.id),
        embedding=embedding,
        payload={
            "org_id": org_id,
            "name": body.name,
            "category": body.category or "",
            "risk_level": "low",
            "risk_score": 10.0,
            "is_verified": False,
        },
    )

    await db.commit()
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

    # Invoice history
    inv_result = await db.execute(
        select(func.count(Invoice.id), func.sum(Invoice.total_amount), Invoice.currency)
        .where(Invoice.vendor_id == vendor_id)
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
        threshold=0.75,
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
        "website": meta.get("website"),          # stored in extra_metadata, not a column
        "risk_level": v.risk_level,
        "risk_score": float(v.risk_score or 0),
        "is_verified": v.is_verified,
        "is_active": v.is_active,
        "total_paid": float(v.total_paid or 0),
        "payment_currency": v.payment_currency,
        "created_at": v.created_at.isoformat(),
    }
