from dotenv import load_dotenv
import os
load_dotenv("backend/.env")

import asyncio
from sqlalchemy import select, text
from app.core.database import AsyncSessionLocal
from app.models.models import Expense, Vendor

async def backfill():
    async with AsyncSessionLocal() as db:
        print("Starting backfill of vendor_id for expenses...")
        
        # Get all expenses with a vendor_name but no vendor_id
        res = await db.execute(select(Expense).where(Expense.vendor_name.isnot(None), Expense.vendor_id.is_(None)))
        expenses = res.scalars().all()
        print(f"Found {len(expenses)} expenses to backfill.")
        
        for exp in expenses:
            # Find vendor by name
            v_res = await db.execute(select(Vendor).where(Vendor.name == exp.vendor_name, Vendor.org_id == exp.org_id).limit(1))
            vendor = v_res.scalar_one_or_none()
            if vendor:
                exp.vendor_id = vendor.id
                print(f"Linked expense {exp.id} to vendor {vendor.name}")
        
        await db.commit()
        print("Backfill complete.")

if __name__ == "__main__":
    asyncio.run(backfill())
