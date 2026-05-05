"""Direct API simulation - reproduce exactly what list_vendors does for Mankind"""
import asyncio
from sqlalchemy import select, func, text
from app.core.database import AsyncSessionLocal
from app.core.fx import fx_service
from app.models.models import Vendor, Invoice, Expense, Organization

ORG_ID = "9c7a7f55-5f53-4b3d-ac53-0afc9e291f4e"

async def check():
    async with AsyncSessionLocal() as db:
        # Step 1: base currency
        org_res = await db.execute(select(Organization.default_currency).where(Organization.id == ORG_ID))
        base_currency = org_res.scalar_one_or_none() or "USD"
        print(f"Base currency: {base_currency}")
        rates = await fx_service.get_rates(base_currency)
        print(f"FX rates (sample): USD={rates.get('USD')}, INR={rates.get('INR')}")

        # Step 2: Invoice totals
        q_inv = (
            select(Vendor.id, Invoice.currency, func.sum(Invoice.total_amount).label("curr_total"))
            .join(Invoice, Invoice.vendor_id == Vendor.id)
            .where(Vendor.org_id == ORG_ID, Invoice.status == "paid")
            .group_by(Vendor.id, Invoice.currency)
        )
        res_inv = await db.execute(q_inv)
        vendor_currency_map = {}
        for v_id, curr, total in res_inv.all():
            amt_base = fx_service.convert(float(total or 0), curr, base_currency, rates)
            vendor_currency_map[str(v_id)] = vendor_currency_map.get(str(v_id), 0) + amt_base
            print(f"Invoice contrib: vendor={v_id} {total} {curr} -> {amt_base} {base_currency}")

        # Step 3: Expense totals (excl payment link)
        q_exp = (
            select(Vendor.id, Expense.currency, func.sum(Expense.amount).label("curr_total"))
            .join(Expense, Expense.vendor_id == Vendor.id)
            .where(
                Expense.org_id == ORG_ID,
                ~Expense.description.ilike("Paid via Payment Link%"),
            )
            .group_by(Vendor.id, Expense.currency)
        )
        res_exp = await db.execute(q_exp)
        for v_id, curr, total in res_exp.all():
            amt_base = fx_service.convert(float(total or 0), curr, base_currency, rates)
            vendor_currency_map[str(v_id)] = vendor_currency_map.get(str(v_id), 0) + amt_base
            print(f"Expense contrib: vendor={v_id} {total} {curr} -> {amt_base} {base_currency}")

        # Step 4: Get Mankind vendor
        r = await db.execute(text("SELECT id, name, total_paid, payment_currency FROM vendors WHERE name ILIKE '%mankind%' LIMIT 1"))
        v = r.fetchone()
        if v:
            vid = str(v.id)
            print(f"\nMankind vendor_currency_map entry: {vendor_currency_map.get(vid, 'NOT FOUND')}")
            print(f"Mankind vendor.total_paid column: {v.total_paid}")
            print(f"Mankind vendor.payment_currency: {v.payment_currency}")
            if vid in vendor_currency_map:
                print(f"=> USING vendor_currency_map = {vendor_currency_map[vid]}")
            else:
                fallback = fx_service.convert(float(v.total_paid or 0), v.payment_currency, base_currency, rates)
                print(f"=> USING fallback vendor.total_paid = {fallback}")

asyncio.run(check())
