import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal

async def migrate():
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("ALTER TABLE invoices ADD COLUMN extra_metadata JSON;"))
            print("Added extra_metadata to invoices table.")
        except Exception as e:
            print(f"invoices.extra_metadata already exists or error: {e}")

        await db.commit()

if __name__ == "__main__":
    asyncio.run(migrate())
