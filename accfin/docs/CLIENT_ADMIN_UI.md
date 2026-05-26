# Client Admin UI (`client-admin-ui` + admin API)

**Host:** `https://admin.mmlogistix.bp0.work`  
**Branding:** mmlogistix Client Admin  
**Deploy version:** `0.14.4-gl-period-posting-controls` (`accfin` `GET /api/health` → `version`)  
**Package:** `client-admin-ui/package.json` → `0.14.3-gl-cutoff-reminders` (finance-ui unchanged `0.13.12`)

### GL period posting (`0.14.4`)

- Workers call `assert_period_allows_posting` before journal create (bootstrap if no periods).
- Closed period → manager escalation (`PERIOD_CLOSED`); email approve reprocesses with override.
- `POST /api/accounting-periods/{period_id}/override-post` — body `{ case_id, override_reason }` (CFO / Finance Manager / Client Admin).

## Stack

| Layer | Detail |
|-------|--------|
| UI | SvelteKit 2, `@sveltejs/adapter-node`, `export const ssr = false` |
| Auth | JWT (`client_admin` role only) |
| API | `/api/*` (FastAPI) |

## Accounting calendar (`0.14.3`)

**Settings** (`GET|PATCH /api/admin/accounting-settings` → `system_settings`):

| Key | Values |
|-----|--------|
| `accounting_fye_month` | 1–12 (default 12) |
| `trial_balance_frequency` | `monthly` \| `weekly` |
| `audit_frequency` | `annual` \| `semi_annual` \| `quarterly` |
| `gl_cutoff_working_days` | integer (default 3; also mirrors `gl_posting_cutoff_working_days`) |

**Period generation** (`POST /api/accounting-periods/generate?months=13`):

- Current month + next 12 months (forward)
- `period_type`: `monthly` \| `audit` \| `year_end` from FYE + audit frequency
- GL cutoff = N **working days** after month end (weekends + Singapore public holidays skipped)

**GL close** (`POST /api/accounting-periods/{id}/close`):

- All: trial balance approved first
- `audit`: requires `audit_adjustments_completed`
- `year_end`: requires `year_end_adjustments_completed`
- Optional `auditor_name`, `auditor_firm`, `sign_off_date` → `audit_metadata` JSONB

**GL cutoff reminders** (`gl_cutoff_reminders` table, migration `052`):

| Method | Path |
|--------|------|
| GET | `/api/admin/gl-cutoff-reminders` |
| POST | `/api/admin/gl-cutoff-reminders` |
| PATCH | `/api/admin/gl-cutoff-reminders/{id}` |
| DELETE | `/api/admin/gl-cutoff-reminders/{id}` |

**Cron** (daily 08:00 SGT = 00:00 UTC):

```bash
0 0 * * * curl -s -X POST http://localhost:8000/api/internal/jobs/gl-cutoff-reminders \
  -H "Authorization: Bearer $FINANCE_INTERNAL_CRON__TOKEN" \
  -H "Content-Type: application/json" >> /var/log/gl-cutoff-reminders.log 2>&1
```

- Sender: `acc.mmlogistix@bp0.work` (SMTP)
- Logs: `finance_activity_log` action `gl_cutoff_reminder_sent`

**Dashboard:** “GL reminder recipients” complete when ≥1 active recipient.

## Migrations

| Revision | Summary |
|----------|---------|
| `052` | `gl_cutoff_reminders` |
| `053` | `accounting_periods.period_type`, `audit_metadata` |

## Deploy

```bash
cd accfin
docker compose run --rm fastapi alembic upgrade head   # through 053
docker compose build fastapi client-admin-ui
docker compose up -d --force-recreate traefik fastapi client-admin-ui
curl -s http://localhost:8000/api/health | jq .version
# → "0.14.3-gl-cutoff-reminders"
```

Cross-ref: `platform_dox/06_Database_Schema_Design.md`, `05_API_Specification.md` §19, `11_Deployment_Operations_Runbook.md` §4.5g.
