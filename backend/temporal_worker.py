import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from loguru import logger

from app.core.config import settings
from app.workflows.invoice_workflows import InvoiceApprovalWorkflow
from app.activities.invoice_activities import (
    extract_invoice_data_activity,
    check_compliance_policy_activity,
    execute_payment_activity,
)


async def main():
    logger.info(f"Connecting to Temporal cluster at {settings.TEMPORAL_HOST}...")
    client = await Client.connect(
        settings.TEMPORAL_HOST,
        namespace=settings.TEMPORAL_NAMESPACE
    )

    logger.info(f"Starting Temporal Worker on queue '{settings.TEMPORAL_TASK_QUEUE}'...")
    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[InvoiceApprovalWorkflow],
        activities=[
            extract_invoice_data_activity,
            check_compliance_policy_activity,
            execute_payment_activity,
        ],
    )
    
    logger.info("Worker is listening! Press Ctrl+C to exit.")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
