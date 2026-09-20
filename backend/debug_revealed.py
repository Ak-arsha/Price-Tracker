import os
import time
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from playwright.sync_api import sync_playwright
from tracker.scraper import selectors as sel
from tracker.scraper.scraper import _dismiss_cookie_banner, _human_like_reveal, _read_price_status

url = sel.detail_url("8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_selector(sel.DETAIL_NAME, timeout=8000)
    _dismiss_cookie_banner(page)

    for i in range(1, 6):
        print(f"Attempt {i}: revealing...")
        try:
            _human_like_reveal(page)
        except Exception as e:
            print(f"  reveal action failed: {e}")
            time.sleep(1.5)
            continue

        time.sleep(1.2)
        status = _read_price_status(page)
        print(f"  status text: {status!r}")

        if status and "hidden" not in status.lower() and "fail" not in status.lower() and "again" not in status.lower():
            print("\n*** LOOKS REVEALED — dumping full price-block HTML ***\n")
            print(page.locator(sel.PRICE_BLOCK).inner_html())
            print("\n*** Also dumping the price-block's outer class attribute ***")
            print(page.locator(sel.PRICE_BLOCK).get_attribute("class"))
            break
        time.sleep(2)

    print("\nBrowser stays open 20s so you can also look/screenshot manually.")
    time.sleep(20)
    browser.close()