"""Invoice API routes — full CRUD + AI pipeline with Redis caching + Qdrant dedup."""
import os
import uuid
import aiofiles
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from loguru import logger

from app.core.database import get_db
from app.core.config import settings
from app.core.redis_client import cache, TTL_DASHBOARD
from app.core.vector_store import vector_store
from app.models.models import Invoice, Vendor, Approval, AuditLog, Organization
from app.agents.invoice_agent import invoice_agent
from app.agents.compliance_agent import compliance_agent
from app.api.deps import get_org_id

router = APIRouter()


class InvoiceUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[datetime] = None


async def extract_text_from_file(file_path: str, content_type: str) -> str:
    """Extract text from PDF or image file."""
    try:
        if "pdf" in content_type.lower():
            import PyPDF2
            text = ""
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
            return text
        else:
            try:
                import pytesseract
                from PIL import Image
                img = Image.open(file_path)
                return pytesseract.image_to_string(img)
            except ImportError:
                return f"Image file: {os.path.basename(file_path)}"
    except Exception as e:
        logger.error(f"File extraction error: {e}")
        return ""


async def process_invoice_background(invoice_id: str, file_path: str, content_type: str, org_id: str):
    """
    Background task: full AI invoice processing pipeline.
    Steps: OCR → AI Extraction → Qdrant Duplicate Check → Vendor Match →
           Risk Analysis → Compliance → Approval Creation → Vector Index
    """
    from app.core.database import AsyncSessionLocal
    from app.core.model_router import model_router

    async with AsyncSessionLocal() as db:
        try:
            invoice = await db.get(Invoice, invoice_id)
            if not invoice:
                return

            # ── Step 1: OCR extraction ───────────────────────────────────────
            raw_text = await extract_text_from_file(file_path, content_type)
            invoice.ocr_raw_text = raw_text
            invoice.status = "processing"
            await db.commit()

            # ── Step 2: AI field extraction (GPT-4o-mini) ───────────────────
            extracted = await invoice_agent.extract_from_text(
                raw_text or f"Invoice file: {os.path.basename(file_path)}"
            )
            invoice.extracted_fields = extracted
            invoice.invoice_number = extracted.get("invoice_number")
            invoice.description = extracted.get("description")

            if extracted.get("amount"):
                invoice.amount = float(extracted["amount"] or 0)
            if extracted.get("tax_amount"):
                invoice.tax_amount = float(extracted["tax_amount"] or 0)
            if extracted.get("total_amount"):
                invoice.total_amount = float(extracted["total_amount"] or 0)
            if extracted.get("currency"):
                invoice.currency = extracted["currency"]
            if extracted.get("due_date"):
                try:
                    invoice.due_date = datetime.fromisoformat(extracted["due_date"])
                except Exception:
                    pass

            await db.commit()

            # ── Step 3: Qdrant duplicate detection ──────────────────────────
            # Build embedding text from extracted fields
            embed_text = (
                f"{extracted.get('vendor_name', '')} "
                f"{extracted.get('invoice_number', '')} "
                f"{extracted.get('total_amount', '')} "
                f"{extracted.get('currency', '')} "
                f"{extracted.get('invoice_date', '')} "
                f"{extracted.get('description', '')}"
            ).strip()

            logger.info(f"Invoice {invoice_id[:8]}: embedding text = '{embed_text[:120]}'")
            embedding = await model_router.embed(embed_text)

            if not embedding:
                logger.warning(
                    f"Invoice {invoice_id[:8]}: embedding failed (empty result) — "
                    "skipping duplicate detection. Check OPENAI_API_KEY."
                )
            else:
                duplicates = await vector_store.find_duplicate_invoices(
                    embedding=embedding,
                    org_id=org_id,
                    threshold=0.94,
                    exclude_id=invoice_id,
                )
                if duplicates:
                    invoice.is_duplicate = True
                    invoice.status = "duplicate"
                    await db.commit()
                    logger.warning(f"Invoice {invoice_id} flagged as duplicate: {duplicates[0]}")
                    # Still index it so future uploads can detect THIS as a duplicate too
                    await vector_store.upsert_invoice(
                        invoice_id=invoice_id,
                        embedding=embedding,
                        payload={"org_id": org_id, **extracted},
                    )
                    return  # Stop further processing

                # Not a duplicate — index it for future dedup checks
                indexed = await vector_store.upsert_invoice(
                    invoice_id=invoice_id,
                    embedding=embedding,
                    payload={"org_id": org_id, **extracted},
                )
                logger.info(f"Invoice {invoice_id[:8]}: indexed in Qdrant (indexed={indexed})")

            # ── Step 4: Vendor matching / creation via dedup utility ──────────
            if extracted.get("vendor_name"):
                from app.core.vendor_utils import find_or_create_vendor
                vendor, created = await find_or_create_vendor(
                    db=db,
                    org_id=org_id,
                    name=extracted["vendor_name"],
                    email=extracted.get("vendor_email"),
                    semantic_threshold=0.88,
                )
                invoice.vendor_id = vendor.id
                # Bust the vendor list cache so the new vendor appears immediately
                # on the Vendors page (TTL_VENDOR_LIST is 5 min without this).
                await cache.invalidate_pattern("vendors")
                if created:
                    logger.info(f"New vendor '{vendor.name}' created and vendor cache invalidated.")

            # ── Step 5: Risk analysis (GPT-4o via compliance model) ──────────
            vendor_history = {}
            if invoice.vendor_id:
                vendor_obj = await db.get(Vendor, invoice.vendor_id)
                if vendor_obj:
                    vendor_history = {
                        "name": vendor_obj.name,
                        "risk_level": vendor_obj.risk_level,
                        "risk_score": float(vendor_obj.risk_score or 0),
                        "total_paid": float(getattr(vendor_obj, "total_paid", 0) or 0),
                        "is_verified": bool(getattr(vendor_obj, "is_verified", False)),
                    }

            risk = await invoice_agent.analyze_risk(
                extracted_fields=extracted,
                vendor_history=vendor_history,
            )
            invoice.risk_level = risk.get("risk_level", "low")
            invoice.risk_score = float(risk.get("risk_score", 0))
            invoice.policy_violations = risk.get("policy_violations", [])

            # ── Step 6: Compliance check (GPT-4o) ───────────────────────────
            compliance_result = await compliance_agent.evaluate(
                transaction={**extracted, "risk_level": invoice.risk_level, "risk_score": invoice.risk_score, "org_id": org_id}
            )
            if compliance_result.get("violations"):
                invoice.policy_violations = (invoice.policy_violations or []) + compliance_result["violations"]

            invoice.status = "awaiting_approval"
            invoice.ai_confidence = float(risk.get("confidence", 0.92))
            await db.commit()

            # ── Step 7: Redis Cache Invalidation ─────────────────────────────
            # We no longer create the Approval record here. 
            # It is created durably within the Temporal workflow's compliance activity.
            await cache.invalidate_pattern("dashboard")
            await cache.invalidate_pattern("analytics")

            # ── Step 9: Publish real-time event ─────────────────────────────
            await cache.publish("invoice_processed", {
                "invoice_id": invoice_id,
                "status": invoice.status,
                "risk_level": invoice.risk_level,
                "amount": float(invoice.total_amount or 0),
                "currency": invoice.currency,
            })

            logger.info(f"✅ Invoice {invoice_id} processed: risk={invoice.risk_level}, status={invoice.status}")

            # ── Step 10: Start Temporal workflow ────────────────────────────
            # This ensures that a durable workflow is running and ready to receive 
            # the 'approve' or 'reject' signals from the UI.
            from app.core.temporal import temporal_manager
            if temporal_manager.client:
                try:
                    await temporal_manager.client.start_workflow(
                        "InvoiceApprovalWorkflow",
                        invoice_id,
                        id=f"invoice-workflow-{invoice_id}",
                        task_queue=settings.TEMPORAL_TASK_QUEUE,
                    )
                    logger.info(f"Temporal workflow started for invoice {invoice_id}")
                except Exception as e:
                    logger.error(f"Failed to auto-start Temporal workflow for invoice {invoice_id}: {e}")

        except Exception as e:
            logger.error(f"Invoice processing failed for {invoice_id}: {e}")
            async with AsyncSessionLocal() as db2:
                inv = await db2.get(Invoice, invoice_id)
                if inv:
                    inv.status = "pending"
                    await db2.commit()


