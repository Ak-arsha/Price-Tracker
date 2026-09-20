import os
import time
import random
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from . import selectors as sel

load_dotenv()
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

# Production can fail fast after one bounded attempt instead of risking a
# request timeout; local defaults retain the fuller headed-demo retry behavior.
MAX_OUTER_RETRIES = int(os.environ.get("SCRAPE_MAX_OUTER_RETRIES", 2))
MAX_CHALLENGE_RETRIES = int(os.environ.get("SCRAPE_MAX_CHALLENGE_RETRIES", 2))
MAX_RATE_LIMIT_RETRIES = int(os.environ.get("SCRAPE_MAX_RATE_LIMIT_RETRIES", 1))
HOVER_POLL_SECONDS = float(os.environ.get("SCRAPE_HOVER_POLL_SECONDS", 5))
REVEAL_POLL_SECONDS = float(os.environ.get("SCRAPE_REVEAL_POLL_SECONDS", 8))
NAV_TIMEOUT_MS = int(os.environ.get("SCRAPE_NAV_TIMEOUT_MS", 15000))
SELECTOR_TIMEOUT_MS = int(os.environ.get("SCRAPE_SELECTOR_TIMEOUT_MS", 8000))


def _human_like_reveal(page):
    """Move the mouse toward the price area and hover — the page enables
    the button only while genuinely, continuously hovered (a mousemove-
    driven state), so we keep gently jiggling the mouse right up until
    the moment we click, and click with raw coordinates rather than
    locator.click() (which re-hovers internally and can undo our hover)."""
    block = page.locator(sel.PRICE_BLOCK)
    box = block.bounding_box()
    if not box:
        raise RuntimeError("Price block not found on page")

    target_x = box["x"] + box["width"] / 2
    target_y = box["y"] + box["height"] / 2

    start_x = target_x - random.randint(80, 200)
    start_y = target_y - random.randint(40, 120)
    page.mouse.move(start_x, start_y)
    steps = 4
    for i in range(1, steps + 1):
        page.mouse.move(
            start_x + (target_x - start_x) * i / steps,
            start_y + (target_y - start_y) * i / steps,
        )
        time.sleep(0.05)
    deadline = time.time() + HOVER_POLL_SECONDS
    enabled = False
    while time.time() < deadline:
        page.mouse.move(target_x + random.uniform(-2, 2), target_y + random.uniform(-2, 2))
        enabled = page.evaluate(
            """(sel) => {
                const btn = document.querySelector(sel);
                return btn ? !btn.disabled : false;
            }""",
            sel.REVEAL_BUTTON,
        )
        if enabled:
            break
        time.sleep(0.15)

    if not enabled:
        raise RuntimeError("Reveal button never became enabled after hover")

    button = page.locator(sel.REVEAL_BUTTON)
    bbox = button.bounding_box()
    click_x = bbox["x"] + bbox["width"] / 2
    click_y = bbox["y"] + bbox["height"] / 2
    page.mouse.move(click_x, click_y)
    page.mouse.down()
    time.sleep(0.05)
    page.mouse.up()


def _read_price_status(page):
    try:
        return page.locator(sel.PRICE_STATUS).first.text_content(timeout=2000)
    except Exception:
        return None

def _dismiss_cookie_banner(page):
    texts = ["Accept", "Accept all", "I agree", "Got it", "OK"]
    deadline = time.time() + 1.5
    while time.time() < deadline:
        for text in texts:
            button = page.get_by_role("button", name=text, exact=False)
            if button.count() > 0:
                try:
                    button.first.click(timeout=1000)
                    time.sleep(0.4)
                except Exception:
                    pass
                return
        time.sleep(0.2)

