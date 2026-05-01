import asyncio
import sys
import json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def verify():
    from app.tools.expense_tools import EXPENSE_TOOLS
    from app.tools.treasury_tools import TREASURY_TOOLS
    from app.langgraph.tool_logger import call_tool_with_logging
    import uuid

    run_id = str(uuid.uuid4())
    print(f"run_id: {run_id}")

    # Test 1: expense tool
    t = next(t for t in EXPENSE_TOOLS if t.name == "get_category_spend_summary")
    print(f"\n[1] Tool: {t.name}")
    has_coro = hasattr(t, "coroutine") and t.coroutine is not None
    print(f"    Has coroutine: {has_coro}")

    result = await call_tool_with_logging(
        t, {"days": 30, "currency": "USD"},
        agent_id="expense-agent", agent_name="Expense Intelligence",
        run_id=run_id, org_id="org_demo_001"
    )
    print(f"    grand_total: {result.get('grand_total')}")
    print(f"    categories: {len(result.get('categories', []))}")

    # Test 2: treasury tool
    t2 = next(t for t in TREASURY_TOOLS if t.name == "get_burn_rate")
    print(f"\n[2] Tool: {t2.name}")
    result2 = await call_tool_with_logging(
        t2, {"days": 30, "currency": "USD"},
        agent_id="treasury-agent", agent_name="Treasury Agent",
        run_id=run_id, org_id="org_demo_001"
    )
    print(f"    monthly_burn_rate: {result2.get('monthly_burn_rate')}")
    print(f"    daily_burn_rate: {result2.get('daily_burn_rate')}")

    # Wait for async DB writes to flush
    await asyncio.sleep(2)

    # Verify DB logs were written
    from app.core.database import AsyncSessionLocal
    from app.models.models import AgentToolLog
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        logs = (await db.execute(
            select(AgentToolLog).where(AgentToolLog.run_id == run_id)
        )).scalars().all()
        print(f"\n[3] DB logs written for this run: {len(logs)}")
        for l in logs:
            print(f"    [{l.status}] {l.tool_name} | {l.duration_ms}ms | {l.output_summary[:70]}")

asyncio.run(verify())
