import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.core.redis_client import cache

async def check():
    async with AsyncSessionLocal() as db:
        r = await db.execute(text("SELECT id, name, org_id FROM vendors WHERE name ILIKE '%mankind%' LIMIT 1"))
        vendor = r.fetchone()
        if not vendor:
            print("Mankind not found")
            return

        vid = str(vendor.id)
        org_id = vendor.org_id
        print(f"Vendor: {vendor.name}  id={vid}  org={org_id}")

        # All invoices
        r2 = await db.execute(text("SELECT invoice_number, status, total_amount, currency FROM invoices WHERE vendor_id=:id ORDER BY created_at"), {"id": vid})
        invs = r2.fetchall()
        print(f"\nInvoices ({len(invs)}):")
        for inv in invs:
            print(f"  #{inv.invoice_number}  {inv.status}  {inv.total_amount}  {inv.currency}")

        # All expenses
        r3 = await db.execute(text("SELECT description, amount, currency FROM expenses WHERE vendor_id=:id"), {"id": vid})
        exps = r3.fetchall()
        print(f"\nExpenses ({len(exps)}):")
        for e in exps:
            print(f"  [{e.description[:60]}]  {e.amount}  {e.currency}")

        # Invoice total (paid only)
        r4 = await db.execute(text("SELECT SUM(total_amount), currency FROM invoices WHERE vendor_id=:id AND status='paid' GROUP BY currency"), {"id": vid})
        rows = r4.fetchall()
        print(f"\nInvoice SUM (paid): {[(float(row[0]), row[1]) for row in rows]}")

        # Expense total (excluding payment link)
        r5 = await db.execute(text("SELECT SUM(amount), currency FROM expenses WHERE vendor_id=:id AND description NOT ILIKE 'Paid via Payment Link%' GROUP BY currency"), {"id": vid})
        rows2 = r5.fetchall()
        print(f"Expense SUM (excl payment-link): {[(float(row[0]) if row[0] else 0, row[1]) for row in rows2]}")

        # Check vendor cache
        cached = await cache.get("vendors", f"{org_id}:None:0:50")
        if cached:
            for v in cached.get("vendors", []):
                if "mankind" in v.get("name", "").lower():
                    print(f"\nCACHED total_paid for Mankind = {v['total_paid']}")
        else:
            print("\nNo cache entry for vendor list")

asyncio.run(check())
