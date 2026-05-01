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
        async with AsyncSessionLocal() as db:
            invoice = await db.get(Invoice, request.invoice_id)
            if invoice:
                invoice.status = new_status
                await db.commit()
                await cache.invalidate_pattern("invoices")
            
        return {"message": f"Signal '{request.action}' sent to workflow {request.invoice_id}"}
    except Exception as e:
        logger.error(f"Failed to signal workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))
