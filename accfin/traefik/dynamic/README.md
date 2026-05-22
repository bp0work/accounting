# Traefik dynamic configuration (`accfin/traefik/dynamic/`)

Mounted read-only at `/etc/traefik/dynamic` (see `docker-compose.yml` → `traefik` service).

| File | Purpose |
|------|---------|
| `api-routes.yml` | Routes API path prefixes on `finance.mmlogistix.bp0.work` to `http://fastapi:8000`. Router `finance-api` must reference service **`fastapi-service`** (same key under `http.services`). |
| `security.yml` | Shared `security-headers` middleware (also applied on `websecure` in `traefik.yml`). |

FastAPI has **no** public hostname; the `fastapi` container uses `traefik.enable=false`. After editing `api-routes.yml`, reload Traefik or recreate the `traefik` container.
