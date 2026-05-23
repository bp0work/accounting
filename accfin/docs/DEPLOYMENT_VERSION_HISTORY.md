# Deployment version history (`accfin/` + `finance-ui/`)

Authoritative smoke-test version: `GET /health` → `version` from `app/core/config.py`.  
Finance-ui package version: `finance-ui/package.json`.

| Deploy version | Date | Git (main) | Summary |
|----------------|------|------------|---------|
| **0.12.8-finance-token-refresh** | 2026-05-20 | *(pending)* | finance-ui silent JWT refresh: store access + refresh in `localStorage`; proactive `POST /auth/refresh` within 2 min of expiry; redirect `/login` on failure. Package `0.12.5-finance-token-refresh`. |
| **0.12.7-ollama-extraction** | 2026-05-20 | `e3e0a1f` | Hermes Ollama extraction (`qwen2.5:7b`): `/extract/invoice`, `/extract/expense-claim`, `/extract/document-text`; mailbox-first classification (`accar`/`accap`/`accexp`); PDF text at ingest via pypdf. |
| **0.12.6-gateway-imap-poller** | 2026-05-20 | `0669e6f` | Mail Gateway: enable `FINANCE_MAIL__POLL_ENABLED` in compose; fix IMAP poller async SQLAlchemy sessions (`gateway/imap/poller.py` — per-mailbox `async with session_factory()`, plain IMAP settings for `asyncio.to_thread`). Migration head `20260530_047`. |
| **0.12.5-finance-dashboard** | 2026-05-22 | `51b30d4` | Finance oversight UI: dashboard, all-cases list, CSV `GET /cases/export`, branding **mmlogistix Finance Operations**. finance-ui `0.12.4-finance-dashboard`. |
| **0.12.4-client-auth** | 2026-05-22 | `353f9a9`, `4adfb9d` | finance-ui: `ssr = false` on authenticated routes; `goto()` after login (`localStorage` JWT). |
| **0.12.3-mmlogistix-branding** | 2026-05-20 | `dc3d0b0` | Product name **mmlogistix Finance** (replaces LogiScore Finance). finance-ui `0.12.2-mmlogistix-branding`. |
| **0.12.2-traefik-ui-root** | 2026-05-20 | `d354943` | `/` → finance-ui (priority 1); API prefixes only in `api-routes.yml` (no `PathPrefix('/')`). |
| **0.12.1-traefik-routes** | 2026-05-20 | `9eb45a8`, `eed8255`, `1a45276` | `traefik/dynamic/api-routes.yml`: `finance-api` service; single-line `rule`. |
| **0.12.0-url-structure** | 2026-05-20 | `a2531e0` | MVP host `finance.mmlogistix.bp0.work` (UI + edge API); FastAPI internal only; no `api.bp0.work`. |
| *(infra, same API)* | 2026-05-19 | `51b0652` | Traefik Docker label `traefik.docker.network=accfin_frontend`. |
| *(infra, same API)* | 2026-05-19 | `eccf320` | Traefik **v2.11** (VPS Docker API incompatible with v3). |
| *(infra, same API)* | 2026-05-19 | `8a8564e` | Production Traefik HTTPS, Let's Encrypt, finance-ui + fastapi routing (superseded by 0.12.0+). |
| **0.11.0-phase11b** | 2026-05-19 | `43430d2` | Phase 11b: executive email SOP, migrations `045`–`046`, daily log job, escalations. |

**Spec alignment:** `platform_dox/11` v2.23+, `14` v2.20+, `04` v2.8+, `17` v2.11+, `15` v2.14+, `05` v1.3.12+, `00` v2.41+.

**Production checklist:** `PRODUCTION_DEPLOYMENT_CHECKLIST.md` (Gate E).
