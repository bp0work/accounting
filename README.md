# AI Finance Operations Platform — Implementation Monorepo

Runnable code for the bp0.work finance platform. **This repository contains application code only** — no platform specification documents.

| Path | Purpose |
|------|---------|
| `accfin/` | FastAPI API, workers, mail gateway, orchestrator, Hermes, Alembic, Docker Compose |
| `finance-ui/` | Finance Approval UI (SvelteKit) |
| `platform-admin-ui/` | Platform Admin UI (SvelteKit) |
| `client-admin-ui/` | Client Admin UI — `admin.mmlogistix.bp0.work` |

## Quick start

```bash
cd accfin
cp .env.example .env
python3 scripts/generate-keys.py >> .env   # or merge output manually
# Set FINANCE_DATABASE_URL for local Compose (see accfin/README.md)
docker compose up -d db redis
docker compose up -d ollama hermes fastapi
curl -s http://localhost:8000/api/health | jq .
```

See `accfin/README.md` for migrations, compose profiles, and seed users.
