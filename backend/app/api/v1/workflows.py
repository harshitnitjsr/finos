"""Workflows API — full CRUD from DB, cached."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.core.database import get_db
from app.core.redis_client import cache
from app.models.models import Workflow
from app.api.deps import get_org_id

router = APIRouter()


@router.get("/")
async def list_workflows(
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """List workflows from DB, optionally filtered by status."""
    cache_key = f"{org_id}:{status}:{limit}"
    cached = await cache.get("workflows", cache_key)
    if cached:
        return cached

    q = (
        select(Workflow)
        .where(Workflow.org_id == org_id)
        .order_by(desc(Workflow.started_at))
        .limit(limit)
    )
    if status:
        q = q.where(Workflow.status == status)

    result = await db.execute(q)
    wfs = result.scalars().all()

    counts_result = await db.execute(
        select(Workflow.status, func.count(Workflow.id).label("cnt"))
        .where(Workflow.org_id == org_id)
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

    # ── Redis: acquire distributed retry lock (prevent double-retry) ──────────
    locked = await cache.acquire_retry_lock(workflow_id)
    if not locked:
        raise HTTPException(status_code=409, detail="Retry already in progress for this workflow")

    try:
        # ── Redis: check retry limit ──────────────────────────────────────────
        can_retry, retry_count = await cache.increment_retry_count(workflow_id, max_retries=5)
        if not can_retry:
            raise HTTPException(
                status_code=429,
                detail=f"Workflow has exceeded max retries ({retry_count - 1}/5). Manual intervention required."
            )

        # ── SQL: update workflow record ───────────────────────────────────────
        wf.status = "running"
        wf.retry_count = (wf.retry_count or 0) + 1
        wf.error = None
        wf.started_at = datetime.utcnow()
        await db.commit()

        # ── Redis: broadcast real-time workflow state ─────────────────────────
        await cache.set_workflow_state(workflow_id, {
            "workflow_id": workflow_id,
            "status": "running",
            "current_step": 0,
            "current_step_name": "Starting retry...",
            "retry_count": retry_count,
            "started_at": datetime.utcnow().isoformat(),
        })

        await cache.invalidate_pattern("workflows")
        return _wf_to_dict(wf)

    finally:
        # Always release lock so next retry can proceed
        await cache.release_retry_lock(workflow_id)


@router.get("/{workflow_id}/state")
async def get_workflow_realtime_state(workflow_id: str):
    """
    Real-time workflow execution state from Redis.
    Returns None if workflow is not currently active.
    Faster than hitting the DB — used for live polling.
    """
    state = await cache.get_workflow_state(workflow_id)
    if not state:
        return {"workflow_id": workflow_id, "state": None, "message": "No active state (workflow may be completed or not started)"}
    return {"workflow_id": workflow_id, "state": state}



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
