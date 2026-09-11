from django.db import models


class Payment(models.Model):
    PROVIDER_CHOICES = (
        ('PAYSTACK', 'Paystack'),
        ('FLUTTERWAVE', 'Flutterwave'),
        # Legacy choices kept for database backward compatibility
        ('CARD', 'Card Payment (Legacy)'),
        ('BANK_TRANSFER', 'Bank Transfer (Legacy)'),
        ('USSD', 'USSD (Legacy)'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('SUCCESSFUL', 'Successful'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    )

    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='payment')
    payment_provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default='PAYSTACK')
    payment_reference = models.CharField(max_length=100, unique=True, db_index=True)
    payment_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    gateway_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def is_successful(self):
        return self.payment_status == 'SUCCESSFUL'

    def mark_successful(self, gateway_response=None):
        self.payment_status = 'SUCCESSFUL'
        if gateway_response:
            self.gateway_response = gateway_response
        self.save(update_fields=['payment_status', 'gateway_response', 'updated_at'])

    def mark_failed(self, gateway_response=None):
        self.payment_status = 'FAILED'
        if gateway_response:
            self.gateway_response = gateway_response
        self.save(update_fields=['payment_status', 'gateway_response', 'updated_at'])

    def __str__(self):
        return f"Payment {self.payment_reference} for {self.order.order_number} ({self.payment_status} - ₦{self.amount})"
