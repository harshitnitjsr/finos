"""
Payments API — full payment orchestration endpoints.

Routes:
  GET    /payments/sources                          List connected sources
  POST   /payments/sources                          Connect a new source
  PATCH  /payments/sources/{id}                     Update source (set default)
  DELETE /payments/sources/{id}                     Remove a source
  GET    /payments/vendors/{vendor_id}/details       Get vendor payment details
  POST   /payments/vendors/{vendor_id}/details       Set vendor payment details
  DELETE /payments/vendors/{vendor_id}/details/{id}  Remove a vendor detail
  POST   /payments/execute                           Execute a payment
  POST   /payments/execute/invoice/{invoice_id}      Quick-pay an approved invoice
  GET    /payments/                                  List payment history
  GET    /payments/{payment_id}                      Get single payment
  POST   /payments/{payment_id}/sync                 Force-sync status from provider
  POST   /payments/webhook/stripe                    Stripe webhook receiver
  POST   /payments/webhook/razorpay                  Razorpay webhook receiver
"""
import hashlib
import hmac
import json
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, field_validator
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_org_id
from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import cache
from app.models.models import (
    Invoice, Payment, PaymentSource, PaymentStatus, Vendor,
    VendorPaymentDetail,
)
from app.payments import payment_orchestrator

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Schemas
# ─────────────────────────────────────────────────────────────────────────────

class SourceConnect(BaseModel):
    """Body for POST /payments/sources — connect a new payment source."""
    type: str           # stripe | razorpay | upi | bank | card
    display_name: str
    # Tokenized data — what goes here depends on type:
    #   stripe   → {"stripe_account_id": "acct_..."} or {"stripe_customer_id": "cus_..."}
    #   razorpay → {"razorpay_account_id": "..."}
    #   upi      → {"upi_id": "user@upi"}   ← masked before storage
    #   bank     → {"account_number": "...", "ifsc": "...", "account_name": "..."}
    #   card     → {"payment_method_id": "pm_..."}  ← Stripe PM token, never raw PAN
    tokenized_data: dict
    is_default: bool = False

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"stripe", "razorpay", "upi", "bank", "card"}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}")
        return v


class SourceUpdate(BaseModel):
    display_name: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    tokenized_data: Optional[dict] = None


class VendorPaymentDetailCreate(BaseModel):
    """Body for POST /payments/vendors/{id}/details."""
    method: str   # upi | bank | card | stripe_account
    details: dict
    is_primary: bool = True

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        allowed = {"upi", "bank", "card", "stripe_account"}
        if v not in allowed:
            raise ValueError(f"method must be one of {allowed}")
        return v


class ExecutePaymentBody(BaseModel):
    """Body for POST /payments/execute."""
    vendor_id: str
    source_id: str
    amount: float
    currency: str = "INR"
    invoice_id: Optional[str] = None
    notes: Optional[str] = None


class StripeOAuthBody(BaseModel):
    code: str


class RazorpayOAuthBody(BaseModel):
    code: str


# ─────────────────────────────────────────────────────────────────────────────
# Helper serialisers
# ─────────────────────────────────────────────────────────────────────────────

def _source_to_dict(s: PaymentSource) -> dict:
    # Mask sensitive fields before returning to client
    masked_data: dict = {}
    raw: dict = s.tokenized_data or {}
    for k, v in raw.items():
        if isinstance(v, str) and len(v) > 6:
            masked_data[k] = v[:4] + "****" + v[-2:]
        else:
            masked_data[k] = v
    return {
        "id": s.id,
        "type": s.type,
        "provider": s.provider,
        "display_name": s.display_name,
        "tokenized_data": masked_data,
        "is_active": s.is_active,
        "is_default": s.is_default,
        "created_at": s.created_at.isoformat(),
    }


def _vpd_to_dict(v: VendorPaymentDetail) -> dict:
    masked: dict = {}
    raw: dict = v.details or {}
    for k, val in raw.items():
        if k == "account_number" and isinstance(val, str) and len(val) > 4:
            masked[k] = "****" + val[-4:]
        else:
            masked[k] = val
    return {
        "id": v.id,
        "vendor_id": v.vendor_id,
        "method": v.method,
        "details": masked,
        "is_primary": v.is_primary,
        "is_verified": v.is_verified,
        "created_at": v.created_at.isoformat(),
    }