@router.post("/upload")
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    currency: str = Form("USD"),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Upload and enqueue invoice for the AI processing pipeline."""
    file_ext = os.path.splitext(file.filename or "invoice.pdf")[1]
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.STORAGE_LOCAL_PATH, file_name)

    os.makedirs(settings.STORAGE_LOCAL_PATH, exist_ok=True)
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    invoice = Invoice(
        org_id=org_id,
        file_path=file_path,
        currency=currency,
        status="processing",
        amount=0,
        total_amount=0,
    )
    db.add(invoice)
    await db.flush()
    invoice_id = invoice.id
    await db.commit()

    background_tasks.add_task(
        process_invoice_background,
        invoice_id=invoice_id,
        file_path=file_path,
        content_type=file.content_type or "application/pdf",
        org_id=org_id,
    )

    return {
        "id": invoice_id,
        "status": "processing",
        "message": "Invoice uploaded. AI pipeline started (OCR → Extract → Dedup → Risk → Approval).",
    }


@router.get("/")
async def list_invoices(
    status: Optional[str] = None,
    currency: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """List all invoices with optional filtering. Redis-cached for 30s."""
    cache_key = f"{org_id}:{status}:{currency}:{skip}:{limit}"
    cached = await cache.get("invoices", cache_key)
    if cached:
        return cached

    q = select(Invoice).where(Invoice.org_id == org_id).order_by(desc(Invoice.created_at))
    if status:
        q = q.where(Invoice.status == status)
    if currency:
        q = q.where(Invoice.currency == currency)
    q = q.offset(skip).limit(limit)

    result = await db.execute(q)
    invoices = result.scalars().all()
    
    # Fetch vendors in bulk for bank details
    vendor_ids = [inv.vendor_id for inv in invoices if inv.vendor_id]
    vendor_map: dict = {}
    if vendor_ids:
        vq = select(Vendor).where(Vendor.id.in_(vendor_ids))
        vendor_results = await db.execute(vq)
        for v in vendor_results.scalars().all():
            vendor_map[v.id] = v

    # Total count
    count_q = select(func.count(Invoice.id)).where(Invoice.org_id == org_id)
    total = (await db.execute(count_q)).scalar_one_or_none() or 0

    response = {
        "invoices": [_invoice_to_dict(inv, vendor_map.get(inv.vendor_id)) for inv in invoices],
        "total": total,
    }
    await cache.set("invoices", response, 30, cache_key)
    return response


@router.get("/stats/summary")
async def invoice_stats(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Invoice statistics — cached 60s."""
    cached = await cache.get("invoice_stats", org_id)
    if cached:
        return cached

    result = await db.execute(
        select(
            func.count(Invoice.id).label("total"),
            func.sum(Invoice.total_amount).label("total_amount"),
            Invoice.status,
            Invoice.currency,
        ).where(Invoice.org_id == org_id).group_by(Invoice.status, Invoice.currency)
    )
    rows = result.all()
    response = {
        "stats": [
            {"count": r.total, "total_amount": float(r.total_amount or 0), "status": r.status, "currency": r.currency}
            for r in rows
        ]
    }
    await cache.set("invoice_stats", response, 60, org_id)
    return response


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    """Get single invoice details."""
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    vendor = await db.get(Vendor, invoice.vendor_id) if invoice.vendor_id else None
    return _invoice_to_dict(invoice, vendor)


