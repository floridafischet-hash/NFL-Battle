# Entwicklung, Tests & Kubernetes

## Tests

| Bereich | Befehl | Inhalt |
|---|---|---|
| Backend (Unit + API, echte PostgreSQL) | `cd backend && pytest` | Login, Bracket-Logik, Weiterrücken, Reseeding, Tipp-Lock, Änderungsanträge, Punkte, exakter Score, Super-Bowl-Bonus, Ergebniskorrektur, Neuberechnung, Admin-Rechte, ChatGPT-Agent (OpenAI gemockt) inkl. Quellenprüfung, Login-Sperre, Uploads, Chat & WebSocket, Audit-Log |
| Frontend (Unit) | `cd frontend && npm test` | Formatierung, Bracket-Hilfsfunktionen |
| End-to-End / Abnahme | `./scripts/e2e.sh` | startet einen **frischen** Stack ohne Demo-Daten und spielt eine komplette Saison durch (UI + ChatGPT-Agent gegen einen lokalen OpenAI-Mock), inkl. Smartphone-Test |

Backend-Tests brauchen eine PostgreSQL-Datenbank:
```bash
docker run -d --name nbb-testdb -p 5433:5432 -e POSTGRES_PASSWORD=test -e POSTGRES_DB=nfl_test postgres:16-alpine
cd backend && pip install -r requirements-dev.txt
TEST_DATABASE_URL="postgresql+psycopg://postgres:test@localhost:5433/nfl_test" pytest
```

## Lokale Entwicklung

```bash
# Datenbank
docker run -d --name nbb-devdb -p 5432:5432 -e POSTGRES_USER=nfl -e POSTGRES_PASSWORD=nfl -e POSTGRES_DB=nfl postgres:16-alpine

# Backend (http://localhost:8000, API-Doku unter /api/docs – nur außerhalb von APP_ENV=production)
cd backend
python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://nfl:nfl@localhost:5432/nfl DATA_DIR=./.data UPLOAD_DIR=./.data/uploads \
       APP_ENV=development ADMIN_PASSWORD="$(openssl rand -base64 12)" SEED_DEMO_DATA=true
echo "Admin-Passwort: $ADMIN_PASSWORD"
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload --port 8000

# Frontend (http://localhost:3000, leitet /api an das Backend weiter)
cd frontend && npm install
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws npm run dev
```

Code-Qualität: `ruff check . && ruff format --check .` (Backend), `npm run typecheck` (Frontend).

## Kubernetes

Die Anwendung ist so gebaut, dass sie ohne Umbau auf Kubernetes läuft:
- `backend` und `frontend` sind zustandslos → `Deployment`s mit beliebig vielen Replikas
  (Realtime über PostgreSQL, Scheduler mit Advisory-Lock).
- `migrate` → `Job` bzw. `initContainer` mit `alembic upgrade head && python -m app.seed`.
- `app-data` (`/data`) → `PersistentVolumeClaim` (ReadWriteMany bei mehreren Backend-Replikas oder
  `SECRET_KEY` fest setzen und Uploads auf ein gemeinsames Volume legen).
- Nginx-Routing → `Ingress` (Pfade `/api`, `/ws`, `/media` → backend, `/` → frontend; WebSocket-Timeouts erhöhen).
- Health-Endpunkte: `/api/public/health` (liveness), `/api/public/ready` (readiness), Frontend `/login`.

## Datenbank, Migrationen & Seed-Daten

- Das Schema wird ausschließlich über **Alembic** verwaltet (`backend/alembic/versions`).
- Der Dienst `migrate` führt bei jedem Start `alembic upgrade head` und danach `python -m app.seed` aus:
  - 32 NFL-Teams (Namen, Kürzel, Conference, Division, Farben, Logo-URL) – fehlende werden ergänzt
  - initialer Admin (falls nicht vorhanden)
  - Demo-Daten (falls `SEED_DEMO_DATA=true` und noch keine Saison existiert): Benutzer Florian, Dennis,
    Stefan, Marcel, Lisa, Kevin, Tobi; zwei abgeschlossene Saisons (Hall of Fame) und eine laufende
    Saison mit Ergebnissen, Tipps, Chat und offenen Spielen in den nächsten Tagen.
- Manuell:
  ```bash
  docker compose run --rm migrate alembic upgrade head      # Migrationen
  docker compose run --rm migrate python -m app.seed --demo # Demo-Daten erzwingen (nur leere DB)
  docker compose exec db psql -U nfl -d nfl                 # SQL-Konsole
  ```
- Demo-Daten entfernen = Neustart mit leerer DB: `docker compose down -v` (**löscht alle Daten!**),
  `SEED_DEMO_DATA=false` setzen, `docker compose up -d`.
