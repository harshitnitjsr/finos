import asyncio
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.database import engine, Base
from app.models.models import * # Ensure all models are loaded
from app.core.seed import seed_demo_data

async def reset_db():
    print("Initializing Qdrant collections...")
    from app.core.vector_store import vector_store
    await vector_store.initialize()
    
    print("Dropping all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    print("Recreating all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    print("Seeding fresh data...")
    await seed_demo_data()
    print("Database reset complete!")

if __name__ == "__main__":
    asyncio.run(reset_db())
