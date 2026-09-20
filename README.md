# Product Price Tracker

A Django + vanilla JavaScript app for tracking prices from INE's hosted mock store. Successful scrapes create history points; failed and retried attempts remain visible in the scrape log and never create fabricated history data.

## Project layout

- `backend/`: Django API, models, Playwright scraper, and Render deployment files.
- `frontend/`: plain static HTML/CSS/JS dashboard for Vercel or another static host.

## Local setup

### Backend

```powershell
cd backend
python -m pip install -r requirements.txt
python -m playwright install chromium
python manage.py migrate
python manage.py runserver
```

Create `backend/.env` with:

```env
DJANGO_SECRET_KEY=replace-with-a-long-random-value
DEBUG=True
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/postgres
SCRAPE_TRIGGER_SECRET=replace-with-a-cron-secret
FRONTEND_ORIGIN=http://localhost:5500
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:5500
```

### Frontend

```powershell
cd frontend
python -m http.server 5500
```

Update `API_BASE` near the top of `frontend/script.js` when the backend URL changes:

```js
const API_BASE = "http://localhost:8000";
```

## API

- `GET /api/products/search?q=keyboard`: search INE's listing page.
- `POST /api/products/track`: body `{ "url": "...", "name": "..." }`; track and scrape immediately.
- `GET /api/products`: list active tracked products.
- `GET /api/products/<uuid>/history`: successful readings, oldest first.
- `GET /api/products/<uuid>/logs`: up to 200 attempts, newest first.
- `POST /api/scrape/run`: sequentially scrape all active products. Requires `X-Scrape-Secret`.

## Scheduling

Configure cron-job.org to send a `POST` every 2 hours to:

```text
https://YOUR-RENDER-SERVICE.onrender.com/api/scrape/run
```

Set the `X-Scrape-Secret` header to the same value as Render's `SCRAPE_TRIGGER_SECRET`. Products are scraped sequentially because the mock store is intentionally fragile.

## Supabase

Set Render's `DATABASE_URL` to the Supabase Postgres connection string. Run migrations with `python manage.py migrate`; `backend/build.sh` runs migrations during deployment. The existing Django models store products, tracked products, successful price history, and every scrape attempt.

## Deployment

### Render backend

Create a Render Web Service with root directory `backend`, build command `bash build.sh`, and start command `gunicorn config.wsgi:application`. Configure `DJANGO_SECRET_KEY`, `DATABASE_URL`, `SCRAPE_TRIGGER_SECRET`, `FRONTEND_ORIGIN`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `DEBUG=False`. `build.sh` collects static files, runs migrations, and installs Chromium for Playwright.

### Vercel frontend

Deploy the `frontend` folder as a static Vercel project. No build command or framework preset is required. Point `API_BASE` in `frontend/script.js` at the Render backend URL before deploying.

## Headed run

From `backend`, run:

```powershell
python test_scrape.py 12
```

This opens Playwright headed, performs the human-like reveal attempts, and prints each outcome. Record the browser and terminal for assignment evidence. A failed scrape must remain a failed log entry and must not add a history point.

## Verification

```powershell
cd backend
python manage.py check
python manage.py test
```

The current Django test suite is still a scaffold and should be expanded with mocked scraper tests before depending on unattended production runs. Verify Supabase network connectivity from the deployment environment.