# Traefik dynamic configuration (`accfin/traefik/dynamic/`)

Mounted read-only at `/etc/traefik/dynamic` (see `docker-compose.yml` → `traefik` service).

## Routing

| Host | Traffic | Router | Priority | Backend |
|------|---------|--------|----------|---------|
| `finance.mmlogistix.bp0.work` | SvelteKit UI (`/`, `/login`, `/dashboard`, `/approvals`, …) | `finance-ui` (Docker labels) | **1** | `finance-ui:3000` |
| `finance.mmlogistix.bp0.work` | `PathPrefix(/api)` | `finance-api` | **100** | `http://fastapi:8000` |
| `admin.mmlogistix.bp0.work` | **Client Admin UI** (all non-API paths) | `client-admin-ui` (Docker labels) | **1** | `client-admin-ui:3000` |
| `admin.mmlogistix.bp0.work` | `PathPrefix(/api)` | `client-admin-api` | **100** | `http://fastapi:8000` |

**Do not** add `PathPrefix(\`/\`)` to API routers — that steals `/` from the UI apps.

**Do not** route `/approvals`, `/cases`, `/company`, etc. to FastAPI — UI apps own those paths; REST uses `/api/...` only (`0.13.12`).

| File | Purpose |
|------|---------|
| `api-routes.yml` | `finance-api` + `client-admin-api` → **`finance-api`** service → `fastapi:8000` |
| `security.yml` | Shared `security-headers` middleware |

After edits: `docker compose up -d --force-recreate traefik`.

See `accfin/docs/CLIENT_ADMIN_UI.md`, `11_Deployment_Operations_Runbook.md` §4.5g, `14_Environment_and_Configuration_Reference.md` §9.0.
