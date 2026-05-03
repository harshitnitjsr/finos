from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.core.temporal import temporal_manager
from app.core.config import settings

router = APIRouter()


class StartInvoiceRequest(BaseModel):
    invoice_id: str


class SignalInvoiceRequest(BaseModel):
    invoice_id: str  # We use this as the Workflow ID
    action: str      # 'approve' or 'reject'


@router.post("/invoice/start")
async def start_invoice_workflow(request: StartInvoiceRequest):
    """Kicks off the durable invoice approval workflow."""
    if not temporal_manager.client:
        raise HTTPException(status_code=500, detail="Temporal client not connected.")

    try:
        from app.core.database import AsyncSessionLocal
        from app.models.models import Invoice
        from app.core.redis_client import cache
        
        # Immediately set status to processing so UI shows loading state
        async with AsyncSessionLocal() as db:
            invoice = await db.get(Invoice, request.invoice_id)
            if invoice:
                invoice.status = "processing"
                
                # Create a real Workflow record for the Workflow Monitor UI!
                from app.models.models import Workflow
                wf = Workflow(
                    org_id=invoice.org_id,
                    name=f"Invoice Approval Workflow",
                    workflow_type="InvoiceApprovalWorkflow",
                    status="running",
                    steps=[
                        {"id": 1, "name": "Extract", "status": "running"},
                        {"id": 2, "name": "Compliance", "status": "pending"},
                        {"id": 3, "name": "Approval", "status": "pending"},
                        {"id": 4, "name": "Payment", "status": "pending"}
                    ],
                    current_step=0,
                    context={"invoice_id": invoice.id}
                )
                db.add(wf)
                
                await db.commit()
                await cache.invalidate_pattern("invoices")
                await cache.invalidate_pattern("workflows")
                
        # Start the workflow, but don't wait for it to finish
        handle = await temporal_manager.client.start_workflow(
            "InvoiceApprovalWorkflow",
            request.invoice_id,
            id=f"invoice-workflow-{request.invoice_id}",
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )
        return {"message": "Workflow started", "workflow_id": handle.id}
    except Exception as e:
        logger.error(f"Failed to start workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invoice/signal")
async def signal_invoice_workflow(request: SignalInvoiceRequest):
    """Sends an approval or rejection signal to a sleeping workflow."""
    if not temporal_manager.client:
        raise HTTPException(status_code=500, detail="Temporal client not connected.")

    if request.action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    try:
        from app.core.database import AsyncSessionLocal
        from app.models.models import Invoice
        from app.core.redis_client import cache
        
        # Get the running workflow handle by ID
        handle = temporal_manager.client.get_workflow_handle(f"invoice-workflow-{request.invoice_id}")
        
        # Send the correct signal
        if request.action == "approve":
            await handle.signal("approve_invoice")
            new_status = "approved"
        else:
            await handle.signal("reject_invoice")
            new_status = "rejected"
            
        # Immediately update UI state so it feels responsive and the button hides
        invoice_data: dict = {}
        async with AsyncSessionLocal() as db:
            invoice = await db.get(Invoice, request.invoice_id)
            if invoice:
                invoice.status = new_status
                await db.commit()
                await cache.invalidate_pattern("invoices")
                invoice_data = {
                    "org_id": invoice.org_id,
                    "invoice_id": str(invoice.id),
                    "amount": float(invoice.total_amount or invoice.amount or 0),
                    "currency": invoice.currency,
                    "risk_level": invoice.risk_level or "low",
                    "risk_score": float(invoice.risk_score or 0),
                }

        # ── Index workflow outcome in Qdrant for future approval pattern learning ─
        if invoice_data:
            import asyncio
            asyncio.get_event_loop().create_task(
                _embed_and_index_workflow(
                    invoice_id=request.invoice_id,
                    action=request.action,
                    new_status=new_status,
                    invoice_data=invoice_data,
                )
            )

        return {"message": f"Signal '{request.action}' sent to workflow {request.invoice_id}"}
    except Exception as e:
        logger.error(f"Failed to signal workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _embed_and_index_workflow(
    invoice_id: str,
    action: str,
    new_status: str,
    invoice_data: dict,
) -> None:
    """Background: embed workflow outcome text and upsert to afos_workflows."""
    try:
        from app.core.vector_store import vector_store
        from app.core.model_router import model_router
        from datetime import datetime

        embed_text = (
            f"Invoice workflow {action}d. "
            f"Risk level: {invoice_data.get('risk_level', 'low')}. "
            f"Amount: {invoice_data.get('amount', 0)} {invoice_data.get('currency', 'USD')}. "
            f"Outcome: {new_status}."
        )
        embedding = await model_router.embed(embed_text)

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
                "outcome": new_status,
                "completed_at": datetime.utcnow().isoformat(),
            },
        )
        logger.debug(f"Qdrant: indexed workflow outcome for invoice {invoice_id} → {new_status}")
    except Exception as e:
        logger.warning(f"Workflow Qdrant indexing failed (non-critical): {e}")
