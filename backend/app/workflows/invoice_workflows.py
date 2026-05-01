from datetime import timedelta
from temporalio import workflow

# Import non-deterministic and external modules inside this block
with workflow.unsafe.imports_passed_through():
    from loguru import logger
    from app.activities.invoice_activities import (
        extract_invoice_data_activity,
        check_compliance_policy_activity,
        execute_payment_activity,
    )


@workflow.defn
class InvoiceApprovalWorkflow:
    def __init__(self) -> None:
        self.is_approved = False
        self.is_rejected = False

    @workflow.signal
    def approve_invoice(self) -> None:
        """Signal to approve the invoice."""
        self.is_approved = True

    @workflow.signal
    def reject_invoice(self) -> None:
        """Signal to reject the invoice."""
        self.is_rejected = True

    @workflow.run
    async def run(self, invoice_id: str) -> dict:
        """The durable workflow execution."""
        
        # 1. Extract Data
        invoice_data = await workflow.execute_activity(
            extract_invoice_data_activity,
            invoice_id,
            start_to_close_timeout=timedelta(minutes=5),
        )

        # 2. Check Compliance & Rules
        policy_result = await workflow.execute_activity(
            check_compliance_policy_activity,
            invoice_data,
            start_to_close_timeout=timedelta(minutes=2),
        )

        # 3. Handle Human-in-the-Loop if needed
        if policy_result.get("requires_human_approval"):
            # Put the workflow to SLEEP until a signal is received.
            # This is fully durable. The server can crash here safely.
            await workflow.wait_condition(
                lambda: self.is_approved or self.is_rejected
            )
            
            if self.is_rejected:
                return {"status": "rejected", "invoice": invoice_id}
                
        # 4. Execute Payment
        payment_result = await workflow.execute_activity(
            execute_payment_activity,
            invoice_id,
            start_to_close_timeout=timedelta(minutes=2),
        )

        return {
            "status": "paid",
            "invoice": invoice_id,
            "payment_message": payment_result
        }
