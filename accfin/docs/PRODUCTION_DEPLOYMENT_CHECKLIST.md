# Production Deployment Checklist

Operational go-live checklist for the AI Finance Operations Platform backend (`accfin/`). Authoritative gates: `platform_dox/11_Deployment_Operations_Runbook.md` Appendix **§20.0**.

**Target version:** `0.13.4-ollama-healthcheck-wget` (migrations `001`–`047`; finance-ui `0.13.1-case-retry`)

See `DEPLOYMENT_VERSION_HISTORY.md` for the full deploy timeline (Phase 11b → Traefik → URL structure → routing fixes → branding → client auth).

---

## Gate A — Business sign-off

| # | Item | Owner | Done |
|---|------|-------|------|
| A1 | Compliance sign-off recorded | Compliance | ☐ |
| A2 | CFO sign-off recorded | CFO | ☐ |
| A3 | Business Owner UAT sign-off (`12` UAT-010/011) | Business Owner | ☐ |
| A4 | Technical Lead sign-off | Technical Lead | ☐ |
| A5 | CEO sign-off recorded | CEO | ☐ |

Reference: `01_Business_Requirement_Document.md` Document Governance.

---

## Gate B — Phase acceptance (staging)

| # | Item | Done |
|---|------|------|
| B1 | Phases **1–10** acceptance criteria met in staging | ☐ |
| B2 | Phase **11** Expense Management (MVP) — APIs, worker, policies | ☐ |
| B3 | Phase **11b** Executive Email SOP — `finance_activity_log`, escalations, daily log job | ☐ |
| B4 | Full pytest suite green on staging DB after `alembic upgrade head` | ☐ |

Reference: `03_Cursor_Development_Brief.md` §6.

---

## Gate C — Expense Worker (OBS-3) — production only

| # | Item | Done |
|---|------|------|
| C1 | `worker-expense` uses dedicated `workers/expense/Dockerfile` (not stub) | ☐ |
| C2 | `depends_on`: `hermes` + `redis` with `service_healthy` | ☐ |
| C3 | Resource limits validated under load | ☐ |

Reference: `19_Expense_Worker_Specification.md` §1, §11.

> Staging may run the expense worker stub; **production must not pass Gate C until complete.**

---

## Gate D — Mail transport

| # | Item | Done |
|---|------|------|
| D1 | Mail Gateway polls **IMAP only** (`bp0.work:993` SSL) for `executive_agent` mailboxes | ☐ |
| D1a | `FINANCE_MAIL__POLL_ENABLED: "true"` on `gateway` in `docker-compose.yml`; gateway container rebuilt after deploy | ☐ |
| D1b | Gateway logs show successful poll (no `MissingGreenlet` / SQLAlchemy async errors) | ☐ |
| D2 | Manager mailboxes (`acc`, `fin`, `cfo`, `ceo`) are **not** on intake poller | ☐ |
| D3 | `requires_outbound_client_approval` backfill applied (migration `045`) | ☐ |
| D4 | Escalation / outbound approval emails include `[CAS-…]` in Subject | ☐ |

Reference: `17_Worker_Specifications.md` §2.1.1–§10.

---

## Gate E — Migrations, secrets, and infrastructure

### E1 — Database migrations

```bash
cd accfin && alembic upgrade head
alembic current   # expect head: 20260530_047
```

| Migration band | Purpose |
|----------------|---------|
| `001`–`039` | Core platform through audit |
| `039b` | Expense `case_type` enum |
| `040`–`044` | Expense management |
| `045` | `finance_activity_log`, SOP seeds, notification templates |
| `046` | `case_escalations`, `pending_outbound_emails` |
| `047` | mmlogistix CFO + Finance Manager users (`cfo.mmlogistix`, `finmanager.mmlogistix`) |

### E2 — Required secrets (`.env` from `.env.example`)

