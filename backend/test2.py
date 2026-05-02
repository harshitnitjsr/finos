import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.models import Invoice

async def run():
    async with AsyncSessionLocal() as db:
        q = select(Invoice).where(Invoice.org_id == 'cc95cadf-ba95-474f-929e-b77f8b0b934c')
        res = await db.execute(q)
        print('Count for cc95cadf:', len(res.scalars().all()))
        
        q2 = select(Invoice).where(Invoice.org_id == 'org_demo_001')
        res2 = await db.execute(q2)
        print('Count for org_demo_001:', len(res2.scalars().all()))

asyncio.run(run())
