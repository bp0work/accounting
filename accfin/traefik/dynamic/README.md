# Traefik dynamic configuration (`accfin/traefik/dynamic/`)

Mounted read-only at `/etc/traefik/dynamic` (see `docker-compose.yml` → `traefik` service).

## Routing on `finance.mmlogistix.bp0.work`

| Traffic | Router | Priority | Backend |
|---------|--------|----------|---------|
| `finance.mmlogistix.bp0.work` UI | `finance-ui` (Docker labels) | **1** | `finance-ui:3000` |
| `admin.mmlogistix.bp0.work` UI | `client-admin-ui` (Docker labels) | **1** | `client-admin-ui:3000` |
| `PathPrefix(/api)` on finance or admin host | `finance-api` / `client-admin-api` | **100** | `http://fastapi:8000` |

**Do not** add `PathPrefix(\`/\`)` to `api-routes.yml` — that matches every path and sends `/` to FastAPI instead of the Approval UI.

**Do not** route `/approvals` or `/cases` to FastAPI — the UI owns those paths; REST calls use `/api/approvals`, `/api/cases`, etc.

| File | Purpose |
|------|---------|
| `api-routes.yml` | `Host(finance…) && PathPrefix(\`/api\`)` → **`finance-api`**. |
| `security.yml` | Shared `security-headers` middleware (also on `websecure` in `traefik.yml`). |

FastAPI has **no** public hostname; `fastapi` uses `traefik.enable=false`. After edits, recreate `traefik` and rebuild `finance-ui` / `fastapi` as needed.

Authoritative spec: `platform_dox/11_Deployment_Operations_Runbook.md` §5, `14_Environment_and_Configuration_Reference.md` §9.0.
