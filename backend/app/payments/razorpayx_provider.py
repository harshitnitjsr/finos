"""
RazorpayX Payout Provider Adapter.

RazorpayX is the business banking / payout arm of Razorpay.
It supports fund transfers via UPI, IMPS, NEFT, and RTGS directly
from a registered business account to any bank/UPI destination.

This adapter handles:
  - UPI payouts     (instant, 24×7)
  - IMPS payouts    (instant, up to ₹5 lakh per txn)
  - NEFT payouts    (near-instant during banking hours)

Credentials loaded from settings; never hardcoded.
Docs: https://razorpay.com/docs/razorpayx/api/payouts/
"""
import hashlib
import hmac
import json
from typing import Optional
from loguru import logger

from app.core.config import settings
from app.payments.base import BasePaymentProvider, PaymentResult


# Razorpay payout status → normalised status
RAZORPAY_STATUS_MAP = {
    "queued": "processing",
    "pending": "processing",
    "processing": "processing",
    "processed": "completed",
    "reversed": "refunded",
    "cancelled": "failed",
    "rejected": "failed",
}


class RazorpayXProvider(BasePaymentProvider):
    """
    Uses the official razorpay Python SDK (razorpay>=1.4.2).
    Dispatches UPI / IMPS / NEFT payouts via RazorpayX.
    """

    @property
    def name(self) -> str:
        return "razorpayx"

    def _client(self, source_data: dict):
        """Return a configured Razorpay client using user's credentials or OAuth token."""
        import razorpay
        
        # If we have an OAuth token, we create a client with dummy basic auth, 
        # and forcefully override the requests Session to send the Bearer token instead.
        access_token = source_data.get("razorpay_access_token")
        if access_token:
            client = razorpay.Client(auth=("", ""))
            client.session.auth = None  # Remove basic auth
            client.session.headers.update({"Authorization": f"Bearer {access_token}"})
            return client
            
        # Fallback to manual API keys if provided
        key_id = source_data.get("razorpay_key_id") or settings.RAZORPAY_KEY_ID
        key_secret = source_data.get("razorpay_key_secret") or settings.RAZORPAY_KEY_SECRET
        return razorpay.Client(auth=(key_id, key_secret))

    def _select_mode(self, method: str) -> str:
        """
        Pick the best payout mode for a given method.
        UPI → UPI; bank → IMPS (instant < ₹5L) or NEFT.
        """
        method_lower = method.lower()
        if method_lower == "upi":
            return "UPI"
        # Default to IMPS for bank transfers (fastest within limits)
        return "IMPS"

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
        Create a RazorpayX payout.

        destination_data shapes:
          UPI  → {"upi_id": "vendor@upi"}
          Bank → {"account_number": "...", "ifsc": "...", "account_name": "..."}
        """
        client = self._client(source_data)
        
        # Must use the user's RazorpayX virtual account number
        account_number = source_data.get("razorpayx_account_number")
        
        if not account_number:
            return PaymentResult(
                success=False,
                provider=self.name,
                status="failed",
                failure_reason="No razorpayx_account_number provided in the payment source",
            )

        # Razorpay amounts are in paisa (smallest unit); 1 INR = 100 paisa
        amount_paisa = int(round(amount * 100))

        try:
            # ── Step 1: Create / resolve fund account ────────────────────────
            fund_account_id = await self._get_or_create_fund_account(
                client=client,
                destination_data=destination_data,
            )

            if not fund_account_id:
                return PaymentResult(
                    success=False,
                    provider=self.name,
                    status="failed",
                    failure_reason="Could not create fund account with provided destination details",
                )

            method = destination_data.get("method", "bank")
            mode = self._select_mode(method)

            # ── Step 2: Create payout ────────────────────────────────────────
            payout_payload = {
                "account_number": account_number,
                "fund_account_id": fund_account_id,
                "amount": amount_paisa,
                "currency": currency.upper(),  # Must be INR for RazorpayX
                "mode": mode,
                "purpose": "payout",
                "queue_if_low_balance": True,
                "reference_id": ref_id,          # Idempotency key
                "narration": notes or f"Payment {ref_id[:8]}",
            }

            payout = client.payout.create(data=payout_payload)

            logger.info(
                f"RazorpayX payout created: {payout.get('id')} "
                f"status={payout.get('status')} mode={mode}"
            )

            raw_status = payout.get("status", "pending")
            return PaymentResult(
                success=True,
                provider=self.name,
                provider_ref=payout["id"],
                status=RAZORPAY_STATUS_MAP.get(raw_status, "processing"),
                raw_response=payout,
            )

        except Exception as e:
            logger.error(f"RazorpayX payout failed [{ref_id}]: {e}")
            return PaymentResult(
                success=False,
                provider=self.name,
                status="failed",
                failure_reason=str(e),
            )

    async def _get_or_create_fund_account(
        self,
        client,
        destination_data: dict,
    ) -> Optional[str]:
        """
        RazorpayX requires a Fund Account object before creating a payout.
        We create one on-the-fly using the vendor's routing details.
        In production, these IDs should be cached in VendorPaymentDetail.details.
        """
        try:
            # If we already have a fund_account_id stored, reuse it
            if destination_data.get("fund_account_id"):
                return destination_data["fund_account_id"]

            contact_name = destination_data.get("account_name") or destination_data.get("name") or "Vendor"
            contact_email = destination_data.get("email") or "vendor@noreply.com"

            # Step A: Create Contact
            contact = client.contact.create(data={
                "name": contact_name,
                "email": contact_email,
                "type": "vendor",
            })
            contact_id = contact["id"]

            method = destination_data.get("method", "bank")

            # Step B: Create Fund Account
            if method == "upi":
                fa_payload = {
                    "contact_id": contact_id,
                    "account_type": "vpa",
                    "vpa": {"address": destination_data["upi_id"]},
                }
            else:
                # bank / IMPS / NEFT
                fa_payload = {
                    "contact_id": contact_id,
                    "account_type": "bank_account",
                    "bank_account": {
                        "name": contact_name,
                        "ifsc": destination_data["ifsc"],
                        "account_number": destination_data["account_number"],
                    },
                }

            fa = client.fund_account.create(data=fa_payload)
            return fa["id"]

        except Exception as e:
            logger.error(f"RazorpayX fund account creation failed: {e}")
            return None

    async def get_status(self, provider_ref: str, source_data: dict = None) -> str:
        client = self._client(source_data or {})
        try:
            payout = client.payout.fetch(provider_ref)
            raw = payout.get("status", "pending")
            return RAZORPAY_STATUS_MAP.get(raw, "processing")
        except Exception as e:
            logger.error(f"RazorpayX get_status failed for {provider_ref}: {e}")
            return "processing"

    async def validate_source(self, tokenized_data: dict) -> bool:
        """
        Verify RazorpayX connectivity using the provided keys or tokens.
        """
        client = self._client(tokenized_data)
        try:
            # For RazorpayX payouts to work, we absolutely need the account number
            account_number = tokenized_data.get("razorpayx_account_number")
            if not account_number:
                # Still technically "valid" if they just connected OAuth, 
                # but they can't execute payouts yet.
                pass 
                
            # Attempt to fetch balance or account details to verify token/keys are active
            try:
                # Fund account fetch is a lightweight call just to test auth
                # If it raises a 401, keys are invalid
                pass
            except Exception:
                pass
                
            client.account.fetch(account_number)
            return True
        except Exception:
            # Gracefully handle: key may be valid but account.fetch is not always available
            # Try a lighter-weight call
            try:
                client.contact.all()
                return True
            except Exception:
                return False

    @staticmethod
    def verify_webhook_signature(payload_body: bytes, signature: str) -> bool:
        """
        Verify a RazorpayX webhook using HMAC-SHA256.
        https://razorpay.com/docs/webhooks/validate-test/
        """
        secret = settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8")
        digest = hmac.new(secret, payload_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)


razorpayx_provider = RazorpayXProvider()
