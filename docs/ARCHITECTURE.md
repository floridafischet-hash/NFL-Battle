# Architektur – NFL Bracket Battle

Dieses Dokument beschreibt Aufbau, Datenmodell, Rollen, API, Bracket-Logik und Punktesystem.
Alle technischen Entscheidungen inkl. Begründung stehen zusätzlich kompakt in
[`DECISIONS.md`](DECISIONS.md).

## 1. Überblick

```
                        Browser (Desktop / Tablet / Smartphone)
                                        │  HTTPS (eine Domain)
                                        ▼
                     ┌───────────────────────────────────────┐
  Produktion:        │ Traefik  (TLS, Let's Encrypt, :80/443)│
                     └───────────────────┬───────────────────┘
                                         ▼
                     ┌───────────────────────────────────────┐
                     │ Nginx  (Pfad-Routing, Rate-Limits,    │
                     │         Security-Header, Caching)     │
                     └──────────┬────────────────────┬───────┘
                             /  │                    │  /api /ws /media
                                ▼                    ▼
                       ┌──────────────┐     ┌──────────────────┐
                       │  frontend    │     │  backend         │
                       │  Next.js     │     │  FastAPI         │
                       │  (standalone)│     │  + WebSocket     │
                       └──────────────┘     │  + Login/Benutzer│
                                            └────────┬─────────┘
                                                     │ SQL + LISTEN/NOTIFY
                                                     ▼
                                            ┌──────────────────┐
                                            │ PostgreSQL 16    │
                                            └──────────────────┘
        Ergebnis-Agent (im Backend) ──HTTPS──▶ OpenAI API (ChatGPT + Websuche)
```

* **Eine Domain, Pfad-Routing.** Frontend (`/`), API (`/api`), WebSocket (`/ws`) und Uploads (`/media`)
  laufen unter derselben Origin. Dadurch entfallen CORS-Probleme und die Konfiguration bleibt minimal.
* **Eingebaute Benutzerverwaltung.** Kein externer Identity-Provider: Admins legen Benutzer mit
  Benutzername und Passwort direkt in der App an (bewusst einfach gehalten, siehe `DECISIONS.md`).
* **Stateless Backend.** Serverseitige Sitzungen gibt es nicht, jede Anfrage trägt ein signiertes
  Access-Token. Realtime-Ereignisse
  laufen über PostgreSQL `LISTEN/NOTIFY` – damit kann das Backend ohne Zusatzdienst (Redis)
  horizontal skaliert werden (Kubernetes-tauglich).
* **Migrationen als eigener Job.** Der Dienst `migrate` führt `alembic upgrade head` und das Seeding
  aus, bevor das Backend startet (in Kubernetes: `Job` bzw. `initContainer`).

## 2. Projektstruktur

```
.
├── backend/                 FastAPI-Anwendung
│   ├── app/
│   │   ├── api/             HTTP-/WebSocket-Router (user, admin, public)
│   │   ├── core/            Konfiguration, Security, Rate-Limits, Logging
│   │   ├── models/          SQLAlchemy-Modelle (= Datenmodell)
│   │   ├── schemas/         Pydantic-Schemas (Ein-/Ausgabe-Validierung)
│   │   ├── services/        Fachlogik: bracket engine, scoring, results, agent (Prüfung), result_agent (ChatGPT), bot, chat, audit …
│   │   ├── realtime/        WebSocket-Hub + PostgreSQL LISTEN/NOTIFY
│   │   ├── seed/            Demo- und Stammdaten (32 NFL-Teams)
│   │   └── main.py
│   ├── alembic/             Datenbankmigrationen
│   └── tests/               pytest (Unit + API gegen echte PostgreSQL)
├── frontend/                Next.js (App Router) + TypeScript + Tailwind CSS
│   ├── src/app/             Seiten (Dashboard, Mein Bracket, Spiele, …, Admin)
│   ├── src/components/      UI-Bausteine (Bracket, MatchCard, Chat, …)
│   ├── src/lib/             API-Client, Auth (Login/Token), Realtime, Hooks
│   ├── public/logos/        neutrale Ersatz-Wappen (offizielle Logos kommen per logo_url)
│   └── e2e/                 Playwright UI- und Abnahmetests
├── nginx/                   Reverse-Proxy-Konfiguration
├── scripts/                 Backup, Restore, Secrets, Logos, Update
├── docs/                    Architektur, API, ChatGPT-Agent, Entscheidungen
├── docker-compose.yml       Komplettes System (lokal/Server, HTTP)
├── docker-compose.prod.yml  Overlay: Traefik + HTTPS (Let's Encrypt)
└── .env.example             Alle Konfigurationswerte (keine echten Secrets)
```