| Variable | Purpose |
|----------|---------|
| `FINANCE_DATABASE_URL` | PostgreSQL |
| `FINANCE_REDIS__PASSWORD` | Redis auth |
| `FINANCE_JWT__SECRET` | User sessions |
| `FINANCE_PRIVACY_ENCRYPTION_KEY` | Fernet field encryption |
| `FINANCE_HASH_SECRET` | Audit hash chain |
| `FINANCE_INTERNAL_CRON__TOKEN` | `POST /internal/jobs/finance-daily-log` |
| `FINANCE_MAIL_ACTION__SECRET` | Escalation / outbound signed links |
| `FINANCE_HERMES_API_KEY` | Hermes service auth |
| `FINANCE_WASABI__ACCESS_KEY_ID` / `SECRET_ACCESS_KEY` | Offsite logs (`bp0workacc`) |
| `FINANCE_INTERNAL__API_BASE_URL` | `http://fastapi:8000` (cron; no public API host) |
| `FINANCE_PUBLIC__APP_HOST` | `finance.mmlogistix.bp0.work` |
| `FINANCE_LETS_ENCRYPT_EMAIL` | `system@bp0.work` (Traefik ACME) |

Generate: `python scripts/generate-keys.py`

### E3 — Scheduled jobs

| Job | Schedule | Endpoint |
|-----|----------|----------|
| Finance daily activity digest | **21:00 Asia/Singapore** daily | `POST /internal/jobs/finance-daily-log` |

Example (`11` §17.5):

```bash
curl -sS -X POST \
  -H "Authorization: Bearer ${FINANCE_INTERNAL_CRON__TOKEN}" \
  -H "X-Request-ID: $(uuidgen)" \
  http://fastapi:8000/internal/jobs/finance-daily-log
```

Configure `systemd` timer or host cron; verify idempotent `skipped` on second same-day run.

### E4 — Smoke tests (production)

| # | Check | Expected |
|---|-------|----------|
| E4.1 | `GET /health` (internal or via `https://finance.mmlogistix.bp0.work/health`) | `200`, version `0.13.4-ollama-healthcheck-wget` |
| E4.1b | `GET https://finance.mmlogistix.bp0.work/` | Approval UI (HTML), not FastAPI JSON 404 |
| E4.1c | Browser login → remain signed in >15 min (silent refresh) | Session persists; no redirect to `/login` until refresh token expires (7d) |
| E4.1d | Browser login → `/approvals` | Pending approvals load (client-side auth; not SSR 401) |
| E4.2 | `GET /metrics` (if enabled) | Prometheus scrape OK |
| E4.3 | Login + `GET /mail/status` | Executive/manager mailbox counts |
| E4.4 | Cron job (dry run with `force=true` in staging only) | CSV path + `row_count` |
| E4.5 | Expense worker health `:8014/health` | Healthy after Gate C |

### E5 — Explicit exclusions

| # | Item | Done |
|---|------|------|
| E5.1 | No prototype Admin UI on port **8080** in production | ☐ |
| E5.2 | Traefik v2.11; `GET /` → finance-ui; `api-routes.yml` API prefixes only (priority 100); finance-ui priority 1 | ☐ |
| E5.2a | DNS `finance.mmlogistix.bp0.work` → VPS; TLS valid (`system@bp0.work`) | ☐ |
| E5.3 | Wasabi `logs/finance_daily_{date}.csv` upload verified (when credentials live) | ☐ |
| E5.4 | SMTP digest to `FINANCE_DAILY_LOG_RECIPIENT` verified (when mail transport live) | ☐ |

---

## Post-deploy sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Technical Lead | | | |
| DevOps | | | |
| CFO (operational) | | | |

---

## Related documents

| Document | Topic |
|----------|--------|
| `DEPLOYMENT_VERSION_HISTORY.md` | Deploy version timeline |
| `11_Deployment_Operations_Runbook.md` §17.5, §20.0 | Gates, compose, daily log |
| `traefik/dynamic/README.md` | API path routing on finance host |
| `05_API_Specification.md` §8.8a, §19.1 | Escalation + cron APIs |
| `06_Database_Schema_Design.md` §7.4–§7.6 | SOP tables |
| `17_Worker_Specifications.md` §10 | Executive email SOP |
| `12_Testing_and_UAT_Strategy.md` §11.3 | UAT-010/011 |
