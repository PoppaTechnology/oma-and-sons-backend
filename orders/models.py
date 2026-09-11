from django.db import models
from django.conf import settings
import uuid
import datetime


class PromoCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)  # e.g., 10.00 for 10%
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_valid(self):
        if not self.is_active:
            return False
        if self.valid_until and self.valid_until < datetime.datetime.now(datetime.timezone.utc):
            return False
        return True

    def __str__(self):
        return f"{self.code} ({self.discount_percent}% off)"

class Order(models.Model):
    FULFILLMENT_CHOICES = (
        ('ship', 'Ship to address'),
        ('pickup', 'Store pickup'),
    )

    DELIVERY_METHOD_CHOICES = (
        ('standard', 'Standard Delivery (2-4 business days)'),
        ('express', 'Express Delivery (1-2 business days)'),
        ('pickup', 'Store Pickup (Ready in 2 hours)'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending Payment'),
        ('CONFIRMED', 'Order Confirmed'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    )

    order_number = models.CharField(max_length=64, unique=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    recipient_name = models.CharField(max_length=200, blank=True, default='')
    email = models.EmailField()
    phone_number = models.CharField(max_length=30)

    fulfillment_type = models.CharField(max_length=20, choices=FULFILLMENT_CHOICES, default='ship')
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHOD_CHOICES, default='standard')
    delivery_address = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    pickup_store = models.CharField(max_length=150, blank=True, default='')

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_code = models.CharField(max_length=50, blank=True, default='')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    order_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            random_suffix = uuid.uuid4().hex[:6].upper()
            self.order_number = f"#OS-{datetime.date.today().strftime('%y%m')}-{random_suffix}"
        if not self.recipient_name:
            self.recipient_name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_number} - {self.recipient_name} (₦{self.total_amount})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items'
    )
    product_name = models.CharField(max_length=255)
    variant_name = models.CharField(max_length=150, blank=True, default='')
    product_slug = models.CharField(max_length=255, blank=True, default='')
    size = models.CharField(max_length=100, blank=True, default='')
    image = models.CharField(max_length=500, blank=True, default='')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity}x {self.product_name} ({self.variant_name})"