def scrape_product(product_url, headed=False, on_attempt=None):
    attempts_used = 0
    last_reason = "unknown"

    def log(status, reason=None, raw=None, duration_ms=0):
        if on_attempt:
            on_attempt(status, attempts_used, duration_ms, reason, raw)

    def run_page(context):
        nonlocal attempts_used, last_reason

        page = context.new_page()
        page.set_default_timeout(SELECTOR_TIMEOUT_MS)

        started = time.time()
        response = page.goto(product_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        if not response or not response.ok:
            attempts_used += 1
            log("failed", "http_error", None, int((time.time() - started) * 1000))
            return {"ok": False, "reason": "http_error", "attempts": attempts_used}

        page.wait_for_selector(sel.DETAIL_NAME, timeout=SELECTOR_TIMEOUT_MS)
        name = page.locator(sel.DETAIL_NAME).first.text_content()
        _dismiss_cookie_banner(page)
        
        challenge_retries = 0
        rate_limit_retries = 0

        while True:
            attempts_used += 1
            attempt_started = time.time()

            try:
                _human_like_reveal(page)
            except Exception as e:
                last_reason = "reveal_button_not_found"
                log("failed", last_reason, str(e), int((time.time() - attempt_started) * 1000))
                return {"ok": False, "reason": last_reason, "attempts": attempts_used}

            status_text = None
            block_class = ""
            poll_deadline = time.time() + REVEAL_POLL_SECONDS
            while time.time() < poll_deadline:
                status_text = _read_price_status(page)
                block_class = page.locator(sel.PRICE_BLOCK).get_attribute("class") or ""
                if "loading" not in block_class.lower() and "loading" not in (status_text or "").lower():
                    break
                time.sleep(0.3)
            duration_ms = int((time.time() - attempt_started) * 1000)

            substatus_text = ""
            try:
                substatus_text = page.locator("p.price-substatus").first.text_content(timeout=1000) or ""
            except Exception:
                pass

            if "price-idle" in block_class:
                last_reason = "reveal_no_response"
            elif "price-error" in block_class:
                combined = f"{status_text or ''} {substatus_text}".lower()
                if "429" in combined or "rate" in combined:
                    last_reason = "rate_limited"
                    rate_limit_retries += 1
                    log("retried", last_reason, status_text, duration_ms)
                    if rate_limit_retries > MAX_RATE_LIMIT_RETRIES:
                        log("failed", last_reason, status_text, duration_ms)
                        return {"ok": False, "reason": last_reason, "attempts": attempts_used}
                    time.sleep(10 + random.uniform(0, 5))
                    continue
                else:
                    last_reason = "challenge_failed"
                    challenge_retries += 1
                    log("retried", last_reason, status_text, duration_ms)
                    if challenge_retries > MAX_CHALLENGE_RETRIES:
                        log("failed", last_reason, status_text, duration_ms)
                        return {"ok": False, "reason": last_reason, "attempts": attempts_used}
                    time.sleep(1.5 * (2 ** (challenge_retries - 1)))
                    continue
            else:
                # Neither idle nor error class - genuinely revealed.
                break

            if challenge_retries + rate_limit_retries > MAX_CHALLENGE_RETRIES:
                log("failed", last_reason, status_text, duration_ms)
                return {"ok": False, "reason": last_reason, "attempts": attempts_used}
            time.sleep(1.0)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        price_el = soup.select_one(sel.PRICE_REVEALED_VALUE)
        raw_price_text = price_el.get_text(strip=True) if price_el else None
        price = sel.parse_price(raw_price_text)

        stock_text = None
        if sel.STOCK_STATUS:
            stock_el = soup.select_one(sel.STOCK_STATUS)
            stock_text = stock_el.get_text(strip=True) if stock_el else None
        stock = sel.parse_stock(stock_text)

        duration_ms = int((time.time() - started) * 1000)

        if price is None:
            with open("debug_price_block.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"\n[DEBUG] raw_price_text={raw_price_text!r}")
            print("[DEBUG] Full page HTML saved to debug_price_block.html\n")

            last_reason = "validation_failed"
            log("failed", last_reason, raw_price_text, duration_ms)
            return {"ok": False, "reason": last_reason, "attempts": attempts_used}

        log("success", None, raw_price_text, duration_ms)
        return {"ok": True, "price": price, "stock": stock, "name": name.strip() if name else None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed, slow_mo=150 if headed else 0)
        try:
            result = {"ok": False, "reason": last_reason, "attempts": attempts_used}
            for outer_attempt in range(MAX_OUTER_RETRIES + 1):
                context = None
                try:
                    context = browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/120 Safari/537.36"
                        )
                    )
                    result = run_page(context)
                except Exception as e:
                    last_reason = "outer_retry_failed"
                    result = {"ok": False, "reason": last_reason, "attempts": attempts_used}
                    log("failed", last_reason, str(e), 0)
                finally:
                    if context:
                        context.close()

                if result.get("ok") or outer_attempt == MAX_OUTER_RETRIES:
                    return result
                time.sleep(2)

            return result
        finally:
            browser.close()