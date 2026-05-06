
import asyncio
import os
import sys
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.append(os.getcwd())

from app.core.database import AsyncSessionLocal
from app.models.models import Vendor, Invoice, Organization, Payment
from app.core.fx import fx_service

async def cleanup_data():
    async with AsyncSessionLocal() as session:
        # 1. Find NIT JAMSHEDPUR
        print("\nFixing NIT JAMSHEDPUR...")
        stmt = select(Vendor).where(Vendor.name.ilike("%NIT JAMSHEDPUR%"))
        result = await session.execute(stmt)
        v = result.scalar_one_or_none()
        
        if v:
            print(f"Current: {v.total_paid} {v.payment_currency}")
            
            # Find the org base currency
            org = await session.get(Organization, v.org_id)
            base_currency = org.default_currency if org else "USD"
            print(f"Org Base Currency: {base_currency}")
            
            # Recalculate from invoices
            inv_stmt = select(Invoice).where(Invoice.vendor_id == v.id, Invoice.status == "paid")
            inv_result = await session.execute(inv_stmt)
            invoices = inv_result.scalars().all()
            
            new_total_base = 0
            rates = await fx_service.get_rates(base_currency)
            
            for inv in invoices:
                amt_base = fx_service.convert(float(inv.total_amount), inv.currency, base_currency, rates)
                print(f"  Invoice {inv.invoice_number}: {inv.total_amount} {inv.currency} -> {amt_base} {base_currency}")
                new_total_base += amt_base
                
            v.total_paid = Decimal(str(round(new_total_base, 2)))
            v.payment_currency = base_currency
            print(f"Updated Vendor: {v.total_paid} {v.payment_currency}")
            
            await session.commit()
            print("Done.")
        else:
            print("NIT JAMSHEDPUR not found.")

if __name__ == "__main__":
    asyncio.run(cleanup_data())
