#!/usr/bin/env bash
# logs.sh — Tail logs for one or all services
# Usage:
#   bash scripts/logs.sh              # all services
#   bash scripts/logs.sh api          # api only
#   bash scripts/logs.sh api worker   # multiple services

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

DC="docker compose -f docker-compose.prod.yml --env-file .env.prod"

$DC logs -f --tail=100 "$@"
