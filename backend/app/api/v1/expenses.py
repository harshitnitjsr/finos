"""Expenses API routes — with Redis caching + Qdrant anomaly clustering."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from loguru import logger

from app.core.database import get_db
from app.core.redis_client import cache, TTL_ANALYTICS
from app.core.vector_store import vector_store
from app.core.model_router import model_router
from app.models.models import Expense
from app.agents.expense_agent import expense_agent
from app.api.deps import get_org_id

router = APIRouter()


class ExpenseCreate(BaseModel):
    description: str
    amount: float
    currency: str = "USD"
    vendor_name: Optional[str] = None
    department: Optional[str] = None
    transaction_date: Optional[datetime] = None


class ExpenseUpdate(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None


async def categorize_expense_background(expense_id: str):
    """Background: AI categorize + embed into Qdrant + cache invalidation."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        expense = await db.get(Expense, expense_id)
        if not expense:
            return

        # Step 1: AI categorization (GPT-4o-mini)
        result = await expense_agent.categorize(
            description=expense.description,
            vendor_name=expense.vendor_name or "",
            amount=float(expense.amount),
            currency=expense.currency,
        )
        expense.category = result.get("category", "Other")
        expense.subcategory = result.get("subcategory")
        expense.department = expense.department or result.get("department")
        expense.is_recurring = result.get("is_recurring", False)
        expense.ai_category_confidence = result.get("confidence", 0.8)
        expense.status = "categorized"

        # Step 2: Anomaly detection (GPT-4o-mini — uses similar expense context)
        anomaly = await expense_agent.detect_anomaly({
            "description": expense.description,
            "amount": float(expense.amount),
            "currency": expense.currency,
            "category": expense.category,
            "vendor_name": expense.vendor_name,
        })
        expense.is_anomaly = anomaly.get("is_anomaly", False)
        expense.anomaly_score = anomaly.get("anomaly_score", 0.0)
        expense.anomaly_reason = anomaly.get("reason")
        if expense.is_anomaly:
            expense.status = "flagged"

        await db.commit()

        # Step 3: Embed and upsert into Qdrant for future anomaly clustering
        embed_text = (
            f"{expense.description} {expense.vendor_name or ''} "
            f"{expense.category or ''} {expense.currency} {float(expense.amount)}"
        )
        embedding = await model_router.embed(embed_text)
        await vector_store.upsert_expense(
            expense_id=expense_id,
            embedding=embedding,
            payload={
                "org_id": ORG_ID,
                "category": expense.category or "",
                "amount": float(expense.amount),
                "currency": expense.currency,
                "vendor_name": expense.vendor_name or "",
                "is_anomaly": expense.is_anomaly,
            },
        )

        # Step 4: Invalidate analytics caches
        await cache.invalidate_pattern("dashboard")
        await cache.invalidate_pattern("analytics")
        await cache.invalidate_pattern("category_breakdown")



@router.post("/")
async def create_expense(
    expense_in: ExpenseCreate,
    background_tasks: BackgroundTasks,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Create expense and trigger AI categorization."""
    expense = Expense(
        org_id=org_id,
        description=expense_in.description,
        amount=expense_in.amount,
        currency=expense_in.currency,
        vendor_name=expense_in.vendor_name,
        department=expense_in.department,
        transaction_date=expense_in.transaction_date or datetime.utcnow(),
        status="pending",
    )
    db.add(expense)
    await db.flush()
    expense_id = expense.id
    await db.commit()

    background_tasks.add_task(categorize_expense_background, expense_id)
    return {"id": expense_id, "status": "pending", "message": "Expense created. AI categorization queued."}


@router.get("/")
async def list_expenses(
    status: Optional[str] = None,
    category: Optional[str] = None,
    is_anomaly: Optional[bool] = None,
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"{org_id}:{status}:{category}:{is_anomaly}:{skip}:{limit}"
    cached = await cache.get("expenses", cache_key)
    if cached:
        return cached

    q = select(Expense).where(Expense.org_id == org_id).order_by(desc(Expense.transaction_date))
    if status:
        q = q.where(Expense.status == status)
    if category:
        q = q.where(Expense.category == category)
    if is_anomaly is not None:
        q = q.where(Expense.is_anomaly == is_anomaly)
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    expenses = result.scalars().all()

    total_q = select(func.count(Expense.id)).where(Expense.org_id == org_id)
    total = (await db.execute(total_q)).scalar_one_or_none() or 0

    response = {"expenses": [_expense_to_dict(e) for e in expenses], "total": total}
    await cache.set("expenses", response, 30, cache_key)
    return response


@router.get("/analytics/by-category")
async def expenses_by_category(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            Expense.category,
            Expense.currency,
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count"),
        ).where(Expense.org_id == org_id).group_by(Expense.category, Expense.currency)
    )
    rows = result.all()
    return {"data": [{"category": r.category or "Uncategorized", "currency": r.currency, "total": float(r.total or 0), "count": r.count} for r in rows]}


@router.get("/analytics/anomalies")
async def get_anomalies(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Expense).where(
            Expense.org_id == org_id,
            Expense.is_anomaly == True
        ).order_by(desc(Expense.anomaly_score)).limit(20)
    )
    expenses = result.scalars().all()
    return {"anomalies": [_expense_to_dict(e) for e in expenses]}


@router.post("/analyze/subscriptions")
async def analyze_subscriptions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Expense).where(
            Expense.org_id == ORG_ID,
            Expense.is_recurring == True
        ).limit(100)
    )
    recurring = result.scalars().all()
    analysis = await expense_agent.analyze_subscriptions([_expense_to_dict(e) for e in recurring])
    return analysis


@router.get("/{expense_id}")
async def get_expense(expense_id: str, db: AsyncSession = Depends(get_db)):
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return _expense_to_dict(expense)


@router.patch("/{expense_id}")
async def update_expense(expense_id: str, update: ExpenseUpdate, db: AsyncSession = Depends(get_db)):
    expense = await db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(expense, field, value)
    await db.commit()
    return _expense_to_dict(expense)


def _expense_to_dict(e: Expense) -> dict:
    return {
        "id": e.id,
        "description": e.description,
        "amount": float(e.amount),
        "currency": e.currency,
        "category": e.category,
        "subcategory": e.subcategory,
        "department": e.department,
        "vendor_name": e.vendor_name,
        "status": e.status,
        "is_anomaly": e.is_anomaly,
        "anomaly_score": float(e.anomaly_score or 0),
        "anomaly_reason": e.anomaly_reason,
        "is_recurring": e.is_recurring,
        "ai_category_confidence": float(e.ai_category_confidence or 0),
        "transaction_date": e.transaction_date.isoformat() if e.transaction_date else None,
        "created_at": e.created_at.isoformat(),
    }
