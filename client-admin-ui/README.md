# client-admin-ui

**mmlogistix Client Admin** — tenant configuration at `https://admin.mmlogistix.bp0.work`.

## Auth

- Login: `system.mmlogistix` / `ChangeMeOnFirstLogin!` (seed) — **`client_admin` role only**
- JWT in `localStorage` (`client_admin_access_token`)
- All API calls use `/api/*` prefix

## Routes

| Path | Purpose |
|------|---------|
| `/dashboard` | Configuration completeness checklist |
| `/company` | Tenant company profile |
| `/chart-of-accounts` | COA CSV import + CRUD |
| `/mailboxes` | Executive & manager mailbox display/escalation |
| `/users` | CEO/CFO/Finance/Accounts role emails |
| `/policies` | Expense limits + regulatory documents |
| `/agreements` | Rental + director expense agreements |
| `/travel-requests` | Approve/reject travel pre-approvals |
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

Version: `0.14.0-client-admin-ui`
