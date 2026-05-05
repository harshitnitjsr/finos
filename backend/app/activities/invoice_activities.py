from temporalio import activity
from loguru import logger
import asyncio
from typing import Dict, Any

from app.core.database import AsyncSessionLocal
from app.models.models import Invoice
from app.agents.invoice_agent import invoice_agent
from app.agents.compliance_agent import compliance_agent
from app.core.redis_client import cache

@activity.defn
async def extract_invoice_data_activity(invoice_id: str) -> Dict[str, Any]:
    """Uses real AI OCR extraction via the InvoiceAgent."""
    logger.info(f"Activity: Extracting data for invoice {invoice_id}")
    async with AsyncSessionLocal() as db:
        invoice = await db.get(Invoice, invoice_id)
        if not invoice:
            raise Exception(f"Invoice {invoice_id} not found")
        
        raw_text = invoice.ocr_raw_text or f"Invoice {invoice_id}"
        extracted = await invoice_agent.extract_from_text(raw_text)
        
        # Match vendor name from extraction to real vendor in DB
        vendor_name = extracted.get("vendor_name")
        if vendor_name:
            from sqlalchemy import select
            from app.models.models import Vendor
            # Try exact match first
            result = await db.execute(select(Vendor).where(Vendor.name.ilike(f"%{vendor_name}%")).limit(1))
            vendor = result.scalar_one_or_none()
            if vendor:
                invoice.vendor_id = vendor.id
        
        # Update invoice
        invoice.extracted_fields = extracted
        invoice.status = "extracted"
        await db.commit()
        await cache.invalidate_pattern("invoices")
        
        # Ensure we pass the ID to the next activity
        extracted["invoice_id"] = invoice_id
        
        return extracted


@activity.defn
async def check_compliance_policy_activity(invoice_data: Dict[str, Any]) -> Dict[str, Any]:
    """Uses real ComplianceAgent check."""
    logger.info("Activity: Checking policy for invoice data")
    
    # Enrich the transaction data with database fields (risk scores, etc.) before giving to AI
    invoice_id = invoice_data.get("invoice_id", invoice_data.get("id"))
    transaction_context = dict(invoice_data)
    
    async with AsyncSessionLocal() as db:
        invoice = await db.get(Invoice, invoice_id)
        if invoice:
            transaction_context.update({
                "amount": float(invoice.total_amount) if invoice.total_amount else invoice_data.get("total_amount"),
                "vendor_risk_score": invoice.risk_score,
                "is_duplicate": invoice.is_duplicate,
                "vendor_verified": True, # Hardcoded to true for demo, or based on risk
                "is_international": invoice.currency != "USD", # Simple heuristic
            })
    
    compliance_result = await compliance_agent.evaluate(
        transaction=transaction_context
    )
    
    # We decide it requires approval if there are violations
    violations = compliance_result.get("violations", [])
    
    amount = transaction_context.get("amount") or 0
    requires_approval = len(violations) > 0 or float(amount) > 500.0
    
    # Update DB status so the UI knows Temporal is pausing for human input
    if requires_approval:
        from app.models.models import Approval, Workflow
        async with AsyncSessionLocal() as db:
            invoice = await db.get(Invoice, invoice_data.get("invoice_id", invoice_data.get("id")))
            if invoice:
                invoice.status = "awaiting_approval"
                invoice.policy_violations = violations
                
                # Create an explicit Approval record for the unified Approval Center UI
                approval = Approval(
                    org_id=invoice.org_id,
                    invoice_id=invoice.id,
                    status="pending",
                    amount=amount,
                    currency=invoice.currency,
                    risk_score=invoice.risk_score,
                    risk_level=invoice.risk_level,
                    ai_recommendation="review",
                    ai_explanation=f"Workflow flagged {len(violations)} policy violations." if violations else "High value transaction.",
                    policy_checks=[{"policy": v["policy_name"], "passed": False} for v in violations]
                )
                db.add(approval)
                
                # Find and update the live Workflow record to show progress on the graph
                from sqlalchemy import select
                result = await db.execute(select(Workflow).where(Workflow.context.op("->>")("invoice_id") == invoice.id).order_by(Workflow.created_at.desc()))
                wf = result.scalars().first()
                if wf:
                    wf.steps = [
                        {"id": 1, "name": "Extract", "status": "completed"},
                        {"id": 2, "name": "Compliance", "status": "completed"},
                        {"id": 3, "name": "Approval", "status": "running"},
                        {"id": 4, "name": "Payment", "status": "pending"}
                    ]
                    wf.current_step = 2
                
                await db.commit()
                await cache.invalidate_pattern("invoices")
                await cache.invalidate_pattern("approvals")
                await cache.invalidate_pattern("workflows")
    
    return {
        "passed_auto_policy": not requires_approval,
        "requires_human_approval": requires_approval,
        "violations": violations,
        "reason": "Violations found or amount exceeds threshold" if requires_approval else "Within limits",
    }


