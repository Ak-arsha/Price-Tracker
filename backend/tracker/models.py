from django.db import models

import uuid
from django.db import models


class Product(models.Model):
    """One row per product we know about on the mock store."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_product_url = models.URLField(unique=True)
    name = models.CharField(max_length=500)
    image_url = models.URLField(blank=True, null=True)
    last_known_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    last_known_stock = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class TrackedProduct(models.Model):
    """Which products the user is actively tracking, and how often."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='tracked')
    is_active = models.BooleanField(default=True)
    scrape_interval_minutes = models.IntegerField(default=120)  # bonus: configurable per product
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tracking: {self.product.name}"


class PriceHistory(models.Model):
    """One row per SUCCESSFUL scrape only — never write failed/invalid data here."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_status = models.CharField(max_length=20)  # 'in_stock' | 'out_of_stock' | 'unknown'
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scraped_at']

    def __str__(self):
        return f"{self.product.name} @ {self.price} ({self.scraped_at})"


class ScrapeLog(models.Model):
    """Every scrape ATTEMPT, success or failure — the honest audit trail."""
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('retried', 'Retried'),
        ('failed', 'Failed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='scrape_logs')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    attempt_number = models.IntegerField(default=1)
    duration_ms = models.IntegerField(blank=True, null=True)
    failure_reason = models.CharField(max_length=50, blank=True, null=True)
    raw_price_text = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} — {self.status} (attempt {self.attempt_number})"