## 3. Rollenmodell & Login

| Rolle   | Wie                                   | Darf                                                                                  |
|---------|---------------------------------------|---------------------------------------------------------------------------------------|
| `USER`  | Benutzerkonto (Name + Passwort)       | eigenes Bracket tippen, Änderungen beantragen, Chat, Ranglisten, Statistiken, fremde Brackets (nur aufgedeckte Spiele) |
| `ADMIN` | Benutzerkonto mit Rolle ADMIN         | alles von USER + `/api/admin/*` (Benutzer, Saisons, Teams, Spiele, Ergebnisse, Anträge, Punkte, ChatGPT-Agent, Audit) |

* **Login:** `POST /api/auth/login` mit Benutzername + Passwort ⇒ signiertes Access-Token (JWT, HS256,
  Laufzeit `TOKEN_TTL_DAYS`, Standard 30 Tage). Das Frontend sendet es als `Authorization: Bearer`.
* **Passwörter** werden nur als gesalzener PBKDF2-SHA256-Hash gespeichert. Login ist rate-limitiert.
* **Benutzerverwaltung** im Adminbereich: anlegen, Passwort zurücksetzen, sperren/aktivieren,
  Rolle ändern. Jeder Benutzer kann sein eigenes Passwort im Profil ändern.
* Passwortänderung oder Sperre wirken sofort: jedes Token trägt eine `token_version`, die bei
  Passwortänderung erhöht wird; gesperrte Benutzer werden bei jeder Anfrage abgewiesen.
* Beim ersten Start legt das System einen Admin aus `ADMIN_USERNAME`/`ADMIN_PASSWORD` an.
* Es gibt **keinen Maschinen-Zugang** von außen. Der ChatGPT-Ergebnis-Agent läuft im Backend
  (`app/services/result_agent.py`) und handelt intern als Principal „ChatGPT (Modell)“ – im Audit-Log
  als Akteur `AGENT`. Fehlgeschlagene Logins sperren nur das Paar (Konto, IP) für 15 Minuten.

## 4. Datenmodell

Alle Tabellen besitzen Primärschlüssel, Fremdschlüssel und passende Unique-Constraints.
Zeitstempel sind `timestamptz` (UTC). Das Schema wird ausschließlich über Alembic-Migrationen verwaltet.

```
users ─┬─< brackets >── seasons ──< season_teams >── teams
       │      │            │                            │
       │      └─< predictions >── matches ──────────────┘ (home/away/winner)
       │                │          │
       │                │          ├─< result_reports >── agent_runs
       │                │          └─< scores
       ├─< prediction_changes (Änderungsanträge)
       ├─< leaderboards (pro Saison)
       ├─< chat_messages >── system_messages (NFL Bot), uploads
       ├─< notifications
       └─< audit_logs
seasons ──1 hall_of_fame
```

