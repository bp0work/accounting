# finance-ui — mmlogistix Finance (SvelteKit)

**Product name:** mmlogistix Finance (Approval UI). See `platform_dox/15_Approval_UI_Specification.md`.

**Package version:** `0.12.3-client-auth`

Authenticated routes (`/approvals`, `/settings/*`) set `export const ssr = false` so API calls run in the browser with the JWT from `localStorage`.

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
