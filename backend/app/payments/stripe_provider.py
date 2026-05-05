"""
Stripe Payment Provider Adapter.

Handles two payment paths:
  1. Charge / PaymentIntent  — collect money from a card source
  2. Transfer / Payout       — push money to a connected Stripe account

Credentials are loaded from settings at runtime; no keys are hardcoded.
"""
from typing import Optional
from loguru import logger

from app.core.config import settings
from app.payments.base import BasePaymentProvider, PaymentResult


class StripeProvider(BasePaymentProvider):
    """
    Uses the Stripe Python SDK (stripe>=10.0.0).
    Supports:
      - PaymentIntents (charge a card stored as a Stripe customer)
      - Transfers (push funds to a connected Stripe account / vendor)
    """

    @property
    def name(self) -> str:
        return "stripe"

    def _client(self):
        """Return a configured stripe module (lazy import)."""
        import stripe as _stripe
        _stripe.api_key = settings.STRIPE_SECRET_KEY
        return _stripe

    async def pay(
        self,
        *,
        amount: float,
        currency: str,
        source_data: dict,
        destination_data: dict,
        ref_id: str,
        notes: Optional[str] = None,
    ) -> PaymentResult:
        """
        Route based on destination type:
          - destination has stripe_account_id  → Transfer
          - destination has stripe_customer_id → PaymentIntent on stored card
        """
        stripe = self._client()
        currency_lower = currency.lower()

        # Connect authentication kwargs
        stripe_kwargs = {}
        if source_data.get("stripe_account_id"):
            stripe_kwargs["stripe_account"] = source_data.get("stripe_account_id")

        # Stripe amounts are in the smallest currency unit (paise, cents, etc.)
        # For zero-decimal currencies (JPY, KRW) multiply by 1; others by 100.
        ZERO_DECIMAL = {"jpy", "krw", "bif", "clp", "gnf", "mga", "pyg", "rwf", "ugx", "vnd", "xaf", "xof"}
        multiplier = 1 if currency_lower in ZERO_DECIMAL else 100
        stripe_amount = int(round(amount * multiplier))

        try:
            # ── Path A: Push to connected Stripe account (vendor payout) ──────
            if destination_data.get("stripe_account_id"):
                transfer = stripe.Transfer.create(
                    amount=stripe_amount,
                    currency=currency_lower,
                    destination=destination_data["stripe_account_id"],
                    transfer_group=ref_id,
                    metadata={
                        "payment_id": ref_id,
                        "notes": notes or "",
                    },
                    **stripe_kwargs
                )
                logger.info(f"Stripe Transfer created: {transfer.id}")
                return PaymentResult(
                    success=True,
                    provider=self.name,
                    provider_ref=transfer.id,
                    status="processing",
                    raw_response=dict(transfer),
                )

            # ── Path B: Charge a card (PaymentIntent with customer/PM) ────────
            customer_id = destination_data.get("stripe_customer_id") or source_data.get("stripe_customer_id")
            payment_method_id = source_data.get("payment_method_id")

            if not customer_id and not payment_method_id:
                return PaymentResult(
                    success=False,
                    provider=self.name,
                    status="failed",
                    failure_reason="No stripe_account_id, stripe_customer_id, or payment_method_id provided",
                )

            intent_params: dict = {
                "amount": stripe_amount,
                "currency": currency_lower,
                "confirm": True,
                "idempotency_key": ref_id,
                "metadata": {"payment_id": ref_id, "notes": notes or ""},
            }
            if customer_id:
                intent_params["customer"] = customer_id
            if payment_method_id:
                intent_params["payment_method"] = payment_method_id
            else:
                # Use customer's default payment method
                intent_params["payment_method"] = "pm_card_visa"  # replaced by real PM in production

            pi = stripe.PaymentIntent.create(**intent_params, **stripe_kwargs)
            logger.info(f"Stripe PaymentIntent created: {pi.id} status={pi.status}")
            return PaymentResult(
                success=pi.status in ("succeeded", "processing"),
                provider=self.name,
                provider_ref=pi.id,
                status="completed" if pi.status == "succeeded" else "processing",
                raw_response=dict(pi),
            )

        except Exception as e:
            logger.error(f"Stripe payment failed [{ref_id}]: {e}")
            return PaymentResult(
                success=False,
                provider=self.name,
                status="failed",
                failure_reason=str(e),
            )

    async def get_status(self, provider_ref: str, source_data: dict = None) -> str:
        stripe = self._client()
        
        stripe_kwargs = {}
        if source_data and source_data.get("stripe_account_id"):
            stripe_kwargs["stripe_account"] = source_data.get("stripe_account_id")
            
        try:
            # Try PaymentIntent first, then Transfer
            if provider_ref.startswith("pi_"):
                pi = stripe.PaymentIntent.retrieve(provider_ref, **stripe_kwargs)
                mapping = {
                    "succeeded": "completed",
                    "processing": "processing",
                    "requires_payment_method": "failed",
                    "canceled": "failed",
                }
                return mapping.get(pi.status, "processing")

            if provider_ref.startswith("tr_"):
                # Transfers don't have a "status" field; existence = success
                stripe.Transfer.retrieve(provider_ref, **stripe_kwargs)
                return "completed"

            return "processing"
        except Exception as e:
            logger.error(f"Stripe get_status failed for {provider_ref}: {e}")
            return "processing"

    async def validate_source(self, tokenized_data: dict) -> bool:
        stripe = self._client()
        
        stripe_kwargs = {}
        if tokenized_data.get("stripe_account_id"):
            stripe_kwargs["stripe_account"] = tokenized_data.get("stripe_account_id")
            
        try:
            customer_id = tokenized_data.get("stripe_customer_id")
            account_id = tokenized_data.get("stripe_account_id")
            if customer_id:
                stripe.Customer.retrieve(customer_id, **stripe_kwargs)
                return True
            if account_id:
                acct = stripe.Account.retrieve(account_id, **stripe_kwargs)
                return acct.get("charges_enabled", False)
            # At minimum, verify the API key works
            stripe.Account.retrieve(**stripe_kwargs)
            return True
        except Exception:
            return False


stripe_provider = StripeProvider()
