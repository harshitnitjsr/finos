import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal

async def check_and_fix():
    async with AsyncSessionLocal() as db:
        invoice_id = "c4c0e0e5-b7b2-4d76-a3a5-1be1e5cc5b04"
        vendor_id = "1f1bda34-7340-4880-b864-d7da17a700c8"

        # Check invoice state
        result = await db.execute(text(
            "SELECT status, total_amount, extra_metadata FROM invoices WHERE id = :id"
        ), {"id": invoice_id})
        row = result.fetchone()
        print(f"Invoice status: {row.status}")
        print(f"Invoice total_amount: {row.total_amount}")
        print(f"Invoice extra_metadata: {row.extra_metadata}")

        # Check vendor state
        result2 = await db.execute(text(
            "SELECT name, total_paid FROM vendors WHERE id = :id"
        ), {"id": vendor_id})
        row2 = result2.fetchone()
        print(f"Vendor name: {row2.name}")
        print(f"Vendor total_paid: {row2.total_paid}")

        # Fix: reset vendor_credited flag and re-run update
        fix = input("\nFix vendor total_paid now? (y/n): ").strip().lower()
        if fix == "y":
            await db.execute(text(
                "UPDATE vendors SET total_paid = total_paid + :amount WHERE id = :id"
            ), {"amount": float(row.total_amount or 0), "id": vendor_id})
            # Clear the flag so future runs work correctly
            await db.execute(text(
                "UPDATE invoices SET extra_metadata = jsonb_set(COALESCE(extra_metadata, '{}')::jsonb, '{vendor_credited}', 'true') WHERE id = :id"
            ), {"id": invoice_id})
            await db.commit()
            print(f"Fixed! Added {row.total_amount} to vendor total_paid.")

if __name__ == "__main__":
    asyncio.run(check_and_fix())
