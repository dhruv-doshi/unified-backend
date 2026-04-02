#!/usr/bin/env bash
set -euo pipefail

# deploy.sh — Pull latest prod branch, rebuild, migrate, reload
# Run on the server: bash scripts/deploy.sh

echo "==> Pulling latest prod branch..."
git pull origin prod

DC="docker compose -f docker-compose.prod.yml --env-file .env.prod"

echo "==> Rebuilding api, worker, and migrate containers..."
$DC build --no-cache api worker migrate

echo "==> Starting all services..."
$DC up -d --remove-orphans

echo "==> Waiting for db to be healthy..."
sleep 5

echo "==> Running database migrations..."
$DC exec -T api alembic upgrade head

echo "==> Seeding accounts..."
$DC exec -T api python scripts/seed_accounts.py

echo "==> Deploy complete."
echo "    Health check: curl http://localhost:8000/health"
