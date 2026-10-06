# API-Dokumentation

Interaktive OpenAPI-Dokumentation: **`/api/docs`** (Swagger UI), Schema: `/api/openapi.json`.

Alle Endpunkte (außer `public` und `auth/login`) erwarten `Authorization: Bearer <token>`.
Fehler werden als `{"detail": "…"}` (deutsch) mit passendem HTTP-Status geliefert.

| Status | Bedeutung |
|---|---|
| 401 | nicht angemeldet / Token ungültig oder abgelaufen |
| 403 | falsche Rolle (z. B. Agent auf User-Endpunkt) oder Benutzer gesperrt |
| 404 | nicht gefunden |
| 409 | Konflikt (z. B. Spiel gesperrt, Antrag schon offen, Folgespiel bereits gewertet) |
| 413/415 | Upload zu groß / kein gültiges Bild |
| 422 | ungültige Eingabe |
| 429 | Rate-Limit erreicht (`Retry-After`) |

## Öffentlich & Login

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/public/health` | Liveness |
| GET | `/api/public/ready` | Readiness (Datenbank erreichbar) |
| GET | `/api/public/config` | App-Name, Zeitzone |
| POST | `/api/auth/login` | `{username, password}` → `{access_token, expires_at, user}` (rate-limitiert) |

## Profil (USER/ADMIN)

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/me` | eigenes Profil inkl. Rolle |
| PATCH | `/api/me` | Anzeigename ändern |
| POST | `/api/me/password` | Passwort ändern (meldet andere Geräte ab, liefert neues Token) |
| POST/DELETE | `/api/me/avatar` | Avatar hochladen (multipart `file`) / entfernen |

## Spiel (USER/ADMIN)

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/seasons` | Saisons (Entwürfe nur für Admins) |
| GET | `/api/seasons/current` | aktive bzw. zuletzt gespielte Saison |
| GET | `/api/teams` | alle Teams |
| GET | `/api/seasons/{id}/teams` | Playoff-Teilnehmer mit Seeds |
| GET | `/api/seasons/{id}/matches` | Spiele inkl. eigenem Tipp, Punkten, Community-Verteilung (nur gesperrte Spiele) |
| GET | `/api/matches/{id}` | Spieldetail: eigener Tipp, eigener Änderungsantrag, Tipps aller (nach Lock) |
| GET | `/api/seasons/{id}/bracket/{userId\|me}` | Bracket-Ansicht (13 Slots, Teams, Herkunft, Tipp-Status, Punkte); fremde Tipps erst nach Lock |
| PUT | `/api/seasons/{id}/bracket/me/picks/{slot}` | Tipp setzen `{winner_team_id, winner_score?, loser_score?}` – Kaskade für nachgelagerte Tipps |
| DELETE | `/api/seasons/{id}/bracket/me/picks/{slot}` | Tipp entfernen (nur offen) |
| POST | `/api/seasons/{id}/bracket/me/submit` | Bracket abgeben (alle offenen Spiele gültig getippt) |
| GET | `/api/seasons/{id}/brackets` | Übersicht aller Brackets (Fortschritt, Champion-Tipp nach SB-Lock) |
| GET | `/api/seasons/{id}/compare?a=&b=` | Vergleich zweier Brackets inkl. `diff` (`same/different/hidden/missing`) |
| GET | `/api/seasons/{id}/distribution` | Tippverteilung (nur gesperrte Spiele) |
| GET | `/api/seasons/{id}/leaderboard` | Rangliste |
| GET | `/api/dashboard` | alles für das Dashboard in einer Anfrage |
| POST | `/api/matches/{id}/change-requests` | Änderungsantrag nach Lock `{winner_team_id, winner_score?, loser_score?, reason?}` |
| GET | `/api/change-requests/me` | eigene Anträge |
| DELETE | `/api/change-requests/{id}` | offenen Antrag zurückziehen |

**Slots:** `AFC-WC-1..3`, `AFC-DIV-1..2`, `AFC-CONF`, `NFC-WC-1..3`, `NFC-DIV-1..2`, `NFC-CONF`, `SB`.

**`pick_state`:** `valid` · `pending` (Gegner steht noch nicht fest, Team kann noch hinkommen) ·
`invalid` (Team nicht in der Paarung / ausgeschieden) · `hidden` (fremder Tipp vor Lock) · `none`.

## Chat, Benachrichtigungen, Statistik

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/chat/messages?before=&limit=` | Verlauf (inkl. NFL-Bot-Nachrichten mit `system.type` und `payload`) |
| POST | `/api/chat/messages` | `{body, upload_id?}` (max. 1000 Zeichen, 20/min) |
| POST | `/api/chat/uploads` | Bild hochladen (PNG/JPEG/WebP/GIF, wird zu WebP) |
| DELETE | `/api/chat/messages/{id}` | eigene Nachricht (Admins: alle) löschen |
| GET | `/api/chat/online` | aktuell verbundene Benutzer |
| GET | `/api/notifications` | Benachrichtigungen + Anzahl ungelesen |
| POST | `/api/notifications/{id}/read`, `/api/notifications/read-all` | als gelesen markieren |
| GET | `/api/stats/users/{userId\|me}?season_id=` | Statistik (Punkte, Quote, Serien, Runden, Saisons) |
| GET | `/api/stats/compare?a=&b=&season_id=` | Vergleich zweier Spieler (Duelle, Übereinstimmung) |
| GET | `/api/stats/overview?season_id=` | Tabelle aller Spieler |
| GET | `/api/hall-of-fame` | Saisonsieger + ewige Tabelle |
| GET | `/api/users` | aktive Spieler (für Auswahllisten) |

