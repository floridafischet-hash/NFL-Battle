# ChatGPT-Ergebnis-Agent

Nach jedem Playoff-Spiel sucht **ChatGPT** (OpenAI API mit Websuche) das Endergebnis und trägt es
ein. Der Agent läuft **im Backend**. Von außen gibt es keinen Zugang mehr (keine Agent-API, keine
Tokens). Jede Antwort von ChatGPT wird geprüft, mit Quellen gespeichert und protokolliert, bevor sie
zählt.

Ohne API-Key ist der Agent aus. Dann trägst du die Ergebnisse unter **Admin → Spiele** ein.

## 1. Einrichten

1. Auf <https://platform.openai.com/api-keys> einen **API-Key** erstellen. Am besten ein eigenes
   Projekt nur für das Tippspiel anlegen und dort ein **monatliches Budget-Limit** setzen (z. B. 5 $).
   Ein ChatGPT-Plus-Abo ist nicht nötig. Die API wird pro Abfrage abgerechnet (bei `gpt-5.4-mini`
   wenige Cent pro Spieltag).
2. Den Key **nur auf dem Server** in die `.env` eintragen:
   ```bash
   OPENAI_API_KEY=sk-...
   ```
   `.env` ist in `.gitignore` und landet nie im Git. Alternativ eine Datei mit dem Key als Docker
   Secret einbinden und `OPENAI_API_KEY_FILE=/run/secrets/openai_api_key` setzen.
3. Backend neu starten: `docker compose up -d backend`.
4. Im Adminbereich unter **ChatGPT** auf **„Verbindung testen“** klicken. Dabei werden Key und
   Modell geprüft, ohne Kosten.

Den Key nie in Chat, Issues oder Screenshots kopieren. Wenn er doch einmal irgendwo gelandet ist:
im OpenAI-Dashboard löschen, neuen erstellen, in der `.env` ersetzen und das Backend neu starten.

## 2. Ablauf

```
Backend (jede Minute)                                  OpenAI (ChatGPT + Websuche)
  │ Welche Spiele brauchen ein Ergebnis?
  │  – Kickoff + RESULT_AGENT_FIRST_CHECK_MINUTES vorbei, noch nicht FINAL
  │  – oder Admin hat „Jetzt prüfen“ geklickt
  │ POST /v1/responses  ───────────────────────────▶  sucht nur auf AGENT_TRUSTED_DOMAINS
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
| `OPENAI_API_KEY` | – | API-Key (geheim, nur in `.env`) |
| `OPENAI_API_KEY_FILE` | – | alternativ: Datei mit dem Key (Docker Secret) |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Modell mit Websuche |
| `OPENAI_REASONING_EFFORT` | `low` | leer lassen bei Modellen ohne Reasoning |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | nur für Proxys/Tests ändern |
| `RESULT_AGENT_ENABLED` | `true` | `false` schaltet den Agenten ab |
| `RESULT_AGENT_FIRST_CHECK_MINUTES` | `200` | erste Suche so viele Minuten nach Kickoff |
| `RESULT_AGENT_RETRY_MINUTES` | `20` | Abstand zwischen Versuchen pro Spiel |
| `RESULT_AGENT_MAX_CALLS_PER_DAY` | `40` | Kostenbremse: max. Abfragen pro 24 h |
| `AGENT_TRUSTED_DOMAINS` | nfl.com, espn.com, … | erlaubte Quellen (Subdomains inklusive) |
| `AGENT_MIN_CONFIRMATIONS` | `2` | übereinstimmende Quellen verschiedener Seiten |
| `AGENT_RESULT_MIN_MINUTES_AFTER_KICKOFF` | `60` | frühester Zeitpunkt für ein Ergebnis |

## 6. Datenschutz

An OpenAI gehen nur Spielpaarung, Runde und Kickoff-Zeit, keine Benutzerdaten. Die Anfrage wird mit
`store: false` gesendet, OpenAI speichert die Antwort also nicht für spätere Abrufe.
