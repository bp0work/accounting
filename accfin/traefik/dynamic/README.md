# Traefik dynamic configuration (`accfin/traefik/dynamic/`)

**Deploy version:** `0.12.1-traefik-routes` (see `app/core/config.py` `version` property).

Mounted read-only at `/etc/traefik/dynamic` (see `docker-compose.yml` → `traefik` service).

| File | Purpose |
|------|---------|
| `api-routes.yml` | Routes API path prefixes on `finance.mmlogistix.bp0.work` to `http://fastapi:8000`. **`rule` must be a single quoted line** (YAML `>-` folded blocks break routing on VPS). Router `finance-api` → service **`finance-api`** (`http.services.finance-api`). Middleware: `security-headers@file`. |
| `security.yml` | Shared `security-headers` middleware (also applied on `websecure` in `traefik.yml`). |

FastAPI has **no** public hostname; the `fastapi` container uses `traefik.enable=false`. After editing `api-routes.yml`, recreate the `traefik` container or wait for the file provider watch.

Authoritative spec: `platform_dox/11_Deployment_Operations_Runbook.md` §5, `14_Environment_and_Configuration_Reference.md` §9.0.