@activity.defn
async def execute_payment_activity(invoice_id: str) -> str:
    """Executes the payment using the Stripe API in test mode."""
    logger.info(f"Activity: Executing payment for invoice {invoice_id}")
    
    from datetime import datetime
    import razorpay
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from app.core.config import settings
    
    # Initialize Razorpay for Route/Payment Links
    razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    
    async with AsyncSessionLocal() as db:
        # Force a fresh SELECT from Postgres — the approval endpoint may have
        # committed bank details to the vendor row AFTER the session was opened.
        from sqlalchemy import select as sa_select
        from app.models.models import Vendor
        invoice_row = await db.execute(sa_select(Invoice).where(Invoice.id == invoice_id))
        invoice = invoice_row.scalar_one_or_none()
        if not invoice:
            return f"Error: Invoice {invoice_id} not found"

        try:
            amount_in_cents = int(float(invoice.total_amount) * 100) if invoice.total_amount else 1000

            # Fresh SELECT for vendor so bank details committed at approval time are visible
            vendor = None
            if invoice.vendor_id:
                vendor_row = await db.execute(sa_select(Vendor).where(Vendor.id == invoice.vendor_id))
                vendor = vendor_row.scalar_one_or_none()
            
            # Calculate commission
            commission_pct = settings.PLATFORM_COMMISSION_PERCENT or 0.0
            invoice_amount_paise = int(amount_in_cents)
            commission_amount_paise = int(invoice_amount_paise * commission_pct / 100)
            total_amount_paise = invoice_amount_paise + commission_amount_paise
            
            currency = invoice.currency.upper() if invoice.currency else "INR"
            commission_display = f"{currency} {commission_amount_paise / 100:.2f}" if commission_pct else "None"
            
            payment_link_payload = {
                "amount": total_amount_paise,
                "currency": currency,
                "accept_partial": False,
                "description": f"Payment for Invoice {invoice.invoice_number or invoice_id[:8]}" + (f" (incl. {commission_pct}% platform fee)" if commission_pct else ""),
                "customer": {
                    "name": vendor.name if vendor else "Vendor",
                    "email": vendor.email if vendor and vendor.email else "vendor@example.com",
                },
                "notify": {"sms": False, "email": False},
                "reminder_enable": True,
                "notes": {
                    "invoice_id": str(invoice.id),
                    "org_id": invoice.org_id,
                    "vendor_id": str(invoice.vendor_id) if invoice.vendor_id else "",
                    "commission_pct": str(commission_pct),
                    "commission_amount": str(commission_amount_paise / 100),
                }
            }
            
            try:
                link_response = razorpay_client.payment_link.create(payment_link_payload)
                payment_id = link_response.get("id")
                short_url = link_response.get("short_url")
                
                # Save the short_url and mark invoice as payment_pending
                extra_meta = dict(invoice.extra_metadata or {})
                extra_meta["payment_link"] = short_url
                extra_meta["payment_link_id"] = payment_id
                invoice.extra_metadata = extra_meta
                # Do NOT mark as "paid" yet — wait for the Razorpay webhook
                invoice.status = "payment_pending"
                
                # Mark the Temporal workflow as completed
                from sqlalchemy import select
                from app.models.models import Workflow
                result = await db.execute(
                    select(Workflow)
                    .where(Workflow.context.op("->>")("invoice_id") == invoice.id)
                    .order_by(Workflow.created_at.desc())
                )
                wf = result.scalars().first()
                if wf:
                    wf.status = "completed"
                    wf.steps = [
                        {"id": 1, "name": "Extract",    "status": "completed"},
                        {"id": 2, "name": "Compliance", "status": "completed"},
                        {"id": 3, "name": "Approval",   "status": "completed"},
                        {"id": 4, "name": "Payment",    "status": "completed"},
                    ]
                    wf.current_step = 4
                
                await db.commit()
                await cache.invalidate_pattern("invoices")
                await cache.invalidate_pattern("vendors")
                await cache.invalidate_pattern("dashboard")
                await cache.invalidate_pattern("workflows")
                
                logger.info(f"Payment routed via Razorpay Link: {payment_id} -> {short_url}")
                
                # ── Send notification email ───────────────────────────────────
                try:
                    # Re-read extra_metadata after commit so admin_email is fresh
                    admin_email = extra_meta.get("admin_email") or settings.SMTP_FROM_EMAIL
                    
                    vendor_meta = vendor.extra_metadata or {} if vendor else {}
                    bank_name   = vendor_meta.get("bank_account_name")   or "Not provided"
                    bank_number = vendor_meta.get("bank_account_number") or "Not provided"
                    bank_ifsc   = vendor_meta.get("bank_ifsc_code")       or "Not provided"
                    bank_note   = (
                        "" if bank_number != "Not provided"
                        else "\n                    Note: Bank details were not entered at approval time. "
                             "You can add them via the Vendors page."
                    )

                    msg = MIMEMultipart()
                    msg['From'] = settings.SMTP_FROM_EMAIL
                    msg['To'] = admin_email
                    msg['Subject'] = f"Action Required: Pay Vendor Invoice {invoice.invoice_number or invoice_id[:8]}"
                    
                    body = f"""
                    Hello,

                    The invoice for {vendor.name if vendor else 'Unknown Vendor'} has been approved.

                    Please click the link below to securely pay the vendor via Razorpay:
                    {short_url}

                    Vendor Bank Details Provided:
                    Account Name:   {bank_name}
                    Account Number: {bank_number}
                    IFSC Code:      {bank_ifsc}{bank_note}

                    Once paid, the invoice will automatically be marked as Paid in your dashboard.
                    """
                    msg.attach(MIMEText(body, 'plain'))
                    
                    if settings.SMTP_SERVER and settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
                        server.starttls()
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                        server.sendmail(settings.SMTP_FROM_EMAIL, admin_email, msg.as_string())
                        server.quit()
                        logger.info(f"Payment Link email sent to {admin_email} via SMTP.")
                    else:
                        logger.warning(f"SMTP not configured. Simulating Email to {admin_email}...")
                        print(f"\n{'='*50}\n[MOCK EMAIL -> {admin_email}]\n{body}\n{'='*50}\n")
                except Exception as email_err:
                    logger.error(f"Failed to send email: {email_err}")
                
                return f"Payment Link generated successfully! URL: {short_url}"
            except Exception as e:
                logger.exception("Failed to generate Razorpay Payment Link")
                raise Exception(f"Failed to generate Payment Link: {str(e)}")

        except Exception as outer:
            logger.error(f"execute_payment_activity failed for {invoice_id}: {outer}")
            raise
