#!/usr/bin/env bash
# Update to the latest version: backup, pull code, rebuild images, restart (migrations run automatically).
#   ./scripts/update.sh            (HTTP)
#   PROD=1 ./scripts/update.sh     (with Traefik/HTTPS overlay)
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE=(docker compose)
[ "${PROD:-0}" = "1" ] && COMPOSE+=(-f docker-compose.yml -f docker-compose.prod.yml)

echo "→ Backup vor dem Update"
./scripts/backup.sh
echo "→ Code aktualisieren"
git pull --ff-only
echo "→ Images bauen"
"${COMPOSE[@]}" build --pull
echo "→ Neu starten"
"${COMPOSE[@]}" up -d
"${COMPOSE[@]}" ps
