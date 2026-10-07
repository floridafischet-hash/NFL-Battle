# OpenClaw-Integration (Agent-API)

OpenClaw recherchiert nach NFL-Spielen die Ergebnisse und meldet sie über eine **eigene, abgesicherte
API**. OpenClaw kann die Datenbank nicht direkt verändern. Jede Meldung wird vom Backend geprüft,
mit Quelle gespeichert und protokolliert.

## 1. Zugang einrichten

1. Als Admin anmelden → **Admin → OpenClaw → „Token erstellen“**.
2. Den angezeigten Token (`nbb_…`) **sofort** in OpenClaw hinterlegen. Er wird nur einmal angezeigt;
   gespeichert ist nur ein SHA-256-Hash.
3. Jede Anfrage sendet den Header `Authorization: Bearer nbb_…`.

Der Token hat ausschließlich die Rolle **AGENT**:

| Endpunkt | AGENT-Token | Benutzer/Admin-Login |
|---|---|---|
| `/api/agent/*` | ✅ | ❌ 403 |
| alle anderen `/api/*` | ❌ 403 | ✅ (je nach Rolle) |

Token widerrufen: Admin → OpenClaw → Papierkorb. Ein widerrufener Token erhält sofort `401`.

## 2. Ablauf

```
OpenClaw                                   NFL Bracket Battle
   │  GET /api/agent/matches/pending   ───▶  Spiele, die ein Ergebnis brauchen
   │  (recherchiert Ergebnis bei ESPN, NFL.com …)
   │  POST /api/agent/results           ───▶  Validierung
   │                                          ├─ ungültig      → 422/404/409  REJECTED
   │                                          ├─ unsicher      → 202 REVIEW_REQUIRED (Admin prüft)
   │                                          ├─ zu wenig Quellen → 202 PENDING_CONFIRMATION
   │                                          └─ ok            → 200 APPLIED
   │                                              → Spiel FINAL, Punkte, Rangliste,
   │                                                nächste Runde, NFL-Bot-Nachricht, Audit-Log
```

Empfehlung für OpenClaw: alle 10–15 Minuten während der Spieltage `matches/pending` abfragen und
für jedes Spiel das Endergebnis aus **mindestens einer vertrauenswürdigen Quelle** melden. Weitere
Quellen gehören zur Gegenprüfung in `sources`.

## 3. Endpunkte

### `GET /api/agent/whoami`
Prüft den Token. → `{"label": "token:OpenClaw", "roles": ["AGENT"]}`

### `GET /api/agent/matches`
Alle Spiele der aktiven Saison (z. B. für die Spielplan-Recherche).

### `GET /api/agent/matches/pending`
Spiele, die ein Ergebnis benötigen: Teams bekannt, nicht FINAL/VOID und Kickoff vorbei oder gesperrt.
Dazu kommen Spiele, für die ein Admin **„Ergebnisprüfung starten“** geklickt hat
(`result_check_requested: true`).

```json
[
  {
    "id": 34, "slot": "AFC-DIV-2", "round": "DIVISIONAL", "round_label": "Divisional Round",
    "home_team": {"id": 1, "abbreviation": "BUF", "name": "Buffalo Bills", "short_name": "Bills", "...": "..."},
    "away_team": {"id": 5, "abbreviation": "BAL", "name": "Baltimore Ravens", "...": "..."},
    "kickoff_at": "2027-01-17T21:00:00Z", "status": "LOCKED", "result_check_requested": false
  }
]
```

### `POST /api/agent/results`

```json
{
  "match_id": 34,
  "home_team": "BUF",
  "away_team": "BAL",
  "home_score": 24,
  "away_score": 27,
  "winner": "BAL",
  "source": "ESPN",
  "source_url": "https://www.espn.com/nfl/game/_/gameId/401671234",
  "timestamp": "2027-01-18T00:41:00Z",
  "sources": [
    {"source": "NFL.com", "source_url": "https://www.nfl.com/games/ravens-at-bills-2027-post-2", "home_score": 24, "away_score": 27}
  ]
}
```

| Feld | Pflicht | Beschreibung |
|---|---|---|
| `match_id` | ✅ | ID aus `matches/pending` |
| `home_score`, `away_score` | ✅ | 0–99, kein Unentschieden |
| `home_team`, `away_team` | empfohlen | Kürzel (`BUF`), Kurzname (`Bills`), voller Name oder Team-ID. Vertauschte Heim/Gast-Angaben werden erkannt und korrigiert |
| `winner` | empfohlen | muss zum Spielstand passen |
| `source` | ✅ | Name der Quelle |
| `source_url` | ✅* | http(s)-URL. *Ohne URL oder mit nicht vertrauenswürdiger Domain ⇒ `REVIEW_REQUIRED` |
| `timestamp` | optional | Zeitpunkt der Recherche (nicht in der Zukunft, nicht vor Kickoff) |
| `sources` | optional | bis zu 10 Gegenquellen; jede Abweichung ⇒ `REVIEW_REQUIRED` |

**Prüfungen des Backends**

