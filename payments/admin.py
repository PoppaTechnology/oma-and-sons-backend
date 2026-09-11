from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_reference', 'order', 'payment_provider', 'amount', 'payment_status', 'created_at')
    list_filter = ('payment_status', 'payment_provider', 'created_at')
    search_fields = ('payment_reference', 'order__order_number', 'order__email')
