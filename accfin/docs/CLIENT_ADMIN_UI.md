# Client Admin UI (`client-admin-ui` + admin API)

**Host:** `https://admin.mmlogistix.bp0.work`  
**Branding:** mmlogistix Client Admin  
**Deploy version:** `0.14.1-client-admin-ui` (`accfin` `GET /api/health` → `version`)  
**Package:** `client-admin-ui/package.json` → `0.14.1-client-admin-ui`

## Stack

| Layer | Detail |
|-------|--------|
| UI | SvelteKit 2, `@sveltejs/adapter-node`, `export const ssr = false` on layout/pages |
| Auth | JWT (`client_admin` role only); optional TOTP on single login form |
| API | All browser calls use `/api/*` (FastAPI mounted at `/api`) |
| Tokens | `localStorage`: `client_admin_access_token`, `client_admin_refresh_token` |

**Login (seed):** `system.mmlogistix` / `ChangeMeOnFirstLogin!` — rotate on first use.

## Navigation (header)

Dashboard | Company | Chart of Accounts | Mailboxes | Users | Policies | Agreements | Travel Requests | Accounting Calendar | Logout

Layout reads `client_admin_access_token` reactively on route change so nav appears immediately after login (`0.14.1`).

## UI routes

| Path | Purpose |
|------|---------|
| `/login` | Username, password, optional TOTP |
| `/dashboard` | Configuration completeness checklist |
| `/company` | Company profile (`tenant_profiles`) |
| `/chart-of-accounts` | COA CSV import, add/edit/deactivate |
| `/mailboxes` | Executive + manager mailboxes (display name, escalation email) |
| `/users` | CEO / CFO / Finance Manager / Accounts Manager emails |
| `/policies` | Expense limits; regulatory document list |
| `/agreements` | Rental agreements; director expense agreements |
| `/travel-requests` | Approve/reject travel pre-approvals |
| `/accounting-calendar` | GL periods, trial balance approve, GL close |

## Traefik (`accfin/traefik/dynamic/api-routes.yml`)

| Router | Rule | Priority | Backend |
|--------|------|----------|---------|
| `client-admin-ui` | `Host(admin.mmlogistix.bp0.work)` | **1** | `client-admin-ui:3000` (Docker labels) |
| `client-admin-api` | `Host(admin.mmlogistix.bp0.work) && PathPrefix(/api)` | **100** | `http://fastapi:8000` |
| `finance-ui` | `Host(finance.mmlogistix.bp0.work)` | **1** | `finance-ui:3000` |
| `finance-api` | `Host(finance.mmlogistix.bp0.work) && PathPrefix(/api)` | **100** | `http://fastapi:8000` |

## Backend API (`require_client_admin` — `tenant:admin` / `client_admin` role)

All paths prefixed with `/api` in production.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/dashboard` | Configuration completeness |
| GET, PATCH | `/tenants/{id}/profile` | Company profile |
| GET, POST, PATCH | `/coa` | Chart of accounts |
| POST | `/coa/import` | CSV import (`account_code`, `account_name`, `account_type`, `parent_code`) |
| GET, PATCH | `/mail/configuration` | List mailboxes |
| PATCH | `/mail/configuration/{id}` | Display name, escalation email (credentials masked) |
| GET, PATCH | `/users` | Key role holder emails |
| PATCH | `/users/{id}` | Update email / display name |
| GET, PATCH | `/expense-policies/limits` | Meal/transport/accommodation/per diem/entertainment limits |
| GET, POST | `/agreements/rental` | Rental agreements |
| GET, POST | `/agreements/director-expense` | Director expense agreements |
| GET, PATCH | `/travel-requests/{id}` | Travel request list / status |
| GET | `/accounting-periods` | Accounting periods table |
| GET | `/accounting-periods/settings` | GL cutoff working days |
| POST | `/accounting-periods/generate` | Generate periods |
| POST | `/accounting-periods/{id}/approve-trial-balance` | finfa / client_admin |
| POST | `/accounting-periods/{id}/close` | Finance Manager / client_admin |
| GET, POST | `/regulatory-documents` | Metadata; Wasabi path `transactions/regulatory/{filename}` |

Implementation: `accfin/app/api/routes/admin.py`.

## Migrations

| Revision | Summary |
|----------|---------|
| `20260531_049` | `tenant_profiles`, `accounting_periods`, `rental_agreements`, `director_expense_agreements`, `regulatory_documents` |
| `20260531_050` | Seed tenant profile, CEO user, role emails, `gl_posting_cutoff_working_days` |

## Deploy (VPS)

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin
docker compose run --rm fastapi alembic upgrade head
docker compose build fastapi client-admin-ui
docker compose up -d --force-recreate traefik fastapi client-admin-ui
curl -s http://localhost:8000/api/health | jq .version
```

## Dev

```bash
cd client-admin-ui && npm install && npm run dev
# http://localhost:5174 — vite proxies /api → http://localhost:8000
```

Cross-ref: `platform_dox/15_Approval_UI_Specification.md` §8.13, `14_Environment_and_Configuration_Reference.md` §9.0, `11_Deployment_Operations_Runbook.md` §4.5g.
