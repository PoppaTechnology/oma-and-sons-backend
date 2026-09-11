from rest_framework import serializers
from .models import Cart, CartItem
from products.models import ProductVariant, Product


class CartItemSerializer(serializers.ModelSerializer):
    variant_id = serializers.IntegerField(source='variant.id', read_only=True)
    productId = serializers.CharField(source='variant.product.slug', read_only=True)
    product_id = serializers.IntegerField(source='variant.product.id', read_only=True)
    product_name = serializers.CharField(source='variant.product.name', read_only=True)
    product_slug = serializers.CharField(source='variant.product.slug', read_only=True)
    category = serializers.CharField(source='variant.product.category.slug', read_only=True)
    variant_name = serializers.CharField(source='variant.variant_name', read_only=True)
    size = serializers.CharField(source='variant.size', read_only=True)
    image = serializers.CharField(source='variant.image', read_only=True)
    unit_price = serializers.DecimalField(source='variant.price', max_digits=12, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            'id', 'variant_id', 'productId', 'product_id', 'product_name',
            'product_slug', 'category', 'variant_name', 'size', 'image',
            'unit_price', 'quantity', 'subtotal', 'created_at', 'updated_at'
        ]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    lines = CartItemSerializer(source='items', many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'session_key', 'total_items', 'subtotal', 'items', 'lines', 'created_at', 'updated_at']


class AddToCartSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(required=False)
    product_id = serializers.CharField(required=False)  # Can be ID or slug
    quantity = serializers.IntegerField(default=1, min_value=1)

    def validate(self, data):
        variant_id = data.get('variant_id')
        product_id = data.get('product_id')

        if not variant_id and not product_id:
            raise serializers.ValidationError('Either variant_id or product_id must be provided.')

        variant = None
        if variant_id:
            variant = ProductVariant.objects.filter(id=variant_id).first()
        elif product_id:
            if str(product_id).isdigit():
                variant = ProductVariant.objects.filter(product_id=product_id).first()
            if not variant:
                product = Product.objects.filter(slug=product_id).first()
                if product:
                    variant = product.variants.first()

        if not variant:
            raise serializers.ValidationError('Product or Variant not found.')

        if not variant.available or variant.stock_quantity < 1:
            raise serializers.ValidationError('This product is currently out of stock.')

        data['variant'] = variant
        return data


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(required=True, min_value=1)