| Tabelle | Zweck | Wichtige Felder / Constraints |
|---|---|---|
| `users` | Benutzerkonten | `username` (unique), `display_name`, `password_hash`, `token_version`, `avatar_url`, `role` (USER/ADMIN), `is_active`, `is_bot` (NFL Bot) |
| `seasons` | Saison inkl. Punktekonfiguration | `name` (`2026/2027`), `year` unique, `status` (DRAFT/ACTIVE/COMPLETED), `winner_points`, `exact_score_points`, `champion_bonus`, `score_tips_enabled`, `lock_minutes_before_kickoff`, `champion_team_id`; partieller Unique-Index: nur eine ACTIVE-Saison |
| `teams` | Stammdaten der Teams | `name`, `short_name`, `abbreviation` unique, `conference`, `division`, `logo_url`, `primary_color`, `secondary_color` |
| `season_teams` | Playoff-Teilnehmer & Seeds je Saison | PK (`season_id`,`team_id`), `conference`, `seed` 1–7, unique (`season_id`,`conference`,`seed`) |
| `matches` | Ein Spiel = ein Bracket-Slot | `slot` (z. B. `AFC-WC-1`, `NFC-DIV-2`, `SB`) unique je Saison, `round`, `conference`, `home_team_id`, `away_team_id`, `kickoff_at`, `lock_at`, `status` (OPEN/LOCKED/FINAL/VOID), Scores, `winner_team_id`, `result_source` |
| `brackets` | Tippbaum eines Benutzers je Saison | unique (`user_id`,`season_id`), `submitted_at` |
| `predictions` | Tipp für einen Slot | unique (`bracket_id`,`match_id`), `winner_team_id`, `winner_score`, `loser_score` |
| `prediction_changes` | Änderungsanträge nach Tipp-Lock | alter/neuer Tipp, `status` (PENDING/APPROVED/REJECTED/CANCELLED), `decided_by`, `decided_at`; partieller Unique-Index: max. ein offener Antrag pro Benutzer & Spiel |
| `scores` | Punkte pro Benutzer & Spiel | unique (`user_id`,`match_id`) ⇒ **keine Doppelvergabe**, `winner_correct`, `exact_correct`, `base_points`, `bonus_points`, `points` |
| `leaderboards` | Materialisierte Rangliste je Saison | PK (`season_id`,`user_id`), `rank`, `previous_rank`, `points`, `correct_winners`, `wrong_picks`, `exact_scores`, `champion_correct` |
| `chat_messages` | Chat-Verlauf | `user_id`, `body`, `upload_id`, `system_message_id`, `deleted_at` |
| `system_messages` | Strukturierte NFL-Bot-Ereignisse | `type`, `payload` (JSONB), `dedupe_key` unique ⇒ keine doppelten Bot-Posts |
| `uploads` | Hochgeladene Dateien (Chat-Bilder, Avatare, Logos) | `kind`, `path`, `content_type`, `size_bytes`, `uploaded_by` |
| `notifications` | Benachrichtigungen (Glocke) | `user_id`, `type`, `title`, `body`, `link`, `read_at` |
| `audit_logs` | Unveränderliches Protokoll | `actor_type`, `actor_user_id`, `actor_label`, `action`, `object_type`, `object_id`, `old_value`, `new_value`, `source`, `ip_address`, `created_at`; DB-Trigger verhindert UPDATE/DELETE |
| `agent_runs` | Jeder Schritt des Ergebnis-Agenten (ChatGPT-Suche `RESEARCH`, Prüfung `RESULT`, Admin-Anstoß `CHECK_REQUEST`) | `agent_label`, `kind`, `status` (inkl. `NO_RESULT`), `request_payload` (Antwort, belegte/verworfene Quellen, Token-Verbrauch), `message`, `match_id` |
| `result_reports` | Gemeldete Ergebnisse inkl. Quelle | `source`, `source_url`, `reported_at`, Scores, `status` (PENDING_CONFIRMATION/APPLIED/REVIEW_REQUIRED/REJECTED/DUPLICATE/SUPERSEDED) |
| `hall_of_fame` | Dauerhafter Saisonabschluss | PK `season_id`, Gewinner, Punkte, Treffer, exakte Scores, Super-Bowl-Tipp, Snapshot der Abschlusstabelle (JSONB) |

## 5. Bracket-Logik (Bracket Engine)

Die Engine (`backend/app/services/bracket_engine.py`) ist reine Python-Logik ohne Datenbank und
vollständig unit-getestet.

### Slots

Jede Saison besitzt genau 13 Spiele (Slots):

| Runde | AFC | NFC |
|---|---|---|
| Wild Card | `AFC-WC-1` (2 vs 7), `AFC-WC-2` (3 vs 6), `AFC-WC-3` (4 vs 5) | analog `NFC-WC-*` |
| Divisional | `AFC-DIV-1` (Seed 1 vs. schlechtester verbliebener Seed), `AFC-DIV-2` (die beiden anderen) | analog |
| Conference | `AFC-CONF` | `NFC-CONF` |
| Super Bowl | `SB` (AFC-Champion vs. NFC-Champion) | |

Seed 1 hat in der Wild Card Round ein Freilos (Bye).

### NFL-Reseeding

Wie in der echten NFL wird nach der Wild Card Round **neu gesetzt**: Seed 1 spielt gegen den
schlechtesten verbliebenen Seed, die beiden anderen Sieger gegeneinander; das besser gesetzte Team
hat Heimrecht. Die Linien im Bracket werden deshalb dynamisch gezeichnet (jedes Team wird mit dem
Spiel verbunden, aus dem es tatsächlich bzw. laut Tipp kommt).

### „Living Bracket“

* Für jeden Slot werden die beiden Teams so bestimmt:
  1. Sind im echten Spiel beide Teams bekannt ⇒ **tatsächliche Paarung**.
  2. Sonst ⇒ abgeleitet aus den *effektiven Siegern* der Vorrunde: tatsächlicher Sieger, falls das
     Vorrundenspiel FINAL ist, sonst der eigene (gültige) Tipp.
