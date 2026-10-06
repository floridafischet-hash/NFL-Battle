#!/usr/bin/env bash
# End-to-end acceptance test: starts a FRESH stack (separate compose project, no demo data),
# runs the Playwright suite (frontend/e2e) against it and removes it again.
#   ./scripts/e2e.sh                 (KEEP=1 keeps the stack running afterwards)
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT="${E2E_PROJECT:-nbb-e2e}"
PORT="${E2E_PORT:-8090}"
ENV_FILE="$(mktemp)"
rand() { head -c 4096 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | cut -c1-"$1"; }
ADMIN_PASSWORD="$(rand 16)"
cat > "$ENV_FILE" <<ENV
APP_ENV=production
PUBLIC_URL=http://localhost:${PORT}
HTTP_PORT=${PORT}
HTTP_BIND=127.0.0.1
POSTGRES_PASSWORD=$(rand 24)
SECRET_KEY=$(rand 48)
ADMIN_PASSWORD=${ADMIN_PASSWORD}
SEED_DEMO_DATA=false
DEMO_USER_PASSWORD=$(rand 10)
AGENT_RESULT_MIN_MINUTES_AFTER_KICKOFF=0
ENV
COMPOSE=(docker compose -p "$PROJECT" --env-file "$ENV_FILE")
cleanup() {
  if [ "${KEEP:-0}" != "1" ]; then "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true; fi
  rm -f "$ENV_FILE"
}
trap cleanup EXIT

if [ "${E2E_NO_BUILD:-0}" = "1" ]; then "${COMPOSE[@]}" up -d --no-build; else "${COMPOSE[@]}" up -d --build; fi
echo "Warte auf http://localhost:${PORT} …"
for _ in $(seq 1 120); do
  curl -fsS "http://localhost:${PORT}/api/public/ready" >/dev/null 2>&1 && curl -fsS "http://localhost:${PORT}/login" >/dev/null 2>&1 && break
  sleep 2
done

cd frontend
E2E_BASE_URL="http://localhost:${PORT}" E2E_ADMIN_PASSWORD="$ADMIN_PASSWORD" npx playwright test "$@"
