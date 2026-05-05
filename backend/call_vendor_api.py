"""Directly call the vendor API and print the live response"""
import asyncio
import aiohttp
import json

ORG_ID = "9c7a7f55-5f53-4b3d-ac53-0afc9e291f4e"

async def check():
    headers = {
        "x-org-id": ORG_ID,
        "x-internal-token": "f5664602f7550f18456e3a4dce2d6789f6edeb2d3c01d6ff0ea231749654d585",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8000/api/v1/vendors/", headers=headers) as resp:
            status = resp.status
            data = await resp.json()
            print(f"HTTP {status}")
            for v in data.get("vendors", []):
                print(f"  {v['name']:35s} total_paid={v['total_paid']:>10.0f}")

asyncio.run(check())
