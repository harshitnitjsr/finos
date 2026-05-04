"""
Seed demo data for AFOS.
Also indexes vendors and invoices into Qdrant vector store on first run.
"""
from datetime import datetime, timedelta
import random
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.models import Organization, Vendor, Invoice, Expense, Approval, Workflow
from loguru import logger


VENDORS_DATA = [
    {"name": "Amazon Web Services", "category": "Cloud Infrastructure", "risk_level": "low", "risk_score": 5.0, "total_paid": 125000, "currency": "USD"},
    {"name": "Salesforce", "category": "Software & SaaS", "risk_level": "low", "risk_score": 8.0, "total_paid": 84000, "currency": "USD"},
    {"name": "Stripe", "category": "Finance & Banking", "risk_level": "low", "risk_score": 3.0, "total_paid": 22000, "currency": "USD"},
    {"name": "HubSpot", "category": "Marketing & Advertising", "risk_level": "low", "risk_score": 12.0, "total_paid": 36000, "currency": "USD"},
    {"name": "GitHub", "category": "Software & SaaS", "risk_level": "low", "risk_score": 5.0, "total_paid": 14400, "currency": "USD"},
    {"name": "Notion Labs", "category": "Software & SaaS", "risk_level": "low", "risk_score": 10.0, "total_paid": 8400, "currency": "USD"},
    {"name": "Figma Inc", "category": "Software & SaaS", "risk_level": "low", "risk_score": 8.0, "total_paid": 7200, "currency": "USD"},
    {"name": "Twilio", "category": "Cloud Infrastructure", "risk_level": "medium", "risk_score": 28.0, "total_paid": 18000, "currency": "USD"},
    {"name": "Unknown Consulting Ltd", "category": "Professional Services", "risk_level": "high", "risk_score": 75.0, "total_paid": 45000, "currency": "USD"},
    {"name": "DataDog", "category": "Cloud Infrastructure", "risk_level": "low", "risk_score": 6.0, "total_paid": 31200, "currency": "USD"},
    {"name": "Razorpay", "category": "Finance & Banking", "risk_level": "low", "risk_score": 4.0, "total_paid": 890000, "currency": "INR"},
    {"name": "Google Cloud India", "category": "Cloud Infrastructure", "risk_level": "low", "risk_score": 5.0, "total_paid": 2400000, "currency": "INR"},
    {"name": "Tata Consultancy", "category": "Professional Services", "risk_level": "low", "risk_score": 15.0, "total_paid": 1800000, "currency": "INR"},
    {"name": "Microsoft Azure EU", "category": "Cloud Infrastructure", "risk_level": "low", "risk_score": 5.0, "total_paid": 45000, "currency": "EUR"},
]

EXPENSE_CATEGORIES = [
    ("Software & SaaS", "Engineering"),
    ("Cloud Infrastructure", "Engineering"),
    ("Marketing & Advertising", "Marketing"),
    ("Travel & Transportation", "Sales"),
    ("Meals & Entertainment", "Operations"),
    ("Professional Services", "Finance"),
    ("HR & Recruitment", "HR"),
    ("Legal & Compliance", "Legal"),
    ("Office Supplies", "Operations"),
    ("Hardware & Equipment", "Engineering"),
]

CURRENCIES = ["USD", "USD", "USD", "USD", "INR", "EUR", "GBP"]


