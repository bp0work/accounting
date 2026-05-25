# client-admin-ui

**mmlogistix Client Admin** — tenant configuration at `https://admin.mmlogistix.bp0.work`.

**Version:** `0.14.1-client-admin-ui`  
**Authoritative spec:** `accfin/docs/CLIENT_ADMIN_UI.md`

## Stack

- SvelteKit 2 + `@sveltejs/adapter-node`
- JWT auth — **`client_admin` role only**
- All API calls via `/api/*` (`apiUrl()` in `src/lib/api/client.ts`)
- `export const ssr = false` — tokens in `localStorage`

## Auth

- Login: `system.mmlogistix` / `ChangeMeOnFirstLogin!` (seed)
- Tokens: `client_admin_access_token`, `client_admin_refresh_token`
- Single-step login: username + password + optional TOTP (“Leave blank if 2FA is not enabled”)

## Navigation

Dashboard | Company | Chart of Accounts | Mailboxes | Users | Policies | Agreements | Travel Requests | Accounting Calendar | Logout

## Routes

| Path | Purpose |
|------|---------|
| `/dashboard` | Configuration completeness checklist |
| `/company` | Company profile |
| `/chart-of-accounts` | COA CSV import + CRUD |
| `/mailboxes` | Mailbox display name & escalation email |
| `/users` | CEO / CFO / Finance Manager / Accounts Manager emails |
| `/policies` | Expense limits + regulatory documents |
| `/agreements` | Rental + director expense agreements |
| `/travel-requests` | Approve/reject travel requests |
| `/accounting-calendar` | GL periods, trial balance, close |

## Dev

```bash
npm install
npm run dev   # http://localhost:5174 — proxies /api → FastAPI :8000
```

## Deploy

```bash
cd accfin
docker compose build client-admin-ui fastapi
docker compose up -d --force-recreate traefik client-admin-ui fastapi
```
