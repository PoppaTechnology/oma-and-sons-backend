import json
import logging
from decimal import Decimal
from django.db import transaction
from django.conf import settings
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment
from .serializers import (
    PaymentSerializer,
    InitializePaymentSerializer,
    VerifyPaymentSerializer,
)
from .services import (
    PaymentService,
    get_payment_service,
    PaystackService,
    FlutterwaveService,
)
from orders.models import Order
from orders.serializers import OrderDetailSerializer

logger = logging.getLogger(__name__)


class InitializePaymentView(APIView):
    """
    Initializes a payment session with the selected provider (Paystack or Flutterwave).
    Retrieves the actual order amount from the database (never trusts frontend amounts).
    Returns the official provider checkout URL.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = InitializePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'error': 'Validation error',
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        order_num = serializer.validated_data.get('order_number')
        order_id = serializer.validated_data.get('order_id')
        email = serializer.validated_data.get('email', '').strip()
        provider = serializer.validated_data.get('provider', 'PAYSTACK')
        callback_url = serializer.validated_data.get('callback_url')

        # Find Order
        order = None
        if order_num:
            clean_num = order_num.strip().lstrip('#')
            order = (
                Order.objects.filter(
                    order_number__in=[
                        order_num.strip(),
                        f"#{clean_num}",
                        clean_num
                    ]
                ).first()
            )
        elif order_id:
            order = Order.objects.filter(id=order_id).first()

        if not order:
            return Response(
                {'success': False, 'error': 'Order not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Ownership and Guest Verification
        if request.user.is_authenticated:
            # If the order belongs to a registered user, only the owner can initialize payment
            if order.user and order.user != request.user:
                return Response(
                    {'success': False, 'error': 'Order not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            # If guest order being paid by authenticated user, verify email if explicitly supplied
            if not order.user and email and order.email.lower() != email.lower():
                return Response(
                    {'success': False, 'error': 'Order not found with the provided details.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Unauthenticated caller: verify customer email against order record
            if email and order.email.lower() != email.lower():
                return Response(
                    {'success': False, 'error': 'Order not found with the provided details.'},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Status Integrity: Check order status
        if order.order_status in ['CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED']:
            return Response(
                {
                    'success': False,
                    'error': 'This order has already been paid for and confirmed.',
                    'order_status': order.order_status
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if order.order_status == 'CANCELLED':
            return Response(
                {
                    'success': False,
                    'error': 'Cannot initialize payment for a cancelled order.',
                    'order_status': order.order_status
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check existing payment for this order
        existing_payment = Payment.objects.filter(order=order).first()
        if existing_payment and existing_payment.payment_status == 'SUCCESSFUL':
            return Response(
                {
                    'success': False,
                    'error': 'Payment for this order was already completed successfully.',
                    'payment_reference': existing_payment.payment_reference
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure order has valid positive amount
        if order.total_amount <= Decimal('0.00'):
            return Response(
                {
                    'success': False,
                    'error': 'Invalid order total amount for payment initialization.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Initialize payment with selected provider API
        try:
            init_result = PaymentService.initialize(
                order=order,
                provider=provider,
                callback_url=callback_url
            )
        except Exception as exc:
            logger.exception(f"Error initializing payment with {provider}: {exc}")
            return Response(
                {
                    'success': False,
                    'error': f"Failed to initialize payment with {provider}.",
                    'details': str(exc)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if not init_result.success:
            return Response(
                {
                    'success': False,
                    'error': init_result.error or init_result.message or "Initialization failed.",
                    'provider': provider
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update or create local Payment record with PENDING status
        with transaction.atomic():
            payment, created = Payment.objects.get_or_create(
                order=order,
                defaults={
                    'payment_provider': provider,
                    'payment_reference': init_result.reference,
                    'payment_status': 'PENDING',
                    'amount': order.total_amount,
                    'gateway_response': init_result.raw_data,
                }
            )

            if not created:
                payment.payment_provider = provider
                payment.payment_reference = init_result.reference
                payment.payment_status = 'PENDING'
                payment.amount = order.total_amount
                payment.gateway_response = init_result.raw_data
                payment.save()

        return Response(
            {
                'success': True,
                'message': 'Payment initialized successfully',
                'provider': provider,
                'payment_reference': payment.payment_reference,
                'amount': str(payment.amount),
                'currency': 'NGN',
                'checkout_url': init_result.checkout_url,
                'order_number': order.order_number
            },
            status=status.HTTP_200_OK
        )


class VerifyPaymentView(APIView):
    """
    Verifies a transaction directly with the external payment gateway (Paystack or Flutterwave).
    Only marks Payment as SUCCESSFUL and Order as CONFIRMED if the provider API confirms validity,
    and amount/currency match expected database records.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'verified': False,
                    'error': 'Validation error',
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        reference = serializer.validated_data['reference'].strip()
        provider = serializer.validated_data.get('provider')
        transaction_id = serializer.validated_data.get('transaction_id')

        # Find payment record
        payment = Payment.objects.select_related('order').filter(payment_reference=reference).first()
        if not payment:
            # Fallback search by order number if reference provided was an order number
            payment = Payment.objects.select_related('order').filter(order__order_number=reference).first()

        if not payment:
            return Response(
                {
                    'success': False,
                    'verified': False,
                    'error': f"Payment record not found for reference '{reference}'."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        order = payment.order

        # Idempotency check: if payment is already confirmed as successful
        if payment.payment_status == 'SUCCESSFUL' and order.order_status == 'CONFIRMED':
            return Response(
                {
                    'success': True,
                    'verified': True,
                    'message': 'Payment already verified and confirmed successfully.',
                    'payment': PaymentSerializer(payment).data,
                    'order': OrderDetailSerializer(order).data
                },
                status=status.HTTP_200_OK
            )

        target_provider = provider or payment.payment_provider

        # Query provider verification API
        try:
            verify_result = PaymentService.verify(
                reference=payment.payment_reference,
                provider=target_provider,
                transaction_id=transaction_id
            )
        except Exception as exc:
            logger.exception(f"Error calling verification API for {target_provider}: {exc}")
            return Response(
                {
                    'success': False,
                    'verified': False,
                    'error': 'Error communicating with payment gateway for verification.',
                    'details': str(exc)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if not verify_result.success or not verify_result.verified:
            # Mark payment as FAILED
            payment.mark_failed(gateway_response=verify_result.gateway_response)
            return Response(
                {
                    'success': False,
                    'verified': False,
                    'error': verify_result.error or verify_result.message or "Payment was not successful.",
                    'status': verify_result.status,
                    'payment': PaymentSerializer(payment).data
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Integrity Check 1: Currency must match NGN
        if verify_result.currency != 'NGN':
            logger.error(f"Security Alert: Currency mismatch for ref {reference}. Expected NGN, got {verify_result.currency}")
            payment.mark_failed(gateway_response=verify_result.gateway_response)
            return Response(
                {
                    'success': False,
                    'verified': False,
                    'error': f"Payment currency mismatch. Expected NGN, got {verify_result.currency}."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Integrity Check 2: Amount must match expected Order amount
        expected_amount = payment.amount
        verified_amount = verify_result.amount
        if verified_amount is None or verified_amount != expected_amount:
            logger.error(f"Security Alert: Amount mismatch for ref {reference}. Expected {expected_amount}, verified {verified_amount}")
            payment.mark_failed(gateway_response=verify_result.gateway_response)
            return Response(
                {
                    'success': False,
                    'verified': False,
                    'error': f"Payment amount mismatch. Expected ₦{expected_amount}, received ₦{verified_amount}."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # All checks passed! Atomically mark Payment as SUCCESSFUL and Order as CONFIRMED
        with transaction.atomic():
            payment.payment_status = 'SUCCESSFUL'
            payment.gateway_response = verify_result.gateway_response
            payment.save(update_fields=['payment_status', 'gateway_response', 'updated_at'])

            order.order_status = 'CONFIRMED'
            order.save(update_fields=['order_status', 'updated_at'])

        return Response(
            {
                'success': True,
                'verified': True,
                'message': 'Payment verified successfully! Order is confirmed.',
                'payment': PaymentSerializer(payment).data,
                'order': OrderDetailSerializer(order).data
            },
            status=status.HTTP_200_OK
        )


class PaystackWebhookView(APIView):
    """
    Secure webhook listener for Paystack charge events.
    Verifies HMAC-SHA512 signature using PAYSTACK_SECRET_KEY.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        paystack_service = PaystackService()
        if not paystack_service.verify_webhook_signature(request.body, request.META):
            logger.warning("Rejected unauthorized Paystack webhook request (invalid signature).")
            return Response({'error': 'Invalid webhook signature.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return Response({'error': 'Invalid JSON payload.'}, status=status.HTTP_400_BAD_REQUEST)

        event = payload.get('event')
        if event != 'charge.success':
            return Response({'status': 'ignored', 'event': event}, status=status.HTTP_200_OK)

        data = payload.get('data', {})
        reference = data.get('reference')
        if not reference:
            return Response({'error': 'Missing reference in webhook payload.'}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.select_related('order').filter(payment_reference=reference).first()
        if not payment:
            logger.warning(f"Paystack webhook received for unknown reference: {reference}")
            return Response({'status': 'ignored', 'message': 'Payment reference not found.'}, status=status.HTTP_200_OK)

        # Idempotency check
        if payment.payment_status == 'SUCCESSFUL':
            return Response({'status': 'already_processed'}, status=status.HTTP_200_OK)

        amount_kobo = data.get('amount', 0)
        currency = data.get('currency', 'NGN').upper()
        amount_naira = Decimal(str(amount_kobo)) / Decimal('100.00')

        if currency != 'NGN' or amount_naira != payment.amount:
            logger.error(f"Paystack webhook amount/currency mismatch for ref {reference}.")
            return Response({'error': 'Amount or currency mismatch.'}, status=status.HTTP_400_BAD_REQUEST)

        # Confirm payment and order
        with transaction.atomic():
            payment.payment_status = 'SUCCESSFUL'
            payment.gateway_response = data
            payment.save(update_fields=['payment_status', 'gateway_response', 'updated_at'])

            payment.order.order_status = 'CONFIRMED'
            payment.order.save(update_fields=['order_status', 'updated_at'])

        logger.info(f"Paystack webhook successfully processed for order {payment.order.order_number}")
        return Response({'status': 'processed'}, status=status.HTTP_200_OK)


class FlutterwaveWebhookView(APIView):
    """
    Secure webhook listener for Flutterwave charge events.
    Verifies verif-hash header against FLUTTERWAVE_SECRET_HASH.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        flw_service = FlutterwaveService()
        if not flw_service.verify_webhook_signature(request.body, request.META):
            logger.warning("Rejected unauthorized Flutterwave webhook request (invalid hash).")
            return Response({'error': 'Invalid webhook signature hash.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return Response({'error': 'Invalid JSON payload.'}, status=status.HTTP_400_BAD_REQUEST)

        data = payload.get('data', {})
        reference = data.get('tx_ref') or payload.get('tx_ref')
        tx_id = data.get('id') or payload.get('id')

        if not reference and not tx_id:
            return Response({'error': 'Missing reference or transaction ID in webhook.'}, status=status.HTTP_400_BAD_REQUEST)

        payment = None
        if reference:
            payment = Payment.objects.select_related('order').filter(payment_reference=reference).first()

        if not payment:
            return Response({'status': 'ignored', 'message': 'Payment not found.'}, status=status.HTTP_200_OK)

        # Idempotency check
        if payment.payment_status == 'SUCCESSFUL':
            return Response({'status': 'already_processed'}, status=status.HTTP_200_OK)

        # Perform verification check with Flutterwave API to ensure event legitimacy
        verify_result = flw_service.verify_payment(reference=payment.payment_reference, transaction_id=str(tx_id) if tx_id else None)
        if not verify_result.verified or verify_result.amount != payment.amount or verify_result.currency != 'NGN':
            logger.error(f"Flutterwave webhook verification failed for ref {payment.payment_reference}.")
            return Response({'error': 'Verification failed.'}, status=status.HTTP_400_BAD_REQUEST)

        # Confirm payment and order
        with transaction.atomic():
            payment.payment_status = 'SUCCESSFUL'
            payment.gateway_response = data
            payment.save(update_fields=['payment_status', 'gateway_response', 'updated_at'])

            payment.order.order_status = 'CONFIRMED'
            payment.order.save(update_fields=['order_status', 'updated_at'])

        logger.info(f"Flutterwave webhook successfully processed for order {payment.order.order_number}")
        return Response({'status': 'processed'}, status=status.HTTP_200_OK)
