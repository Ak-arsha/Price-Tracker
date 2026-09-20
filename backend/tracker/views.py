import json
import re

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from playwright.sync_api import sync_playwright

from .models import PriceHistory, Product, ScrapeLog, TrackedProduct
from .scraper import selectors as sel
from .scraper.scraper import scrape_product


def _json_body(request):
	try:
		return json.loads(request.body or "{}")
	except json.JSONDecodeError:
		return None


def _product_payload(product):
	try:
		tracked = product.tracked
	except TrackedProduct.DoesNotExist:
		tracked = None
	return {
		"id": str(product.id),
		"name": product.name,
		"url": product.store_product_url,
		"store_product_url": product.store_product_url,
		"last_known_price": str(product.last_known_price) if product.last_known_price is not None else None,
		"last_known_stock": product.last_known_stock,
		"is_active": tracked.is_active if tracked else False,
	}


def _record_scrape(product, result):
	if result.get("ok") and result.get("price") is not None:
		product.last_known_price = result["price"]
		product.last_known_stock = result.get("stock") or "unknown"
		product.save(update_fields=["last_known_price", "last_known_stock", "updated_at"])
		PriceHistory.objects.create(
			product=product,
			price=result["price"],
			stock_status=product.last_known_stock,
		)


def _scrape_and_record(product):
	def on_attempt(status, attempt, duration_ms, reason, raw):
		ScrapeLog.objects.create(
			product=product,
			status=status,
			attempt_number=attempt,
			duration_ms=duration_ms,
			failure_reason=reason,
			raw_price_text=raw,
		)

	try:
		result = scrape_product(product.store_product_url, on_attempt=on_attempt)
	except Exception as exc:
		result = {"ok": False, "reason": "scraper_exception", "error": str(exc)}
		on_attempt("failed", 0, None, result["reason"], str(exc))
	_record_scrape(product, result)
	return result


def _store_product_id(url):
	match = re.search(r"/product/([^/?#]+)", url or "")
	return match.group(1) if match else None


def product_search(request):
	query = request.GET.get("q", "").strip().lower()
	if not query:
		return JsonResponse({"results": []})

	results = []
	with sync_playwright() as playwright:
		browser = playwright.chromium.launch(headless=True)
		try:
			page = browser.new_page()
			page.goto(sel.LISTING_URL, wait_until="domcontentloaded", timeout=15000)
			page.wait_for_selector(sel.TILE, timeout=8000)
			for tile in page.locator(sel.TILE).all():
				name = (tile.locator(sel.TILE_NAME).first.text_content() or "").strip()
				if query not in name.lower():
					continue
				href = tile.locator("a").first.get_attribute("href")
				product_id = tile.get_attribute("data-product-id") or _store_product_id(href)
				if not product_id:
					button = tile.locator(sel.TILE_CTA).first
					product_id = button.get_attribute("data-product-id")
				if product_id:
					url = sel.detail_url(product_id)
					results.append({
						"name": name,
						"store_product_id": product_id,
						"store_product_url": url,
					})
		finally:
			browser.close()
	return JsonResponse({"results": results})


@csrf_exempt
def track_product(request):
	if request.method != "POST":
		return JsonResponse({"error": "POST required"}, status=405)
	body = _json_body(request)
	if not body or not body.get("url") or not body.get("name"):
		return JsonResponse({"error": "url and name are required"}, status=400)
	with transaction.atomic():
		product, _ = Product.objects.update_or_create(
			store_product_url=body["url"],
			defaults={"name": body["name"]},
		)
		TrackedProduct.objects.update_or_create(product=product, defaults={"is_active": True})
	result = _scrape_and_record(product)
	payload = _product_payload(product)
	payload["scrape"] = result
	return JsonResponse(payload, status=201)


def tracked_products(request):
	products = Product.objects.filter(tracked__is_active=True).order_by("name")
	return JsonResponse({"results": [_product_payload(product) for product in products]})


def product_history(request, product_id):
	rows = PriceHistory.objects.filter(product_id=product_id).order_by("scraped_at")
	return JsonResponse({"results": [
		{"price": str(row.price), "stock_status": row.stock_status, "scraped_at": row.scraped_at.isoformat()}
		for row in rows
	]})


def product_logs(request, product_id):
	rows = ScrapeLog.objects.filter(product_id=product_id).order_by("-created_at")[:200]
	return JsonResponse({"results": [
		{
			"status": row.status,
			"attempt_number": row.attempt_number,
			"duration_ms": row.duration_ms,
			"failure_reason": row.failure_reason,
			"raw_price_text": row.raw_price_text,
			"created_at": row.created_at.isoformat(),
		}
		for row in rows
	]})


@csrf_exempt
def scheduled_scrape(request):
	if request.method != "POST":
		return JsonResponse({"error": "POST required"}, status=405)
	expected = getattr(settings, "SCRAPE_TRIGGER_SECRET", "")
	if not expected or request.headers.get("X-Scrape-Secret") != expected:
		return JsonResponse({"error": "unauthorized"}, status=401)
	results = []
	for tracked in TrackedProduct.objects.select_related("product").filter(is_active=True):
		result = _scrape_and_record(tracked.product)
		results.append({"product_id": str(tracked.product_id), "name": tracked.product.name, "result": result})
	return JsonResponse({"results": results})
