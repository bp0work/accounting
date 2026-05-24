# Deployment version history (`accfin/` + `finance-ui/`)

Authoritative smoke-test version: `GET /health` → `version` from `app/core/config.py`.  
Finance-ui package version: `finance-ui/package.json`.

| Deploy version | Date | Git (main) | Summary |
|----------------|------|------------|---------|
| **0.13.7-worker-blpop-idle-fix** | 2026-05-20 | `beef354` | `QueueConsumer` default BLPOP block timeout 5s (`workers/base.py`) — reduces idle CPU spin on empty queues (accounts, AR, AP, expense). |
| **0.13.6-finance-security-2fa** | 2026-05-20 | `9d3fac0` | finance-ui `/settings/security`: 2FA setup (QR via `qrcode`), verify, disable; mandatory-2FA banner for `cfo`/`finance_manager`. Retry button on case detail. Package `0.13.3-security-2fa`. Feature `47c0f57`. |
| **0.13.5-ollama-healthcheck-cli** | 2026-05-20 | `6927279` | Ollama Docker healthcheck: `ollama list` via bundled CLI (image has neither `curl` nor `wget`). Supersedes `0.13.4` wget attempt. Feature `e99848b`. |
| **0.13.4-ollama-healthcheck-wget** | 2026-05-20 | `a405f86` | *(superseded)* Ollama healthcheck used `wget` — unavailable in image. Compose fix `d6bd61d`. |
| **0.13.3-case-retry-hermes-timeout** | 2026-05-20 | `8b2475d` | Hermes client default timeout 120s (slow Ollama CPU). `POST /cases/{id}/retry` requeues `exception`/`manual_review` to `accounts_queue`; Retry button on case detail. finance-ui `0.13.1-case-retry`. Feature `8d049a1`. |
| **0.13.2-case-visibility** | 2026-05-20 | `0286578` | Case timeline audit trail on detail page; error reason + processing stage on list/dashboard; dedupe Message-ID only. finance-ui `0.13.0-case-dashboard`. |
| **0.13.1-mail-text-sanitize** | 2026-05-20 | `be0d1e0` | Sanitize all mail text fields at ingest (`body_text`, `body_html`, `body_preview`, `subject`, `extracted_text`) — strip NUL and invalid UTF-8 before PostgreSQL insert. |
| **0.13.0-executive-mail-sop** | 2026-05-20 | `4bf72a5` | Manager-first processing failure escalation (`ExecutiveMailService`); sender ack with `[CAS-…]` after case_number; failure notify only on manager reject; `finance_activity_log` at ingest/classify/workers. |
| **0.12.9-mail-pdf-sanitize** | 2026-05-20 | `a4717ce` | Strip NUL bytes from PDF `extracted_text` before DB insert (`sanitize_extracted_text` in ingest + email_context). Fixes PostgreSQL `CharacterNotInRepertoireError`. |
| **0.12.8-finance-token-refresh** | 2026-05-20 | `2dfe475` | finance-ui silent JWT refresh: store access + refresh in `localStorage`; proactive `POST /auth/refresh` within 2 min of expiry; redirect `/login` on failure. Package `0.12.5-finance-token-refresh`. |
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
