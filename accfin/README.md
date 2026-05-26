# accfin — Backend & infrastructure

FastAPI, domain workers, mail gateway, workflow orchestrator, Hermes, and Docker Compose for the finance platform.

## Phase 1 — complete

PostgreSQL (`db`), Redis, Ollama, Hermes stub, FastAPI `GET /health`. Traefik: `docker compose --profile proxy up -d`.

## Phase 2 — Auth & RBAC (current)

Alembic migrations `001`–`006d`: roles, permissions, users, refresh tokens, password history, system admins, tenants.

```bash
# Apply migrations (host, with db exposed on 5432)
export FINANCE_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres
alembic upgrade head
alembic current

# Or inside Compose
docker compose run --rm fastapi alembic upgrade head
```

**Seed logins** (password `ChangeMeOnFirstLogin!` — change immediately):

| Username | Email | Role |
|----------|-------|------|
| `system` | `system@bp0.work` | platform_admin |
| `system.mmlogistix` | `system.mmlogistix@bp0.work` | client_admin (tenant: mmlogistix) |
| `cfo.mmlogistix` | `cfo.mmlogistix@bp0.work` | cfo (tenant: mmlogistix) |
| `finmanager.mmlogistix` | `fin.mmlogistix@bp0.work` | finance_manager (tenant: mmlogistix) |

## Local environment

1. `cp .env.example .env`
2. `python3 scripts/generate-keys.py` — fill `[REQUIRED]` secrets
3. **Local Compose database** (default in `docker-compose.yml`):

   ```bash
   FINANCE_DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/postgres
   POSTGRES_PASSWORD=postgres
   FINANCE_REDIS__HOST=redis
   FINANCE_REDIS__PASSWORD=<from generate-keys>
   ```

4. **Supabase Cloud** (production): use connection string from Supabase dashboard (`FINANCE_DATABASE_URL`).

## Compose

```bash
# Infrastructure smoke (M01 §0.5)
docker compose up -d db redis
docker compose ps

# Phase 1 stack
docker compose up -d ollama hermes fastapi

# With Traefik (Phase 1 acceptance — routing)
docker compose --profile proxy up -d

# Health
curl http://localhost:8000/api/health
```

## Layout

Monorepo services: `gateway/`, `orchestrator/`, `workers/`, `hermes/`, `fastapi` app under `app/`. See `docker-compose.yml`.
