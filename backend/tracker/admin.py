from django.contrib import admin
from .models import Product, TrackedProduct, PriceHistory, ScrapeLog

admin.site.register(Product)
admin.site.register(TrackedProduct)
admin.site.register(PriceHistory)
admin.site.register(ScrapeLog)