def _payment_to_dict(p: Payment) -> dict:
    return {
        "id": p.id,
        "org_id": p.org_id,
        "invoice_id": p.invoice_id,
        "vendor_id": p.vendor_id,
        "source_id": p.source_id,
        "amount": float(p.amount),
        "currency": p.currency,
        "status": p.status,
        "provider": p.provider,
        "provider_ref": p.provider_ref,
        "failure_reason": p.failure_reason,
        "action_required": getattr(p, "action_required", False),
        "action_data": getattr(p, "action_data", None),
        "notes": p.notes,
        "executed_at": p.executed_at.isoformat() if p.executed_at else None,
        "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        "created_at": p.created_at.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Payment Sources
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sources")
async def list_sources(
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Return all connected payment sources for this org (credentials masked)."""
    cached = await cache.get("payment_sources", org_id)
    if cached:
        return cached

    result = await db.execute(
        select(PaymentSource)
        .where(PaymentSource.org_id == org_id, PaymentSource.is_active == True)  # noqa: E712
        .order_by(desc(PaymentSource.is_default), PaymentSource.created_at)
    )
    sources = result.scalars().all()
    response = {"sources": [_source_to_dict(s) for s in sources], "total": len(sources)}
    await cache.set("payment_sources", response, 60, org_id)
    return response


@router.post("/sources", status_code=201)
async def connect_source(
    body: SourceConnect,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Connect a new payment source (Stripe account, UPI, bank, card).
    Credentials in tokenized_data must be provider-issued tokens — never raw secrets.
    """
    # Determine which provider will execute payments for this source type
    provider_map = {
        "stripe": "stripe",
        "razorpay": "razorpay",
        "upi": "razorpayx",
        "bank": "razorpayx",
        "card": "stripe",
    }
    provider = provider_map[body.type]

    # If set_as_default, unset existing defaults
    if body.is_default:
        existing_defaults = await db.execute(
            select(PaymentSource).where(
                PaymentSource.org_id == org_id,
                PaymentSource.is_default == True,  # noqa: E712
            )
        )
        for s in existing_defaults.scalars().all():
            s.is_default = False

    source = PaymentSource(
        org_id=org_id,
        type=body.type,
        provider=provider,
        display_name=body.display_name,
        tokenized_data=body.tokenized_data,
        is_default=body.is_default,
        is_active=True,
    )
    db.add(source)
    await db.commit()
    await cache.invalidate_pattern("payment_sources")

    logger.info(f"Payment source connected: {source.id} type={body.type} org={org_id}")
    return _source_to_dict(source)


@router.patch("/sources/{source_id}")
async def update_source(
    source_id: str,
    body: SourceUpdate,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    source = await db.get(PaymentSource, source_id)
    if not source or source.org_id != org_id:
        raise HTTPException(status_code=404, detail="Payment source not found")

    if body.is_default is True:
        existing = await db.execute(
            select(PaymentSource).where(
                PaymentSource.org_id == org_id,
                PaymentSource.is_default == True,  # noqa: E712
            )
        )
        for s in existing.scalars().all():
            s.is_default = False

    for field, value in body.model_dump(exclude_none=True).items():
        if field == "tokenized_data":
            # Merge dictionary
            existing_data = source.tokenized_data or {}
            source.tokenized_data = {**existing_data, **value}
        else:
            setattr(source, field, value)
    source.updated_at = datetime.utcnow()
    await db.commit()
    await cache.invalidate_pattern("payment_sources")
    return _source_to_dict(source)


@router.delete("/sources/{source_id}", status_code=204)
async def remove_source(
    source_id: str,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    source = await db.get(PaymentSource, source_id)
    if not source or source.org_id != org_id:
        raise HTTPException(status_code=404, detail="Payment source not found")
    # Soft delete
    source.is_active = False
    source.updated_at = datetime.utcnow()
    await db.commit()
    await cache.invalidate_pattern("payment_sources")


@router.get("/sources/stripe/oauth/link")
async def get_stripe_oauth_link(
    org_id: str = Depends(get_org_id),
):
    """Generate a Stripe Connect OAuth URL."""
    client_id = settings.STRIPE_CLIENT_ID
    if not client_id:
        raise HTTPException(status_code=500, detail="STRIPE_CLIENT_ID not configured")
    
    # We redirect back to the frontend payments dashboard where the code is handled
    redirect_uri = f"{settings.PAYMENT_BASE_URL}/dashboard/payments"
    url = f"https://connect.stripe.com/oauth/authorize?response_type=code&client_id={client_id}&scope=read_write&redirect_uri={redirect_uri}&state=stripe"
    return {"url": url}


@router.post("/sources/stripe/oauth", status_code=201)
async def connect_stripe_oauth(
    body: StripeOAuthBody,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    try:
        response = stripe.OAuth.token(
            grant_type="authorization_code",
            code=body.code,
        )
    except Exception as e:
        logger.error(f"Stripe OAuth error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
        
    stripe_user_id = response.get("stripe_user_id")
    if not stripe_user_id:
        raise HTTPException(status_code=400, detail="No stripe_user_id received")
        
    # Get account details
    account = stripe.Account.retrieve(stripe_user_id)
    display_name = account.get("settings", {}).get("dashboard", {}).get("display_name") or account.get("business_profile", {}).get("name") or "Stripe Connect"
    
    source = PaymentSource(
        org_id=org_id,
        type="stripe",
        provider="stripe",
        display_name=display_name,
        tokenized_data={"stripe_account_id": stripe_user_id},
        is_default=False,
        is_active=True,
    )
    db.add(source)
    await db.commit()
    await cache.invalidate_pattern("payment_sources")
    return _source_to_dict(source)


@router.get("/sources/razorpay/oauth/link")
async def get_razorpay_oauth_link(
    org_id: str = Depends(get_org_id),
):
    """Generate a Razorpay Partner OAuth URL."""
    client_id = settings.RAZORPAY_CLIENT_ID
    if not client_id:
        raise HTTPException(status_code=500, detail="RAZORPAY_CLIENT_ID not configured")
    
    redirect_uri = f"{settings.PAYMENT_BASE_URL}/dashboard/payments"
    url = f"https://auth.razorpay.com/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope=read_write&state=razorpay"
    return {"url": url}


@router.post("/sources/razorpay/oauth", status_code=201)
async def connect_razorpay_oauth(
    body: RazorpayOAuthBody,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    import requests
    
    client_id = settings.RAZORPAY_CLIENT_ID
    client_secret = settings.RAZORPAY_CLIENT_SECRET
    
    # Exchange code for token
    token_url = "https://auth.razorpay.com/token"
    payload = {
        "grant_type": "authorization_code",
        "code": body.code,
        "redirect_uri": f"{settings.PAYMENT_BASE_URL}/dashboard/payments"
    }
    
    try:
        resp = requests.post(token_url, json=payload, auth=(client_id, client_secret))
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Razorpay OAuth error: {e}")
        raise HTTPException(status_code=400, detail="Failed to authenticate with Razorpay")
        
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    merchant_id = data.get("razorpay_account_id")
    
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token received")
        
    # We create the source. The user will still need to provide the RazorpayX Account Number separately via the UI update.
    source = PaymentSource(
        org_id=org_id,
        type="razorpay",
        provider="razorpayx",
        display_name=f"Razorpay (Acct: {merchant_id})",
        tokenized_data={
            "razorpay_access_token": access_token,
            "razorpay_refresh_token": refresh_token,
            "razorpay_merchant_id": merchant_id,
            # Placeholder, updated later by the user in UI
            "razorpayx_account_number": "" 
        },
        is_default=False,
        is_active=True,
    )
    db.add(source)
    await db.commit()
    await cache.invalidate_pattern("payment_sources")
    return _source_to_dict(source)


# ─────────────────────────────────────────────────────────────────────────────
# Vendor Payment Details
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/vendors/{vendor_id}/details")
async def get_vendor_payment_details(
    vendor_id: str,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Get all payment routing details for a vendor."""
    result = await db.execute(
        select(VendorPaymentDetail)
        .where(
            VendorPaymentDetail.vendor_id == vendor_id,
            VendorPaymentDetail.org_id == org_id,
        )
        .order_by(desc(VendorPaymentDetail.is_primary))
    )
    details = result.scalars().all()
    return {"details": [_vpd_to_dict(d) for d in details]}


@router.post("/vendors/{vendor_id}/details", status_code=201)
async def set_vendor_payment_details(
    vendor_id: str,
    body: VendorPaymentDetailCreate,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Set payment routing for a vendor.
    If is_primary=True, demotes any existing primary detail.
    Validates vendor belongs to this org.
    """
    vendor = await db.get(Vendor, vendor_id)
    if not vendor or vendor.org_id != org_id:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if body.is_primary:
        existing = await db.execute(
            select(VendorPaymentDetail).where(
                VendorPaymentDetail.vendor_id == vendor_id,
                VendorPaymentDetail.is_primary == True,  # noqa: E712
            )
        )
        for d in existing.scalars().all():
            d.is_primary = False

    vpd = VendorPaymentDetail(
        vendor_id=vendor_id,
        org_id=org_id,
        method=body.method,
        details=body.details,
        is_primary=body.is_primary,
        is_verified=False,  # Requires manual/programmatic verification
    )
    db.add(vpd)
    await db.commit()
    await cache.invalidate_pattern("vendors")

    logger.info(f"Vendor payment detail set: vendor={vendor_id} method={body.method}")
    return _vpd_to_dict(vpd)


@router.delete("/vendors/{vendor_id}/details/{detail_id}", status_code=204)
async def remove_vendor_payment_detail(
    vendor_id: str,
    detail_id: str,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    vpd = await db.get(VendorPaymentDetail, detail_id)
    if not vpd or vpd.vendor_id != vendor_id or vpd.org_id != org_id:
        raise HTTPException(status_code=404, detail="Vendor payment detail not found")
    await db.delete(vpd)
    await db.commit()
    await cache.invalidate_pattern("vendors")


# ─────────────────────────────────────────────────────────────────────────────
# Payment Execution
# ─────────────────────────────────────────────────────────────────────────────

class VerifyPaymentBody(BaseModel):
    payment_id: str
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str

@router.post("/execute/verify", status_code=200)
async def verify_payment(
    body: VerifyPaymentBody,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    from app.payments.razorpay_route_provider import RazorpayRouteProvider
    
    payment = await db.get(Payment, body.payment_id)
    if not payment or payment.org_id != org_id:
        raise HTTPException(status_code=404, detail="Payment not found")
        
    is_valid = RazorpayRouteProvider.verify_signature(
        payment_id=body.razorpay_payment_id,
        order_id=body.razorpay_order_id,
        signature=body.razorpay_signature
    )
    
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid payment signature")
        
    payment.status = "completed"
    payment.completed_at = datetime.utcnow()
    # Save the successful razorpay payment id into provider ref or webhook events
    events = list(payment.webhook_events or [])
    events.append({"type": "frontend_verified", "razorpay_payment_id": body.razorpay_payment_id})
    payment.webhook_events = events
    
    if payment.invoice_id:
        invoice = await db.get(Invoice, payment.invoice_id)
        if invoice:
            invoice.status = "paid"
            invoice.paid_at = datetime.utcnow()
            
    # Update vendor total_paid
    if payment.vendor_id:
        vendor = await db.get(Vendor, payment.vendor_id)
        if vendor:
            vendor.total_paid = float(vendor.total_paid or 0) + float(payment.amount)
            
    await db.commit()
    await cache.invalidate_pattern("payments")
    await cache.invalidate_pattern("invoices")
    await cache.invalidate_pattern("dashboard")
    
    return _payment_to_dict(payment)

@router.post("/execute", status_code=201)
async def execute_payment(
    body: ExecutePaymentBody,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a payment immediately.

    Creates a Payment record then calls the orchestrator.
    Returns the payment record with updated status.
    """
    # Validate source belongs to org
    source = await db.get(PaymentSource, body.source_id)
    if not source or source.org_id != org_id or not source.is_active:
        raise HTTPException(status_code=400, detail="Invalid or inactive payment source")

    # Validate vendor belongs to org
    vendor = await db.get(Vendor, body.vendor_id)
    if not vendor or vendor.org_id != org_id:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Validate invoice if provided
    if body.invoice_id:
        invoice = await db.get(Invoice, body.invoice_id)
        if not invoice or invoice.org_id != org_id:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice.status not in ("approved", "awaiting_approval"):
            raise HTTPException(
                status_code=400,
                detail=f"Invoice status is '{invoice.status}' — must be 'approved' to pay"
            )

    # Create the payment record
    payment = Payment(
        org_id=org_id,
        vendor_id=body.vendor_id,
        source_id=body.source_id,
        invoice_id=body.invoice_id,
        amount=Decimal(str(body.amount)),
        currency=body.currency.upper(),
        status=PaymentStatus.PENDING,
        notes=body.notes,
    )
    db.add(payment)
    await db.flush()  # Get the ID
    await db.commit()

    # Execute through orchestrator
    try:
        payment = await payment_orchestrator.execute(payment_id=payment.id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(f"Payment execution error: {e}")
        raise HTTPException(status_code=500, detail="Payment execution failed")

    return _payment_to_dict(payment)


@router.post("/execute/invoice/{invoice_id}", status_code=201)
async def pay_invoice(
    invoice_id: str,
    source_id: str = Query(..., description="Payment source ID to use"),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Convenience endpoint: pay an approved invoice in one call.
    Reads amount, currency, and vendor from the invoice automatically.
    """
    invoice = await db.get(Invoice, invoice_id)
    if not invoice or invoice.org_id != org_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status not in ("approved", "awaiting_approval"):
        raise HTTPException(
            status_code=400,
            detail=f"Invoice status is '{invoice.status}' — must be 'approved' to pay",
        )
    if not invoice.vendor_id:
        raise HTTPException(status_code=400, detail="Invoice has no vendor assigned")

    source = await db.get(PaymentSource, source_id)
    if not source or source.org_id != org_id or not source.is_active:
        raise HTTPException(status_code=400, detail="Invalid or inactive payment source")

    payment = Payment(
        org_id=org_id,
        vendor_id=invoice.vendor_id,
        source_id=source_id,
        invoice_id=invoice_id,
        amount=Decimal(str(invoice.total_amount or invoice.amount or 0)),
        currency=invoice.currency or "INR",
        status=PaymentStatus.PENDING,
        notes=f"Payment for invoice #{invoice.invoice_number}",
    )
    db.add(payment)
    await db.flush()
    await db.commit()

    try:
        payment = await payment_orchestrator.execute(payment_id=payment.id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(f"Invoice pay error: {e}")
        raise HTTPException(status_code=500, detail="Payment execution failed")

    return _payment_to_dict(payment)


# ─────────────────────────────────────────────────────────────────────────────
# Payment History
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/")
async def list_payments(
    status: Optional[str] = None,
    vendor_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(50, ge=1, le=200),
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """List payment history for this org. Redis-cached 30s."""
    cache_key = f"{org_id}:{status}:{vendor_id}:{invoice_id}:{skip}:{limit}"
    cached = await cache.get("payments", cache_key)
    if cached:
        return cached

    q = (
        select(Payment)
        .where(Payment.org_id == org_id)
        .order_by(desc(Payment.created_at))
    )
    if status:
        q = q.where(Payment.status == status)
    if vendor_id:
        q = q.where(Payment.vendor_id == vendor_id)
    if invoice_id:
        q = q.where(Payment.invoice_id == invoice_id)
    q = q.offset(skip).limit(limit)

    result = await db.execute(q)
    payments = result.scalars().all()

    from sqlalchemy import func
    total_q = select(func.count(Payment.id)).where(Payment.org_id == org_id)
    total = (await db.execute(total_q)).scalar_one_or_none() or 0

    # Status summary
    stats_q = (
        select(Payment.status, func.count(Payment.id).label("cnt"))
        .where(Payment.org_id == org_id)
        .group_by(Payment.status)
    )
    stats_res = await db.execute(stats_q)
    status_counts = {r.status: r.cnt for r in stats_res.all()}

    response = {
        "payments": [_payment_to_dict(p) for p in payments],
        "total": total,
        "status_counts": status_counts,
    }
    await cache.set("payments", response, 30, cache_key)
    return response


@router.get("/{payment_id}")
async def get_payment(
    payment_id: str,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    payment = await db.get(Payment, payment_id)
    if not payment or payment.org_id != org_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    return _payment_to_dict(payment)


@router.post("/{payment_id}/sync")
async def sync_payment_status(
    payment_id: str,
    org_id: str = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Force-poll the provider for the latest payment status."""
    payment = await db.get(Payment, payment_id)
    if not payment or payment.org_id != org_id:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment = await payment_orchestrator.sync_status(payment=payment, db=db)
    return _payment_to_dict(payment)


# ─────────────────────────────────────────────────────────────────────────────
# Webhooks
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Receive and verify Stripe webhook events.
    Stripe sends payment_intent.succeeded, payment_intent.payment_failed,
    transfer.paid, etc.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    if webhook_secret:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError:
            logger.warning("Stripe webhook: invalid signature")
            raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    else:
        try:
            event = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    # Map provider_ref → Payment record
    provider_ref = obj.get("id")
    if not provider_ref:
        return {"received": True}

    result = await db.execute(
        select(Payment).where(Payment.provider_ref == provider_ref).limit(1)
    )
    payment: Optional[Payment] = result.scalar_one_or_none()
    if not payment:
        logger.debug(f"Stripe webhook: no payment found for ref {provider_ref}")
        return {"received": True}

    # Append to webhook_events history
    events_log = list(payment.webhook_events or [])
    events_log.append({"type": event_type, "received_at": datetime.utcnow().isoformat()})
    payment.webhook_events = events_log

    # Update status
    status_map = {
        "payment_intent.succeeded": "completed",
        "payment_intent.payment_failed": "failed",
        "payment_intent.canceled": "failed",
        "transfer.paid": "completed",
        "transfer.failed": "failed",
        "charge.refunded": "refunded",
    }
    new_status = status_map.get(event_type)
    if new_status:
        payment.status = new_status
        if new_status == "completed":
            payment.completed_at = datetime.utcnow()
            if payment.invoice_id:
                invoice = await db.get(Invoice, payment.invoice_id)
                if invoice:
                    invoice.status = "paid"
                    invoice.paid_at = datetime.utcnow()

    await db.commit()
    await cache.invalidate_pattern("payments")
    await cache.invalidate_pattern("invoices")

    logger.info(f"Stripe webhook [{event_type}] → payment {payment.id[:8]} → {new_status or 'no-op'}")
    return {"received": True}


@router.post("/webhook/razorpay")
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Receive and verify RazorpayX webhook events.
    RazorpayX sends payout.processed, payout.failed, payout.reversed, etc.
    """
    payload = await request.body()
    sig_header = request.headers.get("x-razorpay-signature", "")
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET

    if webhook_secret:
        from app.payments.razorpayx_provider import RazorpayXProvider
        if not RazorpayXProvider.verify_webhook_signature(payload, sig_header):
            logger.warning("Razorpay webhook: invalid signature")
            raise HTTPException(status_code=400, detail="Invalid Razorpay signature")

    try:
        event = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("event", "")
    payload_data = event.get("payload", {})

    # ── Handle Payment Links (Razorpay Route) ──────────────────────────────────
    if event_type == "payment_link.paid":
        payment_link = payload_data.get("payment_link", {}).get("entity", {})
        notes = payment_link.get("notes", {})
        invoice_id = notes.get("invoice_id")
        
        if invoice_id:
            invoice = await db.get(Invoice, invoice_id)
            if invoice:
                inv_meta = dict(invoice.extra_metadata or {})
                already_credited = inv_meta.get("vendor_credited", False)

                # Always mark invoice as paid (idempotent)
                was_already_paid = invoice.status == "paid"
                invoice.status = "paid"
                if not invoice.paid_at:
                    invoice.paid_at = datetime.utcnow()

                # Update vendor total_paid only once (track via metadata)
                if not already_credited:
                    vendor_id = notes.get("vendor_id") or ""
                    if vendor_id.strip():
                        from app.models.models import Vendor
                        vendor = await db.get(Vendor, vendor_id.strip())
                        if vendor:
                            vendor.total_paid = float(vendor.total_paid or 0) + float(invoice.total_amount or 0)
                            # Also sync the payment_currency to match the invoice so FX display is correct
                            if invoice.currency:
                                vendor.payment_currency = invoice.currency

                            from app.models.models import Expense, ExpenseStatus
                            expense = Expense(
                                org_id=invoice.org_id,
                                vendor_id=vendor.id,  # required for vendor total query join
                                description=f"Paid via Payment Link: {invoice.invoice_number or invoice.id[:8]}",
                                amount=invoice.total_amount or 0,
                                currency=invoice.currency,
                                category=vendor.category or "Accounts Payable",
                                status=ExpenseStatus.APPROVED,
                                vendor_name=vendor.name,
                                transaction_date=invoice.paid_at,
                                extra_metadata={"invoice_id": str(invoice.id), "payment_link_id": payment_link.get("id")}
                            )
                            db.add(expense)

                    # Mark as credited so future duplicate webhooks don't double-count
                    inv_meta["vendor_credited"] = True
                    invoice.extra_metadata = inv_meta

                await db.commit()
                await cache.invalidate_pattern("invoices")
                await cache.invalidate_pattern("vendors")
                await cache.invalidate_pattern("dashboard")
                await cache.invalidate_pattern("expenses")
                logger.info(f"Invoice {invoice_id} marked as PAID via Razorpay Payment Link. (already_paid={was_already_paid}, credited={not already_credited})")

        return {"received": True}

    # ── Handle Payouts (RazorpayX) ─────────────────────────────────────────────
    # RazorpayX payout events carry payout entity
    payout = payload_data.get("payout", {}).get("entity", {})
    provider_ref = payout.get("id")
    reference_id = payout.get("reference_id")  # Our Payment.id

    # Try to find by our reference_id first (most reliable), then provider_ref
    payment: Optional[Payment] = None
    if reference_id:
        result = await db.execute(
            select(Payment).where(Payment.id == reference_id).limit(1)
        )
        payment = result.scalar_one_or_none()
    if not payment and provider_ref:
        result = await db.execute(
            select(Payment).where(Payment.provider_ref == provider_ref).limit(1)
        )
        payment = result.scalar_one_or_none()

    if not payment:
        logger.debug(f"Razorpay webhook: no payment for ref={provider_ref} ref_id={reference_id}")
        return {"received": True}

    events_log = list(payment.webhook_events or [])
    events_log.append({
        "type": event_type,
        "payout_status": payout.get("status"),
        "received_at": datetime.utcnow().isoformat(),
    })
    payment.webhook_events = events_log

    status_map = {
        "payout.processed": "completed",
        "payout.failed": "failed",
        "payout.reversed": "refunded",
        "payout.cancelled": "failed",
        "payout.queued": "processing",
        "payout.pending": "processing",
    }
    new_status = status_map.get(event_type)
    if new_status:
        payment.status = new_status
        if new_status == "completed":
            payment.completed_at = datetime.utcnow()
            if payment.invoice_id:
                invoice = await db.get(Invoice, payment.invoice_id)
                if invoice:
                    invoice.status = "paid"
                    invoice.paid_at = datetime.utcnow()

    await db.commit()
    await cache.invalidate_pattern("payments")
    await cache.invalidate_pattern("invoices")

    logger.info(f"Razorpay webhook [{event_type}] → payment {payment.id[:8]} → {new_status or 'no-op'}")
    return {"received": True}


# ── Alias routes so legacy/configured URLs also work ──────────────────────────
@router.post("/razorpay-webhook")
async def razorpay_webhook_alias(request: Request, db: AsyncSession = Depends(get_db)):
    """Alias for /webhook/razorpay — keeps backward-compat with any configured webhook URL."""
    return await razorpay_webhook(request, db)


@router.post("/stripe-webhook")
async def stripe_webhook_alias(request: Request, db: AsyncSession = Depends(get_db)):
    """Alias for /webhook/stripe — keeps backward-compat with any configured webhook URL."""
    return await stripe_webhook(request, db)
