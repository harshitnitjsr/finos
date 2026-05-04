from dotenv import load_dotenv
import os
load_dotenv("backend/.env")

import asyncio
from sqlalchemy import text
from app.core.database import engine

async def migrate():
    async with engine.begin() as conn:
        print("Checking for vendor_id in expenses table...")
        # Check if column exists
        res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='expenses' AND column_name='vendor_id'"))
        if not res.fetchone():
            print("Adding vendor_id column to expenses table...")
            await conn.execute(text("ALTER TABLE expenses ADD COLUMN vendor_id VARCHAR(36) REFERENCES vendors(id)"))
            print("Column added.")
        else:
            print("Column already exists.")
        
        print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
