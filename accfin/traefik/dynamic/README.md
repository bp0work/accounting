# Traefik dynamic configuration (`accfin/traefik/dynamic/`)

**Deploy version:** `0.13.6-finance-security-2fa` (see `app/core/config.py` and `docs/DEPLOYMENT_VERSION_HISTORY.md`).

Mounted read-only at `/etc/traefik/dynamic` (see `docker-compose.yml` → `traefik` service).

## Routing on `finance.mmlogistix.bp0.work`

| Traffic | Router | Priority | Backend |
|---------|--------|----------|---------|
| `/` and SvelteKit pages (`/login`, `/approvals`, …) | `finance-ui` (Docker labels) | **1** | `finance-ui:3000` |
| API path prefixes only (see below) | `finance-api` (`api-routes.yml`) | **100** | `http://fastapi:8000` |

**Do not** add `PathPrefix(\`/\`)` to `api-routes.yml` — in Traefik that matches every path and sends `/` to FastAPI instead of the Approval UI.

| File | Purpose |
|------|---------|
| `api-routes.yml` | Single-line `rule` with explicit API prefixes only (`/auth`, `/mail`, `/approvals`, …). Router `finance-api` → service **`finance-api`**. No root path. |
| `security.yml` | Shared `security-headers` middleware (also on `websecure` in `traefik.yml`). |

FastAPI has **no** public hostname; `fastapi` uses `traefik.enable=false`. After edits, recreate `traefik` and `finance-ui`.

Authoritative spec: `platform_dox/11_Deployment_Operations_Runbook.md` §5, `14_Environment_and_Configuration_Reference.md` §9.0.
