from unittest.mock import patch
from django.test import TestCase, Client
from tracker.models import Product, TrackedProduct, PriceHistory, ScrapeLog

class ProductModelTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Smart Keyboard",
            store_product_url="https://demo.inelabteamdev.com/product/101",
            last_known_price="49.99",
            last_known_stock="in_stock"
        )

    def test_product_creation(self):
        self.assertEqual(str(self.product), "Test Smart Keyboard")
        self.assertEqual(self.product.last_known_price, "49.99")

class TrackedProductModelTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Mouse",
            store_product_url="https://demo.inelabteamdev.com/product/102"
        )
        self.tracked = TrackedProduct.objects.create(product=self.product)

    def test_tracked_product_str(self):
        self.assertEqual(str(self.tracked), "Tracking: Test Mouse")
        self.assertTrue(self.tracked.is_active)

class PriceHistoryAndScrapeLogTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Display",
            store_product_url="https://demo.inelabteamdev.com/product/103"
        )

    def test_price_history_creation(self):
        history = PriceHistory.objects.create(
            product=self.product,
            price=199.99,
            stock_status="in_stock"
        )
        self.assertIn("199.99", str(history))

    def test_scrape_log_creation(self):
        log = ScrapeLog.objects.create(
            product=self.product,
            status="failed",
            attempt_number=1,
            failure_reason="challenge_failed"
        )
        self.assertEqual(log.status, "failed")
        self.assertIn("failed", str(log))

class ApiViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(
            name="Test Headphones",
            store_product_url="https://demo.inelabteamdev.com/product/104",
            last_known_price="89.00",
            last_known_stock="in_stock"
        )
        self.tracked = TrackedProduct.objects.create(product=self.product)

    def test_tracked_products_list(self):
        response = self.client.get('/api/products')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data.get('results', [])), 1)
        self.assertEqual(data['results'][0]['name'], "Test Headphones")

    def test_product_history_endpoint(self):
        PriceHistory.objects.create(product=self.product, price=89.00, stock_status="in_stock")
        response = self.client.get(f'/api/products/{self.product.id}/history')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['results']), 1)

    def test_product_logs_endpoint(self):
        ScrapeLog.objects.create(product=self.product, status="success", attempt_number=1)
        response = self.client.get(f'/api/products/{self.product.id}/logs')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['results']), 1)

    def test_track_product_endpoint(self):
        response = self.client.post(
            '/api/products/track',
            data={"name": "New Web Cam", "url": "https://demo.inelabteamdev.com/product/105"},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(Product.objects.filter(name="New Web Cam").exists())

    @patch('tracker.views.settings')
    @patch('tracker.views._scrape_and_record')
    def test_scheduled_scrape_unauthorized(self, mock_scrape, mock_settings):
        mock_settings.SCRAPE_TRIGGER_SECRET = "secret123"
        response = self.client.post('/api/scrape/run', HTTP_X_SCRAPE_SECRET="wrongsecret")
        self.assertEqual(response.status_code, 401)

    @patch('tracker.views.settings')
    @patch('tracker.views._scrape_and_record')
    def test_scheduled_scrape_authorized(self, mock_scrape, mock_settings):
        mock_settings.SCRAPE_TRIGGER_SECRET = "secret123"
        mock_scrape.return_value = {"ok": True, "price": "89.00", "stock": "in_stock"}
        response = self.client.post('/api/scrape/run', HTTP_X_SCRAPE_SECRET="secret123")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("product_id"), str(self.product.id))
