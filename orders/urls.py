from django.urls import path
from .views import (
    CheckoutView,
    OrderListView,
    OrderDetailView,
    OrderTrackingView,
    ValidatePromoCodeView
)

urlpatterns = [
    path('checkout/', CheckoutView.as_view(), name='order-checkout'),
    path('track/', OrderTrackingView.as_view(), name='order-track'),
    path('', OrderListView.as_view(), name='order-list'),
    path('validate-promo/', ValidatePromoCodeView.as_view(), name='validate-promo'),
    path('<str:order_number>/', OrderDetailView.as_view(), name='order-detail'),
]
