import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT COUNT(*) FROM vendors WHERE org_id='cc95cadf-ba95-474f-929e-b77f8b0b934c'"))
        print(res.fetchall())

if __name__ == "__main__":
    asyncio.run(main())
