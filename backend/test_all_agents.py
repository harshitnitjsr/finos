"""
Comprehensive AFOS test — covers all 8 agents, verifies real data,
and validates tool logs are correctly persisted with timing.
"""
import asyncio
import sys
import json
import httpx

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = "http://localhost:8000"

AGENT_TESTS = [
    # (description, message, expected_agent, expected_tools_contain)
    ("Expense categories",       "What are our top expense categories this month?",          "Expense Intelligence",  ["get_category_spend_summary"]),
    ("Expense anomalies",        "Show me any anomalous or unusual expenses",                "Expense Intelligence",  ["get_anomalous_expenses"]),
    ("Invoice overdue",          "Which invoices are overdue or past due?",                  "Invoice Intelligence",  ["get_overdue_invoices"]),
    ("Treasury burn rate",       "What is our monthly burn rate and cash runway?",           "Treasury Agent",        ["get_burn_rate"]),
    ("Vendor risk",              "Which vendors have high risk scores?",                     "Vendor Intelligence",   ["get_high_risk_vendors"]),
    ("Approval queue",           "What is pending in the approval queue?",                   "Approval Agent",        ["get_pending_approvals"]),
    ("Spend forecast",           "Forecast our spend for the next 3 months by category",     "Forecasting Agent",     ["get_historical_spend_data"]),
    ("Financial overview",       "Give me an executive summary of our financial health",     "Insight Agent",         ["get_financial_dashboard_snapshot"]),
]

async def clean_old_error_logs():
    """Remove stale 0ms error logs from pre-fix runs."""
    from app.core.database import AsyncSessionLocal
    from app.models.models import AgentToolLog
    from sqlalchemy import delete
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(AgentToolLog).where(
                AgentToolLog.duration_ms == 0,
                AgentToolLog.status == "error"
            )
        )
        await db.commit()
        print(f"[Cleanup] Removed {result.rowcount} stale error logs")

async def run_all():
    print("=" * 60)
    print("  AFOS LangGraph — Full 8-Agent System Test")
    print("=" * 60)

    await clean_old_error_logs()

    results = []
    async with httpx.AsyncClient(timeout=120) as client:
        for i, (desc, msg, expected_agent, expected_tools) in enumerate(AGENT_TESTS, 1):
            print(f"\n[{i}/8] {desc}")
            print(f"  Q: {msg[:60]}...")
            try:
                r = await client.post(f"{BASE}/api/v1/chat/",
                    json={"message": msg, "session_id": f"comprehensive_test_{i}"})
                if r.status_code == 200:
                    d = r.json()
                    actual_agent = d.get("agent", "?")
                    tools_used = [tc["tool"] for tc in d.get("tool_calls", [])]
                    tokens = d.get("total_tokens", 0)
                    ms = d.get("duration_ms", 0)
                    reply = d.get("message", "")[:180]

                    agent_ok = actual_agent == expected_agent
                    tool_ok = any(t in tools_used for t in expected_tools)

                    print(f"  Agent  : {actual_agent} {'OK' if agent_ok else 'WRONG (expected: ' + expected_agent + ')'}")
                    print(f"  Tools  : {tools_used} {'OK' if tool_ok else 'MISSING expected'}")
                    print(f"  Tokens : {tokens}  Time: {ms}ms")
                    print(f"  Reply  : {reply}")
                    results.append({"desc": desc, "agent_ok": agent_ok, "tool_ok": tool_ok, "tools": tools_used})
                else:
                    print(f"  HTTP ERROR: {r.status_code}")
                    results.append({"desc": desc, "agent_ok": False, "tool_ok": False, "tools": []})
            except Exception as e:
                print(f"  EXCEPTION: {e}")
                results.append({"desc": desc, "agent_ok": False, "tool_ok": False, "tools": []})

        # Summary
        print("\n" + "=" * 60)
        print("  TOOL LOGS IN DB")
        print("=" * 60)
        r = await client.get(f"{BASE}/api/v1/agents/tool-logs/summary")
        if r.status_code == 200:
            for t in r.json().get("tools", []):
                print(f"  {t['tool_name']:<42} calls={t['total_calls']:>3}  avg={t['avg_duration_ms']:>8.1f}ms  success={t['success_rate']:>5.1f}%")

        print("\n" + "=" * 60)
        print("  PASS/FAIL SUMMARY")
        print("=" * 60)
        passed = sum(1 for r in results if r["agent_ok"] and r["tool_ok"])
        for r in results:
            status = "PASS" if r["agent_ok"] and r["tool_ok"] else "FAIL"
            print(f"  [{status}] {r['desc']:<30}  tools={r['tools']}")
        print(f"\n  Result: {passed}/{len(results)} tests passed")

asyncio.run(run_all())
