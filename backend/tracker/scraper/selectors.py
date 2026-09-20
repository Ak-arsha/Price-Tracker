STORE_BASE_URL = "https://demo.inelabteamdev.com"

LISTING_URL = f"{STORE_BASE_URL}/"

TILE = "article.tile"
TILE_NAME = "h3.tile-name"
TILE_CATEGORY = "span.tile-category"
TILE_BRAND = "p.tile-brand"
TILE_SKU = "p.tile-sku"
TILE_CTA = "button.tile-cta"

def detail_url(product_id):
    return f"{STORE_BASE_URL}/product/{product_id}"

DETAIL_NAME = "h1"
DETAIL_BRAND = "p.detail-brand"

PRICE_BLOCK = "div.price-block"
PRICE_STATUS = "p.price-status"
REVEAL_BUTTON = f"{PRICE_BLOCK} button.btn-primary"

PRICE_REVEALED_VALUE = "div.price-block .price-value"

STOCK_STATUS = "div.price-block .stock-badge"


def parse_price(raw_text):
    if not raw_text:
        return None
    cleaned = "".join(ch for ch in raw_text if ch.isdigit() or ch == ".")
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def parse_stock(raw_text):
    if not raw_text:
        return "unknown"
    t = raw_text.lower()
    if "out of stock" in t or "unavailable" in t or "sold out" in t:
        return "out_of_stock"
    if "in stock" in t or "available" in t:
        return "in_stock"
    return "unknown"