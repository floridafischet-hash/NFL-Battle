# Setup-Anleitung für KI-Agenten

Du bist ein KI-Agent (Claude Code, Codex, Cursor, …) und sollst **NFL Bracket Battle** für deinen
Menschen installieren. Diese Datei sagt dir, wie das am schnellsten und sichersten geht.
Arbeite die Schritte der Reihe nach ab.

**Ziel:** Die App läuft per Docker Compose. Der Admin kann sich einloggen, und ChatGPT ist über
das **ChatGPT-Abo des Nutzers (Plus/Pro)** verbunden, nicht per API-Key. Damit trägt die App die
Ergebnisse mit Live-Websuche selbst ein.

---

## 0. Spielregeln für dich

- **Keine Geheimnisse ins Git, in Logs, Chats oder Commits.** Passwörter, Keys und der
  ChatGPT-Login gehören in die `.env` bzw. ins Docker-Volume. Gib Passwörter nur einmal an den
  Nutzer weiter und schreib sie nirgendwo sonst hin.
- **Nichts erfinden.** Wenn ein Befehl fehlschlägt, lies die Fehlermeldung und die Logs
  (`docker compose logs <dienst>`). Rate nicht.
- **Destruktives nur mit Erlaubnis**: `docker compose down -v`, Volumes löschen, `.env`
  überschreiben, Ports von anderen Diensten belegen.
- **Den ChatGPT-Login macht der Nutzer selbst** (Device-Code im Browser). Du startest ihn nur und
  reichst Link und Code durch. Frag nie nach seinem ChatGPT-Passwort.

---

## 1. Rückfragen, bevor du loslegst

Stell diese Fragen **gesammelt in einer Nachricht**. Wo es einen sinnvollen Standard gibt, schlag
ihn vor, damit der Nutzer nur „passt“ sagen muss.

| # | Frage | Warum | Standard |
|---|---|---|---|
| 1 | **Wo soll es laufen?** Auf diesem Rechner, auf einem Server per SSH (Adresse und Benutzer?) oder auf einem NAS? | Zielsystem | dieser Rechner |
| 2 | **Soll es aus dem Internet erreichbar sein?** Wenn ja: Welche **Domain** (z. B. `tippspiel.example.de`), zeigt der DNS schon auf den Server, und welche **E-Mail** für Let's Encrypt? | HTTPS mit Traefik | nur im Heimnetz, Port 8080 |
| 3 | Läuft auf dem Server schon ein **Reverse-Proxy** (nginx, Caddy, Traefik, NPM) oder ist Port **80/443/8080** belegt? | Port-Konflikte vermeiden | – |
| 4 | **ChatGPT-Abo:** Hast du **ChatGPT Plus oder Pro**? Soll die App damit die Ergebnisse suchen? (Kein API-Key nötig, du meldest dich einmal per Code im Browser an.) | Ergebnis-Agent über Abo | ja, über das Abo |
| 5 | Falls **kein Abo**: Lieber einen **OpenAI-API-Key** nutzen (kostet pro Abfrage) oder die Ergebnisse **von Hand** eintragen? | Alternative | von Hand |
| 6 | **Admin:** Welcher Benutzername (Standard `admin`) und welcher Anzeigename? Das Passwort würfle ich zufällig aus, außer du willst ein eigenes. | Erster Admin | `admin`, zufällig |
| 7 | **Mitspieler:** Wer spielt mit (Namen)? Soll ich sie gleich anlegen? Oder erst mal mit **Demo-Daten** zum Ausprobieren starten? | Benutzer, `SEED_DEMO_DATA` | Demo-Daten an |
| 8 | **Zeitzone** der Gruppe? | Bot-Nachrichten, Deadlines | `Europe/Berlin` |
| 9 | **Punktesystem**: Standard ist Sieger 1, exakter Endstand 3, Champion-Bonus 3, Tipp-Lock zum Kickoff. Passt das? | Saison-Einstellungen | passt |
| 10 | **Backups**: Soll ich ein nächtliches Backup per cron einrichten? Wohin sollen die Kopien zusätzlich gehen (NAS, anderer Server)? | Datensicherheit | täglich 03:15 lokal |
| 11 | Ist das **GitHub-Repo privat**? Falls nicht: bitte unter Settings → General → Danger Zone auf „Private“ stellen. | Privatsphäre | – |

