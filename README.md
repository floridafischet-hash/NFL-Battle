# 🏈 NFL Bracket Battle

**Dein privates NFL-Playoff-Tippspiel für die Jungs (und Mädels).**

Jeder klickt sich seinen kompletten Playoff-Baum zusammen, von der Wild Card bis zum Super Bowl.
Nach jedem Spiel sucht **ChatGPT** das Endergebnis raus, die Punkte werden verteilt, die Rangliste
springt um und der **NFL Bot** kommentiert das Ganze im Chat. Und am Ende landet einer in der
Hall of Fame. 🏆

![Dashboard](docs/screenshots/dashboard.jpg)

| Mein Bracket | Bracket-Vergleich | Hall of Fame |
|---|---|---|
| ![Bracket](docs/screenshots/bracket.jpg) | ![Vergleich](docs/screenshots/compare.jpg) | ![Hall of Fame](docs/screenshots/hall-of-fame.jpg) |

> 🤖 **Du lässt das von einem KI-Agenten aufsetzen?** Dann gib ihm die Datei
> **[SETUP_AGENT.md](SETUP_AGENT.md)**. Da steht drin, was er tun soll und was er dich vorher fragen muss.

---

## Was kann das Ding?

- **Bracket per Klick**: Logo anklicken, der Sieger rückt automatisch weiter (mit echtem NFL-Reseeding).
  Den Endstand kannst du optional mittippen und gibst ihn per Klick ab.
- **Tipp-Lock**: Zum Kickoff ist Schluss. Vorher sieht keiner die Tipps der anderen, Abschreiben
  ist also nicht drin. 😏
- **Punkte**: richtiger Sieger, exakter Endstand und Champion-Bonus, alles im Admin einstellbar.
- **ChatGPT trägt die Ergebnisse ein**: über **dein ChatGPT-Abo (Plus/Pro)**, ohne API-Key.
  Es sucht live auf NFL.com, ESPN & Co., und erst wenn zwei Seiten dasselbe sagen, wird gewertet.
- **Live-Chat** mit Bildern und Emojis. Der **NFL Bot** postet Paarungen, Kickoffs, Endstände,
  Punkte, die neue Rangliste und erinnert an fehlende Tipps.
- **Rangliste, Statistiken, Bracket-Vergleich, Hall of Fame** und die ewige Tabelle.
- **Offizielle Teamlogos** (werden direkt geladen, nicht im Repo gespeichert).
- **Adminbereich**: Benutzer, Saisons, Teams, Drag & Drop fürs Bracket-Setup, Ergebnisse,
  Änderungsanträge, ChatGPT-Status und ein Audit-Log, das sich nicht manipulieren lässt.
- **Als App aufs Handy**: Auf Android erscheint „App installieren“ direkt auf dem Dashboard, auf dem iPhone geht's über Teilen → „Zum Home-Bildschirm“. Dann startet das Tippspiel im Vollbild mit eigenem Icon.
- **Begrüßung mit König 👑**: Oben auf dem Dashboard wirst du begrüßt, und daneben thront der Vorjahressieger. Name und Titel stellt der Admin unter **Admin → Übersicht → Begrüßung & König** ein.

---

## In 5 Minuten am Laufen

Was du brauchst: einen Rechner oder Server mit **Docker** (Engine 24+, Compose 2.24+), 2 GB RAM, ein paar GB Platz.

```bash
git clone https://github.com/floridafischet-hash/NFL-Battle.git nfl-bracket-battle
cd nfl-bracket-battle
cp .env.example .env
./scripts/generate-secrets.sh     # würfelt sichere Passwörter in die .env
docker compose up -d
```

Fertig. Die App läuft unter **http://localhost:8080** (bzw. `http://<dein-server>:8080`).
Der erste Start dauert ein paar Minuten, weil die Images gebaut werden.

**Wo sind die Passwörter?**

```bash
docker compose logs migrate
# Initialer Admin: Benutzername 'admin', Passwort '…'
```

`docker compose ps` sollte überall `healthy` zeigen. `migrate` steht danach auf `exited (0)`,
das ist so gewollt.

### ChatGPT verbinden (mit deinem Pro- oder Plus-Abo)

Einmal auf dem Server ausführen:

```bash
docker compose exec backend codex login --device-auth
```

Dir wird ein Link plus Code angezeigt. Öffne den Link am Handy oder Laptop, melde dich mit deinem
ChatGPT-Account an und gib den Code ein. Das war's. Danach im Admin unter **ChatGPT → „Verbindung
testen“** kurz checken, ob alles grün ist.

