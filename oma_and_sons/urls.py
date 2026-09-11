"""
URL configuration for oma_and_sons project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


def api_root(request):
    return JsonResponse({
        'name': 'Oma & Sons Dynamics API',
        'version': '1.0.0',
        'status': 'online',
        'documentation': {
            'products': '/products/ or /api/products/',
            'categories': '/products/categories/',
            'cart': '/cart/ or /api/cart/',
            'orders': '/orders/ or /api/orders/',
            'payments': '/payments/ or /api/payments/',
            'accounts': '/accounts/ or /api/accounts/',
        }
    })


urlpatterns = [
    path('', api_root, name='api-root'),
    path('admin/', admin.site.urls),

    # Standard routes
    path('accounts/', include('accounts.urls')),
    path('cart/', include('cart.urls')),
    path('products/', include('products.urls')),
    path('orders/', include('orders.urls')),
    path('payments/', include('payments.urls')),

    # Prefixed API routes (/api/...) for React frontend standard conventions
    path('api/', api_root, name='api-index'),
    path('api/accounts/', include('accounts.urls')),
    path('api/cart/', include('cart.urls')),
    path('api/products/', include('products.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/payments/', include('payments.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
