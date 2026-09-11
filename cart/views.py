from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
import uuid
from .models import Cart, CartItem
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    AddToCartSerializer,
    UpdateCartItemSerializer
)


def get_or_create_cart(request):
    """Helper to retrieve or create cart for user or guest session."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    # Session key lookup
    session_key = request.headers.get('X-Cart-Session') or request.query_params.get('session_key')
    if not session_key:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key or str(uuid.uuid4())

    cart, _ = Cart.objects.get_or_create(session_key=session_key)
    return cart


class CartDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        cart = get_or_create_cart(request)
        serializer = CartSerializer(cart)
        return Response(serializer.data)


class CartItemAddView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        cart = get_or_create_cart(request)
        serializer = AddToCartSerializer(data=request.data)
        if serializer.is_valid():
            variant = serializer.validated_data['variant']
            quantity = serializer.validated_data.get('quantity', 1)

            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                variant=variant,
                defaults={'quantity': quantity}
            )
            if not created:
                cart_item.quantity += quantity
                cart_item.save()

            return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CartItemUpdateView(APIView):
    permission_classes = [permissions.AllowAny]

    def patch(self, request, pk=None):
        cart = get_or_create_cart(request)
        # Search by cart_item id or variant_id or product slug
        cart_item = None
        if pk:
            cart_item = CartItem.objects.filter(cart=cart, id=pk).first()

        if not cart_item:
            product_id = request.data.get('product_id') or request.data.get('productId')
            variant_id = request.data.get('variant_id')
            if variant_id:
                cart_item = CartItem.objects.filter(cart=cart, variant_id=variant_id).first()
            elif product_id:
                cart_item = CartItem.objects.filter(
                    cart=cart
                ).filter(
                    models_q := (
                        CartItem.objects.filter(variant__product__slug=product_id) |
                        CartItem.objects.filter(variant__product_id=product_id if str(product_id).isdigit() else 0)
                    )
                ).first()

        if not cart_item:
            return Response({'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)

        # Quantity adjustment: delta (+1 / -1) or absolute value
        delta = request.data.get('delta')
        if delta is not None:
            new_qty = cart_item.quantity + int(delta)
            if new_qty <= 0:
                cart_item.delete()
            else:
                cart_item.quantity = new_qty
                cart_item.save()
            return Response(CartSerializer(cart).data)

        serializer = UpdateCartItemSerializer(data=request.data)
        if serializer.is_valid():
            cart_item.quantity = serializer.validated_data['quantity']
            cart_item.save()
            return Response(CartSerializer(cart).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        cart = get_or_create_cart(request)
        cart_item = CartItem.objects.filter(cart=cart, id=pk).first()
        if not cart_item:
            product_id = request.data.get('product_id') or request.data.get('productId')
            if product_id:
                cart_item = CartItem.objects.filter(cart=cart, variant__product__slug=product_id).first()

        if cart_item:
            cart_item.delete()
            return Response(CartSerializer(cart).data)
        return Response({'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)


class CartClearView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        cart = get_or_create_cart(request)
        cart.items.all().delete()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