**Wichtig zu Frage 4:** Ein ChatGPT-Abo hat keine klassische API. Die App nutzt deshalb die
offizielle **Codex CLI** von OpenAI („Sign in with ChatGPT“). Die verbraucht das Kontingent des
Abos, hat Live-Websuche und läuft auf dem Server ohne Bildschirm. Erklär das dem Nutzer in einem
Satz, damit er weiß, warum ein Codex-Login auftaucht.

---

## 2. Voraussetzungen prüfen

```bash
docker --version            # Engine 24+
docker compose version      # v2.24+
git --version
free -h; df -h .            # ≥ 2 GB RAM, ≥ 5 GB frei
```

Fehlt Docker, installiere es nach der offiziellen Anleitung für das System (vorher fragen, ob du
Pakete installieren darfst). Der Benutzer muss Docker ohne `sudo` nutzen dürfen, oder du nimmst
konsequent `sudo`.

---

## 3. Installieren

```bash
git clone https://github.com/floridafischet-hash/NFL-Battle.git nfl-bracket-battle
cd nfl-bracket-battle
cp .env.example .env
./scripts/generate-secrets.sh        # setzt POSTGRES_PASSWORD, SECRET_KEY, ADMIN_PASSWORD zufällig
```

Ist das Repo privat, braucht `git clone` Zugriff (SSH-Key oder `gh auth login`). Frag den Nutzer
danach und leg kein Token in der Shell-History ab.

Dann setzt du die Antworten aus Schritt 1 in der `.env` (nur die Zeilen ändern, die nötig sind):

| Antwort | `.env` |
|---|---|
| Admin-Name | `ADMIN_USERNAME=…`, `ADMIN_DISPLAY_NAME=…` |
| Zeitzone | `APP_TIMEZONE=…` |
| Demo-Daten aus | `SEED_DEMO_DATA=false` |
| Port belegt | `HTTP_PORT=8090` |
| eigener Reverse-Proxy | `HTTP_BIND=127.0.0.1` |
| Domain + HTTPS | `DOMAIN=…`, `ACME_EMAIL=…`, `PUBLIC_URL=https://…` |
| ChatGPT-Abo (Standard) | `RESULT_AGENT_PROVIDER=chatgpt` |
| API-Key statt Abo | `RESULT_AGENT_PROVIDER=openai_api` und `OPENAI_API_KEY=…` (den Key gibt der Nutzer **selbst** ein, z. B. per `nano .env`) |
| Ergebnisse nur von Hand | `RESULT_AGENT_ENABLED=false` |

Starten:

```bash
# ohne HTTPS
docker compose up -d
# mit HTTPS (Domain gesetzt, Ports 80/443 frei)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Warten, bis alles läuft:

```bash
docker compose ps                      # backend, frontend, nginx, db: healthy · migrate: exited (0)
curl -fsS http://localhost:8080/api/public/ready    # (bei HTTPS: https://<domain>/api/public/ready)
docker compose logs migrate | tail -30 # Admin-Passwort (und Demo-Passwörter) stehen hier
```

Gib dem Nutzer **einmal** URL, Admin-Benutzername und Passwort. Rat ihm, das Passwort nach dem
ersten Login im Profil zu ändern.

---

## 4. ChatGPT-Abo verbinden (Codex-Login)

Der Login läuft im Backend-Container. Er wird im Volume `app-data` unter `/data/codex` gespeichert
(Rechte 700) und übersteht Neustarts und Updates.

```bash
docker compose exec backend codex login --device-auth
```

Die Ausgabe enthält eine **URL** und einen **Einmal-Code**. Schick beides an den Nutzer:

> „Öffne bitte **<URL>**, melde dich mit deinem ChatGPT-Konto an (dem mit Plus/Pro) und gib den
> Code **<CODE>** ein. Sag mir Bescheid, wenn's durch ist.“

Lass den Befehl laufen, bis er erfolgreich zurückkommt. Danach prüfst du den Status:

```bash
docker compose exec backend codex login status        # erwartet: "Logged in using ChatGPT"
```

Danach soll der Nutzer im Browser **Admin → ChatGPT → „Verbindung testen“** klicken (grüne Meldung).
Erst dann ist der Agent aktiv. Die erste Suche startet automatisch rund 200 Minuten nach jedem
Kickoff, „Jetzt prüfen“ startet sie sofort.

Was dabei schiefgehen kann:
- **„device code login not enabled“ / Fehler beim Login**: Der Nutzer muss in den ChatGPT-Einstellungen
  (Sicherheit) die Geräte-Code-Anmeldung für Codex erlauben, oder bei Business- oder
  Enterprise-Konten der Workspace-Admin. Alternative: Codex auf dem eigenen Rechner einloggen
  (`codex login`) und die Datei `~/.codex/auth.json` sicher auf den Server kopieren:
  `docker compose cp auth.json backend:/data/codex/auth.json`, danach
  `docker compose exec -u 0 backend sh -c 'chown app:app /data/codex/auth.json && chmod 600 /data/codex/auth.json'`.
  Die Datei ist ein Zugangsschlüssel, also nie ins Git und nie in den Chat.
- **Abo-Limit erreicht**: Dann steht „usage limit“ in den Fehlern unter Admin → ChatGPT. Später
  erneut versuchen, `RESULT_AGENT_MAX_CALLS_PER_DAY` senken oder ein Ergebnis von Hand eintragen.
- **Abmelden / Konto wechseln**: `docker compose exec backend codex logout`, dann neu einloggen.

---

## 5. Gruppe einrichten (nach Wunsch)

- **Mitspieler anlegen**: Im Browser unter Admin → Benutzer → „Benutzer anlegen“. Per Kommandozeile
  geht nur der Admin (`python -m app.cli create-admin …`). Für Spieler also die UI nutzen oder den
  Nutzer bitten, das selbst zu machen. Passwörter schickt der Nutzer seinen Freunden selbst.
- **Demo-Daten wieder weg**, wenn es ernst wird: **Achtung, löscht alles** (vorher fragen!):
  `docker compose down -v`, dann `SEED_DEMO_DATA=false` in der `.env`, dann `docker compose up -d`.
- **Saison anlegen**: Das macht der Admin in der UI (Saisons → Bracket-Setup → aktivieren →
  Kickoff-Zeiten). Erklär ihm kurz die Schritte aus der README unter „So läuft eine Saison“.

---

## 6. Backups (wenn gewünscht)

```bash
./scripts/backup.sh            # Test-Backup, landet in backups/<zeitstempel>/
crontab -l 2>/dev/null | { cat; echo "15 3 * * * cd $(pwd) && ./scripts/backup.sh >> backups/backup.log 2>&1"; } | crontab -
```

Das Backup enthält die `.env` und den ChatGPT-Login, also sensible Daten. Wenn du es zusätzlich
woanders ablegst, dann nur verschlüsselt oder auf einem vertrauenswürdigen Speicher.

---

## 7. Abschluss-Check

Hak das ab und melde es dem Nutzer:

- [ ] `docker compose ps`: alles `healthy`
- [ ] Login als Admin klappt (URL im Browser)
- [ ] Admin → ChatGPT: „aktiv“ und „Verbindung testen“ ist grün (oder bewusst „von Hand“ gewählt)
- [ ] Logos werden angezeigt (Mein Bracket öffnen)
- [ ] Chat zeigt „Live verbunden“
- [ ] HTTPS-Zertifikat gültig (falls Domain)
- [ ] Backup-Cron eingerichtet (falls gewünscht)
- [ ] `.env` ist **nicht** im Git (`git status` zeigt sie nicht)

Abschlussnachricht an den Nutzer: URL, Admin-Login (falls noch nicht übergeben) und wie Freunde
dazukommen (Admin → Benutzer). Dazu der Hinweis, dass ChatGPT die Ergebnisse jetzt selbst einträgt
und Unklares unter Admin → ChatGPT → „Prüfung erforderlich“ landet.

---

## Nützliche Befehle

| Zweck | Befehl |
|---|---|
| Logs | `docker compose logs -f backend` |
| Neustart nach `.env`-Änderung | `docker compose up -d` |
| Update | `./scripts/update.sh` (mit HTTPS: `PROD=1 ./scripts/update.sh`) |
| Passwort zurücksetzen | `docker compose exec backend python -m app.cli set-password <user> <neu>` |
| ChatGPT-Status | `docker compose exec backend codex login status` |
| Details | [README.md](README.md), [docs/CHATGPT.md](docs/CHATGPT.md), [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
