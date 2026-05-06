"""
Payment Orchestrator — core execution engine.

Selects the correct provider adapter based on the PaymentSource type,
executes the payment, and persists the result. Both tech users (Stripe /
Razorpay) and non-tech users (UPI / bank / card) flow through this same
class; the only difference is which adapter is selected.

No money is held here — every execution is a direct API call to the
underlying provider.
"""
from datetime import datetime
from typing import Optional
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Payment, PaymentSource, VendorPaymentDetail, Invoice, Vendor
from app.payments.base import BasePaymentProvider, PaymentResult
from app.payments.stripe_provider import stripe_provider
from app.payments.razorpayx_provider import razorpayx_provider
from app.payments.razorpay_route_provider import RazorpayRouteProvider
from app.core.redis_client import cache
from app.core.vendor_utils import update_vendor_spend

razorpay_route_provider = RazorpayRouteProvider()


class PaymentOrchestrator:
    """
    Single execution engine for all payment types.

    Provider selection logic:
        source.type == "stripe"    → StripeProvider  (Transfer / PaymentIntent)
        source.type == "razorpay"  → StripeProvider  (Razorpay native — future)
        source.type == "upi"       → RazorpayXProvider (UPI payout)
        source.type == "bank"      → RazorpayXProvider (IMPS / NEFT)
        source.type == "card"      → StripeProvider  (PaymentIntent)
    """

    # ── Provider registry ──────────────────────────────────────────────────────
    _providers: dict[str, BasePaymentProvider] = {
        "stripe":    stripe_provider,
        "razorpay":  stripe_provider,   # Razorpay standard (card) uses Stripe path for now
        "upi":       razorpay_route_provider,
        "bank":      razorpay_route_provider,
        "card":      razorpay_route_provider,
    }

    def select_provider(self, source_type: str) -> BasePaymentProvider:
        provider = self._providers.get(source_type)
        if not provider:
            raise ValueError(
                f"Unsupported payment source type: '{source_type}'. "
                f"Supported: {list(self._providers.keys())}"
            )
        return provider

    # ── Main execution path ────────────────────────────────────────────────────

    async def execute(
        self,
        *,
        payment_id: str,
        db: AsyncSession,
    ) -> Payment:
        """
        Execute a payment that has already been created in the DB with status=pending.

        Steps:
          1. Load Payment, PaymentSource, VendorPaymentDetail
          2. Select provider
          3. Call provider.pay()
          4. Persist result
          5. Optionally mark linked Invoice as paid
          6. Invalidate caches
        """
        payment: Optional[Payment] = await db.get(Payment, payment_id)
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")

        if payment.status not in ("pending",):
            raise ValueError(f"Payment {payment_id} already in state '{payment.status}' — cannot re-execute")

        source: Optional[PaymentSource] = await db.get(PaymentSource, payment.source_id)
        if not source or not source.is_active:
            payment.status = "failed"
            payment.failure_reason = "Payment source not found or inactive"
            await db.commit()
            raise ValueError("Payment source not found or inactive")

        # Resolve primary vendor payment detail
        from sqlalchemy import select
        vpd_result = await db.execute(
            select(VendorPaymentDetail)
            .where(
                VendorPaymentDetail.vendor_id == payment.vendor_id,
                VendorPaymentDetail.is_primary == True,  # noqa: E712
            )
            .limit(1)
        )
        vpd: Optional[VendorPaymentDetail] = vpd_result.scalar_one_or_none()

        if not vpd:
            payment.status = "failed"
            payment.failure_reason = "No primary payment details set for this vendor"
            await db.commit()
            raise ValueError("No primary payment details found for vendor")

        provider = self.select_provider(source.type)

        # Mark payment as processing before hitting the provider
        payment.status = "processing"
        payment.provider = provider.name
        payment.executed_at = datetime.utcnow()
        await db.commit()

        logger.info(
            f"[Orchestrator] Executing payment {payment_id[:8]} | "
            f"source={source.type} | provider={provider.name} | "
            f"amount={payment.amount} {payment.currency}"
        )

        try:
            result: PaymentResult = await provider.pay(
                amount=float(payment.amount),
                currency=payment.currency,
                source_data=source.tokenized_data or {},
                destination_data={**vpd.details, "method": vpd.method},
                ref_id=payment_id,
                notes=payment.notes,
            )
        except Exception as exc:
            logger.exception(f"[Orchestrator] Provider raised unhandled exception: {exc}")
            result = PaymentResult(
                success=False,
                provider=provider.name,
                status="failed",
                failure_reason=str(exc),
            )

        # Persist result
        payment.status = result.status
        payment.provider_ref = result.provider_ref
        payment.failure_reason = result.failure_reason
        payment.action_required = result.action_required
        payment.action_data = result.action_data

        if result.status == "completed":
            payment.completed_at = datetime.utcnow()
            # Mark linked invoice as paid
            if payment.invoice_id:
                invoice: Optional[Invoice] = await db.get(Invoice, payment.invoice_id)
                if invoice:
                    invoice.status = "paid"
                    invoice.paid_at = datetime.utcnow()

            # Update vendor total_paid (normalized to org base currency)
            if payment.vendor_id:
                vendor: Optional[Vendor] = await db.get(Vendor, payment.vendor_id)
                if vendor:
                    await update_vendor_spend(
                        db=db,
                        vendor=vendor,
                        amount=float(payment.amount),
                        currency=payment.currency,
                        org_id=payment.org_id
                    )

        await db.commit()

        # Invalidate relevant caches
        for pattern in ("payments", "invoices", "dashboard", "treasury_summary", "vendors"):
            await cache.invalidate_pattern(pattern)

        logger.info(
            f"[Orchestrator] Payment {payment_id[:8]} → {result.status} "
            f"(ref={result.provider_ref})"
        )
        return payment

    # ── Status sync (called by webhook handler or polling) ────────────────────

    async def sync_status(
        self,
        *,
        payment: Payment,
        db: AsyncSession,
    ) -> Payment:
        """
        Poll the provider for the latest status and persist any changes.
        Called by the webhook handler when a provider pushes an update,
        or by a background polling task for long-running transfers.
        """
        if not payment.provider_ref or payment.status in ("completed", "failed", "refunded"):
            return payment

        source: Optional[PaymentSource] = await db.get(PaymentSource, payment.source_id)
        if not source:
            return payment

        provider = self.select_provider(source.type)
        latest_status = await provider.get_status(payment.provider_ref, source.tokenized_data)

        if latest_status != payment.status:
            payment.status = latest_status
            if latest_status == "completed":
                payment.completed_at = datetime.utcnow()
                if payment.invoice_id:
                    invoice = await db.get(Invoice, payment.invoice_id)
                    if invoice:
                        invoice.status = "paid"
                        invoice.paid_at = datetime.utcnow()
            await db.commit()
            await cache.invalidate_pattern("payments")
            await cache.invalidate_pattern("invoices")

        return payment
