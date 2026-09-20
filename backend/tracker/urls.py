from django.urls import path

from . import views

urlpatterns = [
    path("products/search", views.product_search),
    path("products/track", views.track_product),
    path("products", views.tracked_products),
    path("products/<uuid:product_id>/history", views.product_history),
    path("products/<uuid:product_id>/logs", views.product_logs),
    path("scrape/run", views.scheduled_scrape),
]