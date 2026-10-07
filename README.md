# 🏈 NFL Bracket Battle

Privates NFL-Playoff-Tippspiel für Freunde: Jeder baut seinen kompletten Playoff-Tippbaum per Klick auf
die Teamlogos, tippt optional den Endstand, chattet live mit den anderen. Ein NFL Bot kommentiert
Ergebnisse, Punkte und Rangliste. Ergebnisse sucht **ChatGPT** nach Spielende automatisch (OpenAI API
mit Websuche, mehrfach geprüft) – oder sie werden im Adminbereich eingetragen.

![Dashboard](docs/screenshots/dashboard.jpg)

| Mein Bracket | Bracket-Vergleich | Hall of Fame |
|---|---|---|
| ![Bracket](docs/screenshots/bracket.jpg) | ![Vergleich](docs/screenshots/compare.jpg) | ![Hall of Fame](docs/screenshots/hall-of-fame.jpg) |

| Admin: Drag & Drop Bracket-Setup | Smartphone |
|---|---|
| ![Admin](docs/screenshots/admin-setup.jpg) | ![Mobil](docs/screenshots/mobile.jpg) |

---

## Inhalt

1. [Funktionen](#funktionen)
2. [Architektur](#architektur)
3. [Voraussetzungen](#voraussetzungen)
4. [Installation (Schnellstart)](#installation-schnellstart)
5. [Konfiguration (.env)](#konfiguration-env)
6. [Produktion mit HTTPS](#produktion-mit-https-traefik--lets-encrypt)
7. [Benutzer & Login](#benutzer--login)
8. [Saison durchspielen (Admin)](#eine-saison-durchspielen-admin)
9. [Datenbank, Migrationen & Seed-Daten](#datenbank-migrationen--seed-daten)
10. [ChatGPT-Ergebnisse](#chatgpt-ergebnisse)
11. [Teamlogos & Hintergrund austauschen](#teamlogos--hintergrund-austauschen)
12. [Backup & Restore](#backup--restore)
13. [Update](#update)
14. [Tests](#tests)
15. [Lokale Entwicklung](#lokale-entwicklung)
16. [Kubernetes](#kubernetes)
17. [Troubleshooting](#troubleshooting)
18. [Projektstatus](#projektstatus)

---

## Funktionen

- **Grafischer Playoff-Bracket**: Wild Card → Divisional → Conference → Super Bowl → Champion,
  mit echtem **NFL-Reseeding**, dynamischen Verbindungslinien, Siegeranimationen und
  hervorgehobenem Super Bowl. Sieger rücken per Klick automatisch weiter.
- **Endstand-Tipps** (optional pro Saison), **konfigurierbares Punktesystem** (Sieger, exakter
  Endstand, Super-Bowl-Bonus), saubere Neuberechnung ohne Doppelvergabe.
- **Tipp-Lock** pro Spiel (OPEN/LOCKED/FINAL/VOID), automatisch zur Deadline; danach
  **Änderungsanträge**, die ein Admin genehmigt oder ablehnt.
- **Dashboard** im Sport-TV-Look: großes Bracket, nächstes Spiel mit Countdown, Live-Chat,
  persönliche Statistik, Rangliste, letzte Ergebnisse.
- **Alle Brackets & Vergleich** (Unterschiede farbig, Community-Verteilung) – mit Schutz gegen
  Abschreiben: fremde Tipps erst nach dem Tipp-Lock.
- **Live-Chat** (WebSocket) mit Emojis und Bildern; **NFL Bot** postet Paarungen, Kickoff,
  Halbzeit, Final Score mit Punkten, neue Rangliste, offene Tipps, nächste Runde und den Champion.
- **Statistiken** (Trefferquote, Serien, Runden, Saisonvergleich, Duell mit Freunden) und
  **Hall of Fame** mit ewiger Tabelle.
- **Adminbereich**: Benutzer (anlegen, Passwort, Rolle, sperren), Saisons & Punkte, Teams & Logos,
  **Drag-&-Drop-Bracket-Setup**, Spielsteuerung, Ergebnisse, Anträge, ChatGPT-Status, Audit-Log.
- **ChatGPT-Ergebnis-Agent** im Backend: sucht Endergebnisse auf vertrauenswürdigen Sportseiten, prüft
  Quellen (nur wirklich besuchte Seiten, mind. zwei übereinstimmende), Review-Workflow für Zweifelsfälle.
- **Audit-Log** aller kritischen Aktionen (append-only).
- Responsive: Desktop zuerst, Tablet und Smartphone mit Mobile-Menü und scrollbarem Bracket.

## Architektur

```
Browser ──HTTPS──▶ Traefik (Let's Encrypt) ──▶ Nginx ─┬─ /            → Frontend (Next.js)
                                                       └─ /api /ws /media → Backend (FastAPI)
                                                                              │
                                       OpenAI API (ChatGPT + Websuche) ◀── Ergebnis-Agent
                                                                              ▼
                                                                         PostgreSQL 16
```

| Teil | Technik |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, TanStack Query, dnd-kit |
| Backend | FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic 2, psycopg 3 |
| Datenbank | PostgreSQL 16 |
| Realtime | WebSockets + PostgreSQL LISTEN/NOTIFY (skalierbar ohne Redis) |
| Login | eingebaute Benutzerverwaltung (Benutzername/Passwort, PBKDF2, signierte Tokens) |
| Deployment | Docker Compose, Nginx, Traefik + Let's Encrypt |

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (Datenmodell, Rollen, Bracket- und Punktelogik) ·
[docs/API.md](docs/API.md) · [docs/CHATGPT.md](docs/CHATGPT.md) · [docs/DECISIONS.md](docs/DECISIONS.md)

```
backend/    FastAPI-App (app/), Migrationen (alembic/), Tests (tests/)
frontend/   Next.js-App (src/), Teamlogos & Hintergrund (public/), Playwright-Tests (e2e/)
nginx/      Reverse-Proxy-Konfiguration
scripts/    generate-secrets, backup, restore, update, e2e, Logo-/Hintergrund-Generatoren
docs/       Architektur, API, ChatGPT-Agent, Entscheidungen, Screenshots
```

## Voraussetzungen

- Linux-Server (oder Mac/Windows mit Docker Desktop), 2 CPU, 2 GB RAM, ~3 GB Platz
- **Docker Engine 24+** und **Docker Compose v2.24+** (`docker compose version`)
- Für HTTPS: eine Domain, deren DNS auf den Server zeigt, Ports 80 und 443 offen

## Installation (Schnellstart)

```bash
git clone <repo-url> nfl-bracket-battle
cd nfl-bracket-battle
cp .env.example .env
./scripts/generate-secrets.sh      # empfohlen: setzt starke Zufalls-Passwörter in .env
docker compose up -d
```

Danach ist die App unter **http://localhost:8080** (bzw. `http://<server>:8080`) erreichbar.
Der erste Start baut die Images (einige Minuten), führt die Migrationen aus und legt Teams,
Admin und – mit `SEED_DEMO_DATA=true` – ein komplettes Demo-Dashboard an.

**Zugangsdaten:**
- mit `generate-secrets.sh`: werden am Ende ausgegeben (und stehen in `.env`)
- ohne (Platzhalter `CHANGE_ME`): werden beim ersten Start zufällig erzeugt und angezeigt:
  ```bash
  docker compose logs migrate
  # Initialer Admin: Benutzername 'admin', Passwort '…'
  # Demo-Benutzer (bitte Passwörter weitergeben, danach ändern lassen):
  #   florian: …   dennis: …   (jeder Benutzer bekommt ein eigenes Passwort)
  ```

Status prüfen: `docker compose ps` – alle Dienste sollten `healthy` sein (`migrate` ist ein
einmaliger Job und steht danach auf `exited (0)`).

## Konfiguration (.env)

| Variable | Standard | Beschreibung |
|---|---|---|
| `PUBLIC_URL` | `http://localhost:8080` | Öffentliche Adresse (für Links/Webhooks) |
| `HTTP_PORT` / `HTTP_BIND` | `8080` / `0.0.0.0` | Port und Bind-Adresse von Nginx (ohne Traefik) |
| `APP_TIMEZONE` | `Europe/Berlin` | Zeitzone für Bot-Nachrichten |
| `POSTGRES_DB/USER/PASSWORD` | `nfl` / `nfl` / – | Datenbank (Passwort nur Buchstaben/Ziffern; wird beim ersten Start festgelegt) |
| `SECRET_KEY` | – | Signatur der Login-Tokens (Platzhalter ⇒ automatisch erzeugt in `/data/.secret_key`) |
| `TOKEN_TTL_DAYS` | `30` | wie lange ein Login gültig bleibt |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_DISPLAY_NAME` | `admin` / – / `Admin` | erster Admin (nur beim allerersten Start) |
| `SEED_DEMO_DATA` | `true` | Demo-Saisons + Demo-Benutzer anlegen, solange noch keine Saison existiert |
| `DEMO_USER_PASSWORD` | – | optional gemeinsames Passwort der Demo-Benutzer (sonst bekommt jeder ein eigenes) |
| `MAX_UPLOAD_MB` | `5` | max. Bildgröße (Chat, Avatar, Logos) |
| `OPENAI_API_KEY` | leer | **geheim** – OpenAI-API-Key für den ChatGPT-Ergebnis-Agenten (nur in `.env`, nie ins Git); leer = Agent aus |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Modell mit Websuche |
| `RESULT_AGENT_MAX_CALLS_PER_DAY` | `40` | Kostenbremse für OpenAI-Abfragen |
| `AGENT_TRUSTED_DOMAINS` | nfl.com, espn.com, … | Seiten, auf denen ChatGPT sucht und die als Quelle zählen |
| `AGENT_MIN_CONFIRMATIONS` | `2` | übereinstimmende Quellen verschiedener Seiten, bevor automatisch gewertet wird |
| `AGENT_RESULT_MIN_MINUTES_AFTER_KICKOFF` | `60` | Ergebnisse frühestens so lange nach Kickoff |
| `REMINDER_HOURS_BEFORE_LOCK` | `24` | NFL Bot erinnert an fehlende Tipps |
| `DOMAIN` / `ACME_EMAIL` | – | nur für HTTPS mit Traefik |

Änderungen an `.env` übernehmen: `docker compose up -d` (Container werden neu erstellt).
`.env` enthält Secrets – niemals committen (steht in `.gitignore`).

## Produktion mit HTTPS (Traefik + Let's Encrypt)

1. DNS-Eintrag (A/AAAA) der Domain auf den Server, Ports 80/443 freigeben.
2. In `.env`: `DOMAIN=tippspiel.example.de`, `ACME_EMAIL=du@example.de`,
   `PUBLIC_URL=https://tippspiel.example.de`.
3. Starten:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```
Traefik holt das Zertifikat automatisch, leitet HTTP auf HTTPS um und setzt HSTS. Nginx ist dann
nicht mehr direkt erreichbar. Läuft bereits ein anderer Reverse-Proxy auf dem Server, lass das
Overlay weg, setze `HTTP_BIND=127.0.0.1` und leite deinen Proxy auf `127.0.0.1:${HTTP_PORT}` weiter
(WebSocket-Upgrade für `/ws` erlauben).

## Benutzer & Login

Die App hat eine **eigene, einfache Benutzerverwaltung** (kein Keycloak nötig):

- **Admin → Benutzer → „Benutzer anlegen“**: Benutzername, Anzeigename, Passwort, Rolle (Spieler/Admin).
- Admins können Passwörter zurücksetzen, Rollen ändern und Benutzer sperren/aktivieren (wirkt sofort).
- Jeder Benutzer kann im **Profil** Anzeigename, Avatar und Passwort ändern.
- Kommandozeile (z. B. wenn man sich ausgesperrt hat):
  `docker compose exec backend python -m app.cli set-password <benutzer> <passwort>` ·
  `… create-admin <benutzer> <passwort>` · `… list-users`
- Passwörter werden nur gehasht gespeichert (PBKDF2-SHA256), der Login ist gegen Durchprobieren
  rate-limitiert.

Rollen: **USER** (Spieler) und **ADMIN** (Verwaltung). Es gibt keinen Maschinen-Zugang von außen – der
ChatGPT-Ergebnis-Agent läuft im Backend.

## Eine Saison durchspielen (Admin)

1. **Admin → Saisons & Punkte**: Saison anlegen (z. B. `2026/2027`), Punktesystem festlegen.
2. **Admin → Bracket-Setup**: Teams per **Drag & Drop** (oder Auswahlliste) auf die Seeds 1–7 je
   Conference ziehen → *Speichern* → **„Wild Card erzeugen“** (2 vs 7, 3 vs 6, 4 vs 5; Seed 1 hat Bye).
   Alternativ Teams direkt in die Match-Slots ziehen und *„Paarungen veröffentlichen“*.
3. **Admin → Saisons**: Saison **aktivieren**.
4. **Admin → Spiele**: Kickoff-Zeiten setzen (Tipp-Lock folgt automatisch; Minuten vor Kickoff
   konfigurierbar).
5. Spieler tippen unter **Mein Bracket** und geben ab.
6. Ergebnisse: automatisch per ChatGPT (**Admin → ChatGPT**, „Jetzt prüfen“ startet sofort) oder
   **Admin → Spiele → „Ergebnis eintragen“**. Danach laufen
   automatisch: Punkte → Rangliste → NFL Bot → **nächste Runde** (inkl. Reseeding) → Benachrichtigungen.
7. Nach dem Super Bowl wird die Saison abgeschlossen und in die **Hall of Fame** übernommen.

Korrekturen: *„Ergebnis korrigieren“* (Punkte werden neu berechnet) oder *„Ergebnis zurücksetzen“*.
Nach Änderungen am Punktesystem: **Saisons → „Punkte neu berechnen“**.

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

## ChatGPT-Ergebnisse

Kurzfassung (Details: **[docs/CHATGPT.md](docs/CHATGPT.md)**):

1. API-Key auf <https://platform.openai.com/api-keys> erstellen (eigenes Projekt mit Budget-Limit).
2. **Nur auf dem Server** in die `.env` eintragen: `OPENAI_API_KEY=sk-…` → `docker compose up -d backend`.
3. Admin → **ChatGPT** → „Verbindung testen“.

Ab dann sucht das Backend nach jedem Spiel (Standard: 200 Minuten nach Kickoff, danach alle 20 Minuten)
das Endergebnis über die OpenAI API mit Websuche – nur auf den Seiten aus `AGENT_TRUSTED_DOMAINS`.
Gezählt werden nur Quellen, die die Websuche wirklich besucht hat; erst wenn zwei verschiedene Seiten
denselben Spielstand zeigen, wird gewertet. Unklare Fälle landen als „Prüfung erforderlich“ beim Admin,
gewertete Spiele werden nie automatisch überschrieben. Ohne Key trägst du Ergebnisse unter
**Admin → Spiele** ein.

## Teamlogos & Hintergrund austauschen

- Jedes Team hat eine `logo_url`. Standardmäßig zeigen sie auf neutrale, generierte Wappen
  (`frontend/public/logos/<KÜRZEL>.svg`) – **keine geschützten NFL-Logos** im Repository.
- Eigene Logos: **Admin → Teams → Team öffnen → Logo hochladen** (PNG/JPEG/WebP; landet im
  Datenvolume und ist im Backup enthalten) oder eine URL eintragen (`/…` oder `https://…`).
- Alternativ Dateien in `frontend/public/logos/` ersetzen (gleicher Name) und das Frontend neu bauen.
- Stadion-Hintergrund: `frontend/public/stadium.jpg` ersetzen (dunkles Bild, ≥ 2400×1350).
- Wappen und Hintergrund neu generieren: `python scripts/generate_team_logos.py`,
  `python scripts/generate_stadium.py` (benötigt `fonttools`, `numpy`, `pillow`).

## Backup & Restore

**Was wird gesichert?**

| Inhalt | Ort | im Backup |
|---|---|---|
| Datenbank (Benutzer, Tipps, Ergebnisse, Chat, Audit …) | Volume `db-data` | `database.dump` (pg_dump) |
| Uploads (Chat-Bilder, Avatare, hochgeladene Teamlogos), generierter `SECRET_KEY` | Volume `app-data` | `app-data.tar.gz` |
| Konfiguration (`.env`, Compose-Dateien, Nginx), Standard-Logos | Projektordner | `config.tar.gz` |

```bash
./scripts/backup.sh                    # → backups/<datum-uhrzeit>/, behält die letzten 14 (BACKUP_KEEP)
./scripts/restore.sh backups/20270210-031500
```

Automatisch jede Nacht (crontab des Server-Users):
```cron
15 3 * * * cd /opt/nfl-bracket-battle && ./scripts/backup.sh >> backups/backup.log 2>&1
```
Backups zusätzlich auf einen anderen Rechner/Speicher kopieren (z. B. `rsync`, restic, NAS).
`config.tar.gz` enthält `.env` mit Secrets – entsprechend geschützt aufbewahren.

## Update

```bash
./scripts/update.sh            # Backup → git pull → Images bauen → Neustart (Migrationen automatisch)
PROD=1 ./scripts/update.sh     # mit HTTPS-Overlay
```

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

## Troubleshooting

| Problem | Lösung |
|---|---|
| Admin-/Demo-Passwort unbekannt | Beim ersten Start in `docker compose logs migrate`. Jederzeit neu setzen: `docker compose exec backend python -m app.cli set-password admin NeuesPasswort` (weitere Befehle: `create-admin`, `list-users`). |
| `set POSTGRES_PASSWORD in .env` | `.env` fehlt → `cp .env.example .env` |
| `password authentication failed` nach Änderung von `POSTGRES_PASSWORD` | Das Passwort wird beim ersten Start festgelegt. Altes Passwort zurück in `.env` oder in der DB ändern: `docker compose exec db psql -U nfl -c "ALTER USER nfl PASSWORD 'neu'"` |
| Seite lädt, aber „Offline“ statt „Live“ | Reverse-Proxy muss WebSocket-Upgrade für `/ws` durchreichen (siehe `nginx/nginx.conf`). |
| Alle nach Neustart abgemeldet | `SECRET_KEY` geändert oder Volume `app-data` gelöscht – fest in `.env` setzen. |
| Let's Encrypt schlägt fehl | DNS zeigt nicht auf den Server, Port 80 blockiert oder Rate-Limit von Let's Encrypt; `docker compose logs traefik`. |
| Port 8080 belegt | `HTTP_PORT=8090` in `.env` |
| ChatGPT trägt kein Ergebnis ein | Admin → ChatGPT: Status („kein API-Key“?), „Verbindung testen“, letzter Lauf und Fehler prüfen; `REVIEW_REQUIRED`-Meldungen dort übernehmen. Tageslimit (`RESULT_AGENT_MAX_CALLS_PER_DAY`) erreicht? |
| Spiel lässt sich nicht tippen | Spiel ist gesperrt (Deadline) → im Spiel „Änderung beantragen“; oder Paarung steht noch nicht fest (Vorrunde tippen). |
| Ergebniskorrektur wird abgelehnt (409) | Das Folgespiel ist bereits gesperrt/gewertet – zuerst dessen Ergebnis zurücksetzen bzw. Paarung im Bracket-Setup anpassen. |
| Logs ansehen | `docker compose logs -f backend` (bzw. `frontend`, `nginx`, `db`) |

## Projektstatus

Alle Phasen der Aufgabenliste sind umgesetzt und getestet (88 Backend-Tests, 5 Frontend-Unit-Tests,
15 End-to-End-Tests inkl. kompletter Saison). Umgesetzte Abweichungen und Grenzen:

- **Keycloak wurde auf Wunsch durch eine eingebaute Benutzerverwaltung ersetzt** (siehe
  [DECISIONS.md](docs/DECISIONS.md)).
- **Der OpenClaw-Zugang wurde auf Wunsch entfernt**; Ergebnisse sucht jetzt der ChatGPT-Agent im
  Backend (OpenAI-API-Key nötig, sonst manuelle Eingabe) – siehe [CHATGPT.md](docs/CHATGPT.md).
- Benachrichtigungen erscheinen in der App (Glocke, Chat, Toasts); E-Mail/Push ist nicht umgesetzt.
- Mitgelieferte Teamlogos sind neutrale Wappen in Teamfarben; offizielle Logos können hochgeladen
  oder per Datei ausgetauscht werden.