* Klickt ein Benutzer auf ein Team, wird es Sieger dieses Slots und rückt automatisch in den
  Folge-Slot vor – bis zum Super Bowl und zum Champion.
* Ändert ein Benutzer einen Tipp, werden nachgelagerte, noch offene Tipps, die dadurch ungültig
  werden, automatisch entfernt (Kaskade).
* Status eines Tipps: `valid` (Team in der Paarung), `pending` (Gegner steht noch nicht fest, das Team
  kann den Slot aber noch erreichen – z. B. der Super-Bowl-Tipp, solange die andere Conference offen
  ist), `invalid` (Team nicht in der Paarung bzw. ausgeschieden). Tipps in Slots mit bereits feststehender echter Paarung
  bleiben erhalten; ist das getippte Team dort nicht (mehr) dabei, wird der Tipp als
  **„ungültig – Team ausgeschieden“** markiert und kann bis zum Lock neu gesetzt werden.
* Tipps sind pro Slot änderbar, solange das Spiel **OPEN** und `lock_at` nicht erreicht ist.

### Tipp-Lock

`gesperrt = status ≠ OPEN  ODER  (lock_at gesetzt UND jetzt ≥ lock_at)`

* `lock_at` = `kickoff_at − lock_minutes_before_kickoff` (Saisoneinstellung) oder manuell gesetzt.
* Ein Scheduler im Backend setzt fällige Spiele auf `LOCKED` und lässt den NFL Bot „Kickoff – Tipps
  gesperrt“ posten. Er läuft mit PostgreSQL-Advisory-Lock, d. h. bei mehreren Replikas nur einmal.
* Admin-Aktionen: öffnen, sperren, wieder öffnen (optional mit neuer Deadline), abschließen
  (Ergebnis setzen), annullieren (VOID).
* Nach dem Lock sind Änderungen nur über **Änderungsanträge** möglich.

### Weiterschaltung der echten Runden

Ist eine Runde einer Conference komplett FINAL, erzeugt das Backend automatisch die Paarungen der
nächsten Runde (inkl. Reseeding), der NFL Bot postet „Nächste Runde“ und alle Benutzer erhalten
eine Benachrichtigung. Wird ein Ergebnis korrigiert und ändert sich dadurch der Sieger, werden
nachgelagerte, noch nicht gesperrte Paarungen neu berechnet; ist ein nachgelagertes Spiel bereits
gesperrt oder gewertet, wird die Korrektur mit `409` abgelehnt (erst nachgelagertes Ergebnis
zurücksetzen).

### Schutz vor Abschreiben

Tipps anderer Benutzer (und die Community-Verteilung „70 % tippen Chiefs“) werden pro Spiel erst
sichtbar, wenn das Spiel gesperrt ist. Vorher sieht man nur, *ob* jemand getippt bzw. sein Bracket
abgegeben hat. Auch abgeleitete Paarungen fremder Brackets werden nur aus bereits aufgedeckten
Tipps berechnet, damit keine verdeckten Tipps durchsickern. Admins sehen alles.

## 6. Punktesystem

Konfigurierbar pro Saison (Adminbereich → Punkte):

| Einstellung | Standard | Bedeutung |
|---|---|---|
| `winner_points` | 1 | richtiger Sieger |
| `exact_score_points` | 3 | exakter Endstand (ersetzt die Siegerpunkte, d. h. max. 3 statt 1) |
| `champion_bonus` | 3 | zusätzlich, wenn der Super-Bowl-Sieger richtig getippt wurde |
| `score_tips_enabled` | true | Endstand-Tipps aktiv |

Ablauf `score_match(match)` (idempotent):

1. Spiel sperren (`SELECT … FOR UPDATE`), bestehende `scores` des Spiels löschen.
2. Für jeden Tipp: Sieger korrekt? ⇒ exakter Score korrekt? ⇒ Punkte; beim Super Bowl + Bonus.
3. `scores` neu schreiben (Unique-Constraint `user_id, match_id` verhindert Doppelvergabe).
4. Rangliste der Saison neu berechnen (`leaderboards`, inkl. `previous_rank` für Trendpfeile).
   Sortierung: Punkte ↓, exakte Ergebnisse ↓, richtige Sieger ↓; Gleichstand teilt den Rang.

`POST /api/admin/seasons/{id}/recalculate` berechnet alle Spiele einer Saison neu (z. B. nach
Änderung der Punktewerte). VOID-Spiele bringen keine Punkte.

## 7. Ergebnisverarbeitung (Admin & ChatGPT)

