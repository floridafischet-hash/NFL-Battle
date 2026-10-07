# ChatGPT-Ergebnis-Agent

Nach jedem Playoff-Spiel sucht **ChatGPT** mit Live-Websuche das Endergebnis und trägt es ein.
Der Agent läuft **im Backend**, von außen gibt es keinen Zugang (keine Agent-API, keine Tokens).
Jede Antwort wird geprüft, mit Quellen gespeichert und protokolliert, bevor sie zählt.

Es gibt zwei Wege zu ChatGPT (`RESULT_AGENT_PROVIDER`):

| Weg | Was du brauchst | Kosten |
|---|---|---|
| `chatgpt` **(Standard)** | ChatGPT **Plus oder Pro**. Die App nutzt die offizielle **Codex CLI** von OpenAI mit „Sign in with ChatGPT“. | im Abo enthalten (Kontingent des Abos) |
| `openai_api` | OpenAI-API-Key | pro Abfrage (wenige Cent pro Spieltag) |

Ohne Login bzw. Key ist der Agent aus, und du trägst die Ergebnisse unter **Admin → Spiele** ein.

## 1. Einrichten

### Mit deinem ChatGPT-Abo (empfohlen)

Ein ChatGPT-Abo hat keine klassische API. Die Codex CLI von OpenAI kann sich aber mit dem Abo
anmelden und dessen Kontingent nutzen, inklusive Websuche. Sie ist im Backend-Image schon
installiert.

```bash
docker compose exec backend codex login --device-auth
```

1. Die Ausgabe zeigt einen Link und einen Code.
2. Den Link öffnen, mit dem ChatGPT-Konto (Plus/Pro) anmelden und den Code eingeben.
3. Prüfen: `docker compose exec backend codex login status` sollte „Logged in using ChatGPT“ melden.
4. Admin → **ChatGPT** → **„Verbindung testen“**.

Der Login liegt im Daten-Volume unter `/data/codex/auth.json` (nur für den App-Benutzer lesbar).
Er übersteht Updates, landet im Backup und **nie im Git**. Abmelden geht mit
`docker compose exec backend codex logout`.

Falls die Geräte-Code-Anmeldung abgelehnt wird, musst du sie in den ChatGPT-Sicherheitseinstellungen
für Codex erlauben (bei Business/Enterprise macht das der Workspace-Admin). Alternative: Auf dem
eigenen Rechner `codex login` ausführen und `~/.codex/auth.json` sicher nach `/data/codex/` im
Backend kopieren (siehe [SETUP_AGENT.md](../SETUP_AGENT.md)).

### Mit API-Key (Alternative)

1. API-Key auf <https://platform.openai.com/api-keys> erstellen. Am besten ein eigenes Projekt mit
   Budget-Limit anlegen.
2. **Nur auf dem Server** in die `.env` eintragen: `RESULT_AGENT_PROVIDER=openai_api` und
   `OPENAI_API_KEY=sk-…`. Alternativ `OPENAI_API_KEY_FILE` für ein Docker Secret.
3. `docker compose up -d backend` und dann Admin → ChatGPT → „Verbindung testen“.

Keys und Login-Dateien nie in Chats, Issues oder Screenshots kopieren. Wenn so etwas doch irgendwo
gelandet ist: Bei OpenAI widerrufen (Key löschen bzw. in ChatGPT alle Sitzungen abmelden) und neu
einrichten.

## 2. Ablauf

```
Backend (jede Minute)                                  OpenAI (ChatGPT + Websuche)
  │ Welche Spiele brauchen ein Ergebnis?
  │  – Kickoff + RESULT_AGENT_FIRST_CHECK_MINUTES vorbei, noch nicht FINAL
  │  – oder Admin hat „Jetzt prüfen“ geklickt
  │ codex exec / Responses API ────────────────────▶  sucht nur auf AGENT_TRUSTED_DOMAINS
  │                     ◀───────────────────────────  JSON: Status, Spielstand, Quellen + besuchte URLs
  │ Prüfung (siehe unten)
  ├─ ok                         → Spiel FINAL, Punkte, Rangliste, nächste Runde, NFL Bot, Audit-Log
  ├─ nur eine Quelle            → wartet auf Bestätigung (nächste Suche)
  ├─ unsicher / widersprüchlich → „Prüfung erforderlich“ beim Admin (Glocke)
  └─ noch nicht beendet         → neuer Versuch nach RESULT_AGENT_RETRY_MINUTES
```

## 3. Prüfungen

ChatGPTs Antwort gilt als **nicht vertrauenswürdige Eingabe**. Sie wird so geprüft:

| Prüfung | Folge bei Fehlschlag |
|---|---|
| Antwort entspricht exakt dem JSON-Schema (Structured Outputs) | Fehler im Lauf, später neuer Versuch |
| Jede Quellen-URL wurde von der Websuche **wirklich besucht** (keine erfundenen Links) | Quelle wird verworfen; ohne belegte Quelle → Admin-Prüfung |
| Quelle liegt auf einer vertrauenswürdigen Domain (`AGENT_TRUSTED_DOMAINS`) | Admin-Prüfung |
| Teams stimmen mit der Paarung überein (vertauschtes Heim/Gast wird korrigiert) | abgelehnt |
| Plausibel: 0–99 Punkte, kein Unentschieden, Sieger passt, Spiel kann schon beendet sein | abgelehnt |
| Alle Quellen nennen denselben Spielstand, keine widersprüchliche frühere Meldung | Admin-Prüfung |
| Mindestens `AGENT_MIN_CONFIRMATIONS` (Standard 2) Quellen von **verschiedenen** Seiten | wartet auf Bestätigung |
| **Zwei unabhängige ChatGPT-Suchen** (`RESULT_AGENT_CONFIRM_RUNS`, Standard 2) melden denselben Spielstand | wartet auf die nächste Suche; abweichend → Admin-Prüfung |
| Spiel ist schon gewertet | identisch: nichts passiert; abweichend: Admin-Prüfung (nie automatisch überschrieben) |

Inhalte von Webseiten können versuchen, ChatGPT Anweisungen unterzuschieben (Prompt Injection).
Das wird auf mehreren Ebenen abgefangen:
- Die Suche ist auf die vertrauenswürdigen Sportseiten beschränkt.
- Die Antwort hat ein festes Format.
- Es zählen nur wirklich besuchte Quellen, und mindestens zwei unabhängige Seiten müssen übereinstimmen.
- Gewertete Spiele werden nie automatisch geändert.

## 4. Adminbereich → ChatGPT

- **Status**: aktiv / kein API-Key, Modell, Abrufe der letzten 24 h gegen das Tageslimit. Der Key
  selbst wird nirgends angezeigt.
- **Verbindung testen**: prüft Key und Modell.
- **Jetzt prüfen**: alle Spiele, die ein Ergebnis brauchen, werden innerhalb einer Minute gesucht.
  Das gilt auch, wenn die erste automatische Suche noch nicht fällig ist.
- **Prüfung erforderlich**: unsichere Ergebnisse mit Grund und Quellen-Links. Mit **„Übernehmen &
  werten“** oder **„Verwerfen“** entscheidest du.
- **Läufe**: jede Suche mit Ergebnis, verwendeten und verworfenen Quellen sowie dem Token-Verbrauch.
  Fehler (z. B. ungültiger Key) stehen hier, mit unkenntlich gemachtem Key.

## 5. Einstellungen (`.env`)

| Variable | Standard | Bedeutung |
|---|---|---|
| `RESULT_AGENT_PROVIDER` | `chatgpt` | `chatgpt` (Abo über Codex CLI) oder `openai_api` |
| `CODEX_MODEL` | leer | Modell für das Abo (leer = Standard der Codex CLI) |
| `OPENAI_API_KEY` | – | API-Key (geheim, nur in `.env`; nur `openai_api`) |
| `OPENAI_API_KEY_FILE` | – | alternativ: Datei mit dem Key (Docker Secret) |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Modell mit Websuche |
| `OPENAI_REASONING_EFFORT` | `low` | leer lassen bei Modellen ohne Reasoning |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | nur für Proxys/Tests ändern |
| `RESULT_AGENT_ENABLED` | `true` | `false` schaltet den Agenten ab |
| `RESULT_AGENT_FIRST_CHECK_MINUTES` | `200` | erste Suche so viele Minuten nach Kickoff |
| `RESULT_AGENT_RETRY_MINUTES` | `20` | Abstand zwischen Versuchen pro Spiel |
| `RESULT_AGENT_MAX_CALLS_PER_DAY` | `40` | Kostenbremse: max. Abfragen pro 24 h |
| `AGENT_TRUSTED_DOMAINS` | nfl.com, espn.com, … | erlaubte Quellen (Subdomains inklusive) |
| `RESULT_AGENT_CONFIRM_RUNS` | `2` | unabhängige Suchen, die übereinstimmen müssen (Schutz vor manipulierten Webseiten) |
| `AGENT_MIN_CONFIRMATIONS` | `2` | übereinstimmende Quellen verschiedener Seiten |
| `AGENT_RESULT_MIN_MINUTES_AFTER_KICKOFF` | `60` | frühester Zeitpunkt für ein Ergebnis |

## 6. Abschottung von Codex

Über das Abo darf Codex **nur im Web suchen**: Shell, Dateizugriff, Browser-/Computer-Steuerung,
Plugins und Bildfunktionen sind abgeschaltet (`features.*=false`), eigene Codex-Konfigurationen
werden ignoriert. Eine manipulierte Webseite kann Codex also nicht dazu bringen, Dateien wie den
Login oder den App-Schlüssel zu lesen. Das Codex-Programm ist auf eine Version gepinnt und wird
beim Bauen per SHA-256 geprüft. Freitext des Modells wird gekürzt und von schlüsselartigen
Zeichenketten bereinigt.

## 7. Datenschutz

An OpenAI gehen nur Spielpaarung, Runde und Kickoff-Zeit, keine Benutzerdaten. Über die API wird mit
`store: false` gesendet. Über das Abo läuft jede Suche als kurzlebige Codex-Sitzung (`--ephemeral`)
mit schreibgeschützter Sandbox. Die Codex CLI bekommt keine Datenbank- oder App-Geheimnisse als
Umgebungsvariablen.
