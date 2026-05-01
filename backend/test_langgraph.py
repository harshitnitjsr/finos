import asyncio
import httpx
import json
import os

# Windows console fix
if os.name == 'nt':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def test():
    async with httpx.AsyncClient(timeout=90) as client:

        print("=== AFOS LangGraph System Test ===\n")

        # 1. Health
        r = await client.get("http://localhost:8000/health")
        print(f"[Health] {r.status_code} - {r.json().get('status')}")

        # 2. Expense query
        print("\n[Test 1] Expense category query")
        r = await client.post("http://localhost:8000/api/v1/chat/",
            json={"message": "What are our top expense categories this month?", "session_id": "test001"})
        if r.status_code == 200:
            d = r.json()
            print(f"  Agent  : {d['agent']}")
            print(f"  Intent : {d['intent']}")
            print(f"  Tools  : {[tc['tool'] for tc in d.get('tool_calls', [])]}")
            print(f"  Tokens : {d['total_tokens']}")
            print(f"  Time   : {d['duration_ms']}ms")
            print(f"  Reply  : {d['message'][:250]}")
        else:
            print(f"  ERROR {r.status_code}: {r.text[:300]}")

        # 3. Treasury query
        print("\n[Test 2] Treasury burn rate query")
        r = await client.post("http://localhost:8000/api/v1/chat/",
            json={"message": "What is our monthly burn rate and cash runway?", "session_id": "test001"})
        if r.status_code == 200:
            d = r.json()
            print(f"  Agent  : {d['agent']}")
            print(f"  Tools  : {[tc['tool'] for tc in d.get('tool_calls', [])]}")
            print(f"  Reply  : {d['message'][:300]}")
        else:
            print(f"  ERROR {r.status_code}: {r.text[:300]}")

        # 4. Vendor query
        print("\n[Test 3] Vendor risk query")
        r = await client.post("http://localhost:8000/api/v1/chat/",
            json={"message": "Which vendors have high risk scores?", "session_id": "test002"})
        if r.status_code == 200:
            d = r.json()
            print(f"  Agent  : {d['agent']}")
            print(f"  Tools  : {[tc['tool'] for tc in d.get('tool_calls', [])]}")
            print(f"  Reply  : {d['message'][:300]}")
        else:
            print(f"  ERROR {r.status_code}: {r.text[:300]}")

        # 5. Tool logs
        print("\n[Test 4] Tool logs (DB)")
        r = await client.get("http://localhost:8000/api/v1/agents/tool-logs?limit=15")
        if r.status_code == 200:
            d = r.json()
            print(f"  Total tool logs in DB: {d['total']}")
            for tl in d.get("tool_logs", [])[:8]:
                status_icon = "OK" if tl['status'] == 'success' else "ERR"
                print(f"  [{status_icon}] {tl['agent_name']} -> {tl['tool_name']} ({tl['duration_ms']}ms)")
                if tl.get('error'):
                    print(f"       Error: {tl['error'][:100]}")
                else:
                    print(f"       Out: {tl['output_summary'][:80]}")
        else:
            print(f"  ERROR {r.status_code}: {r.text[:200]}")

        # 6. Tool summary
        print("\n[Test 5] Tool summary")
        r = await client.get("http://localhost:8000/api/v1/agents/tool-logs/summary")
        if r.status_code == 200:
            d = r.json()
            for t in d.get("tools", []):
                print(f"  {t['tool_name']:<40} calls={t['total_calls']} avg={t['avg_duration_ms']}ms success={t['success_rate']}%")
        else:
            print(f"  ERROR {r.status_code}")

        # 7. Agent status
        print("\n[Test 6] Agent status")
        r = await client.get("http://localhost:8000/api/v1/agents/status")
        if r.status_code == 200:
            d = r.json()
            for a in d.get("agents", []):
                print(f"  {a['name']:<30} status={a['status']} reqs24h={a['requests_24h']} tokens={a['tokens_24h']}")
        else:
            print(f"  ERROR {r.status_code}")

asyncio.run(test())