```
Ergebnis (Admin oder ChatGPT-Agent)
  → Validierung (Match existiert, Teams stimmen, plausibel, schon gewertet?)
  → Match FINAL + Scores speichern
  → Punkte berechnen (score_match) → Rangliste
  → nächste Runde erzeugen (falls Runde komplett)
  → NFL Bot: FINAL-Nachricht mit Punkten & neuer Rangliste
  → Audit-Log, Benachrichtigungen, Realtime-Event
  → Super Bowl? ⇒ Saison COMPLETED + Hall of Fame
```

ChatGPT-spezifisch (siehe [`CHATGPT.md`](CHATGPT.md)): Suche nur auf vertrauenswürdigen Domains,
nur von der Websuche wirklich besuchte Quellen zählen, widersprüchliche Quellen oder abweichende
Meldungen ⇒ `REVIEW_REQUIRED` + Admin-Benachrichtigung, mindestens `AGENT_MIN_CONFIRMATIONS`
(Standard 2) übereinstimmende Seiten.

## 8. API-Struktur

Vollständige Liste: [`API.md`](API.md); interaktiv unter `/api/docs` (OpenAPI, nur außerhalb von Produktion).

| Präfix | Schutz | Inhalt |
|---|---|---|
| `/api/public/*`, `/api/auth/login` | keiner | Health, Konfiguration, Login |
| `/api/me`, `/api/seasons/*`, `/api/matches/*`, `/api/chat/*`, `/api/stats/*`, `/api/hall-of-fame/*`, `/api/notifications/*` | USER oder ADMIN | Spiel-Funktionen |
| `/api/admin/*` | ADMIN | Verwaltung |
| `/ws` | Token als erste Nachricht | Realtime (Chat, Live-Updates, Benachrichtigungen) |

## 9. Realtime

* Schreibende Vorgänge rufen innerhalb ihrer DB-Transaktion `pg_notify('nbb_events', …)` auf.
  PostgreSQL liefert die Nachricht **erst nach Commit** aus – es gibt also keine Events für
  zurückgerollte Änderungen.
* Jede Backend-Instanz hält eine `LISTEN`-Verbindung und verteilt Events an ihre WebSocket-Clients
  (Chat-Nachrichten vollständig, sonst kleine Invalidierungs-Events, z. B. `leaderboard_updated`).
* Das Frontend invalidiert daraufhin gezielt die betroffenen React-Query-Caches – keine Reloads.

## 10. Sicherheit (Kurzfassung)

* Login mit Benutzername/Passwort, Passwörter gehasht (PBKDF2-SHA256), Login-Rate-Limit,
  signierte Access-Tokens (HS256, `SECRET_KEY` aus `.env`).
* Bearer-Token statt Cookies ⇒ kein CSRF-Angriffsvektor auf die API.
* Pydantic-Validierung aller Eingaben, SQLAlchemy (parametrisierte Queries), React-Escaping, keine
  HTML-Ausgabe von Benutzertext, CSP- und Security-Header über Nginx.
* Uploads: nur Rasterbilder (PNG/JPEG/WebP/GIF), Prüfung + Neukodierung mit Pillow (entfernt EXIF),
  Größenlimit, `nosniff`.
* Rate-Limits: Nginx (pro IP) + Backend (pro Benutzer, z. B. Chat, Passwort, Avatar); Login-Sperre
  nur nach Fehlversuchen pro (Konto, IP). Nginx gibt nur die selbst ermittelte Client-IP weiter.
* Uploads werden vor dem Dekodieren auf Pixelzahl geprüft und in einem Worker-Thread verarbeitet.
* OpenAI-API-Key nur aus `.env`/Secret-Datei, nie in API-Antworten, Logs oder der Datenbank
  (Fehlermeldungen werden geschwärzt). Keine eingehende Agent-API mehr.
* Änderungsanträge nur bis Kickoff, Genehmigung nie nach dem Ergebnis; Entwurfs-Saisons nur für Admins.
* WebSocket-Verbindungen werden jede Minute neu geprüft (Sperre/Abmeldung wirkt auch dort).
* Audit-Log ist per Datenbank-Trigger gegen UPDATE/DELETE geschützt.
* Secrets nur über `.env` (nicht im Repository). Platzhalter (`CHANGE_ME…`) werden beim ersten Start
  durch Zufallswerte ersetzt (Signaturschlüssel in `/data/.secret_key`, Admin-/Demo-Passwort im Log
  des `migrate`-Dienstes); `scripts/generate-secrets.sh` setzt feste Werte in `.env`.
