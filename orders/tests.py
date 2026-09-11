from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal

from orders.models import Order, OrderItem, PromoCode
from products.models import Product, Category, ProductVariant

User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OrderSecurityAndTrackingTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.user_a = User.objects.create_user(
            email='customer_a@example.com',
            password='Password123!',
            first_name='Customer',
            last_name='A',
            phone_number='+2348011111111'
        )
        self.user_b = User.objects.create_user(
            email='customer_b@example.com',
            password='Password123!',
            first_name='Customer',
            last_name='B',
            phone_number='+2348022222222'
        )

        # Products
        self.category = Category.objects.create(name='Apparel', slug='apparel')
        self.product = Product.objects.create(
            category=self.category,
            name='Luxury Blazer',
            slug='luxury-blazer',
            description='Test blazer'
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            variant_name='Navy Blue / M',
            size='M',
            price=Decimal('25000.00'),
            stock_quantity=10
        )

        # Customer A's Order
        self.order_a = Order.objects.create(
            user=self.user_a,
            order_number='#OS-2609-A1B2C3',
            first_name='Customer',
            last_name='A',
            email='customer_a@example.com',
            phone_number='+2348011111111',
            fulfillment_type='ship',
            delivery_method='standard',
            delivery_address='10 Private Estate, Victoria Island',
            city='Lagos',
            state='Lagos',
            subtotal=Decimal('25000.00'),
            delivery_fee=Decimal('2500.00'),
            tax_amount=Decimal('1250.00'),
            total_amount=Decimal('28750.00'),
            order_status='CONFIRMED'
        )
        OrderItem.objects.create(
            order=self.order_a,
            variant=self.variant,
            product_name=self.product.name,
            variant_name=self.variant.variant_name,
            product_slug=self.product.slug,
            size=self.variant.size,
            quantity=1,
            unit_price=self.variant.price,
            subtotal=Decimal('25000.00')
        )

        # Customer B's Order
        self.order_b = Order.objects.create(
            user=self.user_b,
            order_number='#OS-2609-D4E5F6',
            first_name='Customer',
            last_name='B',
            email='customer_b@example.com',
            phone_number='+2348022222222',
            fulfillment_type='ship',
            delivery_method='standard',
            delivery_address='20 Secret Boulevard, Ikeja',
            city='Lagos',
            state='Lagos',
            subtotal=Decimal('25000.00'),
            delivery_fee=Decimal('2500.00'),
            tax_amount=Decimal('1250.00'),
            total_amount=Decimal('28750.00'),
            order_status='PENDING'
        )

        # Guest Order
        self.guest_order = Order.objects.create(
            user=None,
            order_number='#OS-2609-G7H8I9',
            first_name='Guest',
            last_name='Shopper',
            email='guest@example.com',
            phone_number='+2348033333333',
            fulfillment_type='ship',
            delivery_method='standard',
            delivery_address='30 Guest Lane, Lekki',
            city='Lagos',
            state='Lagos',
            subtotal=Decimal('25000.00'),
            delivery_fee=Decimal('2500.00'),
            tax_amount=Decimal('1250.00'),
            total_amount=Decimal('28750.00'),
            order_status='PROCESSING'
        )

    # ==========================================
    # Case 1: Unauthenticated user access
    # ==========================================
    def test_unauthenticated_user_cannot_access_order_detail(self):
        """Unauthenticated requests to /orders/<order_number>/ must return 401 Unauthorized."""
        clean_num = 'OS-2609-A1B2C3'
        response = self.client.get(f'/orders/{clean_num}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_user_cannot_access_order_list(self):
        """Unauthenticated requests to /orders/ must return 401 Unauthorized."""
        response = self.client.get('/orders/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ==========================================
    # Case 2: Authenticated owner access
    # ==========================================
    def test_authenticated_owner_can_retrieve_own_order_detail(self):
        """Customer A can retrieve their own order with and without '#' in the order number."""
        self.client.force_authenticate(user=self.user_a)

        # Without '#'
        clean_num = 'OS-2609-A1B2C3'
        response = self.client.get(f'/orders/{clean_num}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['order_number'], self.order_a.order_number)
        self.assertEqual(data['delivery_address'], '10 Private Estate, Victoria Island')
        self.assertEqual(data['phone_number'], '+2348011111111')
        self.assertEqual(len(data['items']), 1)

        # With query parameter fallback
        response_query = self.client.get(f'/orders/{clean_num}/?order_number={clean_num}')
        self.assertEqual(response_query.status_code, status.HTTP_200_OK)

    def test_authenticated_user_order_list_only_contains_own_orders(self):
        """Customer A only sees their own orders in the list, never Customer B's or guest orders."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get('/orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        orders = response.json()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['order_number'], self.order_a.order_number)

    # ==========================================
    # Case 3: Authenticated non-owner access
    # ==========================================
    def test_authenticated_non_owner_gets_404_not_found(self):
        """
        Customer B requesting Customer A's order must receive 404 Not Found,
        preventing information leakage and order existence enumeration.
        """
        self.client.force_authenticate(user=self.user_b)
        clean_num_a = 'OS-2609-A1B2C3'
        response = self.client.get(f'/orders/{clean_num_a}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {'error': 'Order not found'})

    def test_authenticated_user_cannot_access_guest_order_via_order_detail(self):
        """Customer A requesting a guest order via /orders/<num>/ must receive 404 Not Found."""
        self.client.force_authenticate(user=self.user_a)
        clean_guest_num = 'OS-2609-G7H8I9'
        response = self.client.get(f'/orders/{clean_guest_num}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {'error': 'Order not found'})

    # ==========================================
    # Case 4: Guest Order Tracking
    # ==========================================
    def test_guest_tracking_with_valid_order_number_and_email_via_get(self):
        """Guest tracking via GET /orders/track/?number=...&email=... returns sanitized tracking info."""
        clean_guest_num = 'OS-2609-G7H8I9'
        response = self.client.get(f'/orders/track/?number={clean_guest_num}&email=guest@example.com')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Tracking data must be present
        self.assertEqual(data['order_number'], self.guest_order.order_number)
        self.assertEqual(data['order_status'], 'PROCESSING')
        self.assertEqual(data['fulfillment_type'], 'ship')
        self.assertEqual(data['delivery_method'], 'standard')
        self.assertEqual(Decimal(str(data['total_amount'])), Decimal('28750.00'))

        # Sensitive PII must NOT be present
        self.assertNotIn('phone_number', data)
        self.assertNotIn('delivery_address', data)
        self.assertNotIn('city', data)
        self.assertNotIn('state', data)
        self.assertNotIn('first_name', data)
        self.assertNotIn('last_name', data)
        self.assertNotIn('recipient_name', data)

    def test_guest_tracking_with_valid_order_number_and_email_via_post(self):
        """Guest tracking via POST /orders/track/ returns sanitized tracking info."""
        response = self.client.post('/orders/track/', {
            'order_number': 'OS-2609-G7H8I9',
            'email': 'guest@example.com'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['order_number'], self.guest_order.order_number)
        self.assertNotIn('phone_number', data)
        self.assertNotIn('delivery_address', data)

    def test_guest_tracking_fails_without_email(self):
        """Guest tracking without email returns 400 Bad Request."""
        response = self.client.get('/orders/track/?number=OS-2609-G7H8I9')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.json())

    def test_guest_tracking_fails_with_mismatched_email(self):
        """Guest tracking with wrong email returns 404 Not Found."""
        response = self.client.get('/orders/track/?number=OS-2609-G7H8I9&email=wrong@example.com')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.json())

    # ==========================================
    # Case 5: Public endpoints checkout and promo
    # ==========================================
    def test_checkout_remains_public(self):
        """Checkout endpoint must remain public (AllowAny) for guests."""
        payload = {
            'email': 'anon@example.com',
            'phone': '+2348000000000',
            'firstName': 'Anon',
            'lastName': 'Buyer',
            'fulfillment': 'ship',
            'deliveryMethod': 'standard',
            'address': '1 Street',
            'city': 'Lagos',
            'state': 'Lagos',
            'items': [{'variant_id': self.variant.id, 'quantity': 1}]
        }
        response = self.client.post('/orders/checkout/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_validate_promo_remains_public(self):
        """Validate promo endpoint must remain public (AllowAny)."""
        PromoCode.objects.create(code='TESTPROMO', discount_percent=Decimal('15.00'), is_active=True)
        response = self.client.post('/orders/validate-promo/', {
            'code': 'TESTPROMO',
            'subtotal': '10000.00'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['valid'])
