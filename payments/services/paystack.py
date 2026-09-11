import hmac
import hashlib
import json
import logging
import requests
from decimal import Decimal
from typing import Optional, Dict, Any
from django.conf import settings

from .base import BasePaymentService, PaymentInitResult, PaymentVerifyResult

logger = logging.getLogger(__name__)


class PaystackService(BasePaymentService):
    """
    Service client for Paystack payment gateway REST API.
    """
    provider_name = "PAYSTACK"
    BASE_URL = "https://api.paystack.co"

    def __init__(self, secret_key: Optional[str] = None, public_key: Optional[str] = None):
        self.secret_key = secret_key or getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        self.public_key = public_key or getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def initialize_payment(self, order, reference: str, callback_url: Optional[str] = None) -> PaymentInitResult:
        """
        Initializes a transaction on Paystack and returns the authorization URL.
        Amount must be provided in Kobo (NGN * 100).
        """
        if not self.secret_key:
            logger.error("Paystack initialization failed: PAYSTACK_SECRET_KEY is not configured.")
            return PaymentInitResult(
                success=False,
                error="Payment gateway configuration error. Please check server settings.",
                message="Paystack secret key is not set."
            )

        # Calculate amount in Kobo
        amount_kobo = int(round(Decimal(str(order.total_amount)) * 100))
        resolved_callback = callback_url or getattr(settings, 'PAYMENT_CALLBACK_URL', '')

        payload = {
            "email": order.email,
            "amount": amount_kobo,
            "reference": reference,
            "currency": "NGN",
            "metadata": {
                "order_id": order.id,
                "order_number": order.order_number,
                "customer_name": f"{order.first_name} {order.last_name}".strip(),
                "phone_number": order.phone_number,
                "custom_fields": [
                    {
                        "display_name": "Order Number",
                        "variable_name": "order_number",
                        "value": order.order_number
                    }
                ]
            }
        }
        if resolved_callback:
            payload["callback_url"] = resolved_callback

        url = f"{self.BASE_URL}/transaction/initialize"
        try:
            response = requests.post(url, json=payload, headers=self._get_headers(), timeout=20)
            data = response.json()

            if response.status_code == 200 and data.get("status") is True:
                auth_url = data.get("data", {}).get("authorization_url", "")
                return PaymentInitResult(
                    success=True,
                    checkout_url=auth_url,
                    reference=reference,
                    provider=self.provider_name,
                    amount=order.total_amount,
                    currency="NGN",
                    message="Paystack transaction initialized successfully",
                    raw_data=data.get("data", {})
                )
            else:
                err_msg = data.get("message", "Paystack initialization failed.")
                logger.error(f"Paystack initialization error [{response.status_code}]: {err_msg}")
                return PaymentInitResult(
                    success=False,
                    error=err_msg,
                    message=err_msg,
                    raw_data=data
                )
        except requests.RequestException as exc:
            logger.exception(f"Network error while communicating with Paystack: {exc}")
            return PaymentInitResult(
                success=False,
                error="Failed to connect to Paystack payment gateway. Please try again.",
                message=str(exc)
            )

    def verify_payment(self, reference: str, transaction_id: Optional[str] = None) -> PaymentVerifyResult:
        """
        Verifies a transaction with Paystack using the payment reference.
        """
        if not self.secret_key:
            logger.error("Paystack verification failed: PAYSTACK_SECRET_KEY is not configured.")
            return PaymentVerifyResult(
                success=False,
                error="Payment gateway configuration error.",
                message="Paystack secret key is missing."
            )

        url = f"{self.BASE_URL}/transaction/verify/{reference}"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=20)
            data = response.json()

            if response.status_code == 200 and data.get("status") is True:
                tx_data = data.get("data", {})
                paystack_status = tx_data.get("status", "").lower()
                amount_kobo = tx_data.get("amount", 0)
                amount_naira = (Decimal(str(amount_kobo)) / Decimal("100.00")).quantize(Decimal("0.01"))
                currency = tx_data.get("currency", "NGN").upper()
                tx_ref = tx_data.get("reference", reference)

                if paystack_status == "success":
                    mapped_status = "SUCCESSFUL"
                    is_verified = True
                elif paystack_status in ("failed", "abandoned"):
                    mapped_status = "FAILED"
                    is_verified = False
                else:
                    mapped_status = "PENDING"
                    is_verified = False

                return PaymentVerifyResult(
                    success=True,
                    verified=is_verified,
                    reference=tx_ref,
                    provider=self.provider_name,
                    amount=amount_naira,
                    currency=currency,
                    status=mapped_status,
                    gateway_response=tx_data,
                    message=f"Paystack verification completed with status: {paystack_status}",
                    customer_email=tx_data.get("customer", {}).get("email"),
                    paid_at=tx_data.get("paid_at")
                )
            else:
                err_msg = data.get("message", "Paystack transaction verification failed.")
                return PaymentVerifyResult(
                    success=False,
                    verified=False,
                    reference=reference,
                    provider=self.provider_name,
                    status="FAILED",
                    error=err_msg,
                    message=err_msg,
                    gateway_response=data
                )
        except requests.RequestException as exc:
            logger.exception(f"Network error while verifying Paystack transaction: {exc}")
            return PaymentVerifyResult(
                success=False,
                verified=False,
                reference=reference,
                provider=self.provider_name,
                error="Could not connect to Paystack to verify payment.",
                message=str(exc)
            )

    def verify_webhook_signature(self, request_body: bytes, headers: dict) -> bool:
        """
        Validates Paystack webhook HMAC-SHA512 signature from request headers.
        """
        if not self.secret_key:
            return False

        signature = (
            headers.get("x-paystack-signature") or
            headers.get("X-Paystack-Signature") or
            headers.get("HTTP_X_PAYSTACK_SIGNATURE") or
            ""
        )
        if not signature:
            return False

        computed_signature = hmac.new(
            self.secret_key.encode("utf-8"),
            msg=request_body,
            digestmod=hashlib.sha512
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature)
