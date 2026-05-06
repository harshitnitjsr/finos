
import asyncio
import os
import sys
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.append(os.getcwd())

from app.core.database import AsyncSessionLocal
from app.models.models import Vendor, Invoice, Organization

async def query_data():
    async with AsyncSessionLocal() as session:
        # 0. Check Organization
        print("\n--- ORGANIZATIONS ---")
        stmt = select(Organization)
        result = await session.execute(stmt)
        orgs = result.scalars().all()
        for o in orgs:
            print(f"ID: {o.id} | Name: {o.name} | Default Currency: {o.default_currency}")

        # 1. Query Vendors
        print("\n--- VENDORS ---")
        stmt = select(Vendor).where(Vendor.name.ilike("%NIT JAMSHEDPUR%") | Vendor.name.ilike("%Mankind Pharma%"))
        result = await session.execute(stmt)
        vendors = result.scalars().all()
        
        for v in vendors:
            print(f"ID: {v.id}")
            print(f"Name: {v.name}")
            print(f"Total Paid: {v.total_paid} {v.payment_currency}")
            print(f"Risk Score: {v.risk_score}")
            print("-" * 20)
            
            # 2. Query Invoices for this vendor
            print(f"  Invoices for {v.name}:")
            inv_stmt = select(Invoice).where(Invoice.vendor_id == v.id)
            inv_result = await session.execute(inv_stmt)
            invoices = inv_result.scalars().all()
            for inv in invoices:
                print(f"    Inv#: {inv.invoice_number} | Amount: {inv.total_amount} {inv.currency} | Status: {inv.status}")
            print()

if __name__ == "__main__":
    asyncio.run(query_data())
