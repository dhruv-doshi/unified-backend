#!/usr/bin/env bash
# Restart prod services after a code change.
# Usage:
#   bash scripts/restart.sh          # rebuild + restart all services
#   bash scripts/restart.sh api      # rebuild + restart only the api service
#   bash scripts/restart.sh worker   # rebuild + restart only the celery worker

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SCRIPT_DIR}/.."
COMPOSE="docker compose -f ${ROOT}/docker-compose.prod.yml"

SERVICE="${1:-}"

cd "$ROOT"

if [[ -n "$SERVICE" ]]; then
    echo "→ Rebuilding and restarting: $SERVICE"
    $COMPOSE up -d --build --no-deps "$SERVICE"
else
    echo "→ Rebuilding and restarting all services"
    $COMPOSE up -d --build
fi

echo ""
echo "→ Running containers:"
$COMPOSE ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"
