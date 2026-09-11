from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    ProfileView,
    WishlistView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('sign-up/', RegisterView.as_view(), name='sign-up'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('wishlist/', WishlistView.as_view(), name='wishlist'),
]
