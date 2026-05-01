import asyncio
import random
from datetime import datetime, timedelta
from app.core.database import AsyncSessionLocal
from app.models.models import AgentLog

ORG_ID = "org_demo_001"

AGENTS = [
    {"id": "invoice-agent", "name": "Invoice Intelligence", "model": "gpt-4o-mini"},
    {"id": "expense-agent", "name": "Expense Intelligence", "model": "gpt-4o-mini"},
    {"id": "compliance-agent", "name": "Compliance Agent", "model": "gpt-4o"},
    {"id": "insight-agent", "name": "Insight Agent", "model": "gpt-4o"},
    {"id": "treasury-agent", "name": "Treasury Agent", "model": "gpt-4o"},
    {"id": "vendor-agent", "name": "Vendor Intelligence", "model": "gpt-4o-mini"},
    {"id": "approval-agent", "name": "Approval Agent", "model": "gpt-4o"},
    {"id": "forecasting-agent", "name": "Forecasting Agent", "model": "gpt-4o"},
]

async def populate_logs():
    async with AsyncSessionLocal() as db:
        for _ in range(500):
            agent = random.choice(AGENTS)
            
            log = AgentLog(
                org_id=ORG_ID,
                agent_id=agent["id"],
                agent_name=agent["name"],
                action="process_task",
                status="success",
                model_used=agent["model"],
                tokens_used=random.randint(150, 4500),
                duration_ms=random.randint(400, 2800),
                input_summary="Simulated workload query.",
                output_summary="Successfully processed constraints and responded.",
                created_at=datetime.utcnow() - timedelta(hours=random.uniform(0, 23.9))
            )
            db.add(log)
            
        await db.commit()
        print("Generated 500 AI Agent logs over the last 24h successfully!")

if __name__ == "__main__":
    asyncio.run(populate_logs())