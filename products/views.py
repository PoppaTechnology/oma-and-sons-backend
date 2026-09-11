from rest_framework import status, generics, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Min
from .models import Category, Product, ProductVariant
from .serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductVariantSerializer
)


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class ProductListView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = Product.objects.all().select_related('category').prefetch_related('variants')
        params = self.request.query_params

        # Category filter (by slug or ID)
        category = params.get('category')
        if category:
            if category.isdigit():
                queryset = queryset.filter(category_id=category)
            else:
                queryset = queryset.filter(Q(category__slug__iexact=category) | Q(category__name__iexact=category))

        # Price range filter
        min_price = params.get('min_price') or params.get('minPrice')
        max_price = params.get('max_price') or params.get('maxPrice')
        if min_price:
            try:
                queryset = queryset.filter(variants__price__gte=float(min_price)).distinct()
            except ValueError:
                pass
        if max_price:
            try:
                queryset = queryset.filter(variants__price__lte=float(max_price)).distinct()
            except ValueError:
                pass

        # Badges & Flags
        is_new_arrival = params.get('is_new_arrival') or params.get('new_arrival')
        if is_new_arrival is not None:
            val = is_new_arrival.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(is_new_arrival=val)

        is_featured = params.get('is_featured') or params.get('featured')
        if is_featured is not None:
            val = is_featured.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(is_featured=val)

        # Search query
        search = params.get('search') or params.get('q')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(collection__icontains=search) |
                Q(badge__icontains=search) |
                Q(category__name__icontains=search)
            ).distinct()

        # Sorting: 'featured', 'low', 'high', 'newest'
        sort = params.get('sort', 'featured')
        if sort in ('low', 'price_asc'):
            queryset = queryset.annotate(min_p=Min('variants__price')).order_by('min_p')
        elif sort in ('high', 'price_desc'):
            queryset = queryset.annotate(min_p=Min('variants__price')).order_by('-min_p')
        elif sort in ('newest', 'new'):
            queryset = queryset.order_by('-created_at')
        elif sort == 'featured':
            queryset = queryset.order_by('-is_featured', '-created_at')

        return queryset


class ProductDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        product = Product.objects.filter(slug=slug).select_related('category').prefetch_related('variants').first()
        if not product and slug.isdigit():
            product = Product.objects.filter(id=slug).select_related('category').prefetch_related('variants').first()

        if not product:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductDetailSerializer(product)
        return Response(serializer.data)


class TrendingDealsView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Product.objects.filter(
            Q(badge__in=['HOT', 'SALE', 'BEST SELLER']) | Q(former_price__isnull=False)
        ).select_related('category').prefetch_related('variants')[:8]


class NewArrivalsView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Product.objects.filter(
            Q(is_new_arrival=True) | Q(badge='NEW')
        ).select_related('category').prefetch_related('variants')[:8]
