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
    """Helper to retrieve or create cart for user or guest session.

    Returns (cart, session_key). session_key is None for authenticated users
    (their cart is keyed by user, not by a guest session), and is the guest
    session identifier otherwise. Callers should echo session_key back via
    the X-Cart-Session response header so the frontend can persist it.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart, None

    # Session key lookup
    session_key = request.headers.get('X-Cart-Session') or request.query_params.get('session_key')
    if not session_key:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key or str(uuid.uuid4())

    cart, _ = Cart.objects.get_or_create(session_key=session_key)
    return cart, session_key


def _respond_with_cart(cart, session_key, status_code=status.HTTP_200_OK):
    """Build a cart Response, attaching X-Cart-Session for guest carts."""
    response = Response(CartSerializer(cart).data, status=status_code)
    if session_key:
        response['X-Cart-Session'] = session_key
    return response


class CartDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        cart, session_key = get_or_create_cart(request)
        return _respond_with_cart(cart, session_key)


class CartItemAddView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        cart, session_key = get_or_create_cart(request)
        serializer = AddToCartSerializer(data=request.data)
        if serializer.is_valid():
            variant = serializer.validated_data['variant']
            quantity = serializer.validated_data.get('quantity', 1)

            existing_item = CartItem.objects.filter(cart=cart, variant=variant).first()
            current_qty = existing_item.quantity if existing_item else 0
            requested_total = current_qty + quantity

            if not variant.available or requested_total > variant.stock_quantity:
                response = Response(
                    {'error': f'Only {variant.stock_quantity} unit(s) of this item are available.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                if session_key:
                    response['X-Cart-Session'] = session_key
                return response

            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                variant=variant,
                defaults={'quantity': quantity}
            )
            if not created:
                cart_item.quantity += quantity
                cart_item.save()

            return _respond_with_cart(cart, session_key)
        response = Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        if session_key:
            response['X-Cart-Session'] = session_key
        return response


class CartItemUpdateView(APIView):
    permission_classes = [permissions.AllowAny]

    def patch(self, request, pk=None):
        cart, session_key = get_or_create_cart(request)
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
            response = Response({'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)
            if session_key:
                response['X-Cart-Session'] = session_key
            return response

        # Quantity adjustment: delta (+1 / -1) or absolute value
        delta = request.data.get('delta')
        if delta is not None:
            new_qty = cart_item.quantity + int(delta)
            if new_qty <= 0:
                cart_item.delete()
                return _respond_with_cart(cart, session_key)

            variant = cart_item.variant
            if not variant.available or new_qty > variant.stock_quantity:
                response = Response(
                    {'error': f'Only {variant.stock_quantity} unit(s) of this item are available.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                if session_key:
                    response['X-Cart-Session'] = session_key
                return response

            cart_item.quantity = new_qty
            cart_item.save()
            return _respond_with_cart(cart, session_key)

        serializer = UpdateCartItemSerializer(data=request.data)
        if serializer.is_valid():
            new_qty = serializer.validated_data['quantity']
            variant = cart_item.variant
            if not variant.available or new_qty > variant.stock_quantity:
                response = Response(
                    {'error': f'Only {variant.stock_quantity} unit(s) of this item are available.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                if session_key:
                    response['X-Cart-Session'] = session_key
                return response

            cart_item.quantity = new_qty
            cart_item.save()
            return _respond_with_cart(cart, session_key)

        response = Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        if session_key:
            response['X-Cart-Session'] = session_key
        return response

    def delete(self, request, pk=None):
        cart, session_key = get_or_create_cart(request)
        cart_item = CartItem.objects.filter(cart=cart, id=pk).first()
        if not cart_item:
            product_id = request.data.get('product_id') or request.data.get('productId')
            if product_id:
                cart_item = CartItem.objects.filter(cart=cart, variant__product__slug=product_id).first()

        if cart_item:
            cart_item.delete()
            return _respond_with_cart(cart, session_key)
        response = Response({'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)
        if session_key:
            response['X-Cart-Session'] = session_key
        return response


class CartClearView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        cart, session_key = get_or_create_cart(request)
        cart.items.all().delete()
        return _respond_with_cart(cart, session_key)
