from django.urls import path
from .views import (
    ProductListView,
    ProductDetailView,
    CategoryListView,
    TrendingDealsView,
    NewArrivalsView
)

urlpatterns = [
    path('', ProductListView.as_view(), name='product-list'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('trending-deals/', TrendingDealsView.as_view(), name='trending-deals'),
    path('new-arrivals/', NewArrivalsView.as_view(), name='new-arrivals'),
    path('<slug:slug>/', ProductDetailView.as_view(), name='product-detail'),
]
