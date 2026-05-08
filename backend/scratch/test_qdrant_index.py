import asyncio
from app.core.vector_store import vector_store

async def main():
    print("Initializing vector store...")
    await vector_store.initialize()
    print("Done initializing. Fetching stats...")
    stats = await vector_store.get_collection_stats()
    for name, info in stats.items():
        print(f"{name}: {info}")

if __name__ == "__main__":
    asyncio.run(main())
