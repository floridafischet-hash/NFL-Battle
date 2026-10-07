#!/usr/bin/env bash
# Backup: PostgreSQL (custom format dump), uploads/team logos + generated secret (app-data volume),
# configuration (.env, nginx). Usage: ./scripts/backup.sh [target-dir]   (default: ./backups)
# Keeps the last BACKUP_KEEP (default 14) backups. Run e.g. nightly via cron:
#   15 3 * * * cd /opt/nfl-bracket-battle && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
TARGET="${1:-./backups}"
KEEP="${BACKUP_KEEP:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DIR="${TARGET}/${STAMP}"
mkdir -p "$DIR"
set -a; [ -f .env ] && . ./.env; set +a

echo "→ Datenbank sichern"
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-nfl}" -d "${POSTGRES_DB:-nfl}" -Fc > "${DIR}/database.dump"

echo "→ Uploads, Teamlogos und App-Daten sichern"
docker compose run --rm --no-deps -T --user 0 -v "$(cd "${DIR}" && pwd):/backup" --entrypoint sh backend \
  -c "tar -czf /backup/app-data.tar.gz -C /data ."

echo "→ Konfiguration sichern"
tar -czf "${DIR}/config.tar.gz" .env docker-compose.yml docker-compose.prod.yml nginx frontend/public/logos 2>/dev/null || true
chmod 600 "${DIR}"/*

echo "→ Alte Backups aufräumen (behalte ${KEEP})"
ls -1dt "${TARGET}"/*/ 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -rf

echo "Backup fertig: ${DIR}"
ls -lh "${DIR}"
