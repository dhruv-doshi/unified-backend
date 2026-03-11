# Setup Guide — Actions Required From You

This document lists everything you need to do manually to get the backend running end-to-end.
The code is fully written and all tests pass locally.

---

## 1. One-Time: External Services Setup

### 1a. Cloudflare R2 (Image Storage)
1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) → R2 Storage
2. Create a bucket named `unified-backend` (or any name — update `R2_BUCKET_NAME` in `.env`)
3. Go to **R2 Overview** → **Manage R2 API Tokens** → **Create API Token**
   - Permissions: `Object Read & Write`
   - Copy: **Access Key ID** and **Secret Access Key**
4. From R2 Overview, copy your **Account ID** (appears in the URL and sidebar)
5. (Optional) Set up a **Custom Domain** on the bucket for public CDN access → becomes `R2_PUBLIC_BASE_URL`
   - Alternatively, enable **Public Access** on the bucket and use `https://<account-id>.r2.cloudflarestorage.com/<bucket-name>` as the public base URL

### 1b. OpenRouter (LLM API)
1. Go to [openrouter.ai](https://openrouter.ai) → Sign in
2. **Keys** → **Create Key** → Copy the key (starts with `sk-or-`)
3. Add credits to your account (Gemini Flash is cheap: ~$0.0001/image analysis)

### 1c. Google OAuth (optional — only needed for `POST /auth/oauth-callback`)
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. **Create Credentials** → OAuth 2.0 Client ID → Web Application
3. Add authorized origins: `http://localhost:3000` and your production frontend URL
4. Copy the **Client ID**

### 1d. SMTP Email (for verify-email + forgot-password)
**Option A — Gmail (quick):**
1. Enable 2FA on your Google account
2. Go to myaccount.google.com → Security → App Passwords → generate one
3. Use: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USERNAME=your@gmail.com`, `SMTP_PASSWORD=<app-password>`

**Option B — Resend / Postmark / SendGrid (production):**
- Resend: create account at [resend.com](https://resend.com), get API key, use their SMTP credentials

---

## 2. Configure `.env`

Copy `.env.example` to `.env` and fill in all values:

```bash
cp .env.example .env
```

Then edit `.env`:
```env
# Required — change these
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
R2_ENDPOINT_URL=https://<your-account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<from step 1a>
R2_SECRET_ACCESS_KEY=<from step 1a>
R2_BUCKET_NAME=unified-backend
R2_PUBLIC_BASE_URL=https://<your-custom-domain-or-public-r2-url>
OPENROUTER_API_KEY=sk-or-<from step 1b>
SMTP_USERNAME=your@gmail.com
SMTP_PASSWORD=<app-password from step 1d>

# Optional — only if using Google OAuth
GOOGLE_CLIENT_ID=<from step 1c>

# Set to your frontend URL
FRONTEND_URL=http://localhost:3000
```

---

## 3. Local Development (without Docker)

### Prerequisites
- Python 3.11
- PostgreSQL running locally (or Docker for just the DB)
- Redis running locally (or Docker for just Redis)

### Quick start with Docker for DB + Redis only:
```bash
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=unified_backend -p 5432:5432 postgres:16-alpine
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### Start the API:
```bash
source venv/bin/activate

# Run DB migrations (first time only)
alembic upgrade head

# Start the API server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# In a separate terminal — start the Celery worker
celery -A src.workers.celery_app worker --loglevel=info --concurrency=2
```

API is now at: http://localhost:8000
Swagger docs at: http://localhost:8000/docs

---

## 4. Full Docker Compose (Production-like)

### Prerequisites
- Docker Desktop installed and running
- `.env` file populated (step 2 above)

```bash
# Build and start all 5 services: db, redis, api, worker, nginx
docker compose up --build

# Or in background:
docker compose up --build -d
```

Services:
- **API** (direct): http://localhost:8000
- **Via Nginx**: http://localhost (port 80)
- **Swagger UI**: http://localhost/docs

### First run — apply DB migrations:
```bash
# After `docker compose up --build`, in a new terminal:
docker compose exec api alembic upgrade head
```

### Verify end-to-end:
```bash
# Register
curl -s -X POST http://localhost/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","password":"Password123!"}' | jq

# (Check your email for verification link, or manually verify via DB for testing)
# Upload an image (after getting token from login):
curl -s -X POST http://localhost/api/v1/analysis/upload \
  -H "Authorization: Bearer <token>" \
  -F "image=@/path/to/photo.jpg" | jq
```

---

## 5. Generate Alembic Migration (when you change models)

After changing any ORM model in `src/infrastructure/models/`:
```bash
source venv/bin/activate
alembic revision --autogenerate -m "describe_your_change"
alembic upgrade head
```

To rollback one migration:
```bash
alembic downgrade -1
```

---

## 6. Run Tests

```bash
source venv/bin/activate
pytest tests/ -v
pytest tests/ --cov=src --cov-report=html  # generates htmlcov/index.html
```

---

## 7. Production Deployment Checklist

Before going to production:
- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Use a strong random `SECRET_KEY` (32+ chars)
- [ ] Set up TLS on Nginx (add certbot/Let's Encrypt config)
- [ ] Use a managed PostgreSQL (e.g. Neon, Supabase, Railway, or RDS)
- [ ] Use a managed Redis (e.g. Upstash, Redis Cloud)
- [ ] Point `FRONTEND_URL` to your production frontend domain
- [ ] Add CORS origins for your production frontend domain in `src/main.py`
- [ ] Set up log aggregation (the app outputs JSON logs via structlog)
- [ ] Add a health check monitor for `/health`

---

## 8. Adding a New App (Multi-App Architecture)

To add a new app (e.g. "Color Palette"):
1. Add to `src/apps/registry.py`:
   ```python
   class AppName(StrEnum):
       SHOOT_RIGHT = "shoot_right"
       COLOR_PALETTE = "color_palette"   # add this

   APP_MODEL_MAPPING = {
       AppName.SHOOT_RIGHT: "google/gemini-2.0-flash-001",
       AppName.COLOR_PALETTE: "anthropic/claude-3-5-sonnet",  # add this
   }
   ```
2. The analysis pipeline, storage, and DB models are already app-aware.
3. Add new API routes if the new app needs different endpoints.

---

## 9. Common Issues

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Make sure `source venv/bin/activate` is active and `PYTHONPATH=.` is set |
| DB connection refused | PostgreSQL not running — start it or run the docker containers |
| Email not sending | Check SMTP credentials; Gmail requires App Password (not your account password) |
| R2 upload fails | Check `R2_ENDPOINT_URL` has your account ID; check bucket name matches |
| Celery tasks not running | Redis must be running; start the worker in a separate terminal |
| Alembic error on first run | Run `alembic upgrade head` after DB is up |
