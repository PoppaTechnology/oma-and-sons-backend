from rest_framework import serializers
from .models import Category, Product, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source='products.count', read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'product_count', 'created_at']


class ProductVariantSerializer(serializers.ModelSerializer):
    product_slug = serializers.CharField(source='product.slug', read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'product', 'product_slug', 'variant_name', 'size',
            'price', 'image', 'stock_quantity', 'available'
        ]


class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.slug', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    price = serializers.DecimalField(source='primary_price', max_digits=12, decimal_places=2, read_only=True)
    formerPrice = serializers.DecimalField(source='former_price', max_digits=12, decimal_places=2, read_only=True)
    variant = serializers.CharField(source='primary_variant', read_only=True)
    image = serializers.CharField(source='primary_image', read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'category', 'category_name',
            'price', 'formerPrice', 'collection', 'variant',
            'badge', 'image', 'description', 'is_new_arrival',
            'is_featured', 'variants', 'created_at'
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.slug', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    price = serializers.DecimalField(source='primary_price', max_digits=12, decimal_places=2, read_only=True)
    formerPrice = serializers.DecimalField(source='former_price', max_digits=12, decimal_places=2, read_only=True)
    variant = serializers.CharField(source='primary_variant', read_only=True)
    image = serializers.CharField(source='primary_image', read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    recommendations = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'category', 'category_name',
            'price', 'formerPrice', 'collection', 'variant',
            'badge', 'image', 'description', 'is_new_arrival',
            'is_featured', 'variants', 'recommendations',
            'created_at', 'updated_at'
        ]

    def get_recommendations(self, obj):
        same_cat = Product.objects.filter(category=obj.category).exclude(id=obj.id)[:4]
        if not same_cat.exists():
            same_cat = Product.objects.exclude(id=obj.id)[:4]
        return ProductListSerializer(same_cat, many=True).data
