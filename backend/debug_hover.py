import os
import time
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from playwright.sync_api import sync_playwright
from tracker.scraper import selectors as sel
from tracker.scraper.scraper import _dismiss_cookie_banner

url = sel.detail_url("6")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=0)
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    page.wait_for_selector(sel.DETAIL_NAME, timeout=8000)

    print("Checking for cookie banner...")
    _dismiss_cookie_banner(page)
    print("Done with banner check.")

    block = page.locator(sel.PRICE_BLOCK)
    box = block.bounding_box()
    target_x = box["x"] + box["width"] / 2
    target_y = box["y"] + box["height"] / 2
    print(f"Price block center: ({target_x}, {target_y})")

    page.mouse.move(target_x, target_y)
    print("Moved mouse onto price block. Polling disabled state for 6 seconds...")

    last_state = None
    start = time.time()
    while time.time() - start < 6:
        disabled = page.evaluate(
            """(sel) => {
                const btn = document.querySelector(sel);
                return btn ? btn.disabled : 'NOT FOUND';
            }""",
            sel.REVEAL_BUTTON,
        )
        if disabled != last_state:
            print(f"  t={time.time()-start:.2f}s  disabled={disabled}")
            last_state = disabled
        time.sleep(0.1)

    print("\nDone polling. Browser stays open 10s for you to look manually.")
    time.sleep(10)
    browser.close()