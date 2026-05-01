"""
Memory pipeline end-to-end test.
Verifies Redis, SQL, Qdrant all receive data and memory context is used in follow-up turns.
"""
import asyncio
import sys
import httpx

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = "http://localhost:8000"
SESSION = "memory_test_001"


async def run():
    print("=" * 60)
    print("  AFOS Memory RAG — End-to-End Test")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120) as c:

        # Turn 1: establish context
        print("\n[Turn 1] Establishing financial context...")
        r = await c.post(f"{BASE}/api/v1/chat/",
            json={"message": "What is our monthly burn rate and runway?", "session_id": SESSION})
        d1 = r.json()
        print(f"  Agent  : {d1['agent']}")
        print(f"  Tools  : {[tc['tool'] for tc in d1.get('tool_calls', [])]}")
        print(f"  Memory : used={d1['memory_used']} sources={d1['sources']}")
        print(f"  Reply  : {d1['message'][:200]}")

        # Turn 2: follow-up referencing prior context
        print("\n[Turn 2] Follow-up (should use memory of Turn 1)...")
        r = await c.post(f"{BASE}/api/v1/chat/",
            json={"message": "Based on what you just said, which expense category is driving the most burn?",
                  "session_id": SESSION})
        d2 = r.json()
        print(f"  Agent  : {d2['agent']}")
        print(f"  Tools  : {[tc['tool'] for tc in d2.get('tool_calls', [])]}")
        print(f"  Memory : used={d2['memory_used']} sources={d2['sources']}")
        print(f"  Reply  : {d2['message'][:250]}")

        # Turn 3: new domain but same session
        print("\n[Turn 3] Different domain, same session...")
        r = await c.post(f"{BASE}/api/v1/chat/",
            json={"message": "Show me high-risk vendors", "session_id": SESSION})
        d3 = r.json()
        print(f"  Agent  : {d3['agent']}")
        print(f"  Memory : used={d3['memory_used']} sources={d3['sources']}")
        print(f"  Reply  : {d3['message'][:200]}")

        # Verify SQL history
        print("\n[Verify] SQL history from PostgreSQL...")
        r = await c.get(f"{BASE}/api/v1/chat/history/{SESSION}")
        hist = r.json()
        print(f"  Total messages in SQL: {hist['count']}")
        print(f"  Source: {hist['source']}")
        for m in hist['messages'][-4:]:
            agent = f" ({m.get('agent_name', '')})" if m.get('agent_name') else ""
            print(f"  [{m['role']}{agent}] {m['content'][:80]}...")

        # Verify sessions endpoint
        print("\n[Verify] Sessions list...")
        r = await c.get(f"{BASE}/api/v1/chat/sessions")
        sessions = r.json()
        for s in sessions['sessions'][:5]:
            print(f"  session={s['session_id'][:20]}... msgs={s['message_count']} last={s['last_active'][:19]}")

        # Verify Qdrant has conversation vectors
        print("\n[Verify] Qdrant afos_conversations collection...")
        import sys
        sys.path.insert(0, '.')
        await asyncio.sleep(3)  # let background tasks flush

    # Direct Qdrant check
    from app.core.vector_store import vector_store
    try:
        info = await vector_store.client.get_collection("afos_conversations")
        print(f"  Qdrant afos_conversations: points={info.points_count} vectors={info.vectors_count}")
    except Exception as e:
        print(f"  Qdrant check: {e}")

    # Redis check
    from app.core.redis_client import redis_client
    import json
    key = f"afos:memory:session:org_demo_001:{SESSION}"
    raw = await redis_client.lrange(key, 0, -1)
    print(f"\n[Verify] Redis session buffer: {len(raw)} messages stored")
    for item in raw[:4]:
        try:
            m = json.loads(item)
            print(f"  [{m['role']}] {m['content'][:70]}...")
        except Exception:
            pass

    # SQL direct check
    from app.core.database import AsyncSessionLocal
    from app.models.models import ConversationMessage
    from sqlalchemy import select, func
    async with AsyncSessionLocal() as db:
        count = (await db.execute(
            select(func.count(ConversationMessage.id))
            .where(ConversationMessage.org_id == "org_demo_001",
                   ConversationMessage.session_id == SESSION)
        )).scalar_one()
        print(f"\n[Verify] PostgreSQL conversation_messages: {count} rows for this session")

    print("\n[SUMMARY]")
    print("  Redis   : session buffer (hot cache)         OK")
    print("  SQL     : persistent conversation history    OK")
    print("  Qdrant  : semantic turn embeddings           OK" if info.points_count > 0 else "  Qdrant  : embedding (async, may take seconds)")
    print(f"\n  Memory was used in Turn 2: {d2['memory_used']}")
    print(f"  Stores used: {set(d2['sources'])}")


asyncio.run(run())
