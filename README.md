# Unified Backend

A production-ready FastAPI backend for portfolio applications. Currently powers **ShootRight** — an AI-powered photography analysis tool.

## Quick Start

```bash
# Local development
cp .env.example .env          # fill in your values
source venv/bin/activate
uvicorn src.main:app --reload

# Run tests
pytest tests/ -v

# Docker (all services)
docker compose up --build
# First run only:
docker compose exec api alembic upgrade head
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| API | 8000 | FastAPI application |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Rate limiting + Celery broker |
| Celery | — | Background analysis tasks |
| Nginx | 80 | Reverse proxy |

## Documentation

- [Setup Guide](docs/SETUP_GUIDE.md) — External services, local dev, Docker
- [Frontend API Contract](docs/FRONTEND_CHANGES.md) — All endpoints, request/response shapes
- [Deployment Guide](docs/DEPLOY.md) — VPS deployment with SSL
- [Backend Requirements](docs/backend-requirement.md) — Original spec
