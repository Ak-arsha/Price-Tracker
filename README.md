# Product Price Tracker

A full-stack web application for tracking product prices and stock status from INE's hosted mock store (`https://demo.inelabteamdev.com/`). Successful scrapes generate price history data points; failed and retried attempts remain transparently visible in per-product scrape logs without poisoning history metrics with invalid data.

- **Live Frontend (Vercel)**: [https://price-tracker-frontend-liart.vercel.app](https://price-tracker-frontend-liart.vercel.app)
- **Live Backend API (Render)**: [https://price-tracker-5jbv.onrender.com](https://price-tracker-5jbv.onrender.com)
- **GitHub Repository**: [https://github.com/Ak-arsha/Price-Tracker](https://github.com/Ak-arsha/Price-Tracker)

---

## Project Layout

- `backend/`: Django REST API, Supabase PostgreSQL configuration, Playwright scraping engine, and Render deployment scripts.
- `frontend/`: Clean responsive dashboard interface for searching, tracking, price history visualization, and scrape log auditing.
- `.github/workflows/ci.yml`: GitHub Actions CI pipeline for automated testing and Django integrity checks.

---

## Technical Stack & Infrastructure

- **Frontend**: HTML5, CSS3, ES6 JavaScript (deployed on **Vercel**).
- **Backend**: Python 3.11, Django 5.2, Playwright (deployed on **Render**).
- **Database**: Supabase PostgreSQL.
- **Scraper Engine**: Playwright Chromium (Headless in production, Headed for demonstration/debugging).
- **Scheduler**: Scheduled Cron endpoint (`/api/scrape/run`) triggered every 2 hours via **cron-job.org**.

---

## Required Environment Variables

### Backend (`backend/.env`)

```env
DJANGO_SECRET_KEY=your-django-secret-key
DEBUG=False
DATABASE_URL=postgresql://postgres.xxxx:yourpassword@aws-0-region.pooler.supabase.com:6543/postgres
SCRAPE_TRIGGER_SECRET=your-cron-secret-key
FRONTEND_ORIGIN=https://price-tracker-frontend-liart.vercel.app
ALLOWED_HOSTS=price-tracker-5jbv.onrender.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://price-tracker-frontend-liart.vercel.app,https://price-tracker-5jbv.onrender.com
```

### Configurable Scraper Environment Overrides (Optional)

```env
SCRAPE_MAX_OUTER_RETRIES=2
SCRAPE_MAX_CHALLENGE_RETRIES=2
SCRAPE_MAX_RATE_LIMIT_RETRIES=1
SCRAPE_NAV_TIMEOUT_MS=15000
SCRAPE_SELECTOR_TIMEOUT_MS=8000
```

---

## Local Setup & Development

### 1. Backend Setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
python manage.py migrate
python manage.py runserver
```

### 2. Frontend Setup

```powershell
cd frontend
python -m http.server 5500
```

Open `http://localhost:5500` in your browser.

---

## API Reference

- `GET /api/products/search?q=<query>`: Search INE's hosted mock store by partial or full product name.
- `POST /api/products/track`: Track a product (Body: `{"name": "...", "url": "..."}`).
- `GET /api/products`: Retrieve all active tracked products.
- `GET /api/products/<id>/history`: Retrieve chronological successful price history for a product.
- `GET /api/products/<id>/logs`: Retrieve up to 200 audit scrape log entries for a product.
- `POST /api/scrape/run`: Trigger a scheduled scrape. Requires `X-Scrape-Secret` header matching `SCRAPE_TRIGGER_SECRET`.

---

## Scheduling Setup (cron-job.org)

1. Create a cron job on [cron-job.org](https://cron-job.org).
2. Set URL to: `https://price-tracker-5jbv.onrender.com/api/scrape/run`.
3. Set Request Method to `POST`.
4. Set Schedule to run **every 2 hours** (or custom interval).
5. Add HTTP Header: `X-Scrape-Secret: <YOUR_SCRAPE_TRIGGER_SECRET>`.

---

## Headed Mode Demonstration (Screen Recording)

To run the scraper in headed (visible) browser mode for recording assignment evidence:

```powershell
cd backend
.\venv\Scripts\python test_scrape.py 850
```

This launches Chromium visibly (`headed=True`), performs human-like hover micro-movements to unlock the price reveal button, handles cookie banners and simulated load delays, and outputs logs to stdout.

---

## Verification & Testing

Run unit tests and Django system check:

```powershell
cd backend
.\venv\Scripts\python manage.py check
.\venv\Scripts\python manage.py test tracker
```

CI runs automatically via GitHub Actions on every push to `main`.

---

## Design Note

### 1. Scraping Reliability Strategy
The INE mock store (`demo.inelabteamdev.com`) enforces non-trivial anti-scraping patterns:
- **Hover-Gated UI Actionability**: The price reveal button is disabled by default and requires continuous, realistic mouse movement (`mousemove`) over the container element to become enabled.
- **Micro-movement Simulation**: Simple `element.hover()` calls fail because the store validates mouse trajectory over time. The scraper simulates human cursor drift using multi-step linear interpolation with random perturbations (`page.mouse.move()`) before firing coordinate-level click events (`page.mouse.down()`, `page.mouse.up()`). Direct `locator.click()` calls are intentionally avoided because Playwright's default pre-click actionability check momentarily alters mouse focus, re-disabling the button.
- **Resilient Error Recovery & Jittered Backoff**: Scrape attempts encounter `429 Too Many Requests` (rate limiting) or dynamic DOM challenges (`price-error`). The scraper detects status block classes and responds with exponential backoff and randomized jitter (10s–15s for rate limits, 1.5s step-doubling for challenges).
- **Honest Audit Logging**: Scrapes are logged per attempt into Supabase (`ScrapeLog`) capturing status (`success`, `retried`, `failed`), attempt count, execution duration, raw unparsed text, and exact failure reason. Crucially, `PriceHistory` records are written **only** when price parsing strictly succeeds (`ok=True`), guaranteeing zero data corruption.

### 2. Architectural Trade-Offs
- **Headless Browser vs. HTTP Parsing**: Fast HTTP clients (e.g. `requests` + `BeautifulSoup`) were insufficient because the target store's price unlocking logic requires real client-side JavaScript execution and live event listener state. Playwright Chromium was selected despite higher CPU/memory overhead.
- **Single-Product Round-Robin Execution**: Render's free tier imposes a strict 30-second HTTP request timeout. Executing multi-product bulk scrapes within a single cron request frequently caused Render proxy 504 timeouts when retries occurred. The `/api/scrape/run` endpoint was engineered to select and scrape **one product per cron invocation** (ordered by `latest_scrape_at nulls_first`), achieving round-robin coverage while keeping execution times safely under HTTP proxy boundaries.

### 3. AI Tool Missteps & Corrections
- **Mistake 1: Standard `locator.click()` Usage**: Early AI-generated code relied on standard Playwright `.click()`. On this mock store, standard `.click()` triggers an implicit hover check that resets the button's `disabled` state right as the click is dispatched.
  - *Correction*: Replaced `.click()` with continuous mouse movement jiggling (`page.mouse.move()`) followed by low-level press events (`page.mouse.down()`, `page.mouse.up()`).
- **Mistake 2: Bulk Scrape Timeout on Free Tier**: The initial AI plan attempted to loop through all tracked products inside a single POST request. Under network delay or retry conditions, this hit Render's 30s timeout.
  - *Correction*: Redesigned the scheduled route to execute a targeted round-robin single-product scrape per cron ping.
- **Mistake 3: Missing Headless Browser Binaries in CI/Production**: Playwright browsers were missing during the initial deployment phase on Render.
  - *Correction*: Configured `build.sh` with `python -m playwright install chromium` and set `PLAYWRIGHT_BROWSERS_PATH=0` in environment configuration.