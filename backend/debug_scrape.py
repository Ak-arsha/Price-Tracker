import os
import time
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from playwright.sync_api import sync_playwright
from tracker.scraper import selectors as sel

product_id = "4"
url = sel.detail_url(product_id)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=150)
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_selector(sel.DETAIL_NAME, timeout=8000)
    print("Page loaded. Taking screenshot BEFORE any dismiss attempt...")
    page.screenshot(path="debug_1_initial.png")

    # Try dismissing cookie banner
    for text in ["Accept", "Accept all", "I agree", "Got it", "OK"]:
        try:
            btn = page.get_by_role("button", name=text, exact=False)
            if btn.count() > 0:
                print(f"Found a button matching '{text}', clicking it...")
                btn.first.click(timeout=2000)
                time.sleep(0.5)
                break
        except Exception as e:
            print(f"  '{text}' didn't match: {e}")

    page.screenshot(path="debug_2_after_dismiss.png")
    print("Screenshot taken AFTER dismiss attempt.")

    price_block_html = page.locator(sel.PRICE_BLOCK).inner_html()
    print("\n--- price-block HTML right now ---")
    print(price_block_html)
    print("--- end ---\n")

    print("Browser will stay open for 15 seconds so you can look at it manually...")
    time.sleep(15)
    browser.close()