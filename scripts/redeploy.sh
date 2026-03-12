#!/usr/bin/env bash
set -euo pipefail

# redeploy.sh — Pull latest code and redeploy all services
# Run from /srv/app/unified-backend on the server:
#   bash scripts/redeploy.sh

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

DC="docker compose -f docker-compose.prod.yml --env-file .env.prod"

echo "==> Pulling latest code..."
git pull origin prod

echo "==> Rebuilding images..."
$DC build --no-cache api worker

echo "==> Restarting services..."
$DC up -d --remove-orphans

echo "==> Waiting for API to be healthy..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "    API is up."
        break
    fi
    echo "    Attempt $i/15..."
    sleep 3
done

echo ""
echo "==> Service status:"
$DC ps

echo ""
echo "==> Done. To tail logs:"
echo "    docker compose -f docker-compose.prod.yml logs -f api worker"
