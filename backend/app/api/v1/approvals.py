"""Approvals API — full CRUD + approve/reject shortcuts + status counts. Redis-cached."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from app.core.database import get_db
from app.core.redis_client import cache
from app.models.models import Approval, Invoice
from app.api.deps import get_org_id

router = APIRouter()


class ApprovalDecision(BaseModel):
    decision: str  # approve | reject | escalate
    notes: Optional[str] = None
    decision_by: str = "user@example.com"


@router.get("/")
async def list_approvals(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(50, ge=1, le=200),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """List approvals with status counts. Cached 10s."""
    cache_key = f"{org_id}:{status}:{skip}:{limit}"
    cached = await cache.get("approvals", cache_key)
    if cached:
        return cached

    q = select(Approval).where(Approval.org_id == org_id).order_by(desc(Approval.created_at))
    if status:
        q = q.where(Approval.status == status)
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    approvals = result.scalars().all()

    total_q = select(func.count(Approval.id)).where(Approval.org_id == org_id)
    total = (await db.execute(total_q)).scalar_one_or_none() or 0

    counts_result = await db.execute(
        select(Approval.status, func.count(Approval.id).label("cnt"))
        .where(Approval.org_id == org_id)
        .group_by(Approval.status)
    )
    counts = {r.status: r.cnt for r in counts_result.all()}

    response = {
        "approvals": [_approval_to_dict(a) for a in approvals],
        "total": total,
        "counts": counts,
    }
    await cache.set("approvals", response, 10, cache_key)
    return response


@router.get("/{approval_id}")
async def get_approval(approval_id: str, db: AsyncSession = Depends(get_db)):
    approval = await db.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return _approval_to_dict(approval)


@router.post("/{approval_id}/approve")
async def approve(approval_id: str, db: AsyncSession = Depends(get_db)):
    """Quick approve endpoint (no body required)."""
    return await _decide(approval_id, "approve", db)


@router.post("/{approval_id}/reject")
async def reject(approval_id: str, db: AsyncSession = Depends(get_db)):
    """Quick reject endpoint (no body required)."""
    return await _decide(approval_id, "reject", db)


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
):
    return await _decide(approval_id, decision.decision, db, decision.notes, decision.decision_by)


async def _decide(
    approval_id: str,
    decision: str,
    db: AsyncSession,
    notes: Optional[str] = None,
    decision_by: str = "system",
):
    approval = await db.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail=f"Approval already {approval.status}")

    approval.status = decision
    approval.decision_by = decision_by
    approval.decision_at = datetime.utcnow()
    approval.notes = notes

    invoice_data: dict = {}
    if approval.invoice_id:
        from app.core.temporal import temporal_manager

        invoice = await db.get(Invoice, approval.invoice_id)
        if invoice:
            invoice.status = "approved" if decision == "approve" else "rejected"
            invoice.updated_at = datetime.utcnow()
            invoice_data = {
                "org_id": invoice.org_id,
                "invoice_id": str(invoice.id),
                "amount": float(invoice.total_amount or invoice.amount or 0),
                "currency": invoice.currency or "USD",
                "risk_level": invoice.risk_level or "low",
                "risk_score": float(invoice.risk_score or 0),
            }

            try:
                if temporal_manager.client:
                    handle = temporal_manager.client.get_workflow_handle(
                        f"invoice-workflow-{approval.invoice_id}"
                    )
                    if decision == "approve":
                        await handle.signal("approve_invoice")
                    elif decision == "reject":
                        await handle.signal("reject_invoice")
            except Exception:
                pass  # Temporal is optional

    await db.commit()
    await cache.invalidate_pattern("approvals")
    await cache.invalidate_pattern("dashboard")
    await cache.invalidate_pattern("invoices")

    # ── Index workflow outcome in Qdrant (background, non-blocking) ───────────
    if invoice_data:
        import asyncio
        try:
            asyncio.ensure_future(_index_workflow_outcome(
                invoice_id=approval.invoice_id,
                decision=decision,
                invoice_data=invoice_data,
            ))
        except RuntimeError:
            pass  # No running event loop (tests etc.)

    return _approval_to_dict(approval)


async def _index_workflow_outcome(
    invoice_id: str,
    decision: str,
    invoice_data: dict,
) -> None:
    """Fire-and-forget: embed and index the approval outcome into afos_workflows."""
    try:
        from app.core.vector_store import vector_store
        from app.core.model_router import model_router
        from loguru import logger

        embed_text = (
            f"Invoice {decision}d. "
            f"Risk level: {invoice_data.get('risk_level', 'low')}. "
            f"Amount: {invoice_data.get('amount', 0)} {invoice_data.get('currency', 'USD')}. "
            f"Outcome: {decision}."
        )
        embedding = await model_router.embed(embed_text)
        if not embedding:
            logger.warning(f"Workflow Qdrant: embed returned empty for invoice {invoice_id}")
            return

        await vector_store.upsert_workflow_context(
            workflow_id=f"wf_{invoice_id}",
            embedding=embedding,
            payload={
                "org_id": invoice_data.get("org_id", ""),
                "workflow_type": "InvoiceApprovalWorkflow",
                "invoice_id": invoice_id,
                "status": "completed",
                "amount": invoice_data.get("amount", 0),
                "risk_level": invoice_data.get("risk_level", "low"),
                "outcome": decision,
                "completed_at": datetime.utcnow().isoformat(),
            },
        )
        logger.debug(f"Qdrant: indexed workflow outcome for invoice {invoice_id} → {decision}")
    except Exception as e:
        logger.warning(f"Workflow Qdrant indexing failed (non-critical): {e}")



@router.get("/stats/pending-count")
async def pending_count(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count(Approval.id)).where(
            Approval.org_id == org_id, Approval.status == "pending"
        )
    )
    return {"pending_count": result.scalar_one_or_none() or 0}


def _approval_to_dict(a: Approval) -> dict:
    return {
        "id": a.id,
        "invoice_id": a.invoice_id,
        "status": a.status,
        "requested_by": a.requested_by,
        "assigned_to": a.assigned_to,
        "decision_by": a.decision_by,
        "decision_at": a.decision_at.isoformat() if a.decision_at else None,
        "risk_score": float(a.risk_score or 0),
        "risk_level": a.risk_level,
        "ai_recommendation": a.ai_recommendation,
        "ai_explanation": a.ai_explanation,
        "amount": float(a.amount or 0),
        "currency": a.currency,
        "notes": a.notes,
        "policy_checks": a.policy_checks or [],
        "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        "created_at": a.created_at.isoformat(),
    }