@router.patch("/{invoice_id}")
async def update_invoice(invoice_id: str, update: InvoiceUpdate, db: AsyncSession = Depends(get_db)):
    """Update invoice fields and invalidate caches."""
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(invoice, field, value)
    invoice.updated_at = datetime.utcnow()
    await db.commit()
    await cache.invalidate_pattern("invoices")
    await cache.invalidate_pattern("dashboard")
    vendor = await db.get(Vendor, invoice.vendor_id) if invoice.vendor_id else None
    return _invoice_to_dict(invoice, vendor)


@router.post("/{invoice_id}/analyze")
async def analyze_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    """Re-run AI analysis on an existing invoice."""
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    risk = await invoice_agent.analyze_risk(invoice.extracted_fields or {})
    invoice.risk_level = risk.get("risk_level", "low")
    invoice.risk_score = float(risk.get("risk_score", 0))
    invoice.policy_violations = risk.get("policy_violations", [])
    await db.commit()
    await cache.invalidate_pattern("invoices")
    return {"risk": risk, "invoice_id": invoice_id}


def _invoice_to_dict(inv: Invoice, vendor: "Vendor | None" = None) -> dict:
    vendor_meta = vendor.extra_metadata or {} if vendor else {}
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "status": inv.status,
        "amount": float(inv.amount or 0),
        "currency": inv.currency,
        "tax_amount": float(inv.tax_amount or 0),
        "total_amount": float(inv.total_amount or 0),
        "risk_level": inv.risk_level,
        "risk_score": float(inv.risk_score or 0),
        "ai_confidence": float(inv.ai_confidence or 0),
        "is_duplicate": inv.is_duplicate,
        "description": inv.description,
        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        "extracted_fields": inv.extracted_fields,
        "policy_violations": inv.policy_violations,
        "created_at": inv.created_at.isoformat(),
        "vendor_id": inv.vendor_id,
        "vendor_name": vendor.name if vendor else None,
        # Pre-fill bank details for the approval modal
        "vendor_bank": {
            "account_name": vendor_meta.get("bank_account_name"),
            "account_number": vendor_meta.get("bank_account_number"),
            "ifsc_code": vendor_meta.get("bank_ifsc_code"),
        } if vendor else None,
    }
