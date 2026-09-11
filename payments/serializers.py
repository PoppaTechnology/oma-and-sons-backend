from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'order_number', 'payment_provider',
            'payment_reference', 'payment_status', 'amount',
            'gateway_response', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order', 'order_number', 'payment_provider',
            'payment_reference', 'payment_status', 'amount',
            'gateway_response', 'created_at', 'updated_at'
        ]


class InitializePaymentSerializer(serializers.Serializer):
    order_number = serializers.CharField(required=False, allow_blank=True)
    order_id = serializers.IntegerField(required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    provider = serializers.ChoiceField(
        choices=['PAYSTACK', 'FLUTTERWAVE'],
        default='PAYSTACK'
    )
    callback_url = serializers.URLField(required=False, allow_blank=True)

    def validate_provider(self, value):
        if not value:
            return 'PAYSTACK'
        upper_val = str(value).upper().strip()
        if upper_val not in ('PAYSTACK', 'FLUTTERWAVE'):
            raise serializers.ValidationError("Provider must be either PAYSTACK or FLUTTERWAVE.")
        return upper_val

    def validate(self, attrs):
        order_num = attrs.get('order_number')
        order_id = attrs.get('order_id')
        if not order_num and not order_id:
            raise serializers.ValidationError("Either 'order_number' or 'order_id' must be provided.")
        return attrs


class VerifyPaymentSerializer(serializers.Serializer):
    reference = serializers.CharField(required=True, trim_whitespace=True)
    provider = serializers.ChoiceField(
        choices=['PAYSTACK', 'FLUTTERWAVE'],
        required=False,
        allow_blank=True,
        allow_null=True
    )
    transaction_id = serializers.CharField(required=False, allow_blank=True)

    def validate_provider(self, value):
        if not value:
            return None
        upper_val = str(value).upper().strip()
        if upper_val not in ('PAYSTACK', 'FLUTTERWAVE'):
            raise serializers.ValidationError("Provider must be either PAYSTACK or FLUTTERWAVE.")
        return upper_val
