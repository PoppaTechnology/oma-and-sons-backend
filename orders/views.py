from rest_framework import status, permissions, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from decimal import Decimal
import uuid

from .models import Order, OrderItem, PromoCode
from .serializers import (
    OrderDetailSerializer,
    OrderTrackingSerializer,
    CheckoutSerializer,
    ValidatePromoSerializer
)
from products.models import ProductVariant, Product
from cart.models import Cart
from payments.models import Payment


DELIVERY_RATES = {
    'standard': Decimal('2500.00'),
    'express': Decimal('5000.00'),
    'pickup': Decimal('0.00'),
}
TAX_RATE = Decimal('0.05')  # 5%


class CheckoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        raw_items = data.get('items') or data.get('cartLines') or []

        # If no items explicitly sent in body, try fetching from current user's / session cart
        if not raw_items:
            cart = None
            if request.user.is_authenticated:
                cart = Cart.objects.filter(user=request.user).first()
            session_key = request.headers.get('X-Cart-Session') or request.session.session_key
            if not cart and session_key:
                cart = Cart.objects.filter(session_key=session_key).first()

            if cart and cart.items.exists():
                raw_items = [{'variant_id': item.variant_id, 'quantity': item.quantity} for item in cart.items.all()]

        if not raw_items:
            return Response({'error': 'No items in order payload or cart.'}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve items and compute subtotal
        order_items_to_create = []
        subtotal = Decimal('0.00')

        for item_data in raw_items:
            variant_id = item_data.get('variant_id')
            product_id = item_data.get('productId') or item_data.get('product_id')
            quantity = int(item_data.get('quantity', 1))

            variant = None
            if variant_id:
                variant = ProductVariant.objects.select_related('product').filter(id=variant_id).first()
            elif product_id:
                if str(product_id).isdigit():
                    variant = ProductVariant.objects.select_related('product').filter(product_id=product_id).first()
                if not variant:
                    product = Product.objects.filter(slug=product_id).first()
                    if product:
                        variant = product.variants.first()

            if not variant:
                continue

            item_subtotal = Decimal(str(variant.price)) * quantity
            subtotal += item_subtotal

            order_items_to_create.append({
                'variant': variant,
                'product_name': variant.product.name,
                'variant_name': variant.variant_name,
                'product_slug': variant.product.slug,
                'size': variant.size,
                'image': variant.image,
                'quantity': quantity,
                'unit_price': variant.price,
                'subtotal': item_subtotal
            })

        if not order_items_to_create:
            return Response({'error': 'Could not resolve any valid product variants for checkout.'}, status=status.HTTP_400_BAD_REQUEST)

        # Delivery method & fee
        delivery_method = data.get('deliveryMethod', 'standard')
        fulfillment = data.get('fulfillment', 'ship')
        if fulfillment == 'pickup':
            delivery_method = 'pickup'

        delivery_fee = DELIVERY_RATES.get(delivery_method, Decimal('2500.00'))

        # Tax calculation
        tax_amount = (subtotal * TAX_RATE).quantize(Decimal('0.01'))

        # Discount promo code
        discount_code_str = data.get('discountCode', '').strip()
        discount_amount = Decimal('0.00')
        if discount_code_str:
            promo = PromoCode.objects.filter(code__iexact=discount_code_str, is_active=True).first()
            if promo and promo.is_valid():
                discount_amount = ((subtotal * promo.discount_percent) / Decimal('100.00')).quantize(Decimal('0.01'))
            elif discount_code_str.lower() == 'omawhite':
                # Default 10% prototype code fallback
                discount_amount = (subtotal * Decimal('0.10')).quantize(Decimal('0.01'))

        total_amount = subtotal - discount_amount + delivery_fee + tax_amount

        # Pickup store if applicable
        pickup_store_str = data.get('pickupStore') or data.get('pickup_store') or ''
        if not pickup_store_str and data.get('pickupStoreId'):
            pickup_store_str = f"Store #{data.get('pickupStoreId')}"

        # Create Order
        user = request.user if request.user.is_authenticated else None
        order = Order.objects.create(
            user=user,
            first_name=data['firstName'],
            last_name=data['lastName'],
            email=data['email'],
            phone_number=data['phone'],
            fulfillment_type=fulfillment,
            delivery_method=delivery_method,
            delivery_address=data.get('address', ''),
            city=data.get('city', ''),
            state=data.get('state', ''),
            pickup_store=pickup_store_str,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            discount_code=discount_code_str,
            total_amount=total_amount,
            order_status='PENDING'
        )

        for item_kwargs in order_items_to_create:
            OrderItem.objects.create(order=order, **item_kwargs)

        # Create initial Payment record
        payment_ref = f"OS-PST-{uuid.uuid4().hex[:12].upper()}"
        Payment.objects.create(
            order=order,
            payment_provider='PAYSTACK',
            payment_reference=payment_ref,
            payment_status='PENDING',
            amount=total_amount
        )

        # Clear cart if user had an active cart
        if user:
            Cart.objects.filter(user=user).update(session_key=None)
            Cart.objects.filter(user=user).first() and Cart.objects.filter(user=user).first().items.all().delete()

        serializer = OrderDetailSerializer(order)
        return Response({
            'message': 'Order created successfully',
            'order': serializer.data,
            'payment_reference': payment_ref
        }, status=status.HTTP_201_CREATED)


class OrderListView(generics.ListAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items')


class OrderDetailView(APIView):
    """
    Authenticated order detail view.
    Only allows authenticated users to view orders that belong to their account.
    Returns 401 for unauthenticated requests and 404 for non-existent or unauthorized orders.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_number=None):
        num = (
            order_number
            or request.query_params.get('order_number')
            or request.query_params.get('number')
        )

        if not num:
            return Response(
                {'error': 'Order number is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        clean_num = num.lstrip('#')

        order = (
            Order.objects
            .filter(
                user=request.user
            )
            .filter(
                order_number__in=[
                    num,
                    f"#{clean_num}",
                    clean_num
                ]
            )
            .prefetch_related('items')
            .first()
        )

        if not order:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = OrderDetailSerializer(order)
        return Response(serializer.data)


class OrderTrackingView(APIView):
    """
    Public guest order tracking endpoint.
    Requires order_number and email for secure verification.
    Uses OrderTrackingSerializer to return tracking progress without exposing private customer PII.
    """
    permission_classes = [permissions.AllowAny]

    def _track_order(self, order_num, email):
        if not order_num or not email:
            return Response(
                {'error': 'Both order number and email are required for order tracking.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        clean_num = order_num.strip().lstrip('#')
        clean_email = email.strip()

        order = (
            Order.objects
            .filter(
                order_number__in=[
                    order_num.strip(),
                    f"#{clean_num}",
                    clean_num
                ],
                email__iexact=clean_email
            )
            .prefetch_related('items')
            .first()
        )

        if not order:
            return Response(
                {'error': 'No order found matching the provided order number and email address.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = OrderTrackingSerializer(order)
        return Response(serializer.data)

    def get(self, request):
        order_num = (
            request.query_params.get('order_number')
            or request.query_params.get('number')
        )
        email = request.query_params.get('email')
        return self._track_order(order_num, email)

    def post(self, request):
        order_num = (
            request.data.get('order_number')
            or request.data.get('number')
            or request.query_params.get('order_number')
            or request.query_params.get('number')
        )
        email = request.data.get('email') or request.query_params.get('email')
        return self._track_order(order_num, email)


class ValidatePromoCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ValidatePromoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        code = serializer.validated_data['code'].strip()
        subtotal = serializer.validated_data.get('subtotal', Decimal('0.00'))

        promo = PromoCode.objects.filter(code__iexact=code, is_active=True).first()
        if promo and promo.is_valid():
            discount_amount = ((subtotal * promo.discount_percent) / Decimal('100.00')).quantize(Decimal('0.01'))
            return Response({
                'valid': True,
                'code': promo.code,
                'discount_percent': promo.discount_percent,
                'discount_amount': discount_amount,
                'message': f"{promo.discount_percent}% discount applied!"
            })
        elif code.lower() == 'omawhite':
            discount_amount = (subtotal * Decimal('0.10')).quantize(Decimal('0.01'))
            return Response({
                'valid': True,
                'code': 'OMAWHITE',
                'discount_percent': Decimal('10.00'),
                'discount_amount': discount_amount,
                'message': "10% discount applied!"
            })

        return Response({
            'valid': False,
            'message': 'Invalid or expired promo code.'
        }, status=status.HTTP_400_BAD_REQUEST)
