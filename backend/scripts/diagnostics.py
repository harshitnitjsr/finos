import asyncio
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, func
from app.core.database import engine
from app.models.models import Organization, Invoice, Expense, Approval

async def diagnostics():
    print("--- System Diagnostics ---")
    async with engine.begin() as conn:
        # Orgs
        orgs = await conn.execute(select(Organization))
        for org in orgs:
            print(f"Org: {org.name} (ID: {org.id}) | Default Currency: {org.default_currency}")
            
            # Detailed expense check
            exps = await conn.execute(select(Expense).where(Expense.org_id == org.id))
            for e in exps:
                print(f"    Expense: {e.description} | {e.amount} {e.currency} | Date: {e.transaction_date}")
                
            # Detailed invoice check
            invs = await conn.execute(select(Invoice).where(Invoice.org_id == org.id))
            for i in invs:
                print(f"    Invoice: {i.invoice_number} | {i.total_amount} {i.currency} | Status: {i.status} | Due: {i.due_date}")

if __name__ == "__main__":
    asyncio.run(diagnostics())
