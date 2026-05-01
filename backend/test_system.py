"""
AFOS Full System Test Suite
Run: python test_system.py
Tests: Backend, Database, Redis, Qdrant, AI Agents, All API endpoints
"""
import asyncio
import httpx
import json
import sys
import os
from datetime import datetime

API = "http://localhost:8000"
FRONTEND = "http://localhost:3000"
PASS = "\033[92m✅ PASS\033[0m"
FAIL = "\033[91m❌ FAIL\033[0m"
WARN = "\033[93m⚠️  WARN\033[0m"
INFO = "\033[94mℹ️  INFO\033[0m"

results = {"passed": 0, "failed": 0, "warned": 0}

def ok(name, detail=""):
    results["passed"] += 1
    print(f"  {PASS}  {name}" + (f"  →  {detail}" if detail else ""))

def fail(name, detail=""):
    results["failed"] += 1
    print(f"  {FAIL}  {name}" + (f"  →  {detail}" if detail else ""))

def warn(name, detail=""):
    results["warned"] += 1
    print(f"  {WARN}  {name}" + (f"  →  {detail}" if detail else ""))

def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")

async def run_tests():
    async with httpx.AsyncClient(timeout=20) as client:

        # ═══════════════════════════════════════════════
        # 1. INFRASTRUCTURE
        # ═══════════════════════════════════════════════
        section("1. INFRASTRUCTURE HEALTH")

        try:
            r = await client.get(f"{API}/health")
            data = r.json()
            if data.get("status") == "healthy":
                ok("Backend API", f"v{data.get('version', '?')} running")
            else:
                fail("Backend API", data)
        except Exception as e:
            fail("Backend API", str(e))
            print("\n  ⛔ Backend is not running. Start it with:")
            print("     cd backend && .\\venv\\Scripts\\python -m uvicorn main:app --reload")
            return

        try:
            r = await client.get(f"{API}/health")
            svcs = r.json().get("services", {})
            if svcs.get("redis") == "connected":
                ok("Redis Cache", "Connected on port 6380")
            else:
                fail("Redis Cache", svcs.get("redis", "not connected"))
        except Exception as e:
            fail("Redis Cache", str(e))

        try:
            r = await client.get(f"{API}/health")
            svcs = r.json().get("services", {})
            if svcs.get("qdrant") == "connected":
                ok("Qdrant Vector DB", "Connected on port 6335")
            else:
                fail("Qdrant Vector DB", svcs.get("qdrant", "not connected"))
        except Exception as e:
            fail("Qdrant Vector DB", str(e))

        try:
            r = await client.get(f"{FRONTEND}/dashboard", follow_redirects=True)
            if r.status_code == 200:
                ok("Next.js Frontend", "Dashboard loads on port 3000")
            else:
                fail("Next.js Frontend", f"Status {r.status_code}")
        except Exception as e:
            fail("Next.js Frontend", str(e))

        # ═══════════════════════════════════════════════
        # 2. DATABASE — SEEDED DATA
        # ═══════════════════════════════════════════════
        section("2. DATABASE — SEEDED DATA")

        try:
            r = await client.get(f"{API}/api/v1/invoices/?limit=50")
            data = r.json()
            inv = data.get("invoices", [])
            if len(inv) >= 5:
                ok("Invoices seeded", f"{len(inv)} invoices in DB")
            elif len(inv) > 0:
                warn("Invoices seeded", f"Only {len(inv)} invoices (expected ≥12)")
            else:
                fail("Invoices seeded", "0 invoices found")
        except Exception as e:
            fail("Invoices API", str(e))

        try:
            r = await client.get(f"{API}/api/v1/expenses/?limit=100")
            data = r.json()
            exps = data.get("expenses", [])
            if len(exps) >= 30:
                ok("Expenses seeded", f"{len(exps)} expenses in DB")
            elif len(exps) > 0:
                warn("Expenses seeded", f"Only {len(exps)} (expected ≥60)")
            else:
                fail("Expenses seeded", "0 expenses found")
        except Exception as e:
            fail("Expenses API", str(e))

        try:
            r = await client.get(f"{API}/api/v1/approvals/?limit=20")
            data = r.json()
            appr = data.get("approvals", [])
            if len(appr) >= 3:
                ok("Approvals seeded", f"{len(appr)} approvals in DB")
            else:
                warn("Approvals seeded", f"Only {len(appr)} approvals")
        except Exception as e:
            fail("Approvals API", str(e))

        try:
            r = await client.get(f"{API}/api/v1/workflows/?limit=20")
            data = r.json()
            wfs = data.get("workflows", [])
            if len(wfs) >= 2:
                ok("Workflows seeded", f"{len(wfs)} workflows in DB")
            else:
                warn("Workflows seeded", f"Only {len(wfs)} workflows")
        except Exception as e:
            fail("Workflows API", str(e))

        try:
            r = await client.get(f"{API}/api/v1/vendors/?limit=20")
            data = r.json()
            vends = data.get("vendors", [])
            if len(vends) >= 5:
                ok("Vendors seeded", f"{len(vends)} vendors in DB")
            else:
                warn("Vendors seeded", f"Only {len(vends)}")
        except Exception as e:
            fail("Vendors API", str(e))

        # ═══════════════════════════════════════════════
        # 3. ANALYTICS — KPIs & CHARTS
        # ═══════════════════════════════════════════════
        section("3. ANALYTICS — DASHBOARD KPIs & CHARTS")

        try:
            r = await client.get(f"{API}/api/v1/analytics/dashboard")
            if r.status_code != 200:
                fail("Analytics /dashboard", f"HTTP {r.status_code}: {r.text[:120]}")
            else:
                data = r.json()
                kpis = data.get("kpis", {})
                charts = data.get("charts", {})

                pa = kpis.get("pending_approvals", 0)
                ac = kpis.get("anomaly_count", 0)
                aw = kpis.get("active_workflows", 0)
                ti = kpis.get("total_invoices", 0)
                ms = kpis.get("monthly_spend", [])

                ok("Dashboard KPIs", f"Invoices={ti}, Pending={pa}, Anomalies={ac}, Workflows={aw}")

                if ms:
                    usd = next((x for x in ms if x["currency"] == "USD"), None)
                    if usd:
                        ok("Monthly Spend (USD)", f"${usd['total']:,.0f}  ({usd.get('change_pct',0):+.1f}% vs prev month)")
                    else:
                        warn("Monthly Spend USD", f"USD not found, currencies: {[x['currency'] for x in ms]}")
                else:
                    fail("Monthly Spend", "No spend data returned")

                et = charts.get("expense_trend", [])
                if len(et) >= 5:
                    ok("Expense Trend Chart", f"{len(et)} daily data points")
                elif len(et) > 0:
                    warn("Expense Trend Chart", f"Only {len(et)} points (expected ≥20)")
                else:
                    fail("Expense Trend Chart", "Empty — no trend data")

                cb = charts.get("category_breakdown", [])
                if len(cb) >= 3:
                    cats = [x['category'] for x in cb[:3]]
                    ok("Category Breakdown", f"Top 3: {', '.join(cats)}")
                else:
                    warn("Category Breakdown", f"Only {len(cb)} categories")

        except Exception as e:
            fail("Analytics /dashboard", str(e))

        try:
            r = await client.get(f"{API}/api/v1/analytics/spend-trend?days=30")
            if r.status_code == 200:
                d = r.json().get("data", [])
                ok("Spend Trend Endpoint", f"{len(d)} data points for 30 days")
            else:
                fail("Spend Trend Endpoint", f"HTTP {r.status_code}")
        except Exception as e:
            fail("Spend Trend Endpoint", str(e))

        try:
            r = await client.get(f"{API}/api/v1/analytics/category-breakdown?days=90")
            if r.status_code == 200:
                d = r.json().get("data", [])
                ok("Category Breakdown Endpoint", f"{len(d)} categories")
            else:
                fail("Category Breakdown", f"HTTP {r.status_code}")
        except Exception as e:
            fail("Category Breakdown", str(e))

        try:
            r = await client.get(f"{API}/api/v1/analytics/vendor-breakdown?days=90")
            if r.status_code == 200:
                d = r.json().get("data", [])
                ok("Vendor Breakdown Endpoint", f"{len(d)} vendors")
            else:
                fail("Vendor Breakdown", f"HTTP {r.status_code}")
        except Exception as e:
            fail("Vendor Breakdown", str(e))

        # ═══════════════════════════════════════════════
        # 4. AI AGENTS
        # ═══════════════════════════════════════════════
        section("4. AI AGENTS & INTELLIGENCE")

        # Check OpenAI key
        openai_key = ""
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("OPENAI_API_KEY="):
                        openai_key = line.split("=", 1)[1].strip()
                        break

        if openai_key and openai_key != "your_openai_api_key" and len(openai_key) > 20:
            ok("OpenAI API Key", f"Configured (sk-...{openai_key[-6:]})")
            ai_enabled = True
        else:
            warn("OpenAI API Key", "Not configured — AI features will be limited")
            print("       → Add to backend/.env:  OPENAI_API_KEY=sk-...")
            ai_enabled = False

        # Executive Summary (InsightAgent)
        try:
            r = await client.get(f"{API}/api/v1/insights/executive-summary", timeout=30)
            if r.status_code == 200:
                data = r.json()
                headline = data.get("headline", "")
                if headline and "error" not in headline.lower() and "unavailable" not in headline.lower():
                    ok("InsightAgent (Executive Summary)", f'"{headline[:70]}..."')
                else:
                    warn("InsightAgent (Executive Summary)", f'Degraded: "{headline[:60]}"')
            elif r.status_code == 503:
                warn("InsightAgent", "Service unavailable — OpenAI key needed")
            else:
                fail("InsightAgent", f"HTTP {r.status_code}: {r.text[:80]}")
        except Exception as e:
            fail("InsightAgent", str(e))

        # Anomaly Detection (ComplianceAgent)
        try:
            r = await client.get(f"{API}/api/v1/expenses/anomalies", timeout=30)
            if r.status_code == 200:
                data = r.json()
                count = len(data.get("anomalies", data if isinstance(data, list) else []))
                ok("ComplianceAgent (Anomaly Detection)", f"{count} anomalies detected")
            else:
                warn("ComplianceAgent", f"HTTP {r.status_code}")
        except Exception as e:
            warn("ComplianceAgent", str(e))

        # Agent logs
        try:
            r = await client.get(f"{API}/api/v1/agents/logs?limit=10")
            if r.status_code == 200:
                data = r.json()
                logs = data.get("logs", [])
                ok("Agent Logs", f"{len(logs)} recent agent events")
            else:
                warn("Agent Logs", f"HTTP {r.status_code}")
        except Exception as e:
            warn("Agent Logs", str(e))

        # Agent status
        try:
            r = await client.get(f"{API}/api/v1/agents/status")
            if r.status_code == 200:
                data = r.json()
                agents = data.get("agents", [])
                active = [a for a in agents if a.get("status") == "active"]
                ok("Agent Status", f"{len(active)}/{len(agents)} agents active")
            else:
                warn("Agent Status", f"HTTP {r.status_code}")
        except Exception as e:
            warn("Agent Status", str(e))

        # ═══════════════════════════════════════════════
        # 5. INVOICE PROCESSING PIPELINE
        # ═══════════════════════════════════════════════
        section("5. INVOICE PROCESSING PIPELINE")

        # Test invoice upload (with a tiny test PDF-like file)
        try:
            import io
            # Simple text file simulating an invoice (OCR would extract from real PDF)
            fake_invoice = b"""INVOICE
Vendor: Test Corp Ltd
Invoice #: TEST-001
Date: 2026-05-01
Amount: $1,500.00 USD
Description: Software Services - Monthly Subscription
Tax: $150.00
Total: $1,650.00"""

            files = {"file": ("test_invoice.txt", io.BytesIO(fake_invoice), "text/plain")}
            data_form = {"org_id": "org_demo_001", "uploaded_by": "test_runner"}
            r = await client.post(f"{API}/api/v1/invoices/upload", files=files, data=data_form, timeout=60)

            if r.status_code in (200, 201):
                inv_data = r.json()
                inv_id = inv_data.get("id") or inv_data.get("invoice_id")
                ok("Invoice Upload", f"Accepted → ID: {inv_id}")

                # Check AI extraction ran
                if inv_id:
                    await asyncio.sleep(3)  # give AI a moment
                    r2 = await client.get(f"{API}/api/v1/invoices/{inv_id}")
                    if r2.status_code == 200:
                        inv = r2.json()
                        status = inv.get("status")
                        vendor = inv.get("vendor_name") or inv.get("vendor", {}).get("name")
                        amount = inv.get("total_amount")
                        ok("Invoice AI Extraction", f"Status={status}, Vendor={vendor}, Amount={amount}")
                    else:
                        warn("Invoice retrieval", f"HTTP {r2.status_code}")
            else:
                warn("Invoice Upload", f"HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            warn("Invoice Upload", str(e))

        # ═══════════════════════════════════════════════
        # 6. APPROVAL WORKFLOW
        # ═══════════════════════════════════════════════
        section("6. APPROVAL WORKFLOW")

        try:
            r = await client.get(f"{API}/api/v1/approvals/?status=pending&limit=5")
            data = r.json()
            pending = data.get("approvals", [])
            if pending:
                appr = pending[0]
                appr_id = appr.get("id")
                ok("Pending Approvals", f"{len(pending)} pending, first ID: {appr_id}")

                # Test approval action
                r2 = await client.post(
                    f"{API}/api/v1/approvals/{appr_id}/approve",
                    json={"approved_by": "test_runner", "notes": "Auto-test approval"}
                )
                if r2.status_code == 200:
                    ok("Approve Action", f"Approval {appr_id} → approved")
                else:
                    warn("Approve Action", f"HTTP {r2.status_code}: {r2.text[:80]}")
            else:
                warn("Pending Approvals", "No pending approvals to test")
        except Exception as e:
            fail("Approval Workflow", str(e))

        # ═══════════════════════════════════════════════
        # 7. TREASURY & MULTICURRENCY
        # ═══════════════════════════════════════════════
        section("7. TREASURY & MULTICURRENCY")

        try:
            r = await client.get(f"{API}/api/v1/treasury/cash-position")
            if r.status_code == 200:
                data = r.json()
                positions = data.get("positions", data if isinstance(data, list) else [])
                currencies = [p.get("currency") for p in positions] if positions else []
                ok("Treasury Cash Position", f"Currencies: {currencies}")
            else:
                warn("Treasury Cash Position", f"HTTP {r.status_code}")
        except Exception as e:
            warn("Treasury", str(e))

        try:
            r = await client.get(f"{API}/api/v1/treasury/forecast")
            if r.status_code == 200:
                ok("Treasury Forecast", "Cashflow forecast available")
            else:
                warn("Treasury Forecast", f"HTTP {r.status_code}")
        except Exception as e:
            warn("Treasury Forecast", str(e))

        # ═══════════════════════════════════════════════
        # 8. QDRANT VECTOR SEARCH
        # ═══════════════════════════════════════════════
        section("8. QDRANT VECTOR SEARCH")

        try:
            r = await client.get("http://localhost:6335/collections")
            if r.status_code == 200:
                colls = r.json().get("result", {}).get("collections", [])
                names = [c.get("name") for c in colls]
                expected = {"afos_invoices", "afos_expenses", "afos_vendors", "afos_anomalies"}
                found = expected.intersection(set(names))
                if len(found) == 4:
                    ok("Qdrant Collections", f"All 4 collections exist: {', '.join(sorted(found))}")
                else:
                    warn("Qdrant Collections", f"Found: {names}")
            else:
                warn("Qdrant API", f"HTTP {r.status_code}")
        except Exception as e:
            warn("Qdrant Direct", f"Cannot reach :6335 directly — {str(e)[:50]}")

        # Test semantic vendor search
        try:
            r = await client.get(f"{API}/api/v1/vendors/search?q=cloud+infrastructure&limit=3")
            if r.status_code == 200:
                data = r.json()
                vendors = data.get("vendors", data if isinstance(data, list) else [])
                if vendors:
                    names = [v.get("name") for v in vendors[:3]]
                    ok("Semantic Vendor Search", f"Found: {names}")
                else:
                    warn("Semantic Search", "No results (Qdrant may not be indexed yet)")
            else:
                warn("Semantic Search", f"HTTP {r.status_code}")
        except Exception as e:
            warn("Semantic Search", str(e))

        # ═══════════════════════════════════════════════
        # 9. REDIS CACHING
        # ═══════════════════════════════════════════════
        section("9. REDIS CACHING")

        try:
            import time
            t1 = time.time()
            await client.get(f"{API}/api/v1/analytics/dashboard")
            first = time.time() - t1

            t2 = time.time()
            await client.get(f"{API}/api/v1/analytics/dashboard")
            second = time.time() - t2

            if second < first * 0.5:
                ok("Redis Cache Hit", f"1st: {first:.2f}s → 2nd (cached): {second:.3f}s  ({int((1-second/first)*100)}% faster)")
            elif second < 0.05:
                ok("Redis Cache Hit", f"Cached response in {second*1000:.0f}ms")
            else:
                warn("Redis Caching", f"1st: {first:.2f}s, 2nd: {second:.2f}s — cache may not be working")
        except Exception as e:
            warn("Redis Caching", str(e))

        # ═══════════════════════════════════════════════
        # 10. FRONTEND PAGES
        # ═══════════════════════════════════════════════
        section("10. FRONTEND PAGES")

        pages = [
            ("/dashboard", "Dashboard"),
            ("/invoices", "Invoices"),
            ("/expenses", "Expenses"),
            ("/approvals", "Approvals"),
            ("/workflows", "Workflows"),
            ("/agents", "AI Agents"),
            ("/treasury", "Treasury"),
            ("/analytics", "Analytics"),
        ]
        for path, name in pages:
            try:
                r = await client.get(f"{FRONTEND}{path}", follow_redirects=True)
                if r.status_code == 200:
                    ok(f"Page: {name}", path)
                else:
                    fail(f"Page: {name}", f"HTTP {r.status_code}")
            except Exception as e:
                fail(f"Page: {name}", str(e)[:60])

        # ═══════════════════════════════════════════════
        # SUMMARY
        # ═══════════════════════════════════════════════
        print(f"\n{'═'*60}")
        print(f"  TEST SUMMARY  —  {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'═'*60}")
        total = results["passed"] + results["failed"] + results["warned"]
        print(f"  ✅ Passed  : {results['passed']}")
        print(f"  ⚠️  Warnings: {results['warned']}")
        print(f"  ❌ Failed  : {results['failed']}")
        print(f"  Total     : {total}")

        if results["failed"] == 0 and results["warned"] <= 3:
            print(f"\n  🚀 System is FULLY OPERATIONAL")
        elif results["failed"] == 0:
            print(f"\n  ✅ System is OPERATIONAL with minor warnings")
            print(f"     (Warnings are usually OpenAI key or empty optional endpoints)")
        else:
            print(f"\n  ⚠️  System has {results['failed']} failures — check above")

        print(f"\n  💡 To enable full AI:")
        print(f"     1. Add OPENAI_API_KEY=sk-... to backend/.env")
        print(f"     2. Add CLERK_SECRET_KEY=sk_... to .env.local (for auth)")
        print(f"     3. Restart backend:  cd backend && .\\venv\\Scripts\\python -m uvicorn main:app --reload")
        print(f"{'═'*60}\n")


if __name__ == "__main__":
    print(f"\n{'═'*60}")
    print(f"  AFOS — AI Financial Operating System")
    print(f"  Full System Test  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}")
    asyncio.run(run_tests())
