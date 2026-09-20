import sys
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tracker.scraper.scraper import scrape_product
from tracker.scraper import selectors as sel

def on_attempt(status, attempt, duration_ms, reason, raw):
    print(f"  attempt {attempt}: {status}" + (f" ({reason})" if reason else "") + f" — {duration_ms}ms" + (f" — raw: {raw!r}" if raw else ""))

if __name__ == "__main__":
    product_id = sys.argv[1] if len(sys.argv) > 1 else "1"
    url = sel.detail_url(product_id)
    print(f"Scraping {url} in HEADED mode — watch the browser window...\n")
    result = scrape_product(url, headed=True, on_attempt=on_attempt)
    print("\nFinal result:", result)