Was dahintersteckt: Die App nutzt die offizielle **Codex CLI** von OpenAI. Die kann sich mit deinem
ChatGPT-Abo anmelden und nutzt dann dessen Kontingent (inklusive Live-Websuche, also immer aktuelle
Ergebnisse). Die Login-Daten liegen im Daten-Volume unter `/data/codex` und **nie im Git**. Lieber
API-Key statt Abo? Geht auch, siehe [docs/CHATGPT.md](docs/CHATGPT.md).

Ohne Login ist ChatGPT einfach aus, und du trägst die Ergebnisse unter **Admin → Spiele** selbst ein.

### Mit eigener Domain und HTTPS

```bash
# in der .env:
DOMAIN=tippspiel.deine-domain.de
ACME_EMAIL=du@deine-domain.de
PUBLIC_URL=https://tippspiel.deine-domain.de

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Traefik holt sich das Let's-Encrypt-Zertifikat automatisch. Voraussetzung: Die Domain zeigt auf
den Server, und die Ports 80 und 443 sind offen. Hast du schon einen anderen Reverse-Proxy? Dann
lass das Overlay weg, setz `HTTP_BIND=127.0.0.1` und leite auf `127.0.0.1:8080` weiter
(WebSockets für `/ws` durchlassen!).

---

## So läuft eine Saison

1. **Admin → Saisons & Punkte**: Saison anlegen (z. B. `2026/2027`) und Punkte festlegen.
2. **Admin → Bracket-Setup**: Teams per Drag & Drop auf die Seeds 1–7 ziehen → *Speichern* →
   **„Wild Card erzeugen“**.
3. **Admin → Saisons**: Saison **aktivieren**.
4. **Admin → Spiele**: Kickoff-Zeiten eintragen. Der Tipp-Lock setzt sich automatisch.
5. Alle tippen unter **Mein Bracket** und geben ab.
6. Nach den Spielen trägt ChatGPT die Ergebnisse ein (oder du unter Admin → Spiele). Punkte,
   Rangliste, Bot-Nachricht und die nächste Runde laufen dann von allein.
7. Nach dem Super Bowl geht's ab in die **Hall of Fame**.

Falsches Ergebnis? *„Ergebnis korrigieren“*, und die Punkte werden neu berechnet.
Punktesystem geändert? **Saisons → „Punkte neu berechnen“**.

---

## Benutzer

- **Admin → Benutzer → „Benutzer anlegen“**: Name, Passwort und Rolle (Spieler oder Admin). Kein
  Keycloak, kein Schnickschnack.
- **Nur du als Inhaber** (der Admin aus `ADMIN_USERNAME`, der die Instanz aufsetzt) darfst Benutzer
  anlegen, Passwörter zurücksetzen, Rollen ändern und sperren. Weitere Admins können Saisons, Spiele
  und Ergebnisse verwalten, aber keine Benutzer.
- Jeder kann im **Profil** Namen, Avatar und Passwort ändern.
- Ausgesperrt? `docker compose exec backend python -m app.cli set-password admin NeuesPasswort`
  (außerdem gibt's `create-admin` und `list-users`).

---

## Einstellungen (`.env`)

Die wichtigsten Variablen. Alle anderen sind in [.env.example](.env.example) kommentiert.

| Variable | Standard | Wofür |
|---|---|---|
| `PUBLIC_URL` | `http://localhost:8080` | Adresse der App |
| `HTTP_PORT` | `8080` | Port, falls 8080 schon belegt ist |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / zufällig | erster Admin |
| `SEED_DEMO_DATA` | `false` | `true` = Demo-Saisons, Demo-Spieler und Chat zum Rumprobieren. Standard: leere Instanz |
| `RESULT_AGENT_PROVIDER` | `chatgpt` | `chatgpt` = dein Abo (Codex-Login), `openai_api` = API-Key |
| `CODEX_MODEL` | leer | optional: bestimmtes Modell für dein Abo |
| `OPENAI_API_KEY` | leer | nur für `openai_api`, **geheim** |
| `RESULT_AGENT_MAX_CALLS_PER_DAY` | `40` | Bremse, damit ChatGPT nicht durchdreht |
| `AGENT_TRUSTED_DOMAINS` | nfl.com, espn.com, … | auf diesen Seiten wird gesucht |
| `AGENT_MIN_CONFIRMATIONS` | `2` | so viele Seiten müssen übereinstimmen |
| `DOMAIN` / `ACME_EMAIL` | – | für HTTPS |

