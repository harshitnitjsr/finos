import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT id, name FROM organizations"))
        print(res.fetchall())

if __name__ == "__main__":
    asyncio.run(main())
