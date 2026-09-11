import uuid
import logging
from typing import Optional

from .base import BasePaymentService, PaymentInitResult, PaymentVerifyResult
from .paystack import PaystackService
from .flutterwave import FlutterwaveService

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = {
    'PAYSTACK': PaystackService,
    'FLUTTERWAVE': FlutterwaveService,
}


def get_payment_service(provider: str) -> BasePaymentService:
    """
    Factory function to retrieve the appropriate payment service client.
    Strictly accepts only PAYSTACK and FLUTTERWAVE.
    """
    norm_provider = (provider or '').strip().upper()
    service_cls = SUPPORTED_PROVIDERS.get(norm_provider)
    if not service_cls:
        raise ValueError(f"Unsupported payment provider '{provider}'. Only PAYSTACK and FLUTTERWAVE are supported.")
    return service_cls()


def generate_payment_reference(provider: str) -> str:
    """
    Generates a unique, collision-resistant payment reference prefixed by provider.
    """
    norm_provider = (provider or '').strip().upper()
    prefix = "PST" if norm_provider == "PAYSTACK" else "FLW"
    suffix = uuid.uuid4().hex[:12].upper()
    return f"OS-{prefix}-{suffix}"


class PaymentService:
    """
    High-level payment manager facilitating initialization, verification, and webhook handling.
    """

    @classmethod
    def initialize(cls, order, provider: str, callback_url: Optional[str] = None) -> PaymentInitResult:
        service = get_payment_service(provider)
        reference = generate_payment_reference(provider)
        result = service.initialize_payment(order=order, reference=reference, callback_url=callback_url)
        return result

    @classmethod
    def verify(cls, reference: str, provider: Optional[str] = None, transaction_id: Optional[str] = None) -> PaymentVerifyResult:
        # If provider is not passed, infer from reference prefix if possible
        if not provider:
            ref_upper = reference.upper()
            if "FLW" in ref_upper:
                provider = "FLUTTERWAVE"
            elif "PST" in ref_upper:
                provider = "PAYSTACK"
            else:
                provider = "PAYSTACK"

        service = get_payment_service(provider)
        return service.verify_payment(reference=reference, transaction_id=transaction_id)


__all__ = [
    'BasePaymentService',
    'PaymentInitResult',
    'PaymentVerifyResult',
    'PaystackService',
    'FlutterwaveService',
    'PaymentService',
    'get_payment_service',
    'generate_payment_reference',
    'SUPPORTED_PROVIDERS',
]