async def seed_demo_data():
    """Seed the database with realistic demo data, then index into Qdrant."""
    async with AsyncSessionLocal() as db:
        # Check if already seeded for this org
        result = await db.execute(select(Vendor).where(Vendor.org_id == "cc95cadf-ba95-474f-929e-b77f8b0b934c").limit(1))
        if result.scalar_one_or_none():
            logger.info("Demo data already seeded for user org, skipping")
            return

        logger.info("Seeding demo data for user org...")

        # Ensure the organization exists
        org = await db.get(Organization, "cc95cadf-ba95-474f-929e-b77f8b0b934c")
        if not org:
            org = Organization(
                id="cc95cadf-ba95-474f-929e-b77f8b0b934c",
                name="Acme Corp (Demo)",
                slug="acme-corp",
                settings={"currency": "USD", "timezone": "UTC"}
            )
            db.add(org)
            await db.flush()
            logger.info("Created demo organization 'cc95cadf-ba95-474f-929e-b77f8b0b934c'")

        # Create vendors
        vendors = []
        for vd in VENDORS_DATA:
            vendor = Vendor(
                org_id="cc95cadf-ba95-474f-929e-b77f8b0b934c",
                name=vd["name"],
                category=vd["category"],
                risk_level=vd["risk_level"],
                risk_score=vd["risk_score"],
                total_paid=vd["total_paid"],
                payment_currency=vd["currency"],
                is_verified=vd["risk_level"] == "low",
                is_active=True,
            )
            db.add(vendor)
            vendors.append(vendor)
        await db.flush()

        # Create invoices (Make all of them pending for easy UI testing)
        statuses = ["pending"]
        invoice_currencies = ["USD", "USD", "USD", "INR", "EUR", "GBP", "USD", "USD"]
        amounts = [12500, 8200, 45000, 850000, 3200, 1500, 99999, 2800, 15000, 38000, 7500, 22000]

        invoices = []
        for i in range(12):
            now = datetime.utcnow()
            vendor = random.choice(vendors[:8])
            currency = invoice_currencies[i % len(invoice_currencies)]
            amount = amounts[i % len(amounts)]
            status = statuses[i % len(statuses)]
            risk_level = "high" if amount > 50000 else "medium" if amount > 10000 else "low"

            inv = Invoice(
                org_id="cc95cadf-ba95-474f-929e-b77f8b0b934c",
                vendor_id=vendor.id,
                invoice_number=f"INV-{2024100 + i}",
                status=status,
                amount=amount * 0.9,
                currency=currency,
                tax_amount=amount * 0.1,
                total_amount=amount,
                invoice_date=now - timedelta(days=random.randint(1, 30)),
                due_date=now + timedelta(days=random.randint(-5, 45)),
                description=f"Services from {vendor.name}",
                risk_level=risk_level,
                risk_score=float(vendor.risk_score),
                ai_confidence=0.94,
                extracted_fields={
                    "vendor_name": vendor.name,
                    "invoice_number": f"INV-{2024100 + i}",
                    "total_amount": amount,
                    "currency": currency,
                    "line_items": [{"description": "Services", "quantity": 1, "unit_price": amount, "total": amount}],
                },
            )
            db.add(inv)
            invoices.append(inv)
        await db.flush()

        # Create expenses (60 entries, realistic spread over 90 days)
        for i in range(60):
            now = datetime.utcnow()
            cat, dept = random.choice(EXPENSE_CATEGORIES)
            currency = random.choice(CURRENCIES)
            base_amounts = {"USD": (500, 8000), "INR": (10000, 200000), "EUR": (400, 6000), "GBP": (350, 5000)}
            lo, hi = base_amounts.get(currency, (500, 8000))
            amount = random.uniform(lo, hi)
            is_anomaly = random.random() < 0.12
            is_recurring = random.random() < 0.3
            vendor_name = random.choice(VENDORS_DATA)["name"]

            exp = Expense(
                org_id="cc95cadf-ba95-474f-929e-b77f8b0b934c",
                description=f"{cat} - {vendor_name}",
                amount=round(amount, 2),
                currency=currency,
                category=cat,
                department=dept,
                vendor_name=vendor_name,
                status="flagged" if is_anomaly else "categorized",
                is_anomaly=is_anomaly,
                anomaly_score=round(random.uniform(0.7, 0.95), 4) if is_anomaly else round(random.uniform(0.0, 0.2), 4),
                anomaly_reason="Spend 3.2x above category average for this month" if is_anomaly else None,
                is_recurring=is_recurring,
                ai_category_confidence=round(random.uniform(0.85, 0.99), 4),
                transaction_date=now - timedelta(days=random.randint(0, 90)),
            )
            db.add(exp)

        # Create approvals for first 6 invoices
        for i, inv in enumerate(invoices[:6]):
            status = "pending" if i < 3 else "approved"
            approval = Approval(
                org_id="cc95cadf-ba95-474f-929e-b77f8b0b934c",
                invoice_id=inv.id,
                status=status,
                requested_by="finance@acme.com",
                assigned_to="cfo@acme.com" if float(inv.total_amount) > 10000 else "manager@acme.com",
                amount=inv.total_amount,
                currency=inv.currency,
                risk_score=inv.risk_score,
                risk_level=inv.risk_level,
                ai_recommendation="approve" if inv.risk_level in ["low", "medium"] else "escalate",
                ai_explanation=(
                    f"Based on vendor history and spend patterns, this {inv.currency} "
                    f"{float(inv.total_amount):,.0f} invoice appears "
                    f"{'standard' if inv.risk_level == 'low' else 'elevated risk'}."
                ),
                policy_checks=[{"policy": "High-Value Threshold", "passed": float(inv.total_amount) < 10000}],
            )
            db.add(approval)

        # Create workflows
        workflow_configs = [
            ("Autonomous Invoice Processing", "invoice_pipeline", "completed", 100),
            ("Expense Categorization Batch", "expense_categorization", "completed", 100),
            ("Approval Routing — INV-2024100", "approval_routing", "running", 65),
            ("Anomaly Investigation #7", "anomaly_investigation", "running", 40),
            ("Vendor Onboarding — Razorpay", "vendor_onboarding", "pending", 0),
            ("Payment Scheduling Q1", "payment_scheduling", "failed", 30),
        ]

        for name, wtype, wstatus, progress in workflow_configs:
            steps_statuses = {
                "completed": ["completed", "completed", "completed", "completed"],
                "running": ["completed", "running", "pending", "pending"],
                "pending": ["pending", "pending", "pending", "pending"],
                "failed": ["completed", "completed", "failed", "pending"],
            }
            step_labels = ["Ingest", "Process", "Validate", "Complete"]
            sstates = steps_statuses.get(wstatus, ["pending"] * 4)

            wf = Workflow(
                org_id="cc95cadf-ba95-474f-929e-b77f8b0b934c",
                name=name,
                workflow_type=wtype,
                status=wstatus,
                steps=[
                    {"id": j + 1, "name": step_labels[j], "status": sstates[j]}
                    for j in range(4)
                ],
                current_step=2 if wstatus in ("running", "failed") else (4 if wstatus == "completed" else 0),
                retry_count=1 if wstatus == "failed" else 0,
                error="Timeout waiting for approval response (48h SLA exceeded)" if wstatus == "failed" else None,
                context={"org_id": "cc95cadf-ba95-474f-929e-b77f8b0b934c", "progress": progress},
                started_at=datetime.utcnow() - timedelta(minutes=random.randint(5, 120)),
            )
            db.add(wf)

        await db.commit()
        logger.info("✅ Demo data seeded successfully")

    # Index vendors into Qdrant (async, non-blocking)
    await _index_vendors_into_qdrant()


async def _index_vendors_into_qdrant():
    """Index all seeded vendors into Qdrant for semantic matching."""
    try:
        from app.core.vector_store import vector_store
        from app.core.model_router import model_router

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Vendor).where(Vendor.org_id == "cc95cadf-ba95-474f-929e-b77f8b0b934c"))
            vendors = result.scalars().all()

        logger.info(f"Indexing {len(vendors)} vendors into Qdrant...")
        embed_texts = [f"{v.name} {v.category or ''} {v.payment_currency or 'USD'}" for v in vendors]
        embeddings = await model_router.embed_batch(embed_texts)

        for vendor, embedding in zip(vendors, embeddings):
            await vector_store.upsert_vendor(
                vendor_id=str(vendor.id),
                embedding=embedding,
                payload={
                    "org_id": vendor.org_id,
                    "name": vendor.name,
                    "category": vendor.category or "",
                    "risk_level": vendor.risk_level,
                    "risk_score": float(vendor.risk_score or 0),
                    "is_verified": bool(vendor.is_verified),
                },
            )
        logger.info(f"✅ {len(vendors)} vendors indexed in Qdrant")
    except Exception as e:
        logger.warning(f"Qdrant vendor indexing failed (non-critical): {e}")
