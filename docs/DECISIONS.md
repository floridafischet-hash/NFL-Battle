# Technische Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| 1 | **Eingebaute Benutzerverwaltung statt Keycloak** (Benutzername + Passwort, vom Admin angelegt) | Ausdrücklicher Wunsch: privates Tippspiel unter Freunden, keine sensiblen Daten, möglichst einfacher Betrieb. Trotzdem: Passwörter als PBKDF2-SHA256-Hash, Login-Rate-Limit, signierte Tokens, sofortige Sperre/Abmeldung über `token_version`. Ein späterer Umstieg auf OIDC wäre in `app/core/security.py` gekapselt. |
| 2 | **FastAPI + SQLAlchemy 2 (async) + psycopg 3** | Async passt zu WebSockets; psycopg 3 kann sync (Alembic) und async (App, LISTEN). |
| 3 | **Realtime über PostgreSQL LISTEN/NOTIFY** | Keine zusätzliche Infrastruktur (Redis); funktioniert mit mehreren Backend-Replikas; Events werden erst nach COMMIT zugestellt. |
| 4 | **Ein Spiel = ein Bracket-Slot (13 pro Saison)** | Tipps, Lock, Ergebnisse, Änderungsanträge und Punkte hängen alle an genau einem Datensatz – einfach und eindeutig. |
| 5 | **NFL-Reseeding** in der Bracket-Engine | Entspricht den echten NFL-Regeln (Seed 1 gegen schlechtesten verbliebenen Seed). Die Bracket-Linien werden deshalb dynamisch aus der Herkunft jedes Teams gezeichnet. |
| 6 | **„Living Bracket“**: Tipps sind pro Spiel bis zum Lock änderbar | Ein Tippbaum wird vor den Playoffs komplett gebaut, ausgeschiedene Teams können bis zum jeweiligen Kickoff ersetzt werden. Ändert man einen Tipp, werden darauf aufbauende, offene Tipps automatisch bereinigt. |
| 7 | **Exakter Endstand ersetzt die Siegerpunkte** (max(Sieger, Exakt)) | Entspricht dem Beispiel aus der Anforderung („Dennis 🎯 +3“). Werte pro Saison konfigurierbar. |
| 8 | **Endstand-Tipp als Sieger-/Verliererpunkte gespeichert** | Robust, wenn sich die Paarung erst später ergibt (Tipp gehört zum Sieger, nicht zu Heim/Gast). |
| 9 | **Fremde Tipps erst nach dem Tipp-Lock sichtbar** (pro Spiel) | Verhindert Abschreiben vollständig; abgeleitete Paarungen fremder Brackets werden nur aus aufgedeckten Tipps berechnet. Vorher sieht man nur, *ob* jemand getippt hat. |
| 10 | **Punkte idempotent neu berechnet** (`scores` mit Unique-Constraint) | Keine Doppelvergabe; Korrekturen und Änderungen am Punktesystem jederzeit sauber nachrechenbar. |
| 11 | **ChatGPT im Backend statt externer Agent-API** (Standard: ChatGPT-Abo über die offizielle Codex CLI, alternativ OpenAI Responses API; Websuche; Domain-Allowlist, nur belegte Quellen, 2 Bestätigungen) | Ausdrücklicher Wunsch: Ergebnisse per ChatGPT, OpenClaw-Zugang entfernt. Kein eingehender Maschinen-Zugang mehr ⇒ kleinere Angriffsfläche. Die Antwort des Modells gilt als unsichere Eingabe: Schema, belegte Quellen, übereinstimmende Seiten; Unsicheres landet als REVIEW_REQUIRED beim Admin, gewertete Spiele werden nie automatisch überschrieben. Kostenbremse über Tageslimit. |
| 12 | **Audit-Log append-only per DB-Trigger** | Auch ein Fehler im Code kann Protokolleinträge nicht verändern oder löschen. |
| 13 | **Uploads neu kodiert (Pillow → WebP), kein SVG** | Entfernt Metadaten und verhindert Script-Injection über Bilddateien. |
| 14 | **Offizielle Team-Logos per `logo_url` vom ESPN-Logo-CDN**, neutrale Wappen als Fallback | Ausdrücklicher Wunsch (privater Gebrauch). Die Logos werden nur verlinkt, nicht im Repository gespeichert; fällt das CDN aus, zeigt das Frontend das generierte Wappen. Jedes Logo ist im Admin austauschbar. |
| 15 | **Next.js als Client-App mit React Query** | Daten kommen aus der API; gezielte Cache-Invalidierung per WebSocket statt Reloads; `output: standalone` für kleine Images. |
| 16 | **Eine Domain mit Pfad-Routing (Nginx), TLS über Traefik** | Keine CORS-/Cookie-Probleme; Traefik übernimmt Let's Encrypt automatisch. |
| 17 | **Migrationen als eigener One-Shot-Dienst** | Sauberer Start, Kubernetes-tauglich (Job/initContainer). |
| 18 | **Platzhalter-Secrets werden beim ersten Start sicher erzeugt** | `cp .env.example .env && docker compose up -d` funktioniert sofort, ohne bekannte Standardpasswörter. `scripts/generate-secrets.sh` für feste Werte. |
| 19 | **Scheduler im Backend mit Advisory-Lock** | Auto-Lock und Erinnerungen ohne zusätzlichen Cron-Container; läuft bei mehreren Replikas nur einmal. |
| 20 | **Stadion-Hintergrund und Wappen prozedural generiert** | Keine Bildrechte-Probleme; Skripte liegen in `scripts/` und sind reproduzierbar. |

## Bekannte Grenzen

- Rollen- oder Passwortänderungen wirken sofort; eine Abmeldung „aller Geräte“ gibt es nur über die Passwortänderung.
- Rate-Limits im Backend gelten pro Instanz (Nginx limitiert zusätzlich pro IP).
- Die Demo-Daten liegen zeitlich relativ zum Installationszeitpunkt. Nach einigen Tagen sind die offenen Demo-Spiele gesperrt und warten auf Ergebnisse.
- Der ChatGPT-Agent braucht ein ChatGPT-Abo (Plus/Pro, Login über die Codex CLI) oder einen OpenAI-API-Key; ohne werden Ergebnisse manuell eingetragen. Das Abo-Kontingent ist begrenzt (Tageslimit in der App).
- Push-Benachrichtigungen außerhalb der App (E-Mail/Mobile Push) sind nicht umgesetzt; Benachrichtigungen erscheinen in der App (Glocke, Chat).
