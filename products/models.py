from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, default='')
    collection = models.CharField(max_length=150, blank=True, default='')
    badge = models.CharField(max_length=50, blank=True, default='')  # e.g., 'BEST SELLER', 'HOT', 'NEW', 'SALE'
    is_new_arrival = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    former_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def primary_price(self):
        first_variant = self.variants.first()
        return first_variant.price if first_variant else None

    @property
    def primary_image(self):
        first_variant = self.variants.first()
        return first_variant.image if first_variant else ''

    @property
    def primary_variant(self):
        first_variant = self.variants.first()
        return first_variant.variant_name if first_variant else ''

    def __str__(self):
        return f"{self.name} ({self.category.name})"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    variant_name = models.CharField(max_length=150, default='Standard')  # e.g., "Matte Black", "Deep Slate"
    size = models.CharField(max_length=100, blank=True, default='')  # e.g., "1.7L", "Size 42", "Large"
    price = models.DecimalField(max_digits=12, decimal_places=2)
    image = models.CharField(max_length=500, blank=True, default='')  # URL or asset path
    stock_quantity = models.PositiveIntegerField(default=10)
    available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} - {self.variant_name} ({self.size})" if self.size else f"{self.product.name} - {self.variant_name}"
