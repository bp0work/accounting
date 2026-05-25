# AI Finance Operations Platform — Implementation Monorepo

Runnable code for the bp0.work finance platform. **Push this folder only** to GitHub (`bp0work/accounting`).

| Path | Purpose |
|------|---------|
| `accfin/` | FastAPI API, workers, mail gateway, orchestrator, Hermes, Alembic, Docker Compose |
| `finance-ui/` | Approval UI (SvelteKit) — Phase 9 |
| `platform-admin-ui/` | Platform Admin UI — Phase 2+ |
| `client-admin-ui/` | Client Admin UI — `0.14.1` @ `admin.mmlogistix.bp0.work` (see `accfin/docs/CLIENT_ADMIN_UI.md`) |

## Specifications

Authoritative design docs live in sibling **`../platform_dox/`** (not committed here). Start with:

- `../platform_dox/cursor_master_development_prompt.md`
- `../platform_dox/03_Cursor_Development_Brief.md`

## Phase 1 — Quick start

```bash
cd accfin
cp .env.example .env
python3 scripts/generate-keys.py >> .env   # or merge output manually
# Set FINANCE_DATABASE_URL for local Compose (see accfin/README.md)
docker compose up -d db redis
docker compose up -d ollama hermes fastapi
curl -s http://localhost:8000/health | jq .
```

Full bootstrap: `../platform_dox/cursor_prompt/M01_workspace_and_bootstrap.md`.

## Development phases

Implement **Phase 1 → 11** in order (`03` §6, `M05`). Current status: **Phase 1** infrastructure scaffold.
