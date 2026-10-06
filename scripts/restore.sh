#!/usr/bin/env bash
# Restore a backup created by scripts/backup.sh.
#   ./scripts/restore.sh backups/20270210-031500
# Replaces the current database and app data! Configuration (config.tar.gz) is NOT restored
# automatically – extract it manually if needed: tar -xzf <dir>/config.tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="${1:?Backup-Verzeichnis angeben, z. B. backups/20270210-031500}"
[ -f "${DIR}/database.dump" ] || { echo "database.dump fehlt in ${DIR}"; exit 1; }
set -a; [ -f .env ] && . ./.env; set +a

read -r -p "Aktuelle Daten werden überschrieben. Fortfahren? [j/N] " answer
[[ "$answer" =~ ^[jJyY]$ ]] || exit 1

echo "→ Anwendung stoppen"
docker compose stop backend nginx frontend
docker compose up -d db
until docker compose exec -T db pg_isready -U "${POSTGRES_USER:-nfl}" >/dev/null 2>&1; do sleep 1; done

echo "→ Datenbank wiederherstellen"
docker compose exec -T db pg_restore -U "${POSTGRES_USER:-nfl}" -d "${POSTGRES_DB:-nfl}" --clean --if-exists --no-owner < "${DIR}/database.dump"

if [ -f "${DIR}/app-data.tar.gz" ]; then
  echo "→ Uploads/App-Daten wiederherstellen"
  docker compose run --rm --no-deps -T --user 0 -v "$(cd "${DIR}" && pwd):/backup:ro" --entrypoint sh backend \
    -c "rm -rf /data/* /data/.secret_key 2>/dev/null; tar -xzf /backup/app-data.tar.gz -C /data"
fi

echo "→ Anwendung starten (Migrationen laufen automatisch)"
docker compose up -d
echo "Wiederherstellung abgeschlossen."
