import hmac
import hashlib
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from payments.models import Payment
from payments.services import (
    PaystackService,
    FlutterwaveService,
    PaymentService,
    get_payment_service,
)
from orders.models import Order, OrderItem
from products.models import Product, Category, ProductVariant


@override_settings(
    PAYSTACK_SECRET_KEY='sk_test_mock_paystack_secret_key',
    PAYSTACK_PUBLIC_KEY='pk_test_mock_paystack_public_key',
    FLUTTERWAVE_SECRET_KEY='FLWSECK_TEST-mock_flw_secret_key',
    FLUTTERWAVE_PUBLIC_KEY='FLWPUBK_TEST-mock_flw_public_key',
    FLUTTERWAVE_SECRET_HASH='mock_flw_secret_hash',
    PAYMENT_CALLBACK_URL='http://localhost:5173/checkout/verify',
)
class PaymentFlowComprehensiveTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create category, product, and variant for test orders
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.product = Product.objects.create(
            category=self.category,
            name='Luxury Blazer',
            slug='luxury-blazer',
            description='Test description'
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            variant_name='Midnight Blue (L)',
            price=Decimal('50000.00'),
            stock_quantity=10
        )

        # Create test order
        self.order = Order.objects.create(
            first_name='Ngozi',
            last_name='Eze',
            email='ngozi@example.com',
            phone_number='+2348012345678',
            subtotal=Decimal('50000.00'),
            delivery_fee=Decimal('2500.00'),
            tax_amount=Decimal('2500.00'),
            total_amount=Decimal('55000.00'),
            order_status='PENDING'
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name=self.product.name,
            variant_name=self.variant.variant_name,
            quantity=1,
            unit_price=Decimal('50000.00'),
            subtotal=Decimal('50000.00')
        )

    # --------------------------------------------------------------------------
    # 1. INITIALIZATION TESTS
    # --------------------------------------------------------------------------

    @patch('requests.post')
    def test_initialize_paystack_payment_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': True,
            'message': 'Authorization URL created',
            'data': {
                'authorization_url': 'https://checkout.paystack.com/0123456789',
                'access_code': '0123456789',
                'reference': 'OS-PST-MOCK12345'
            }
        }
        mock_post.return_value = mock_response

        response = self.client.post('/payments/initialize/', {
            'order_number': self.order.order_number,
            'provider': 'PAYSTACK'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['provider'], 'PAYSTACK')
        self.assertEqual(data['checkout_url'], 'https://checkout.paystack.com/0123456789')
        self.assertEqual(data['amount'], '55000.00')

        # Check Payment model was updated in DB
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.payment_provider, 'PAYSTACK')
        self.assertEqual(payment.payment_status, 'PENDING')
        self.assertEqual(payment.amount, Decimal('55000.00'))

    @patch('requests.post')
    def test_initialize_flutterwave_payment_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'success',
            'message': 'Hosted Link',
            'data': {
                'link': 'https://ravemodal-dev.herokuapp.com/v3/hosted/pay/flw_mock_link'
            }
        }
        mock_post.return_value = mock_response

        response = self.client.post('/payments/initialize/', {
            'order_id': self.order.id,
            'provider': 'FLUTTERWAVE'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['provider'], 'FLUTTERWAVE')
        self.assertEqual(data['checkout_url'], 'https://ravemodal-dev.herokuapp.com/v3/hosted/pay/flw_mock_link')

        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.payment_provider, 'FLUTTERWAVE')
        self.assertEqual(payment.payment_status, 'PENDING')

    def test_initialize_invalid_order_not_found(self):
        response = self.client.post('/payments/initialize/', {
            'order_number': '#NON-EXISTENT-ORDER',
            'provider': 'PAYSTACK'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.json()['success'])

    def test_initialize_invalid_provider_rejected(self):
        response = self.client.post('/payments/initialize/', {
            'order_number': self.order.order_number,
            'provider': 'STRIPE'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()['success'])

    def test_initialize_already_confirmed_order_blocked(self):
        self.order.order_status = 'CONFIRMED'
        self.order.save()

        response = self.client.post('/payments/initialize/', {
            'order_number': self.order.order_number,
            'provider': 'PAYSTACK'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()['success'])
        self.assertIn('already been paid', response.json()['error'])

    def test_initialize_cancelled_order_blocked(self):
        self.order.order_status = 'CANCELLED'
        self.order.save()

        response = self.client.post('/payments/initialize/', {
            'order_number': self.order.order_number,
            'provider': 'PAYSTACK'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()['success'])
        self.assertIn('cancelled order', response.json()['error'])

    @patch('requests.post')
    def test_initialize_amount_tampering_ignored_uses_db_amount(self, mock_post):
        """Even if client attempts to pass amount: 100, the backend initializes with database total 55000.00."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': True,
            'data': {'authorization_url': 'https://checkout.paystack.com/0123456789'}
        }
        mock_post.return_value = mock_response

        response = self.client.post('/payments/initialize/', {
            'order_number': self.order.order_number,
            'amount': 100,  # Attacker attempt
            'provider': 'PAYSTACK'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check amount passed in post payload to Paystack was 5500000 kobo (₦55,000.00), NOT 100
        called_payload = mock_post.call_args[1]['json']
        self.assertEqual(called_payload['amount'], 5500000)
        self.assertEqual(response.json()['amount'], '55000.00')

    def test_initialize_authenticated_non_owner_blocked(self):
        """Customer B cannot initialize payment for Customer A's order."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_a = User.objects.create_user(email='owner@example.com', password='Password123!')
        user_b = User.objects.create_user(email='attacker@example.com', password='Password123!')

        self.order.user = user_a
        self.order.save()

        self.client.force_authenticate(user=user_b)
        response = self.client.post('/payments/initialize/', {
            'order_number': self.order.order_number,
            'provider': 'PAYSTACK'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.json()['success'])

    def test_initialize_guest_with_mismatched_email_blocked(self):
        """Guest payment initialization fails when wrong email is supplied."""
        response = self.client.post('/payments/initialize/', {
            'order_number': self.order.order_number,
            'email': 'wrong_email@example.com',
            'provider': 'PAYSTACK'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.json()['success'])

    # --------------------------------------------------------------------------
    # 2. VERIFICATION TESTS
    # --------------------------------------------------------------------------

    @patch('requests.get')
    def test_verify_paystack_payment_success(self, mock_get):
        payment = Payment.objects.create(
            order=self.order,
            payment_provider='PAYSTACK',
            payment_reference='OS-PST-TESTVERIFY01',
            payment_status='PENDING',
            amount=Decimal('55000.00')
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': True,
            'message': 'Verification successful',
            'data': {
                'id': 998877,
                'status': 'success',
                'reference': 'OS-PST-TESTVERIFY01',
                'amount': 5500000,  # ₦55,000 in kobo
                'currency': 'NGN',
                'gateway_response': 'Successful',
                'paid_at': '2026-09-08T12:00:00.000Z',
                'customer': {'email': 'ngozi@example.com'}
            }
        }
        mock_get.return_value = mock_response

        response = self.client.post('/payments/verify/', {
            'reference': 'OS-PST-TESTVERIFY01'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['verified'])

        # Confirm DB state updated
        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.payment_status, 'SUCCESSFUL')
        self.assertEqual(self.order.order_status, 'CONFIRMED')

    @patch('requests.get')
    def test_verify_flutterwave_payment_success(self, mock_get):
        payment = Payment.objects.create(
            order=self.order,
            payment_provider='FLUTTERWAVE',
            payment_reference='OS-FLW-TESTVERIFY02',
            payment_status='PENDING',
            amount=Decimal('55000.00')
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'success',
            'message': 'Transaction fetched successfully',
            'data': {
                'id': 11223344,
                'tx_ref': 'OS-FLW-TESTVERIFY02',
                'flw_ref': 'FLW-MOCK-REF-99',
                'amount': 55000,
                'charged_amount': 55000,
                'currency': 'NGN',
                'status': 'successful',
                'created_at': '2026-09-08T12:00:00.000Z',
                'customer': {'email': 'ngozi@example.com'}
            }
        }
        mock_get.return_value = mock_response

        response = self.client.post('/payments/verify/', {
            'reference': 'OS-FLW-TESTVERIFY02'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['verified'])

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.payment_status, 'SUCCESSFUL')
        self.assertEqual(self.order.order_status, 'CONFIRMED')

    @patch('requests.get')
    def test_verify_failed_gateway_transaction(self, mock_get):
        payment = Payment.objects.create(
            order=self.order,
            payment_provider='PAYSTACK',
            payment_reference='OS-PST-FAILED01',
            payment_status='PENDING',
            amount=Decimal('55000.00')
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': True,
            'message': 'Verification successful',
            'data': {
                'id': 998877,
                'status': 'failed',
                'reference': 'OS-PST-FAILED01',
                'amount': 5500000,
                'currency': 'NGN',
                'gateway_response': 'Declined'
            }
        }
        mock_get.return_value = mock_response

        response = self.client.post('/payments/verify/', {
            'reference': 'OS-PST-FAILED01'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data['verified'])

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.payment_status, 'FAILED')
        self.assertEqual(self.order.order_status, 'PENDING')

    @patch('requests.get')
    def test_verify_amount_mismatch_fails(self, mock_get):
        payment = Payment.objects.create(
            order=self.order,
            payment_provider='PAYSTACK',
            payment_reference='OS-PST-TAMPERED01',
            payment_status='PENDING',
            amount=Decimal('55000.00')
        )

        # Attacker paid ₦50 instead of ₦55,000
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': True,
            'data': {
                'status': 'success',
                'reference': 'OS-PST-TAMPERED01',
                'amount': 5000,  # ₦50 in kobo
                'currency': 'NGN',
            }
        }
        mock_get.return_value = mock_response

        response = self.client.post('/payments/verify/', {
            'reference': 'OS-PST-TAMPERED01'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()['verified'])
        self.assertIn('amount mismatch', response.json()['error'].lower())

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.payment_status, 'FAILED')
        self.assertEqual(self.order.order_status, 'PENDING')

    @patch('requests.get')
    def test_verify_currency_mismatch_fails(self, mock_get):
        payment = Payment.objects.create(
            order=self.order,
            payment_provider='PAYSTACK',
            payment_reference='OS-PST-CURR01',
            payment_status='PENDING',
            amount=Decimal('55000.00')
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': True,
            'data': {
                'status': 'success',
                'reference': 'OS-PST-CURR01',
                'amount': 5500000,
                'currency': 'USD',  # Mismatched currency
            }
        }
        mock_get.return_value = mock_response

        response = self.client.post('/payments/verify/', {
            'reference': 'OS-PST-CURR01'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()['verified'])
        self.assertIn('currency mismatch', response.json()['error'].lower())

    def test_verify_idempotency_already_successful(self):
        payment = Payment.objects.create(
            order=self.order,
            payment_provider='PAYSTACK',
            payment_reference='OS-PST-ALREADYDONE',
            payment_status='SUCCESSFUL',
            amount=Decimal('55000.00')
        )
        self.order.order_status = 'CONFIRMED'
        self.order.save()

        # Should return success without querying provider API again
        response = self.client.post('/payments/verify/', {
            'reference': 'OS-PST-ALREADYDONE'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['verified'])
        self.assertIn('already verified', data['message'].lower())

    # --------------------------------------------------------------------------
    # 3. WEBHOOK TESTS
    # --------------------------------------------------------------------------

    def test_paystack_webhook_valid_signature_success(self):
        payment = Payment.objects.create(
            order=self.order,
            payment_provider='PAYSTACK',
            payment_reference='OS-PST-WH-001',
            payment_status='PENDING',
            amount=Decimal('55000.00')
        )

        payload = {
            'event': 'charge.success',
            'data': {
                'reference': 'OS-PST-WH-001',
                'amount': 5500000,
                'currency': 'NGN',
                'status': 'success'
            }
        }
        raw_body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(
            'sk_test_mock_paystack_secret_key'.encode('utf-8'),
            msg=raw_body,
            digestmod=hashlib.sha512
        ).hexdigest()

        response = self.client.post(
            '/payments/webhooks/paystack/',
            data=raw_body,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'processed')

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.payment_status, 'SUCCESSFUL')
        self.assertEqual(self.order.order_status, 'CONFIRMED')

    def test_paystack_webhook_invalid_signature_rejected(self):
        payload = {'event': 'charge.success', 'data': {'reference': 'OS-PST-FAKE'}}
        raw_body = json.dumps(payload).encode('utf-8')

        response = self.client.post(
            '/payments/webhooks/paystack/',
            data=raw_body,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE='invalid_tampered_signature'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch.object(FlutterwaveService, 'verify_payment')
    def test_flutterwave_webhook_valid_hash_success(self, mock_verify):
        payment = Payment.objects.create(
            order=self.order,
            payment_provider='FLUTTERWAVE',
            payment_reference='OS-FLW-WH-002',
            payment_status='PENDING',
            amount=Decimal('55000.00')
        )

        from payments.services.base import PaymentVerifyResult
        mock_verify.return_value = PaymentVerifyResult(
            success=True,
            verified=True,
            reference='OS-FLW-WH-002',
            provider='FLUTTERWAVE',
            amount=Decimal('55000.00'),
            currency='NGN',
            status='SUCCESSFUL'
        )

        payload = {
            'event': 'charge.completed',
            'data': {
                'id': 123456,
                'tx_ref': 'OS-FLW-WH-002',
                'amount': 55000,
                'currency': 'NGN',
                'status': 'successful'
            }
        }
        raw_body = json.dumps(payload).encode('utf-8')

        response = self.client.post(
            '/payments/webhooks/flutterwave/',
            data=raw_body,
            content_type='application/json',
            HTTP_VERIF_HASH='mock_flw_secret_hash'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'processed')

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.payment_status, 'SUCCESSFUL')
        self.assertEqual(self.order.order_status, 'CONFIRMED')

    def test_flutterwave_webhook_invalid_hash_rejected(self):
        payload = {'event': 'charge.completed'}
        raw_body = json.dumps(payload).encode('utf-8')

        response = self.client.post(
            '/payments/webhooks/flutterwave/',
            data=raw_body,
            content_type='application/json',
            HTTP_VERIF_HASH='invalid_hash_value'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_webhook_idempotency_duplicate_event(self):
        payment = Payment.objects.create(
            order=self.order,
            payment_provider='PAYSTACK',
            payment_reference='OS-PST-WH-DUP',
            payment_status='SUCCESSFUL',  # Already processed
            amount=Decimal('55000.00')
        )
        self.order.order_status = 'CONFIRMED'
        self.order.save()

        payload = {
            'event': 'charge.success',
            'data': {
                'reference': 'OS-PST-WH-DUP',
                'amount': 5500000,
                'currency': 'NGN'
            }
        }
        raw_body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(
            'sk_test_mock_paystack_secret_key'.encode('utf-8'),
            msg=raw_body,
            digestmod=hashlib.sha512
        ).hexdigest()

        response = self.client.post(
            '/payments/webhooks/paystack/',
            data=raw_body,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'already_processed')
