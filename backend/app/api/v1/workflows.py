"""Workflows API — full CRUD from DB, cached."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.core.database import get_db
from app.core.redis_client import cache
from app.models.models import Workflow

router = APIRouter()
ORG_ID = "org_demo_001"


@router.get("/")
async def list_workflows(
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List workflows from DB, optionally filtered by status."""
    cache_key = f"{ORG_ID}:{status}:{limit}"
    cached = await cache.get("workflows", cache_key)
    if cached:
        return cached

    query = (
        select(Workflow)
        .where(Workflow.org_id == ORG_ID)
        .order_by(desc(Workflow.started_at))
        .limit(limit)
    )
    if status:
        query = query.where(Workflow.status == status)

    result = await db.execute(query)
    wfs = result.scalars().all()

    # Status counts
    counts_result = await db.execute(
        select(Workflow.status, func.count(Workflow.id).label("cnt"))
        .where(Workflow.org_id == ORG_ID)
        .group_by(Workflow.status)
    )
    counts = {r.status: r.cnt for r in counts_result.all()}

    response = {
        "workflows": [_wf_to_dict(w) for w in wfs],
        "total": sum(counts.values()),
        "counts": counts,
    }
    await cache.set("workflows", response, 10, cache_key)
    return response


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _wf_to_dict(wf)


@router.post("/{workflow_id}/retry")
async def retry_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if wf.status not in ("failed", "pending"):
        raise HTTPException(status_code=400, detail="Only failed or pending workflows can be retried")

    wf.status = "running"
    wf.retry_count = (wf.retry_count or 0) + 1
    wf.error = None
    wf.started_at = datetime.utcnow()
    await db.commit()
    await cache.invalidate_pattern("workflows")
    return _wf_to_dict(wf)


def _wf_to_dict(wf: Workflow) -> dict:
    return {
        "id": wf.id,
        "name": wf.name,
        "workflow_type": wf.workflow_type,
        "status": wf.status,
        "steps": wf.steps or [],
        "current_step": wf.current_step,
        "retry_count": wf.retry_count,
        "error": wf.error,
        "context": wf.context or {},
        "started_at": wf.started_at.isoformat() if wf.started_at else None,
        "completed_at": wf.completed_at.isoformat() if wf.completed_at else None,
        "created_at": wf.created_at.isoformat(),
    }
