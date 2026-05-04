import asyncio
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import update
from app.core.database import engine
from app.models.models import Organization

async def fix_org():
    async with engine.begin() as conn:
        await conn.execute(
            update(Organization)
            .where(Organization.id == '9c7a7f55-5f53-4b3d-ac53-0afc9e291f4e')
            .values(default_currency='INR')
        )
        print("Updated test2 to INR")

if __name__ == "__main__":
    asyncio.run(fix_org())
