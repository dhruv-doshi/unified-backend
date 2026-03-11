#!/usr/bin/env bash
# run_local.sh — Start all backend services for local development
# Usage: ./run_local.sh [--no-worker] [--no-migrate]
set -eo pipefail   # Note: no -u so empty arrays don't blow up

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERR]${NC}   $*"; exit 1; }

# ── Flags ─────────────────────────────────────────────────────────────────────
RUN_WORKER=true
RUN_MIGRATE=true
for arg in "$@"; do
  case $arg in
    --no-worker)  RUN_WORKER=false ;;
    --no-migrate) RUN_MIGRATE=false ;;
  esac
done

# ── Cleanup on exit ───────────────────────────────────────────────────────────
PIDS=()
cleanup() {
  echo ""
  info "Shutting down..."
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  success "All processes stopped."
}
trap cleanup EXIT INT TERM

# ── Venv ─────────────────────────────────────────────────────────────────────
if [[ ! -f "venv/bin/activate" ]]; then
  error "venv not found. Run: python3.11 -m venv venv && source venv/bin/activate && pip install -e '.[dev]'"
fi
source venv/bin/activate
success "venv activated ($(python --version))"

# ── .env — parse safely (handles quoted values with spaces) ──────────────────
if [[ ! -f ".env" ]]; then
  error ".env not found. Copy .env.example to .env and fill in your values."
fi
while IFS= read -r line || [[ -n "$line" ]]; do
  # Skip comments and blank lines
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue
  # Strip inline comments and export
  line="${line%%#*}"
  if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
    key="${BASH_REMATCH[1]}"
    val="${BASH_REMATCH[2]}"
    # Strip surrounding quotes if present
    val="${val#\"}" ; val="${val%\"}"
    val="${val#\'}" ; val="${val%\'}"
    export "$key"="$val"
  fi
done < .env

# ── PostgreSQL ────────────────────────────────────────────────────────────────
info "Checking PostgreSQL..."
PG_HOST="${DATABASE_URL#*@}"; PG_HOST="${PG_HOST%%:*}"
PG_PORT="${DATABASE_URL##*:}"; PG_PORT="${PG_PORT%%/*}"
PG_DB="${DATABASE_URL##*/}"

if ! pg_isready -h "$PG_HOST" -p "$PG_PORT" -q 2>/dev/null; then
  info "PostgreSQL not running — starting via Docker..."
  if ! command -v docker &>/dev/null; then
    error "PostgreSQL is not running and Docker is not available. Start PostgreSQL manually."
  fi
  if docker ps -a --format '{{.Names}}' | grep -q '^unified-pg$'; then
    docker start unified-pg >/dev/null
  else
    docker run -d --name unified-pg \
      -e POSTGRES_USER=postgres \
      -e POSTGRES_PASSWORD=postgres \
      -e POSTGRES_DB="$PG_DB" \
      -p "${PG_PORT}:5432" \
      postgres:16-alpine >/dev/null
  fi
  info "Waiting for PostgreSQL to be ready..."
  for i in {1..20}; do
    pg_isready -h "$PG_HOST" -p "$PG_PORT" -q 2>/dev/null && break
    sleep 1
  done
  pg_isready -h "$PG_HOST" -p "$PG_PORT" -q 2>/dev/null || error "PostgreSQL failed to start."
fi
success "PostgreSQL is ready (${PG_HOST}:${PG_PORT})"

# Create DB if it doesn't exist
if ! psql -h "$PG_HOST" -p "$PG_PORT" -U postgres -lqt 2>/dev/null | cut -d\| -f1 | grep -qw "$PG_DB"; then
  info "Creating database '${PG_DB}'..."
  createdb -h "$PG_HOST" -p "$PG_PORT" -U postgres "$PG_DB"
  success "Database '${PG_DB}' created"
else
  success "Database '${PG_DB}' exists"
fi

# ── Redis ─────────────────────────────────────────────────────────────────────
info "Checking Redis..."
REDIS_HOST="${REDIS_URL#redis://}"; REDIS_HOST="${REDIS_HOST%%:*}"
REDIS_PORT="${REDIS_URL##*:}"; REDIS_PORT="${REDIS_PORT%%/*}"

if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping &>/dev/null; then
  info "Redis not running — starting via Docker..."
  if ! command -v docker &>/dev/null; then
    error "Redis is not running and Docker is not available. Start Redis manually."
  fi
  if docker ps -a --format '{{.Names}}' | grep -q '^unified-redis$'; then
    docker start unified-redis >/dev/null
  else
    docker run -d --name unified-redis \
      -p "${REDIS_PORT}:6379" \
      redis:7-alpine >/dev/null
  fi
  info "Waiting for Redis to be ready..."
  for i in {1..10}; do
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping &>/dev/null && break
    sleep 1
  done
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping &>/dev/null || error "Redis failed to start."
fi
success "Redis is ready (${REDIS_HOST}:${REDIS_PORT})"

# ── Alembic migrations ────────────────────────────────────────────────────────
if [[ "$RUN_MIGRATE" == true ]]; then
  info "Running database migrations..."
  PYTHONPATH=. alembic upgrade head
  success "Migrations applied"

  info "Seeding admin and test accounts..."
  PYTHONPATH=. python scripts/seed_accounts.py
  success "Accounts seeded"
fi

# ── Logs directory ────────────────────────────────────────────────────────────
mkdir -p logs

# ── Celery worker ─────────────────────────────────────────────────────────────
if [[ "$RUN_WORKER" == true ]]; then
  info "Starting Celery worker..."
  PYTHONPATH=. celery -A src.workers.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --logfile=logs/celery.log \
    &
  celery_pid=$!
  PIDS+=($celery_pid)
  sleep 1
  success "Celery worker started (PID $celery_pid, logs → logs/celery.log)"
fi

# ── FastAPI ───────────────────────────────────────────────────────────────────
info "Starting FastAPI server..."
PYTHONPATH=. uvicorn src.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --log-level info \
  &
PIDS+=($!)
sleep 2

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Backend running${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  API:     ${CYAN}http://localhost:8000${NC}"
echo -e "  Docs:    ${CYAN}http://localhost:8000/docs${NC}"
echo -e "  Health:  ${CYAN}http://localhost:8000/health${NC}"
[[ "$RUN_WORKER" == true ]] && echo -e "  Worker:  running (logs/celery.log)"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop all services"
echo ""

# ── Wait ──────────────────────────────────────────────────────────────────────
wait
