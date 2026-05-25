# Client Admin UI (`client-admin-ui` + admin API)

**Host:** `https://admin.mmlogistix.bp0.work`  
**Branding:** mmlogistix Client Admin  
**Deploy version:** `0.14.2-client-admin-fixes` (`accfin` `GET /api/health` → `version`)  
**Package:** `client-admin-ui/package.json` → `0.14.2-client-admin-fixes`

## Stack

| Layer | Detail |
|-------|--------|
| UI | SvelteKit 2, `@sveltejs/adapter-node`, `export const ssr = false` on layout/pages |
| Auth | JWT (`client_admin` role only); optional TOTP on single login form |
| API | All browser calls use `/api/*` (FastAPI mounted at `/api`) |
| Tokens | `localStorage`: `client_admin_access_token`, `client_admin_refresh_token` |

**Login (seed):** `system.mmlogistix` / `ChangeMeOnFirstLogin!` — rotate on first use.

## Navigation (header)

Dashboard | Company | Chart of Accounts | Mailboxes | Users | Travel & Expense Policy | Agreements | Travel | Accounting Calendar | Logout

- **Travel** (`/travel-info`) — documentation only; no in-app travel approval (email workflow).
- `/travel-requests` redirects to `/travel-info`.

## UI routes

| Path | Purpose |
|------|---------|
| `/login` | Username, password, optional TOTP |
| `/dashboard` | Live configuration completeness (per-section detail text) |
| `/company` | Company profile + HTML/plain email signature |
| `/chart-of-accounts` | Empty-state banner + CSV upload; searchable table when populated |
| `/mailboxes` | Display names / escalation; IMAP/SMTP note (platform admin for credentials) |
| `/users` | CEO → CFO → Finance Manager (fin) → Accounts Manager (acc) |
| `/policies` | Travel & expense policy PDF + expense limits; regulatory PDF catalog |
| `/travel-info` | How employees submit travel via `accexp.mmlogistix@bp0.work` |
| `/agreements` | Rental + director expense agreements |
| `/accounting-calendar` | Generate current + 12 months; Approve TB / Close GL |

## Traefik (`accfin/traefik/dynamic/api-routes.yml`)

| Router | Rule | Priority | Backend |
|--------|------|----------|---------|
| `client-admin-ui` | `Host(admin.mmlogistix.bp0.work)` | **1** | `client-admin-ui:3000` (Docker labels) |
| `client-admin-api` | `Host(admin.mmlogistix.bp0.work) && PathPrefix(/api)` | **100** | `http://fastapi:8000` |

## Backend API (`require_client_admin`)

All paths prefixed with `/api` in production.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/dashboard` | Completeness checks (company, signature, COA, mailboxes, users, policy PDF, limits, regulatory×5, calendar×13) |
| GET, PATCH | `/tenants/{id}/profile` | Company profile + `email_signature_html` / `email_signature_plain` |
| GET | `/coa/status` | Account count / empty flag |
| GET, POST, PATCH | `/coa` | Chart of accounts |
| POST | `/coa/import` | CSV import |
| GET, PATCH | `/mail/configuration` | Mailboxes |
| GET, PATCH | `/users` | Four role holders (fixed order) |
| GET, PATCH | `/expense-policies/limits` | Numeric expense limits |
| GET, POST | `/expense-policies/document` | Travel policy PDF → `transactions/regulatory/travel-expense-policy.pdf` |
| GET | `/expense-policies/document/download` | Download policy PDF |
| GET | `/regulatory-documents/catalog` | Five regulatory slots + upload status |
| POST | `/regulatory-documents?document_key=` | Upload regulatory PDF (Wasabi + metadata) |
| GET | `/regulatory-documents/{id}/download` | Download regulatory PDF |
| GET, POST | `/agreements/rental`, `/agreements/director-expense` | Agreements |
| GET | `/accounting-periods` | Period list |
| POST | `/accounting-periods/generate?months=13` | Current month + next 12 (forward) |
| POST | `/accounting-periods/{id}/approve-trial-balance` | Approve TB |
| POST | `/accounting-periods/{id}/close` | Close GL |

Implementation: `accfin/app/api/routes/admin.py`, storage: `accfin/app/services/regulatory_storage.py`.

## Migrations

| Revision | Summary |
|----------|---------|
| `20260531_049` | Client Admin tables |
| `20260531_050` | Seed tenant profile, CEO, settings |
| `20260531_051` | `email_signature_*` on `tenant_profiles`; `document_key` on `regulatory_documents` |

## Deploy (VPS)

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin
docker compose run --rm fastapi alembic upgrade head   # through 051
docker compose build fastapi client-admin-ui
docker compose up -d --force-recreate traefik fastapi client-admin-ui
curl -s http://localhost:8000/api/health | jq .version
# → "0.14.2-client-admin-fixes"
```

Cross-ref: `platform_dox/15_Approval_UI_Specification.md` §8.13, `11_Deployment_Operations_Runbook.md` §4.5g.
