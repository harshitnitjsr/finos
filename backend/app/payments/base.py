"""
Abstract base class for all payment provider adapters.

Every concrete provider (Stripe, RazorpayX, …) must implement this interface
so the orchestrator can swap providers transparently.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PaymentResult:
    """Normalised result returned by every provider adapter."""
    success: bool
    provider: str                       # "stripe" | "razorpayx"
    provider_ref: Optional[str] = None  # External txn/payout ID
    status: str = "pending"             # pending | processing | completed | failed
    failure_reason: Optional[str] = None
    action_required: bool = False
    action_data: Optional[dict] = None
    raw_response: dict = field(default_factory=dict)


class BasePaymentProvider(ABC):
    """
    All providers expose exactly three async methods.
    The orchestrator only ever calls these; internals are provider-specific.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. 'stripe' or 'razorpayx'."""

    @abstractmethod
    async def pay(
        self,
        *,
        amount: float,
        currency: str,
        source_data: dict,          # tokenized_data from PaymentSource
        destination_data: dict,     # details from VendorPaymentDetail
        ref_id: str,                # Our internal Payment.id — used as idempotency key
        notes: Optional[str] = None,
    ) -> PaymentResult:
        """Initiate the payment. Returns a normalised result immediately."""

    @abstractmethod
    async def get_status(self, provider_ref: str, source_data: dict = None) -> str:
        """
        Poll provider for latest status of a previously initiated payment.
        Returns one of: pending | processing | completed | failed | refunded
        """

    @abstractmethod
    async def validate_source(self, tokenized_data: dict) -> bool:
        """
        Verify that the stored source credentials are still valid.
        Called during source health-check; must not mutate state.
        """
