from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from .models import User, WishlistItem
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    WishlistItemSerializer
)
from products.models import Product


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'message': 'Account created successfully',
                'token': token.key,
                'user': UserProfileSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'message': 'Login successful',
                'token': token.key,
                'user': UserProfileSerializer(user).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class WishlistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = WishlistItem.objects.filter(user=request.user).select_related('product', 'product__category')
        serializer = WishlistItemSerializer(items, many=True)
        # Also return array of saved product slugs/IDs for instant frontend toggle matching
        saved_ids = [item.product.slug for item in items]
        return Response({
            'saved_ids': saved_ids,
            'items': serializer.data
        })

    def post(self, request):
        product_identifier = request.data.get('product_id') or request.data.get('slug')
        if not product_identifier:
            return Response({'error': 'product_id or slug is required'}, status=status.HTTP_400_BAD_REQUEST)

        product = None
        if str(product_identifier).isdigit():
            product = Product.objects.filter(id=product_identifier).first()
        if not product:
            product = Product.objects.filter(slug=product_identifier).first()

        if not product:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        existing = WishlistItem.objects.filter(user=request.user, product=product).first()
        if existing:
            existing.delete()
            return Response({'message': 'Product removed from saved items', 'saved': False, 'product_slug': product.slug})
        else:
            WishlistItem.objects.create(user=request.user, product=product)
            return Response({'message': 'Product saved for later', 'saved': True, 'product_slug': product.slug}, status=status.HTTP_201_CREATED)
