# client-admin-ui — Client Admin (SvelteKit)

**Status: not implemented** — placeholder for the tenant configuration application.

## Purpose

Standalone app for the **Client System Administrator** only:

- Login: **`system.mmlogistix@bp0.work`** (`client_admin` role)
- Host (target): `https://admin.mmlogistix.bp0.work`

## Planned scope (authoritative spec: `platform_dox/15` §8.13–§8.18)

| Route | Configuration |
|-------|----------------|
| `/mailboxes` | Role email addresses & From names — CEO, CFO/FD, Manager Accounts (`acc`), Manager Finance (`fin`), executives |
| `/chart-of-accounts` | COA import (CSV/XLSX) — **required** before agents can post journals |
| `/company` | Legal name, address, registration (SOA / documents) |
| `/email-signature` | Outbound email footer for all executive mail |
| `/branding` | Client logo |
| `/expense-policy` | Travel & expense rules |

Client Admin **cannot** change their own login email (Platform Admin UI only).

## Dependencies

- Backend: `POST /chart-of-accounts/import`, `GET`/`PUT /tenant/profile`, mail config APIs — specified in `05` §4.16b; **not yet in `accfin`**
- See also `Product_Overview.md` §9.1, `13` §5.9, `17` §5.1.1 (COA prerequisite for STP)