1. Existiert das Match? → sonst `404`
2. Stehen die Teams fest und stimmen sie überein? → sonst `422`
3. Ist das Ergebnis plausibel (0–99, kein Remis, Sieger passt, Zeitstempel, Spiel kann beendet sein:
   `AGENT_RESULT_MIN_MINUTES_AFTER_KICKOFF`)? → sonst `422`/`409`
4. Wurde das Match schon gewertet? → identisch: `DUPLICATE` (`200`), abweichend: `REVIEW_REQUIRED`
5. Ist die Quelle vertrauenswürdig (`AGENT_TRUSTED_DOMAINS`, Subdomains inklusive)?
6. Widersprechen sich Quellen oder frühere Meldungen? → `REVIEW_REQUIRED`
7. Genug unabhängige Quellen (`AGENT_MIN_CONFIRMATIONS`, verschiedene Domains)? → sonst `PENDING_CONFIRMATION`
8. Ergebnis übernehmen: Match `FINAL`, Punkte berechnen, Rangliste, nächste Runde, NFL Bot, Audit-Log.

**Antworten**

| HTTP | `status` | Bedeutung |
|---|---|---|
| 200 | `APPLIED` | Ergebnis übernommen und ausgewertet |
| 200 | `DUPLICATE` | identisches Ergebnis war schon gewertet – nichts geändert |
| 202 | `PENDING_CONFIRMATION` | wartet auf weitere Quelle(n) |
| 202 | `REVIEW_REQUIRED` | keine automatische Wertung, Admin wurde benachrichtigt |
| 404/409/422 | `REJECTED` | ungültig – Grund in `message` |

```json
{"status": "APPLIED", "run_id": 17, "report_id": 9, "message": "Ergebnis übernommen und ausgewertet."}
```

Jeder Aufruf – auch fehlerhafte – wird als **Agent-Lauf** gespeichert (Admin → OpenClaw: letzter
Lauf, Fehler, Meldungen mit Quelle/URL/Zeitpunkt/Agent/Status).

### `POST /api/agent/schedule` (optional)
Kickoff-Zeit eines noch offenen Spiels setzen; die Tipp-Deadline wird daraus berechnet.
```json
{"match_id": 34, "kickoff_at": "2027-01-17T21:00:00Z", "venue": "Highmark Stadium", "source": "NFL.com", "source_url": "https://www.nfl.com/schedules/"}
```

### `POST /api/agent/events` (optional)
Halbzeitstand für den NFL Bot (einmal pro Spiel):
```json
{"match_id": 34, "type": "HALFTIME", "home_score": 10, "away_score": 14, "source": "ESPN"}
```

## 4. Review durch den Admin

Admin → **OpenClaw → „Prüfung erforderlich“** zeigt alle unsicheren Meldungen mit Grund und Quelle:

- **Übernehmen & werten** – Ergebnis wird wie eine Agent-Meldung übernommen (protokolliert mit Admin).
- **Verwerfen** – Meldung wird abgelehnt.

**„Ergebnisprüfung starten“** markiert offene Spiele für OpenClaw (`result_check_requested`) und ruft,
falls `OPENCLAW_WEBHOOK_URL` gesetzt ist, diesen Webhook auf:

```json
POST {OPENCLAW_WEBHOOK_URL}
Authorization: Bearer {OPENCLAW_WEBHOOK_TOKEN}
{"event": "result_check_requested", "match_ids": [34, 35], "pending_url": "https://…/api/agent/matches/pending"}
```

## 5. Beispiel mit curl

```bash
TOKEN=nbb_xxx
BASE=https://tippspiel.example.de

curl -s -H "Authorization: Bearer $TOKEN" $BASE/api/agent/matches/pending | jq '.[] | {id, slot, home: .home_team.abbreviation, away: .away_team.abbreviation}'

curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"match_id":34,"home_team":"BUF","away_team":"BAL","home_score":24,"away_score":27,"winner":"BAL",
       "source":"ESPN","source_url":"https://www.espn.com/nfl/game/_/gameId/401671234","timestamp":"2027-01-18T00:41:00Z"}' \
  $BASE/api/agent/results
```

## 6. Vorschlag für die OpenClaw-Aufgabe

> Rufe `GET /api/agent/matches/pending` auf. Recherchiere für jedes Spiel das **Endergebnis** auf
> ESPN und NFL.com. Melde es nur, wenn das Spiel beendet ist („Final“). Sende `POST /api/agent/results`
> mit `source`/`source_url` der Hauptquelle und trage die zweite Quelle in `sources` ein. Bei
> `REVIEW_REQUIRED` oder `REJECTED` nichts erneut senden, sondern die `message` im Bericht ausgeben.

## 7. Sicherheit

- Token nur als SHA-256-Hash gespeichert, jederzeit widerrufbar, `last_used_at` sichtbar.
- Rate-Limit: 120 Anfragen/Minute pro Token (Backend) + Nginx-Limit pro IP.
- Agent-Tokens können keine Benutzer-, Tipp- oder Admin-Endpunkte verwenden.
- Bereits gewertete Spiele werden nie automatisch überschrieben (nur per Admin-Korrektur/Review).