## Admin (ADMIN)

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET/POST | `/api/admin/users` | Benutzer auflisten / anlegen `{username, display_name, password, role}` |
| PATCH | `/api/admin/users/{id}` | `display_name`, `role` (USER/ADMIN), `is_active` (sperren/aktivieren) |
| POST | `/api/admin/users/{id}/password` | Passwort zurücksetzen |
| GET | `/api/admin/users/{id}/predictions?season_id=` | Tipps eines Benutzers |
| POST | `/api/admin/seasons` | Saison erstellen (legt die 13 Slots an) |
| PATCH | `/api/admin/seasons/{id}` | Punktesystem / Optionen |
| POST | `/api/admin/seasons/{id}/activate` | aktivieren (nur eine aktive Saison) |
| PUT | `/api/admin/seasons/{id}/teams` | Setzliste `[{team_id, seed}]` |
| POST | `/api/admin/seasons/{id}/generate-wildcard` | Wild-Card-Paarungen 2v7, 3v6, 4v5 + Bot-Ankündigung |
| POST | `/api/admin/seasons/{id}/announce` | offene Paarungen im Chat veröffentlichen |
| POST | `/api/admin/seasons/{id}/recalculate` | alle Punkte neu berechnen |
| GET | `/api/admin/seasons/{id}/matches` | Spiele inkl. Anzahl Tipps / Prüfbedarf |
| POST/PUT | `/api/admin/teams`, `/api/admin/teams/{id}` | Team anlegen / bearbeiten |
| POST | `/api/admin/teams/{id}/logo` | Logo hochladen |
| PATCH | `/api/admin/matches/{id}` | Teams (Drag & Drop), `kickoff_at`, `lock_at`, `venue` |
| POST | `/api/admin/matches/{id}/status` | `{action: lock\|open\|reopen\|void, lock_at?}` |
| POST | `/api/admin/matches/{id}/result` | Ergebnis setzen/korrigieren `{home_score, away_score}` |
| POST | `/api/admin/matches/{id}/reset-result` | Ergebnis zurücksetzen (FINAL → LOCKED) |
| GET | `/api/admin/change-requests?status=PENDING` | Änderungsanträge |
| POST | `/api/admin/change-requests/{id}/approve\|reject` | `{note?}` |
| GET | `/api/admin/agent/overview` | Läufe, Fehler, Tokens, Meldungen |
| POST/DELETE | `/api/admin/agent/tokens[/{id}]` | Agent-Token erstellen (einmalig sichtbar) / widerrufen |
| POST | `/api/admin/agent/check` | „Ergebnisprüfung starten“ |
| POST | `/api/admin/agent/reports/{id}/accept\|reject` | REVIEW_REQUIRED-Meldung übernehmen/verwerfen |
| GET | `/api/admin/audit` | Audit-Log (Filter `action`, `actor_type`, `object_type`, `q`, Paging `before`) |
| GET | `/api/admin/summary` | Kennzahlen für die Admin-Übersicht |

## Agent (AGENT) – siehe [OPENCLAW.md](OPENCLAW.md)

`GET /api/agent/whoami`, `GET /api/agent/matches`, `GET /api/agent/matches/pending`,
`POST /api/agent/results`, `POST /api/agent/schedule`, `POST /api/agent/events`

## WebSocket `/ws`

1. Verbinden, als erste Nachricht `{"type": "auth", "token": "<access_token>"}` senden.
2. Antwort `{"type": "ready"}`; danach Ereignisse:

| `type` | Inhalt |
|---|---|
| `chat_message` | vollständige Nachricht (`message`) |
| `chat_message_deleted` | `id` |
| `notification` | neue Benachrichtigung (nur an den Empfänger) |
| `match_updated`, `bracket_updated`, `leaderboard_updated`, `season_updated`, `teams_updated` | Invalidierung – Daten neu laden |
| `change_request_updated` | Antrag geändert (Admins / Antragsteller) |
| `presence` | Online-Liste geändert |

Ein `"ping"` wird mit `{"type": "pong"}` beantwortet. Die Verbindung endet mit Ablauf des Tokens
(Code 4401) – der Client verbindet sich dann neu.
