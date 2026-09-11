from django.urls import path
from .views import (
    CartDetailView,
    CartItemAddView,
    CartItemUpdateView,
    CartClearView
)

urlpatterns = [
    path('', CartDetailView.as_view(), name='cart-detail'),
    path('items/', CartItemAddView.as_view(), name='cart-item-add'),
    path('items/<int:pk>/', CartItemUpdateView.as_view(), name='cart-item-update-delete'),
    path('clear/', CartClearView.as_view(), name='cart-clear'),
]
