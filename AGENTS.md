# Hinweise für KI-Agenten

- **App installieren / aufsetzen?** Folge [SETUP_AGENT.md](SETUP_AGENT.md) und stell zuerst die Rückfragen aus Abschnitt 1.
- **Am Code arbeiten?** Backend: `cd backend && ruff check . && ruff format --check . && pytest`
  (braucht `TEST_DATABASE_URL`, siehe [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)). Frontend: `cd frontend && npm run typecheck && npm test`.
  Ende-zu-Ende: `./scripts/e2e.sh`.
- **Niemals Geheimnisse committen**: `.env`, API-Keys, `auth.json` aus `/data/codex`. CI scannt die gesamte Historie.
- Schemaänderungen nur über Alembic-Migrationen (`backend/alembic/versions`).
