from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict, Any


@dataclass
class PaymentInitResult:
    success: bool
    checkout_url: str = ""
    reference: str = ""
    provider: str = ""
    amount: Optional[Decimal] = None
    currency: str = "NGN"
    message: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class PaymentVerifyResult:
    success: bool
    verified: bool = False
    reference: str = ""
    provider: str = ""
    amount: Optional[Decimal] = None
    currency: str = "NGN"
    status: str = ""  # SUCCESSFUL, FAILED, PENDING
    gateway_response: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: Optional[str] = None
    customer_email: Optional[str] = None
    paid_at: Optional[str] = None


class BasePaymentService(ABC):
    """
    Abstract base class defining interface for all payment gateway integrations.
    """
    provider_name: str = "UNKNOWN"

    @abstractmethod
    def initialize_payment(self, order, reference: str, callback_url: Optional[str] = None) -> PaymentInitResult:
        """
        Calls gateway initialization API to create a checkout session and get the checkout URL.
        """
        pass

    @abstractmethod
    def verify_payment(self, reference: str, transaction_id: Optional[str] = None) -> PaymentVerifyResult:
        """
        Calls gateway verification API to verify transaction status, amount, and currency.
        """
        pass

    @abstractmethod
    def verify_webhook_signature(self, request_body: bytes, headers: dict) -> bool:
        """
        Validates the authenticity of an incoming webhook event from the provider.
        """
        pass
