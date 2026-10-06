#!/usr/bin/env bash
# Replace every CHANGE_ME placeholder in .env with a strong random value.
# Run BEFORE the first start (the database password is fixed at first start).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env

rand() { head -c 4096 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | cut -c1-"$1"; }

declare -A LENGTHS=( [POSTGRES_PASSWORD]=32 [SECRET_KEY]=64 [ADMIN_PASSWORD]=14 [DEMO_USER_PASSWORD]=10 )
for key in "${!LENGTHS[@]}"; do
  if grep -qE "^${key}=CHANGE_ME" .env; then
    value="$(rand "${LENGTHS[$key]}")"
    sed -i.bak "s|^${key}=CHANGE_ME.*|${key}=${value}|" .env && rm -f .env.bak
    echo "  ${key} gesetzt"
  fi
done
chmod 600 .env
echo
echo "Fertig. Admin-Login: $(grep '^ADMIN_USERNAME=' .env | cut -d= -f2) / $(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2)"
echo "Demo-Passwort:      $(grep '^DEMO_USER_PASSWORD=' .env | cut -d= -f2)"
