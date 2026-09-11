from django.contrib import admin
from .models import Order, OrderItem, PromoCode


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'variant_name', 'unit_price', 'quantity', 'subtotal', 'created_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'recipient_name', 'email', 'phone_number',
        'delivery_method', 'total_amount', 'order_status', 'created_at'
    )
    list_filter = ('order_status', 'fulfillment_type', 'delivery_method', 'created_at')
    search_fields = ('order_number', 'first_name', 'last_name', 'recipient_name', 'email', 'phone_number')
    inlines = [OrderItemInline]


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percent', 'is_active', 'valid_until', 'created_at')
    list_editable = ('is_active',)
    search_fields = ('code',)