Nach Änderungen einfach `docker compose up -d`.
**Die `.env` enthält Geheimnisse und gehört niemals ins Git** (steht deshalb auch in `.gitignore`).

---

## Sicherheit, kurz und knapp

- Passwörter werden nur gehasht gespeichert. Wer zu oft daneben tippt, wird gesperrt, aber nur
  der Angreifer und nicht dein Kumpel.
- Keine Geheimnisse im Repo. CI scannt jeden Push und die komplette Git-Historie nach Keys.
- Von außen gibt es keinen Maschinen-Zugang: ChatGPT läuft im Backend, und seine Antworten werden
  wie unsichere Eingaben behandelt. Es zählen nur Quellen, die wirklich besucht wurden, und zwei
  Seiten müssen übereinstimmen. Alles Unklare landet bei dir zur Prüfung.
- Uploads werden geprüft und neu kodiert. Security-Header, CSP und Rate-Limits sind dabei.
- Tipp: Stell das GitHub-Repo auf **privat** (Settings → General → Danger Zone).

Mehr Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/CHATGPT.md](docs/CHATGPT.md) ·
[docs/API.md](docs/API.md) · [docs/DECISIONS.md](docs/DECISIONS.md)

---

## Backup, Restore, Update

```bash
./scripts/backup.sh                          # → backups/<zeitstempel>/ (behält die letzten 14)
./scripts/restore.sh backups/20270210-031500
./scripts/update.sh                          # Backup → git pull → neu bauen → Neustart
PROD=1 ./scripts/update.sh                   # dasselbe mit HTTPS-Overlay
```

Jede Nacht automatisch sichern (crontab):

```cron
15 3 * * * cd /opt/nfl-bracket-battle && ./scripts/backup.sh >> backups/backup.log 2>&1
```

Im Backup stecken die Datenbank, die Uploads, der ChatGPT-Login und die `.env`. Bewahr es also
gut auf und kopier es am besten zusätzlich woanders hin.

---

## Logos & Hintergrund

- Standardmäßig gibt's die **offiziellen Teamlogos**. Sie werden direkt geladen und liegen nicht
  im Repo, gedacht für den privaten Spaß. Lädt ein Logo mal nicht, springt ein neutrales Wappen
  in Teamfarben ein.
- Eigenes Logo? **Admin → Teams → Logo hochladen** oder eine URL eintragen.
- Anderer Stadion-Hintergrund? `frontend/public/stadium.jpg` austauschen.

---

## Wenn's hakt

| Problem | Lösung |
|---|---|
| Passwort vergessen | `docker compose exec backend python -m app.cli set-password admin NeuesPasswort` |
| ChatGPT trägt nichts ein | Admin → ChatGPT: Steht da „nicht angemeldet“? Dann `docker compose exec backend codex login --device-auth`. Ansonsten Fehler beim letzten Lauf anschauen oder prüfen, ob das Tageslimit erreicht ist. |
| Ergebnis hängt bei „Prüfung erforderlich“ | ChatGPT war sich unsicher. Kurz die Quellen-Links checken, dann „Übernehmen“ oder „Verwerfen“. |
| „Offline“ statt „Live“ im Chat | Dein Reverse-Proxy lässt keine WebSockets für `/ws` durch. |
| Alle nach Neustart ausgeloggt | `SECRET_KEY` geändert oder Volume gelöscht. Am besten fest in die `.env` schreiben. |
| `set POSTGRES_PASSWORD in .env` | `.env` fehlt → `cp .env.example .env` |
| Port 8080 belegt | `HTTP_PORT=8090` in die `.env` |
| Let's Encrypt klappt nicht | Zeigt die DNS auf den Server? Ist Port 80 offen? Mehr steht in `docker compose logs traefik`. |
| Logs | `docker compose logs -f backend` (oder `frontend`, `nginx`, `db`) |

---

## Für Entwickler

```bash
# Tests
cd backend && TEST_DATABASE_URL="postgresql+psycopg://postgres:test@localhost:5433/nfl_test" pytest
cd frontend && npm test && npm run typecheck
./scripts/e2e.sh        # komplette Saison im frischen Stack, ChatGPT dabei gemockt
```

Stack: Next.js 16 + React 19 + Tailwind 4 vorne, FastAPI + SQLAlchemy 2 + PostgreSQL 16 hinten,
WebSockets über PostgreSQL LISTEN/NOTIFY, Docker Compose + Nginx + Traefik. Lokale Entwicklung,
Datenbank/Migrationen und Kubernetes: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md), Architektur:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Viel Spaß beim Tippen, und möge der bessere Bracket gewinnen! 🏈
