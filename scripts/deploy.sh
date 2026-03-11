#!/usr/bin/env bash
set -euo pipefail

# deploy.sh — Pull latest prod branch, rebuild, migrate, reload
# Run on the server: bash scripts/deploy.sh

echo "==> Pulling latest prod branch..."
git pull origin prod

echo "==> Rebuilding api and worker containers..."
docker compose -f docker-compose.prod.yml build --no-cache api worker

echo "==> Starting all services..."
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "==> Waiting for db to be healthy..."
sleep 5

echo "==> Running database migrations..."
docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head

echo "==> Seeding accounts..."
docker compose -f docker-compose.prod.yml exec -T api python scripts/seed_accounts.py

echo "==> Deploy complete."
echo "    Health check: curl http://localhost:8000/health"
