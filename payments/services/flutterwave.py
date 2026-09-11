import hmac
import logging
import requests
from decimal import Decimal
from typing import Optional, Dict, Any
from django.conf import settings

from .base import BasePaymentService, PaymentInitResult, PaymentVerifyResult

logger = logging.getLogger(__name__)


class FlutterwaveService(BasePaymentService):
    """
    Service client for Flutterwave v3 payment gateway REST API.
    """
    provider_name = "FLUTTERWAVE"
    BASE_URL = "https://api.flutterwave.com/v3"

    def __init__(self, secret_key: Optional[str] = None, public_key: Optional[str] = None, secret_hash: Optional[str] = None):
        self.secret_key = secret_key or getattr(settings, 'FLUTTERWAVE_SECRET_KEY', '')
        self.public_key = public_key or getattr(settings, 'FLUTTERWAVE_PUBLIC_KEY', '')
        self.secret_hash = secret_hash or getattr(settings, 'FLUTTERWAVE_SECRET_HASH', '')

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def initialize_payment(self, order, reference: str, callback_url: Optional[str] = None) -> PaymentInitResult:
        """
        Initializes a transaction on Flutterwave (v3 Hosted Checkout) and returns the hosted payment link.
        """
        if not self.secret_key:
            logger.error("Flutterwave initialization failed: FLUTTERWAVE_SECRET_KEY is not configured.")
            return PaymentInitResult(
                success=False,
                error="Payment gateway configuration error. Please check server settings.",
                message="Flutterwave secret key is not set."
            )

        resolved_callback = callback_url or getattr(settings, 'PAYMENT_CALLBACK_URL', '')

        payload = {
            "tx_ref": reference,
            "amount": str(order.total_amount),
            "currency": "NGN",
            "redirect_url": resolved_callback,
            "customer": {
                "email": order.email,
                "phonenumber": order.phone_number,
                "name": f"{order.first_name} {order.last_name}".strip()
            },
            "customizations": {
                "title": "Oma & Sons Dynamics",
                "description": f"Payment for Order {order.order_number}"
            },
            "meta": {
                "order_id": order.id,
                "order_number": order.order_number
            }
        }

        url = f"{self.BASE_URL}/payments"
        try:
            response = requests.post(url, json=payload, headers=self._get_headers(), timeout=20)
            data = response.json()

            if response.status_code == 200 and data.get("status") == "success":
                link = data.get("data", {}).get("link", "")
                return PaymentInitResult(
                    success=True,
                    checkout_url=link,
                    reference=reference,
                    provider=self.provider_name,
                    amount=order.total_amount,
                    currency="NGN",
                    message="Flutterwave payment link generated successfully",
                    raw_data=data.get("data", {})
                )
            else:
                err_msg = data.get("message", "Flutterwave payment initialization failed.")
                logger.error(f"Flutterwave initialization error [{response.status_code}]: {err_msg}")
                return PaymentInitResult(
                    success=False,
                    error=err_msg,
                    message=err_msg,
                    raw_data=data
                )
        except requests.RequestException as exc:
            logger.exception(f"Network error while communicating with Flutterwave: {exc}")
            return PaymentInitResult(
                success=False,
                error="Failed to connect to Flutterwave payment gateway. Please try again.",
                message=str(exc)
            )

    def verify_payment(self, reference: str, transaction_id: Optional[str] = None) -> PaymentVerifyResult:
        """
        Verifies a transaction with Flutterwave by transaction ID or transaction reference.
        """
        if not self.secret_key:
            logger.error("Flutterwave verification failed: FLUTTERWAVE_SECRET_KEY is not configured.")
            return PaymentVerifyResult(
                success=False,
                error="Payment gateway configuration error.",
                message="Flutterwave secret key is missing."
            )

        if transaction_id:
            url = f"{self.BASE_URL}/transactions/{transaction_id}/verify"
        else:
            url = f"{self.BASE_URL}/transactions/verify_by_reference?tx_ref={reference}"

        try:
            response = requests.get(url, headers=self._get_headers(), timeout=20)
            data = response.json()

            if response.status_code == 200 and data.get("status") == "success":
                tx_data = data.get("data", {})
                flw_status = tx_data.get("status", "").lower()
                amount_val = tx_data.get("amount") or tx_data.get("charged_amount", 0)
                amount = Decimal(str(amount_val)).quantize(Decimal("0.01"))
                currency = tx_data.get("currency", "NGN").upper()
                tx_ref = tx_data.get("tx_ref", reference)

                if flw_status == "successful":
                    mapped_status = "SUCCESSFUL"
                    is_verified = True
                elif flw_status in ("failed", "cancelled"):
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
                    amount=amount,
                    currency=currency,
                    status=mapped_status,
                    gateway_response=tx_data,
                    message=f"Flutterwave verification completed with status: {flw_status}",
                    customer_email=tx_data.get("customer", {}).get("email"),
                    paid_at=tx_data.get("created_at")
                )
            else:
                err_msg = data.get("message", "Flutterwave transaction verification failed.")
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
            logger.exception(f"Network error while verifying Flutterwave transaction: {exc}")
            return PaymentVerifyResult(
                success=False,
                verified=False,
                reference=reference,
                provider=self.provider_name,
                error="Could not connect to Flutterwave to verify payment.",
                message=str(exc)
            )

    def verify_webhook_signature(self, request_body: bytes, headers: dict) -> bool:
        """
        Validates Flutterwave webhook secret hash against configured FLUTTERWAVE_SECRET_HASH.
        """
        if not self.secret_hash:
            return False

        incoming_hash = (
            headers.get("verif-hash") or
            headers.get("Verif-Hash") or
            headers.get("verif_hash") or
            headers.get("HTTP_VERIF_HASH") or
            ""
        )
        if not incoming_hash:
            return False

        return hmac.compare_digest(self.secret_hash, incoming_hash)
