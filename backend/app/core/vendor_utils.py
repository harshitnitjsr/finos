"""
Centralized vendor find-or-create utility.
All vendor creation paths (invoice upload, expense categorization, vendor form)
must go through this function to prevent duplicates.

Dedup strategy (in priority order):
1. Case-insensitive exact name match in SQL (fastest, catches same-name vendors)
2. Qdrant semantic similarity match above threshold (catches "AWS" vs "Amazon Web Services")
3. Create new if no match found
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from app.models.models import Vendor


async def find_or_create_vendor(
    *,
    db: AsyncSession,
    org_id: str,
    name: str,
    email: str | None = None,
    category: str | None = None,
    payment_currency: str = "USD",
    website: str | None = None,
    semantic_threshold: float = 0.88,
) -> tuple[Vendor, bool]:
    """
    Find an existing vendor by name (case-insensitive) or semantic similarity,
    or create a new one if none found.

    Returns:
        (vendor, created) — created=True if a new vendor was inserted.
    """
    name = name.strip()
    if not name:
        raise ValueError("Vendor name cannot be empty")

    # ── Step 1: Case-insensitive exact SQL match ──────────────────────────────
    result = await db.execute(
        select(Vendor).where(
            Vendor.org_id == org_id,
            Vendor.name.ilike(name),
        ).limit(1)
    )
    vendor = result.scalar_one_or_none()
    if vendor:
        logger.info(f"[find_or_create_vendor] Exact match: '{vendor.name}' (id={vendor.id})")
        _merge_details(vendor, email=email, category=category, website=website)
        return vendor, False

    # ── Step 2: Partial/fuzzy SQL match (e.g. "AWS" inside "Amazon Web Services") ──
    result = await db.execute(
        select(Vendor).where(
            Vendor.org_id == org_id,
            Vendor.name.ilike(f"%{name[:40]}%"),
        ).limit(1)
    )
    vendor = result.scalar_one_or_none()
    if vendor:
        logger.info(f"[find_or_create_vendor] Partial match: '{vendor.name}' (id={vendor.id})")
        _merge_details(vendor, email=email, category=category, website=website)
        return vendor, False

    # ── Step 3: Qdrant semantic match ─────────────────────────────────────────
    try:
        from app.core.vector_store import vector_store
        from app.core.model_router import model_router

        embedding = await model_router.embed(f"{name} {category or ''} {payment_currency}")
        if embedding:
            similar = await vector_store.find_similar_vendors(
                embedding=embedding,
                org_id=org_id,
                threshold=semantic_threshold,
                limit=1,
            )
            if similar:
                matched_id = similar[0].get("vendor_id")
                if matched_id:
                    vendor = await db.get(Vendor, matched_id)
                    # CRITICAL: verify vendor belongs to the same org
                    if vendor and vendor.org_id == org_id:
                        logger.info(
                            f"[find_or_create_vendor] Semantic match: '{vendor.name}' "
                            f"(id={vendor.id}, score={similar[0].get('score', 0):.3f})"
                        )
                        _merge_details(vendor, email=email, category=category, website=website)
                        return vendor, False
                    elif vendor:
                        logger.warning(
                            f"[find_or_create_vendor] Qdrant returned cross-org vendor '{vendor.name}' "
                            f"(org={vendor.org_id} != expected={org_id}) — ignoring"
                        )
    except Exception as e:
        logger.warning(f"[find_or_create_vendor] Qdrant lookup failed (non-critical): {e}")

    # ── Step 4: Create new vendor ─────────────────────────────────────────────
    meta = {}
    if website:
        meta["website"] = website

    vendor = Vendor(
        org_id=org_id,
        name=name,
        email=email,
        category=category,
        payment_currency=payment_currency,
        risk_level="low",
        risk_score=20.0,
        is_active=True,
        extra_metadata=meta,
    )
    db.add(vendor)
    await db.flush()  # get vendor.id without committing

    # Index in Qdrant
    try:
        from app.core.vector_store import vector_store
        from app.core.model_router import model_router

        embedding = await model_router.embed(f"{name} {category or ''} {payment_currency}")
        await vector_store.upsert_vendor(
            vendor_id=str(vendor.id),
            embedding=embedding,
            payload={
                "org_id": org_id,
                "name": name,
                "category": category or "",
                "risk_level": "low",
                "risk_score": 20.0,
                "is_verified": False,
            },
        )
    except Exception as e:
        logger.warning(f"[find_or_create_vendor] Qdrant upsert failed (non-critical): {e}")

    logger.info(f"[find_or_create_vendor] Created new vendor: '{name}' (id={vendor.id})")
    return vendor, True


def _merge_details(vendor: Vendor, *, email: str | None, category: str | None, website: str | None):
    """Fill in missing details on an existing vendor without overwriting set values."""
    if email and not vendor.email:
        vendor.email = email
    if category and not vendor.category:
        vendor.category = category
    if website:
        meta = dict(vendor.extra_metadata or {})
        if not meta.get("website"):
            meta["website"] = website
            vendor.extra_metadata = meta
