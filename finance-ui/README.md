# finance-ui — mmlogistix Finance Operations (SvelteKit)

**Product name:** mmlogistix Finance Operations — CFO / Finance Manager monitoring and oversight (not a task queue).

**Package version:** `0.12.4-finance-dashboard`

| Route | Purpose |
|-------|---------|
| `/dashboard` | Queue depths, cases by status, avg processing time, overdue SLA |
| `/approvals` | Cases & Approvals — all cases with processing time / overdue indicator |
| `/export` | CSV export by date range |
| `/settings/notifications` | Notification preferences |

Authenticated routes use `export const ssr = false` (JWT in `localStorage`).

## Dev setup

```bash
cd finance-ui
npm install
npm run dev
```

Open http://localhost:5173 — Vite proxies API calls to FastAPI on port 8000.

## Routes

| Path | Purpose |
|------|---------|
| `/login` | JWT sign-in |
| `/approvals` | Pending approvals queue |
| `/approvals/{id}` | Approve / reject |
| `/settings/notifications` | Notification preferences |

Host (production): `https://finance.mmlogistix.bp0.work` (API on same origin; no `api.bp0.work`)
