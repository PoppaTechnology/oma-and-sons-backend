from django.urls import path
from .views import (
    InitializePaymentView,
    VerifyPaymentView,
    PaystackWebhookView,
    FlutterwaveWebhookView,
)

urlpatterns = [
    path('initialize/', InitializePaymentView.as_view(), name='payment-initialize'),
    path('verify/', VerifyPaymentView.as_view(), name='payment-verify'),
    path('webhooks/paystack/', PaystackWebhookView.as_view(), name='payment-webhook-paystack'),
    path('webhooks/flutterwave/', FlutterwaveWebhookView.as_view(), name='payment-webhook-flutterwave'),
]
