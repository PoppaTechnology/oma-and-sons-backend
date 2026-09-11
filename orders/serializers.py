from rest_framework import serializers
from .models import Order, OrderItem, PromoCode
from products.models import ProductVariant, Product
from decimal import Decimal


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_name', 'variant_name', 'product_slug',
            'size', 'image', 'quantity', 'unit_price', 'subtotal',
            'created_at'
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    lines = OrderItemSerializer(source='items', many=True, read_only=True)
    pickup_store_name = serializers.CharField(source='pickup_store', read_only=True)
    payment_status = serializers.SerializerMethodField()
    breakdown = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'first_name', 'last_name', 'recipient_name',
            'email', 'phone_number', 'fulfillment_type', 'delivery_method',
            'delivery_address', 'city', 'state', 'pickup_store', 'pickup_store_name',
            'subtotal', 'delivery_fee', 'tax_amount', 'discount_amount',
            'discount_code', 'total_amount', 'order_status', 'payment_status',
            'breakdown', 'items', 'lines', 'created_at', 'updated_at'
        ]

    def get_payment_status(self, obj):
        return obj.payment.payment_status if hasattr(obj, 'payment') else 'PENDING'

    def get_breakdown(self, obj):
        return {
            'subtotal': obj.subtotal,
            'discount': obj.discount_amount,
            'delivery': obj.delivery_fee,
            'taxes': obj.tax_amount,
            'total': obj.total_amount
        }


class OrderTrackingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_name', 'variant_name', 'product_slug',
            'size', 'image', 'quantity', 'unit_price', 'subtotal'
        ]


class OrderTrackingSerializer(serializers.ModelSerializer):
    """
    Publicly safe serializer for guest order tracking.
    Excludes sensitive customer PII such as full phone number and full delivery address.
    """
    items = OrderTrackingItemSerializer(many=True, read_only=True)
    lines = OrderTrackingItemSerializer(source='items', many=True, read_only=True)
    pickup_store_name = serializers.CharField(source='pickup_store', read_only=True)
    payment_status = serializers.SerializerMethodField()
    breakdown = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'order_number', 'fulfillment_type', 'delivery_method',
            'pickup_store', 'pickup_store_name', 'subtotal',
            'delivery_fee', 'tax_amount', 'discount_amount',
            'discount_code', 'total_amount', 'order_status',
            'payment_status', 'breakdown', 'items', 'lines',
            'created_at', 'updated_at'
        ]

    def get_payment_status(self, obj):
        return obj.payment.payment_status if hasattr(obj, 'payment') else 'PENDING'

    def get_breakdown(self, obj):
        return {
            'subtotal': obj.subtotal,
            'discount': obj.discount_amount,
            'delivery': obj.delivery_fee,
            'taxes': obj.tax_amount,
            'total': obj.total_amount
        }


class CheckoutItemInputSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(required=False)
    productId = serializers.CharField(required=False)
    product_id = serializers.CharField(required=False)
    quantity = serializers.IntegerField(default=1, min_value=1)


class CheckoutSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone = serializers.CharField()
    firstName = serializers.CharField()
    lastName = serializers.CharField()
    fulfillment = serializers.ChoiceField(choices=['ship', 'pickup'], default='ship')
    deliveryMethod = serializers.ChoiceField(choices=['standard', 'express', 'pickup'], default='standard')
    address = serializers.CharField(required=False, allow_blank=True, default='')
    city = serializers.CharField(required=False, allow_blank=True, default='')
    state = serializers.CharField(required=False, allow_blank=True, default='')
    pickupStore = serializers.CharField(required=False, allow_blank=True, default='')
    pickup_store = serializers.CharField(required=False, allow_blank=True, default='')
    discountCode = serializers.CharField(required=False, allow_blank=True, default='')
    items = CheckoutItemInputSerializer(many=True, required=False)
    cartLines = CheckoutItemInputSerializer(many=True, required=False)


class ValidatePromoSerializer(serializers.Serializer):
    code = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
