from typing import Optional
import razorpay
from loguru import logger

from app.core.config import settings
from app.payments.base import BasePaymentProvider, PaymentResult


class RazorpayRouteProvider(BasePaymentProvider):
    """
    Razorpay Route Provider (Payment Gateway + Route).
    Used for Non-Tech users where we must collect money from their bank 
    via a Checkout modal, and automatically split the funds to the vendor.
    """

    @property
    def name(self) -> str:
        return "razorpay_route"

    def _client(self):
        """Always uses the Platform's gateway keys because the platform is the merchant of record."""
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    async def pay(
        self,
        *,
        amount: float,
        currency: str,
        source_data: dict,          # Not used for auth, just tells us it's a non-tech source
        destination_data: dict,     # Vendor's linked account details
        ref_id: str,
        notes: Optional[str] = None,
    ) -> PaymentResult:
        
        client = self._client()
        
        # 1. Vendor must have a Linked Account ID to receive Route transfers
        linked_account_id = destination_data.get("razorpay_linked_account_id")
        if not linked_account_id:
            return PaymentResult(
                success=False,
                provider=self.name,
                status="failed",
                failure_reason="Vendor does not have a Razorpay Linked Account ID (required for Route)",
            )

        # 2. Calculate Split (Platform Fee = ₹10)
        # Razorpay API expects amounts in paise (multiply by 100)
        platform_fee_inr = 10.0
        
        if amount <= platform_fee_inr:
            return PaymentResult(
                success=False,
                provider=self.name,
                status="failed",
                failure_reason=f"Amount ({amount}) must be greater than the platform fee ({platform_fee_inr})",
            )
            
        total_amount_paise = int(amount * 100)
        vendor_transfer_paise = int((amount - platform_fee_inr) * 100)

        # 3. Create the Order with Transfers
        order_payload = {
            "amount": total_amount_paise,
            "currency": currency.upper(),
            "receipt": ref_id,
            "notes": {"payment_id": ref_id},
            "transfers": [
                {
                    "account": linked_account_id,
                    "amount": vendor_transfer_paise,
                    "currency": currency.upper(),
                    "notes": {
                        "branch": "AFOS_Platform"
                    },
                    "linked_account_notes": ["branch"],
                    "on_hold": 0  # 0 means settle immediately after capture
                }
            ]
        }

        try:
            order = client.order.create(order_payload)
            logger.info(f"Created Razorpay Route Order {order['id']} for Payment {ref_id}")
            
            # Since a checkout is required, we return action_required=True
            return PaymentResult(
                success=True,
                provider=self.name,
                provider_ref=order["id"],
                status="pending", # Still pending until they scan the QR
                action_required=True,
                action_data={
                    "type": "razorpay_checkout",
                    "order_id": order["id"],
                    "key_id": settings.RAZORPAY_KEY_ID,
                    "amount": total_amount_paise,
                    "currency": currency.upper(),
                },
                raw_response=order
            )
        except Exception as e:
            logger.exception("Razorpay Route Order Creation Failed")
            return PaymentResult(
                success=False,
                provider=self.name,
                status="failed",
                failure_reason=str(e),
            )

    async def get_status(self, provider_ref: str, source_data: dict = None) -> str:
        """Check order status. If paid, it's completed."""
        client = self._client()
        try:
            order = client.order.fetch(provider_ref)
            if order["status"] == "paid":
                return "completed"
            elif order["status"] == "attempted":
                return "processing"
            else:
                return "pending"
        except Exception:
            return "failed"

    async def validate_source(self, tokenized_data: dict) -> bool:
        """For non-tech sources, validation just assumes True since the user provides it at checkout."""
        return True

    @staticmethod
    def verify_signature(payment_id: str, order_id: str, signature: str) -> bool:
        """Verify the signature returned from the frontend checkout."""
        import hmac
        import hashlib
        msg = f"{order_id}|{payment_id}"
        secret = settings.RAZORPAY_KEY_SECRET.encode("utf-8")
        generated_sig = hmac.new(secret, msg.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated_sig, signature)
