# AI Finance Operations Platform

# Approval UI Specification

## Version 2.32

## Filename: 15_Approval_UI_Specification.md

## Prepared For: mmlogistix

## Date: 25 May 2026

---

# Companion Documents


| Document                              | Filename                                      |
| ------------------------------------- | --------------------------------------------- |
| Project Overview                      | 00_Project_Overview.md                        |
| Business Requirements                 | 01_Business_Requirement_Document.md           |
| Technical Architecture                | 02_Technical_Architecture.md                  |
| Cursor Development Brief              | 03_Cursor_Development_Brief.md                |
| Hermes Integration Specification      | 04_Hermes_Integration_Spec.md                 |
| API Specification                     | 05_API_Specification.md                       |
| Database Schema                       | 06_Database_Schema_Design.md                  |
| AI Runtime Sequences                  | 07_AI_Runtime_Sequence_Diagrams.md            |
| Workflow State Machine                | 08_Workflow_State_Machine.md                  |
| Event Model                           | 09_Event_Model_Specification.md               |
| Policy Engine                         | 10_Policy_Engine_Specification.md             |
| Deployment Runbook                    | 11_Deployment_Operations_Runbook.md           |
| Testing Strategy                      | 12_Testing_and_UAT_Strategy.md                |
| Security & Compliance Specification   | 13_Security_and_Compliance_Specification.md   |
| Environment & Configuration Reference | 14_Environment_and_Configuration_Reference.md |
| Approval UI Specification             | 15_Approval_UI_Specification.md               |
| Migration and ORM Specification       | 16_Migration_and_ORM_Specification.md         |
| Worker Specifications                 | 17_Worker_Specifications.md                   |
| Notification Service Specification    | 18_Notification_Service_Specification.md      |
| Expense Worker Specification          | 19_Expense_Worker_Specification.md            |
| Git Workflow and Prompt Management    | 20_Git_Workflow_and_Prompt_Management.md      |
| OpenAPI Contract                      | 21_openapi.yaml                               |


---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [Repository Boundary](#2-repository-boundary)
3. [Information Architecture](#3-information-architecture)
4. [Authentication & Session](#4-authentication--session)
5. [RBAC & Segregation of Duties (UI)](#5-rbac--segregation-of-duties-ui)
6. [API Consumption Map](#6-api-consumption-map)
7. [Real-Time Updates (SSE)](#7-real-time-updates-sse)
8. [Screen Specifications](#8-screen-specifications)
9. [States, Errors & Empty UX](#9-states-errors--empty-ux)
10. [PII, Security & Client Hardening](#10-pii-security--client-hardening)
11. [Accessibility & i18n Baseline](#11-accessibility--i18n-baseline)
12. [Testing Expectations](#12-testing-expectations)
13. [Frontend Architecture Reference](#13-frontend-architecture-reference)
14. [Out of Scope (MVP)](#14-out-of-scope-mvp)

---

## 1. Purpose & Scope

This document specifies the **Approval UI** for the AI Finance Operations Platform: the human-facing application used to review cases, act on approval requests, view audit-oriented timelines, and receive operational alerts. It is the UI counterpart to **Phase 9** in `00_Project_Overview.md` §5.1.

**Normative sources (do not duplicate here):**

- REST contracts: `05_API_Specification.md` (especially §3 Authentication, §4.13–4.18 Notifications, §5 Cases, §6 Workflow Engine, §7 Approvals, §14 Audit Logs as referenced in API TOC). Phase 11 expense-claim endpoints are fully specified in `05_API_Specification.md` §18 (incorporated in `05` v1.0.3); `19_Expense_Worker_Specification.md` §1 remains authoritative for worker-side processing.
- Persistence: `06_Database_Schema_Design.md` §3.6–3.8 (`notification_templates`, `user_notification_preferences`, `notifications` inbox).
- Workflow guards and statuses: `08_Workflow_State_Machine.md`.
- Real-time channel semantics: `09_Event_Model_Specification.md` §15 (SSE).
- Controls and segregation: `13_Security_and_Compliance_Specification.md`.
- Environment and feature flags: `14_Environment_and_Configuration_Reference.md`.
- Phase 11 expense claim submission flow: `19_Expense_Worker_Specification.md` §1 and §4.

This spec defines **screens, navigation, client behaviour, and API/SSE usage patterns**. Request/response JSON schemas remain authoritative in `05`.

---

## 2. Repository Boundary

The Approval UI MUST be implemented as a **separate client application** (recommended: **SvelteKit**) in its **own repository**, consuming only the published **REST API** and **SSE** endpoints documented in `05` and `09`.

- **No business rules** in the UI beyond presentation validation (required fields, max lengths). Tier selection, posting eligibility, and GM/COO restrictions are enforced by the API, database, state machine, and policy engine (`03_Cursor_Development_Brief.md` §7).
- **No duplication** of policy or accounting logic in the frontend; the UI reflects server decisions and surfaces errors clearly.

Deployment and TLS between browser → Traefik → Approval UI follow `11_Deployment_Operations_Runbook.md`.

**Production URL:** `https://finance.mmlogistix.bp0.work` (`FINANCE_PUBLIC__APP_HOST`, `14` §9.0). The UI calls the REST API on the **same origin** (Traefik forwards API paths to internal `http://fastapi:8000`). There is **no** public `api.bp0.work` hostname.

### 2.1 Product branding (MVP shell)

| Element | Value |
|---------|--------|
| **Product name** | **mmlogistix Finance Operations** |
| **Implementation** | `finance-ui/src/lib/branding.ts` → `APP_TITLE`; used in root `+layout.svelte` header and `<title>`; login screen subtitle |
| **Deprecated** | ~~LogiScore Finance~~ — do not use in Approval UI copy |

Aligns with notification templates (`18` §10: `platform_name` / `from_name` **mmlogistix Finance**). Rebuild `finance-ui` image after branding changes (`package.json` version `0.12.2-mmlogistix-branding`).

### 2.1a Oversight scope (CFO / Finance Manager)

The UI is a **monitoring and oversight dashboard**, not a personal approval task queue. Primary routes:

| Route | Purpose |
|-------|---------|
| `/dashboard` | Queue depths, cases by status, average processing time, overdue (SLA) cases |
| `/approvals` (label: **Cases & Approvals**) | All cases with processing time and overdue indicator |
| `/export` | CSV download via `GET /cases/export?date_from=&date_to=` |
| `/settings/notifications` | Preferences |

Backend: `GET /cases/dashboard`, `GET /cases` (extended fields), `GET /cases/export` (`cases:read`). Case detail retry: `POST /cases/{id}/retry` (`cases:write`) when status is `exception` or `manual_review`. **Security:** `/settings/security` — `POST /auth/2fa/setup`, `POST /auth/2fa/verify`, `POST /auth/2fa/disable`; package `0.13.3-security-2fa`.

### 2.2 Client-side auth (MVP)

JWT is stored in **`localStorage`** (`finance_access_token`). Authenticated pages (`/approvals`, `/approvals/[id]`, `/settings/notifications`, `/`) MUST export **`export const ssr = false`** so data loads only in the browser (SSR cannot read `localStorage`). After login, use SvelteKit **`goto()`** — not `window.location` — to preserve the SPA session. Post-MVP: httpOnly cookie for SSR-safe auth (`13` §5).

---

## 3. Information Architecture

### 3.1 Primary routes (logical)


| Route                     | Purpose                                                                                                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/login`                  | Authenticate; optional 2FA step per `05` §3.                                                                                                                                    |
| `/dashboard`              | Summary widgets: pending approvals for current user, SLA at-risk, optional case counts (if permitted).                                                                          |
| `/approvals`              | Queue of approval requests; filters: `my_pending`, `status`, `tier`, `case_id` (maps to `GET /approvals`).                                                                      |
| `/approvals/{id}`         | Approval detail with linked case summary and primary actions (approve / reject / delegate if allowed).                                                                          |
| `/cases`                  | Searchable case list (`GET /cases`); supports `needs_approval` and other filters from `05` §5.4.                                                                                |
| `/cases/{id}`             | Case workspace: metadata, attachments (via signed URLs or embed rules from API), timeline (`GET /cases/{id}/timeline`), notes, approval panel.                                  |
| `/cases/{id}/audit`       | Read-only audit-oriented view (subset of timeline + links to audit API if exposed); permission `audit-logs:read` or as defined in `05`/`13`.                                    |
| `/settings/notifications` | User notification preferences (Phase 9 DB scope — see `06` §18.4 migrations `034`–`036`).                                                                                       |
| `/settings/security`      | 2FA setup/disable flows calling `05` §3.4–3.6.                                                                                                                                  |
| `/counterparty-accounts`  | **Finance setup (`e73c869`).** Subaccounts, payment terms catalog, GST tax codes — `15` §8.22.                                                                                  |
| `/agreements`             | **Finance setup.** Rental + director expense agreements — §8.23.                                                                                                                |
| `/accounting-calendar`    | **Finance setup.** GL settings, periods, TB approve/close, reopen, cutoff reminders — §8.24.                                                                                |
| `/expense-claims/new`     | **Phase 11.** Expense claim submission form (see §8.7). Calls `POST /expense-claims` (`19` §1). Only visible to authenticated employees with `expenses:write` permission. |
| `/expense-claims`         | **Phase 11.** List of the current user's submitted expense claims and their statuses.                                                                                           |
| `/finance/dashboard`      | **Financial Analyst** (`financial_analyst`). Expense, cost, and revenue summary widgets (`reports:read`). Default landing when role has no pending approvals.                  |
| `/finance/reports`       | Financial statements and management reports (P&L, balance sheet, trial balance) — `reports:read`.                                                                               |
| `/finance/month-end`      | Month-end close checklist, period status, and close actions — `month-end:read` / `month-end:write`.                                                                            |


Exact path strings MAY be adjusted for the SvelteKit app as long as **deep links** to case and approval IDs remain stable for email deep links and bookmarks.

### 3.2 Navigation rules

- After login, default landing: `**/approvals`** with `my_pending=true` for users with `approvals:read` and pending items; `**/finance/dashboard**` for `financial_analyst` when no approval queue applies; otherwise `**/cases**` with role-appropriate defaults.
- **Header nav (`e73c869`):** Dashboard | Cases & Approvals | Counterparty accounts | Agreements | Accounting calendar | Export | Notifications | Security | Logout.
- **Breadcrumb** pattern: `Approvals > CAS-…` or `Cases > CAS-… > Approval`.

---

## 4. Authentication & Session


| Concern       | Requirement                                                                                                                                                                                                                                   |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Transport** | All calls over HTTPS; cookies (if used) `Secure`, `HttpOnly`, `SameSite` per `13`.                                                                                                                                                            |
| **Tokens**    | Bearer JWT from `POST /auth/login` (see `05` §3). **MVP implementation (`0.12.5-finance-token-refresh`):** store `access_token` and `refresh_token` in `localStorage` (`finance-ui/src/lib/api/client.ts`). Login via `setTokens()` in `login/+page.svelte`. |
| **Expiry**    | Before each API call, if access JWT `exp` is within **2 minutes**, silently `POST /auth/refresh` with refresh token (7-day lifetime). On refresh failure, clear tokens and redirect to `/login`. Also retry once on `401`. |
| **2FA**       | If API returns `TOTP_REQUIRED` (alias `2FA_REQUIRED` in UI), show a **second step** on `/login`: 6-digit TOTP field appears only after step 1; resubmit with `username`, `password`, and `totp_code`. No TOTP field on initial load. |
| **Logout**    | Call `POST /auth/logout` then clear client state and EventSource connections.                                                                                                                                                                 |


---

## 5. RBAC & Segregation of Duties (UI)

The UI MUST align with `00_Project_Overview.md` §2.4 and `13_Security_and_Compliance_Specification.md`:


| Role (example codes)                  | UI capability                                                                                                                                                                                                                                                         |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cfo`                                 | Full financial approval actions for Tier 3 (BRD: CFO / Finance Director); visibility into escalations.                                                                                                                                                                |
| `finance_officer` / `finance_manager` | Tier-appropriate approvals per `06` seeds; no admin override unless permission granted.                                                                                                                                                                               |
| `general_manager`                     | **No** financial approval buttons for journal/posting/write-off paths; **operational** views only (communications, escalations) as permitted by `05` permissions. Hide or disable controls server would reject; never rely on hide-only—server remains authoritative. |
| `readonly` / `auditor`                | Read-only screens; no POST approve/reject.                                                                                                                                                                                                                            |
| `platform_admin`                      | **Platform Admin UI only** (`15` §8.12) — separate app; no finance routes.                                                                                                                                                                                            |
| `client_admin`                        | **Client Admin UI only** (`15` §8.13) — separate app; no finance or platform routes.                                                                                                                                                                                  |
| `financial_analyst`                   | **Analysis and period close** (`15` §8.3): expense/cost/revenue views, financial statements, month-end closing. Read-heavy; may post adjusting journals during close (`journal-entries:write`) but **no** financial approval actions (`approvals:approve` absent). |


**Role codes:** JWT / `users.role` align with `06` §19.1 (`cfo`, `finance_manager`, `financial_analyst`, …). Tier 3 UI gates use the **`cfo`** slug consistently with `05` approval configuration.

**Permission-driven rendering:** derive menu entries and action buttons from JWT `permissions` array (`05` §3.1). If permission missing, omit control and avoid leaking existence of restricted actions via disabled tooltips that reveal sensitive workflow names to unauthorized users (use generic “insufficient permission” where needed).

---

## 6. API Consumption Map

Base URL prefix per `05`: `**/api/v1/`** (prepend to paths below).


| User goal                               | Method & path (see `05`)                            | Notes                                                                                                                                                              |
| --------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Login / refresh / logout / 2FA          | §3 `/auth/...`                                      | Handle standardized error envelopes from `05` §16.                                                                                                                 |
| List my pending approvals               | `GET /approvals?my_pending=true`                    | §7.2                                                                                                                                                               |
| List approvals with filters             | `GET /approvals`                                    | `status`, `tier`, `case_id`, `requested_from`                                                                                                                      |
| Approval detail                         | `GET /approvals/{id}`                               | §7.3                                                                                                                                                               |
| Approve                                 | `POST /approvals/{id}/approve`                      | §7.4 — require comment when API requires                                                                                                                           |
| Reject                                  | `POST /approvals/{id}/reject`                       | §7.5                                                                                                                                                               |
| Delegate                                | `POST /approvals/{id}/delegate`                     | §7.6 — only if permitted                                                                                                                                           |
| Escalate                                | `POST /approvals/{id}/escalate`                     | §7.8                                                                                                                                                               |
| Admin override                          | `POST /approvals/{id}/override`                     | §7.7 — `approvals:admin` only                                                                                                                                      |
| List cases                              | `GET /cases`                                        | §5.4 — pagination cursor                                                                                                                                           |
| Case detail                             | `GET /cases/{id}`                                   | §5.5                                                                                                                                                               |
| Case timeline                           | `GET /cases/{id}/timeline`                          | §5.11 — primary audit narrative for approvers                                                                                                                      |
| Add note                                | `POST /cases/{id}/notes`                            | §5.12                                                                                                                                                              |
| Case status change (if exposed to role) | `POST /cases/{id}/status`                           | §5.8 — respect transition matrix `08`                                                                                                                              |
| Case retry (exception / manual review)  | `POST /cases/{id}/retry`                            | §5.8a — `cases:write`; requeues to `accounts_queue` (`0.13.3`)                                                                                                   |
| 2FA setup                               | `POST /auth/2fa/setup`                              | §3.4 — returns `qr_code_uri` (otpauth)                                                                                                                           |
| 2FA verify                              | `POST /auth/2fa/verify`                             | §3.5 — `{ totp_code, secret }`                                                                                                                                   |
| 2FA disable                             | `POST /auth/2fa/disable`                            | §3.6 — `{ totp_code }`                                                                                                                                           |
| Workflow SLA summary                    | `GET /workflow/sla-summary`                         | §6.6 — dashboard                                                                                                                                                   |
| Active workflows                        | `GET /workflow/active`                              | §6.1                                                                                                                                                               |
| Dashboard statistics                    | `GET /cases/statistics`                             | §5.14 — if role may view aggregates                                                                                                                                |
| Notification prefs (self)               | `GET /users/me/notification-preferences`            | `05` §4.13                                                                                                                                                         |
| Notification prefs (self)               | `PUT /users/me/notification-preferences`            | `05` §4.14                                                                                                                                                         |
| Notification catalog                    | `GET /notification-templates`                       | `05` §4.15 — populate settings form                                                                                                                                |
| Notification template (admin)           | `PATCH /admin/notification-templates/{template_id}` | `05` §4.16 — `settings:write` only                                                                                                                                 |
| In-app notification inbox               | `GET /notifications`                                | `05` §4.17 — poll on reconnect or page focus; use `unread_count` to drive the notification bell badge; pass `is_read=false` to show unread only                    |
| Mark notifications read                 | `POST /notifications/read`                          | `05` §4.18 — call with `mark_all: true` when user opens the notification drawer, or with `notification_ids` for individual dismissal                               |
| **Phase 11** Submit expense claim       | `POST /expense-claims`                              | `19` §1 — employees submit claims; body includes `category`, `amount`, `currency`, `receipt_date`, `merchant`, `purpose`, and optional `attachment_ids`. See §8.7. |
| **Phase 11** List own expense claims    | `GET /expense-claims?claimant_id=me`                | `19` §1 — filter to current user's claims; cursor-paginated.                                                                                                       |
| **Phase 11** Expense claim detail       | `GET /expense-claims/{id}`                          | `19` §1 — includes `risk_flags`, `policy_violations`, line items, and linked case.                                                                                 |


Pagination: follow cursor model from `05` §1.4; UI must load next pages without dropping filters.

---

## 7. Real-Time Updates (SSE)


| Item               | Specification                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Endpoint**       | `GET /api/v1/events/stream` with `Authorization: Bearer` (exact path per `09` §15.1 and `05` if prefixed).                                                                                                                                                                                                                                                                                                     |
| **Client**         | Use `EventSource` or polyfill; single connection per logged-in session unless design requires scoped streams.                                                                                                                                                                                                                                                                                                  |
| **Reconnect**      | On error or disconnect, exponential backoff (e.g. 1s → 30s cap); **re-fetch** affected lists (`/approvals`, `/cases`) on reconnect to heal missed events (idempotent merge by IDs).                                                                                                                                                                                                                            |
| **Event handling** | Map SSE `event` + `data` JSON to UI stores per `09` §15.2–15.3 (`case.created`, `case.status_changed`, `approval.requested`, `approval.approved`, `approval.rejected`, `approval.delegated`, `approval.sla_at_risk`, `approval.escalated`, etc.). On `approval.delegated`, update the approvals queue immediately — the item should disappear from the original approver's queue and appear in the delegate's. |
| **Filtering**      | Server filters by role (`09` §15.4); client still validates user still has access before navigating to a case from an event payload.                                                                                                                                                                                                                                                                           |
| **AI streaming**   | Optional: if the product shows token-level AI reasoning in the case view, follow streaming guidance in `07_AI_Runtime_Sequence_Diagrams.md` and any dedicated streaming sub-endpoint in `05`—do not invent ad-hoc WebSocket paths not in spec.                                                                                                                                                                 |


---

## 8. Screen Specifications

### 8.1 Login & 2FA

- Fields: username, password; **TOTP code only after step 1** when `POST /auth/login` returns `401` with `error.code` = `TOTP_REQUIRED` (`05` §3).
- Step 1: submit `{ username, password }`. On success → store tokens and redirect.
- Step 2: show 6-digit authenticator input (`type="text"`, `maxlength="6"` — no HTML `pattern` or `inputmode` to avoid browser format-validation errors); submit `{ username, password, totp_code }`. Field hidden on initial page load.
- Changing username or password after step 1 resets the TOTP step (user must re-authenticate credentials).
- Display lockout / rate-limit messages without revealing whether an account exists (generic copy per `13`).
- **Shipped:** `finance-ui@0.13.5-login-totp-input-fix` (TOTP input); two-step flow from `0.13.4-login-2fa-step` — `login/+page.svelte`, `lib/api/auth.ts`.

### 8.2 Approvals queue (`/approvals`)

- Columns: case number, subject/title, type, tier, amount + currency, SLA badge (`on_track` / `at_risk` / `breached`), risk flags, created time.
- Row click → `/approvals/{id}` or combined case+approval view.
- Sticky filters; preserve in query string for shareability.

### 8.3 Financial Analyst role & workspace

**Role code:** `financial_analyst` (`06` §19.1). **Operational mailbox:** `finfa.mmlogistix@bp0.work` (Finance Analyst — §8.9 mailbox table).

**Purpose:** Users in this role focus on **analysing expenses, cost, and revenue**, **generating financial statements**, and **performing month-end closing**. They work in the Approval UI finance area, not in Platform Admin or Client Admin apps.

**Segregation:** No `approvals:approve` — analysts prepare and analyse; Tier 2/3 approvers (`finance_officer`, `finance_manager`, `cfo`) remain authoritative for financial sign-off (`13` §5.7). Analysts may use `journal-entries:write` only for month-end adjusting entries and close-related postings as defined in the month-end workflow (`month-end:write`).

#### 8.3.1 Finance dashboard (`/finance/dashboard`)

**Permission:** `reports:read`

**Widgets (MVP — consume existing APIs where available):**

| Widget | Data source | Notes |
|--------|-------------|-------|
| Expense summary | `GET /expense-claims` aggregates, `GET /cases/statistics` | By category, period, policy violations (`expenses:read`) |
| Cost / spend trends | `GET /journal-entries` filtered by expense accounts | Requires `journal-entries:read` |
| Revenue / AR snapshot | `GET /cases` + AR open items via case types | Read-only; links to case workspace |
| Period selector | Client state | Defaults to current open accounting period |

#### 8.3.2 Financial reports (`/finance/reports`)

**Permission:** `reports:read`

**Reports to expose (implement when `05` reporting endpoints are available; until then show “API pending” stub with read-only trial balance export if `GET /journal-entries` suffices):**

- Profit & loss (income statement)
- Balance sheet
- Trial balance
- Expense analysis by category / cost centre

**Behaviour:** Export CSV/PDF when API provides signed URLs; no client-side recalculation of GL balances.

#### 8.3.3 Month-end close (`/finance/month-end`)

**Permissions:** `month-end:read` (view); `month-end:write` (execute close steps)

**UI:**

- Checklist: bank reconciliation complete, all cases in terminal states for period, accruals posted, sub-ledgers tied to GL (items sourced from `05` month-end API when implemented; interim checklist may be manual with sign-off timestamps).
- **Close period** action (destructive confirm): requires `month-end:write`; calls `POST /finance/periods/{period_id}/close` (to be added in `05` — post-MVP endpoint; document contract here for Cursor).
- **Reopen period** (if permitted): `cfo` or `finance_manager` only — hide from `financial_analyst` even if API would allow.

**Navigation:** Primary sidebar section **Finance** with Dashboard, Reports, Month-end — visible when any of `reports:read`, `month-end:read` is present.

### 8.4 Approval detail

- Show **case summary** (counterparty, amounts, confidence if permitted, document links).
- **Primary actions**: Approve, Reject (secondary destructive styling).
- **Secondary**: Delegate, Escalate per permissions.
- **SLA**: display `sla_deadline` as an absolute timestamp with locale formatting. When `approval.sla_at_risk` is received via SSE, switch the SLA display to a live countdown using `minutes_remaining` from the event payload (decrement client-side every minute; re-sync from a fresh `GET /approvals/{id}` on reconnect). Apply a warning colour/badge when `percent_remaining <= 50`; apply an urgent/error colour when `percent_remaining <= 20`. Clear the warning state if an `approval.approved`, `approval.rejected`, or `approval.delegated` event arrives for the same `approval_id`. See `09` §8.6 for the full payload definition and emission rules.
- **Risk flags** as chips with tooltips from controlled vocabulary (no raw unescaped HTML from API).

### 8.5 Case workspace (`/cases/{id}`)

- Tabs or sections: **Overview**, **Documents / attachments**, **Timeline**, **Notes**, **Approvals** (nested list for case).
- **Manual review details (`0.13.6-manual-review-detail`):** When `status` is `manual_review` or `on_hold`, render a panel from `GET /cases/{id}` → `workflow_metadata`:
  - `extraction_confidence` (formatted to 2 decimals)
  - `missing_fields` (bulleted list; humanize underscores)
  - `extracted_fields` (key/value table: invoice number, date, vendor, amount, etc.)
- `status_reason` / `error_reason` from API also surface missing-field summary when present.
- Timeline uses `timeline[].event_type` from `05` §5.11; render human-readable labels from a client-side map keyed by `event_type`.
- Attachment download: use URLs returned by API; never guess storage paths.

### 8.6 Notification preferences (`/settings/notifications`)

- Load catalog via `GET /notification-templates` (`05` §4.15); load current prefs via `GET /users/me/notification-preferences` (`05` §4.13); save with `PUT` (`05` §4.14). Admin template text/defaults use `PATCH /admin/notification-templates/{template_id}` (`05` §4.16) only when the session has `settings:write`.
- Gate the screen behind `FINANCE_`* feature flags from `14` if the API is not deployed in a given environment.

### 8.7 Expense claim submission (`/expense-claims/new`) — Phase 11

> **Phase 11 screen.** Only render this route and the `/expense-claims` link in navigation after Phase 11 is deployed (gate behind a feature flag or the presence of the `POST /expense-claims` API endpoint). Users without `expenses:write` permission must not see this route.

**Purpose:** Allow employees to submit expense reimbursement claims directly from the Approval UI, as an alternative to submitting via email. Claims submitted here are enqueued via `POST /expense-claims` (`19` §1), classified as `case_type = 'expense_claim'`, and processed by the Expense Worker.

**Form fields:**


| Field                 | Input type                                                          | Validation                            | API field                                                                   |
| --------------------- | ------------------------------------------------------------------- | ------------------------------------- | --------------------------------------------------------------------------- |
| Category              | Select (transport / meals / accommodation / office / entertainment) | Required                              | `category`                                                                  |
| Merchant / Vendor     | Text                                                                | Required, max 200 chars               | `merchant`                                                                  |
| Amount                | Numeric                                                             | Required, > 0, max 2 decimal places   | `amount_value`                                                              |
| Currency              | Select (default SGD)                                                | Required                              | `amount_currency`                                                           |
| Receipt Date          | Date picker                                                         | Required, not future                  | `receipt_date`                                                              |
| Purpose / Description | Textarea                                                            | Required, min 10 chars, max 500       | `purpose`                                                                   |
| Receipt attachment    | File upload                                                         | Required; PDF / JPEG / PNG; max 10 MB | `attachment_ids` (upload first via `POST /attachments`, then reference IDs) |


**Behaviour:**

- If the tenant has uploaded a written policy (`tenant_profiles.expense_policy_document_*`), show a secondary action **View company travel & expense policy** (`GET /tenant/expense-policy-document/url`, `expenses:read`) opening the signed PDF in a new tab.
- On submit, call `POST /expense-claims` with a valid `Idempotency-Key` (generate UUID on form load, not on submit, to survive duplicate taps).
- On `201 Created`, navigate to the new expense claim detail page (`GET /expense-claims/{id}`) and show a success toast: "Expense claim submitted — reference {case_number}".
- On `422`, display inline field-level errors mapped from the API's `error.details` array.
- On `409 Duplicate`, show a specific banner: "A similar claim already exists. Review {linked case number} before submitting again." Link to the duplicate case.
- Do **not** allow re-submission on success; the Idempotency-Key prevents server-side duplicates, but the UI should also disable the submit button after a `201`.

**Permissions:** visible and functional only when the authenticated user has `expenses:write`. Finance Managers, Finance Officers, and Accounts Clerks should see this route. `auditor` and `general_manager` roles do not need expense submission.

### 8.8 Expense claims list (`/expense-claims`)

> **Phase 11 screen.**

- Lists the current user's own claims only (filtered by `claimant_id=me` via `GET /expense-claims`).
- Columns: reference (case number), merchant, category, amount + currency, receipt date, status, submitted date.
- Row click → expense claim detail view (re-uses case workspace at `/cases/{case_id}` — the linked case contains the full timeline and approval panel).
- Finance Managers with `approvals:read` can toggle to "All claims" view to see team submissions.

### 8.9 Mail Gateway — Mailbox Settings (`/settings/mailboxes`)

**Purpose:** Allow administrators to update the email address and display name for each system mailbox. The role column is read-only (roles are fixed at deployment). Only users with `mail:admin` permission can access this screen.

**Data source:** `GET /mail/configuration` (`05` §8.6) — the `mailboxes` array.

**Save action:** `PATCH /mail/configuration/mailboxes/{id}` (`05` §8.8) per row.

**Screen layout:** A table with one row per mailbox. The Role column is read-only; Email Address and Display Name are inline-editable text fields.


| Column        | Type       | Editable    | Notes                                                                              |
| ------------- | ---------- | ----------- | ---------------------------------------------------------------------------------- |
| Role          | Text       | ❌ Read-only | Fixed label identifying the mailbox function (e.g. "AR Executive", "AP Executive") |
| Email Address | Text input | ✅           | Must be a valid `@bp0.work` address; validated on save                             |
| Display Name  | Text input | ✅           | Shown as the `From:` name in outbound emails from this mailbox                     |
| Status        | Badge      | ❌ Read-only | `active` / `inactive` — reflects `is_active` from `mail_gateway_config`            |


**Confirmed mailboxes (displayed in this order):**


| Role                  | Default Email Address             | Default Display Name                   |
| --------------------- | --------------------------------- | -------------------------------------- |
| CEO / Managing Director | `ceo.mmlogistix@bp0.work` | mmlogistix CEO / Managing Director |
| CFO / Finance Director | `cfo.mmlogistix@bp0.work` | mmlogistix CFO / Finance Director |
| Manager Accounts | `acc.mmlogistix@bp0.work` | mmlogistix Manager Accounts |
| Manager Finance | `fin.mmlogistix@bp0.work` | mmlogistix Manager Finance |
| AR Executive | `accar.mmlogistix@bp0.work` | mmlogistix Account Receivables Executive |
| AP Executive | `accap.mmlogistix@bp0.work` | mmlogistix Account Payables Executive |
| Expense Executive | `accexp.mmlogistix@bp0.work` | mmlogistix Expense Management Executive |
| Treasury Executive | `fintreasury.mmlogistix@bp0.work` | mmlogistix Treasury Executive |
| Financial Reporting Executive | `finfa.mmlogistix@bp0.work` | mmlogistix Financial Reporting Executive |


**Behaviour:**

- On page load, fetch `GET /mail/configuration` and populate the table. Show a loading skeleton while fetching.
- Each row has an **Edit** button that switches the Email Address and Display Name cells to text inputs with **Save** and **Cancel** controls. Only one row may be in edit mode at a time.
- On **Save**, call `PATCH /mail/configuration/mailboxes/{id}` with the updated fields. On `200`, update the row in place and show a success toast. On `409` or `422`, show an inline error beneath the relevant field.
- On **Cancel**, restore the original values without calling the API.
- The Role and Status columns are never editable from this screen.
- Gate the entire screen behind `tenant:admin` or `mail:admin`. Users without either permission must not see the route in navigation. Finance roles (CFO, Finance Manager) do **not** receive this route.

**Permission:** `tenant:admin` (Client Admin) or `mail:admin` / `platform:admin` (Platform Admin break-glass). See `13_Security_and_Compliance_Specification.md` §5.9.

### 8.10 Chart of Accounts — Client Admin (`/chart-of-accounts`)

**Purpose:** Tenant operator imports and maintains the chart of accounts. **No demo accounts** are shipped in production after migration `054` (`06` §10.1) — the tenant CSV is the sole source of GL codes for posting.

**Route:** `https://admin.mmlogistix.bp0.work/chart-of-accounts` (SvelteKit `client-admin-ui`).

**API:** `05` §4.16d.3 — `GET /api/coa`, `GET /api/coa/status`, `POST /api/coa/import`, `POST /api/coa`, `PATCH /api/coa/{id}`.

**Permission:** `client_admin` role (`coa:import` / `tenant:admin`).

#### Empty state

When `GET /api/coa/status` returns `empty: true`:

- Banner: chart not configured; required CSV columns listed (`account_code`, `account_name`, `account_type`; optional `parent_code`)
- Checkbox **Replace entire chart** (default **on**) — maps to `replace_all=true` on import
- **Upload CSV** — on success, green message with `created` / `updated` / `skipped` / `active_count`, then table loads

#### Configured state

- Meta line: `{account_count} active account(s)`
- **Filter by code or name** — text field; **Search** calls `GET /api/coa?q=` (trimmed substring, case-insensitive); **Clear** resets filter and reloads full list (`0.14.7`, Svelte 5 `$state` for table refresh)
- **Replace entire chart on import** — same `replace_all` semantics as empty state
- **Import (CSV)** — file picker; auto-runs import on file select; shows same green summary as empty state
- Table: code, name, type, **Deactivate** per row (`PATCH` `is_active: false`)
- **Add account** card: manual single-row create (`POST /api/coa`)

**Import behaviour (`replace_all=true`):** Deactivates all existing accounts, then upserts CSV rows by `account_code` (updates reactivate matching codes). Use for first production load and when replacing a mistaken chart.

**Search UX (`7502b3e`):** If filter returns zero rows, show “No accounts match …” (do not leave stale rows on screen).

**Svelte 5 implementation (`8d6bf6e`):** Use `$state()` for reactive lists and filters. Event handlers on this page must use the **new** DOM syntax only (`onclick`, `onchange`, `onkeydown`) — mixing `on:click` / `on:change` with `onclick` breaks `vite build` (`mixed_event_handler_syntaxes`). Other Client Admin routes may still use legacy `on:click` until migrated per page.

### 8.22 Counterparty accounts — Finance UI (`/counterparty-accounts`)

**Status:** Shipped (`0.14.8-counterparty-accounts`; moved to finance-ui `e73c869`; inline edit `9b0662e`).  
**Purpose:** Maintain customer/vendor **subaccounts** (subledger parties), **payment terms** (due days catalog), **per-subaccount credit limits**, and **GST tax-code → GL** mapping used during AR/AP document intake. These are **not** COA lines (`15` §8.10).

**Route:** `https://finance.mmlogistix.bp0.work/counterparty-accounts`  
**API:** `05` §4.16d.4 | **Schema:** `06` §4.1a–§4.1c | **Intake:** `17` §3.2.1–§3.2.3

**Permission:** `require_finance_setup_access` — finance roles (`cfo`, `finance_manager`, `accounts_clerk`, `financial_analyst`, `ar_executive`, `ap_executive`, `general_manager`) plus `client_admin` / `tenant:admin`.

#### Tab 1 — Subaccounts

Master list with filters: `type` (customer / supplier), search by name or `account_code`.

**Shipped UI (`finance-ui`):** Create form includes payment-terms dropdown (due days from Tab 2) plus **credit limit amount** and **currency** (SGD/USD/EUR/MYR). Table shows **Credit limit** column. API client: `finance-ui/src/lib/api/finance-setup.ts`. API fields: `credit_limit_amount`, `credit_limit_currency` on `POST/PATCH /api/counterparty-accounts` (`05` §4.16d.4).

**Edit existing subaccount (shipped `9b0662e`):** On each **active** row, **Edit** switches **Payment terms** and **Credit limit** cells to inline controls (terms dropdown from active catalog; amount + currency). **Save** calls `PATCH /api/counterparty-accounts/{id}` with `payment_term_id`, `credit_limit_amount`, `credit_limit_currency` (empty amount clears credit limit). **Cancel** discards changes. Only one row in edit mode at a time. Other columns (code, display name, GST reg, etc.) remain create-only until a future drawer/modal.

| Column | Editable | Notes |
|--------|----------|-------|
| Parent counterparty | On create | Link to `counterparty` master (`06` §4.1) |
| Subaccount code | On create | Unique per parent, e.g. `ACME-SG-01` |
| Display name | On create | SOA / invoice header |
| Role | On create | `bill_to`, `ship_to`, `remit_to`, `statement_to` |
| Payment terms | **Create + inline edit** | Dropdown from Tab 2 active catalog |
| Credit limit (amount) | **Create + inline edit** | Optional `credit_limit_amount` + currency |
| Counterparty GST reg | On create | Their GST/UEN for tax validation |
| Contact email / address | On create | SOA delivery |
| Active | Deactivate | Deactivate only when no open balance |

**Actions:** Add subaccount, **Edit** (payment terms + credit on active rows), **Save** / **Cancel**, Deactivate, **Merge duplicate** (finance post-MVP).

**CSV import (optional MVP+):** `counterparty_code`, `account_code`, `display_name`, `payment_term_code`, `credit_limit_amount`, `counterparty_gst_reg`.

#### Tab 2 — Payment terms

Catalog for **due-date** and optional discount rules (`06` §4.1b). **Does not** store customer credit exposure — credit limits are on **Tab 1 (Subaccounts)**.

| Field | Shipped in UI | Description |
|-------|---------------|-------------|
| Code | Yes | `NET30`, `COD`, … |
| Label | Yes | Display name |
| Due days | Yes | Integer days after invoice date |
| Minimum invoice amount | API only | Term applies when document total ≥ amount (optional) |
| Discount % / if paid within days | API only | Early-payment hints (optional) |

**Defaults seeded:** `COD` (0), `NET7`, `NET30`, `NET60` (migration `056`).

#### Tab 3 — Tax codes (GST)

Maps extraction/policy tax codes to tenant COA (`06` §4.1c, `10` §11.1).

| Field | Description |
|-------|-------------|
| Code | `SR`, `GST9`, `ZR`, `EXEMPT`, … |
| Rate | e.g. `0.09` for 9% |
| Direction | Output (AR), Input (AP), or Both |
| Output GL account | COA code for GST payable / output tax |
| Input GL account | COA code for GST input tax |

**Validation on save:** Selected GL codes must exist in active COA. Warn if tenant `gst_registration_number` empty on Company page but output tax codes configured.

#### Dashboard checklist (add rows)

| Check | Complete when |
|-------|----------------|
| Payment terms configured | ≥1 active `payment_terms` row |
| Tax codes mapped | ≥1 active `tenant_tax_codes` with input + output GL for GST-registered tenant |
| Counterparty accounts | ≥1 active subaccount per recurring customer/supplier OR explicit “intake will auto-create” policy documented |

#### Intake behaviour (read-only on this page)

When AR/AP workers process `ar_invoice`, `ar_credit_note`, `ap_invoice` (and future `ap_debit_note`):

1. Match email/vendor → `counterparty` → best `counterparty_account` (`17` §3.2.1).
2. Apply `payment_terms.due_days` when `due_date` missing (§3.2.2).
3. Resolve `tax_code` → journal GST lines via `tenant_tax_codes` (§3.2.3).

Finance UI case detail shows resolved subaccount, term, tax code, and `tax_amount` from extraction.

### 8.23 Agreements — Finance UI (`/agreements`)

**Status:** Shipped (`e73c869`).  
**Route:** `https://finance.mmlogistix.bp0.work/agreements`  
**API:** `05` §4.16d.9 | **Permission:** `require_finance_setup_access`

**Tabs:**

| Tab | Purpose |
|-----|---------|
| Rental | Property rental agreements (`rental_agreements`) |
| Director expense | Director expense caps (`director_expense_agreements`) |

**UI:** Inline create forms; list existing rows. Moved from Client Admin (`client-admin-ui` route removed).

### 8.12 Platform Admin UI (separate application)

**Login:** `system@bp0.work` (`platform_admin` role).

**Deploy as:** standalone SvelteKit app in monorepo path `accounting/platform-admin-ui/`, e.g. `https://admin.bp0.work` (**post-MVP**). Must not share navigation with Approval UI or Client Admin UI.

**Scope:** Update Client Admin **email addresses** only. The tenant list is **dynamic** — render whatever `GET /platform/tenants` returns (`05` §4.16a.1).

#### 8.11.1 Home — Tenant registry (`/`)


| Column             | Editable | Notes                                                            |
| ------------------ | -------- | ---------------------------------------------------------------- |
| Client name        | No       | `display_name` from tenant                                       |
| Tenant slug        | No       | e.g. `mmlogistix`                                                |
| Client Admin email | Yes      | Inline edit → `PATCH /platform/tenants/{tenant_id}/client-admin` |
| Status             | No       | `active` / `inactive` badge on tenant and user                   |


**Behaviour:**

- On load, fetch `GET /platform/tenants`. Empty state: "No clients onboarded yet" (post-MVP: add tenant flow).
- One row per tenant; no hard-coded mmlogistix-only UI.
- **Save** validates email format and uniqueness; show API errors inline.
- No links to mailboxes, COA, logo, or company profile — those live in Client Admin UI.

**Permission:** `platform:admin` only.

---

### 8.13 Client Admin UI (separate application)

> **Implementation status (`0.14.6-email-signature`, shipped):** SvelteKit app `client-admin-ui/` at `https://admin.mmlogistix.bp0.work`. APIs: `05` §4.16d; schema: `06` §13.2c; deploy: `11` §4.5g; checklist: `11` §20.0.1.

**Host:** `https://admin.mmlogistix.bp0.work`  
**Branding:** mmlogistix Client Admin  
**Deploy version:** `0.14.6-email-signature` (`GET /api/health` → `version` in `accfin/app/core/config.py`)  
**UI package:** `client-admin-ui/package.json` → `0.14.3-gl-cutoff-reminders` (finance-ui unchanged `0.13.12-api-prefix-routing`)

**Technical stack:**

| Layer | Detail |
|-------|--------|
| UI | SvelteKit 2, `@sveltejs/adapter-node`, `export const ssr = false` on all routes |
| Auth | JWT (`client_admin` role only); reactive `client_admin_access_token` in layout (nav visible immediately after login — `0.14.1` fix) |
| API | `/api/*` via Traefik `PathPrefix(/api)` priority 100; UI router priority 1 |

**GL period posting (`0.14.4`+):** Documented in `17` §2.1.3 and finance-ui §8.21. Finance UI configures periods (`§8.24`); CFO/Client Admin may **reopen** closed periods (`0.14.5`); finance leadership overrides closed-period posts or **retries** after reopen.

**Login:** `system.mmlogistix@bp0.work` (seed) — **`client_admin`** role only (tenant bootstrap, not day-to-day finance setup).

**Navigation (header, `0.14.11`):** Dashboard | Company | Chart of Accounts | Users | Policies | **Binding Authority** | Logout

> **Mailboxes removed from header nav (`0.14.11-admin-ui-cleanup`, planned).** The `/mailboxes` route page (§8.14) and the underlying `/mail/configuration` APIs (`05` §8.6 / §8.8) are preserved for ad-hoc access; only the top-nav entry and the corresponding dashboard tile are removed. Mailbox identity, IMAP/SMTP credential rotation, and Approve-outbound-to-client toggles remain a Client Admin responsibility — they are simply no longer in the day-to-day nav surface.

| Route | Section |
| ----- | ------- |
| `/dashboard` | Tenant-bootstrap completeness checklist (7 items: company profile, email signature, chart of accounts, **Key Roles Email (Uses)**, Travel & Entertainment policy PDF, expense limits, regulatory documents). Finance-domain setup tiles (payment terms, GST/tax codes, vendor contracts, accounting calendar, GL reminder recipients) are owned by **finance.mmlogistix** (§8.22–§8.24) and are **not** on the Client Admin checklist. |
| `/company` | Company profile + email signature (HTML/plain) on `tenant_profiles` (`051`) |
| `/chart-of-accounts` | COA empty state, CSV import (`replace_all`), filter/search table, manual add (`15` §8.10) |
| `/users` | CEO → CFO → Finance Manager → Accounts Manager (acc) |
| `/policies` | Travel & Entertainment policy PDF (Wasabi) + expense limits + regulatory PDF catalog |
| `/binding-authority` | AP / AR / expense approval tier ceilings, STP confidence, SLA hours (`05` §4.16d.14, §8.25) |

**Removed from Client Admin (`e73c869`):** `/counterparty-accounts`, `/agreements`, `/accounting-calendar`, `/travel-info`, `/travel-requests` — see finance-ui §8.22–§8.24.

**Removed from Client Admin nav & dashboard (`0.14.11-admin-ui-cleanup`, planned):** `/mailboxes` tab entry. Dashboard tiles deleted: `payment_terms`, `tax_codes`, `vendor_contracts`, `mailboxes`, `calendar`, `gl_reminders`. The `users` tile is relabelled **"Key Roles Email (Uses)"**.

**Post-MVP UI:** `/branding` (logo upload screen).


Client Admin **cannot** edit their own login email here — that is Platform Admin UI only.

**Permission:** `tenant:admin` (implies `mail:admin`, `coa:import`, tenant profile APIs).

---

### 8.14 Mailboxes (Client Admin UI — `/mailboxes`)

> **Nav surface (`0.14.11-admin-ui-cleanup`, planned):** No longer a top-nav entry in `client-admin-ui`. The route page and `/mail/configuration` APIs are preserved and remain reachable via direct URL `https://admin.mmlogistix.bp0.work/mailboxes`. Mailbox display-name and Approve-outbound-to-client maintenance is occasional rather than daily, so it is removed from the day-to-day nav surface but not the application.

**Purpose:** Configure operational mailboxes per `01` §3.2 and §6.8 and `17` §10. Executives use automated listeners; **manager** mailboxes (`acc`, `fin`, `cfo`, `ceo`) are human-monitored only.

**API:** `GET /mail/configuration` (`05` §8.6), `PATCH /mail/configuration/mailboxes/{id}` (`05` §8.8).

**Screen layout:** Table with one row per mailbox (same order as §8.9).

| Column | Type | Editable | Notes |
|--------|------|----------|-------|
| Role | Text | Read-only | Mailbox function label |
| Email Address | Text | Yes | `@bp0.work` |
| Display Name | Text | Yes | Outbound `From:` name |
| Mode | Badge | Read-only | `Executive (agent)` / `Manager (human)` from `mailbox_mode` |
| Escalation manager | Email | Read-only* | Default from seed; *editable post-MVP |
| **Approve outbound to client** | Toggle | Yes | Maps to `requires_outbound_client_approval` — when ON, clarification and other client emails require manager approval before send |
| Status | Badge | Read-only | `active` / `inactive` |

**Toggle behaviour (`requires_outbound_client_approval`):**

- **OFF (default for most executives):** Agent sends clarification/acknowledgement without manager pre-approval (legacy “GM approval OFF”).
- **ON:** Outbound client message held in `pending_outbound_emails` (`06` §7.6); manager notified at the mailbox’s escalation manager (`acc` or `fin` per `01` §3.2.3); send only after approval in Approval UI (§8.19) or manager email (`05` §8.8b). Manager Approve/Reject/**Escalate** for **case processing** escalations uses `case_escalations` (`06` §7.5) — separate queue from client clarification.

**Help text (below table):** “Executives process email using uploaded COA and travel & expense policy. Accounts-branch issues escalate to Manager Accounts; finance-branch issues to Manager Finance. Managers may Approve, Reject, or Escalate to CFO; CFO may Escalate to CEO. Finance activity log is emailed daily at 9pm SGT to the CFO.”

---

### 8.19 Pending client clarifications (Approval UI — case panel)

**Purpose:** When `requires_outbound_client_approval` is ON, managers review drafted **client clarification** emails before SMTP send (`17` §10.5.4–§10.5.5, `01` §6.8.4).

**Surface:** Case detail `/cases/{id}` — panel **“Pending client email”** when a `pending_outbound_emails` row exists with `status='awaiting_manager_approval'`. Optional future route `/mail/outbound-pending` (not MVP).

**API:** Manager email links `GET /mail/outbound/{pending_id}/respond` (`05` §8.8b); case detail MAY embed `pending_outbound` summary from `GET /cases/{id}` when API exposes it.

| UI element | Content |
|------------|---------|
| **Preview** | Read-only `subject`, drafted body (shows quoted prior thread per `17` §10.5.3) |
| **Missing fields** | List from `metadata.missing_fields` |
| **Attachments** | Filenames from `metadata.attachment_ids`; badge **“Attachment may contain data”** when `attachments_not_fully_parsed=true` |
| **Approve** | Confirms send to client with full thread |
| **Reject** | Required `rejection_reason_code` dropdown: *Data in attachment*, *Data in email body*, *Parsing incomplete*, *Other* + comment |

**Reject behaviour:** No email to client. Show toast: “Returned to executive agent for re-extraction.” Case timeline event `clarification_rejected_by_manager`.

**Distinction:** This panel is **not** the financial `approvals` queue (§7.x). It only gates **outbound client** text.

---

### 8.15 Company details (Client Admin UI — `/company`)

**Purpose:** Legal and contact information printed on SOA and other company-generated documents.

**API:** `GET` / `PUT /tenant/profile` (`05` §4.16b.2).

**Form fields:** `legal_name` (required), `trading_name`, `registration_number`, `tax_id`, full address block, `phone`, `company_email`, `website`.

**Behaviour:** Standard save with validation; audit trail via API. Preview panel optional (read-only SOA header mockup).

---

### 8.16 Client logo (Client Admin UI — `/branding`)

**Purpose:** Tenant logo on SOA and formal PDFs.

**API:** `POST /tenant/profile/logo` (`05` §4.16b.3); display via signed URL from `logo_storage_path`.

**UI:** Drag-and-drop or file picker; show current logo thumbnail; max 2 MB; PNG/JPEG/SVG.

---

### 8.17 Email signature (Client Admin UI — `/company`)

**Purpose:** Footer appended to **every outbound SMTP email** from tenant role mailboxes (acknowledgement, manager escalation, clarification, daily finance log, GL cutoff reminders).

**API:** `GET` / `PATCH /tenant/profile` includes `email_signature_html` and `email_signature_plain`; dedicated `PUT /tenant/profile/email-signature` (`05` §4.16b.4).

**UI (`/company` page, shipped `0.14.6`):**

| Control | Field |
|---------|--------|
| HTML signature | `email_signature_html` (textarea; may contain HTML tags) |
| Plain text signature | `email_signature_plain` |
| **Preview signature in email** | Toggle panel: sample acknowledgement body + appended footer in **HTML** and **plain text** views (matches production MIME layout per `18` §10.2) |

**Backend (`0.14.6`):** `OutboundMailService._load_tenant_signature()` → `mail_template_renderer.append_tenant_signature()`. If both signature fields are empty, no `--` separator or `<hr>` block is added.

---

### 8.18 Travel & expense claim policy (Client Admin UI — `/expense-policy`)

**Purpose:** Configure the **travel and expense claim policy** for the tenant — numeric limits and approval thresholds the Expense Worker enforces (`19` §5, `expense_policies` table), plus an optional downloadable **written policy document** (PDF) for employees.

**Permission:** `tenant:admin` only. Finance roles may **read** active rules via the API for display on claim detail (`expenses:read`) but must not edit policy here.

**API:** `05` §4.16c (`GET` / `PUT /tenant/expense-policies`, `POST /tenant/profile/expense-policy-document`).

#### Tab 1 — Policy rules

Data source: `expense_policies` (`19` §3.3). Seeded at install (`19` §13): global receipt/approval thresholds, meals daily limit, accommodation, entertainment, airfare.

**List view (table):**

| Column | Notes |
|--------|-------|
| Display name | `display_name` |
| Category | `category` or “All categories” when `applies_to_all_categories` |
| Daily limit | `daily_limit` (SGD) — blank if N/A |
| Per-claim limit | `per_claim_limit` (SGD) |
| Receipt above | `requires_receipt_above` |
| Approval above | `requires_approval_above` |
| Active | `is_active` toggle |
| Effective | `effective_from` – `effective_to` |

**Edit drawer / modal** (opened from row):

- **Editable:** `display_name`, `description`, `daily_limit`, `per_claim_limit`, `requires_receipt_above`, `requires_approval_above`, `is_active`, `effective_from`, `effective_to`, `department` (when not `applies_to_all_departments`).
- **Read-only:** `name` (system key, e.g. `meals_daily_limit`), `category`, `version` (bump on save — server sets patch version).
- **Validation:** amounts ≥ 0; `effective_to` ≥ `effective_from`; at least one global policy (`applies_to_all_categories`) must remain active.
- **Save:** `PUT /tenant/expense-policies/{policy_id}`; toast on success; audit via API (`13` §9.1 `policy_updated`).

**Behaviour:**

- Changes apply to **the next** expense claim processed by the Expense Worker (`19` §14.2 `Policy reload` test).
- Deactivating a rule sets `is_active = false` (do not delete seeded rows).
- **Out of scope for Client Admin:** creating new `name` keys or new `expense_category` enum values (requires migration — Platform/maintainer).

**Category coverage (travel + expense):** `accommodation`, `airfare`, `ground_transport`, `meals`, `entertainment`, `office_supplies`, `training`, `telecommunications`, `professional_fees`, `other` (`19` §3.2).

#### Tab 2 — Written policy document (optional)

**Purpose:** Store the company’s full travel & expense policy PDF (employee handbook) separate from numeric rules.

**API:** `POST /tenant/profile/expense-policy-document` (multipart `file`, PDF max 10 MB); `DELETE` to remove. Fields on `tenant_profiles`: `expense_policy_document_*` (`06` §13.2b).

**UI:** Drag-and-drop upload; show current filename and “Last updated”; link to signed download URL. If no document, show helper text: “Upload your travel & expense policy for employees.”

**Approval UI (read-only):** Expense claim screens (`§8.7–8.8`) may show “View company expense policy” when a document exists (`GET /tenant/profile` includes document metadata).

**Permission:** `tenant:admin` for upload/delete; authenticated finance users get read-only signed URL via `expenses:read` on claim context.

---

### 8.24 Accounting calendar (Finance UI — `/accounting-calendar`)

**Moved from §8.20 Client Admin (`e73c869`).** Same behaviour; host is finance.mmlogistix.

**Purpose:** Configure GL month-end calendar, trial balance workflow, audit/year-end period types, and cutoff reminder recipients (`06` §13.2c, `05` §4.16d.10–§4.16d.12).

#### Panel 1 — Accounting settings

| Control | Maps to `system_settings` key |
|---------|-------------------------------|
| Financial year-end month | `accounting_fye_month` (1–12) |
| Trial balance frequency | `trial_balance_frequency` (`monthly` \| `weekly`) |
| Audit frequency | `audit_frequency` (`annual` \| `semi_annual` \| `quarterly`) |
| GL cutoff working days | `gl_cutoff_working_days` (after month-end, business days excl. SG holidays) |

**API:** `GET` / `PATCH /api/admin/accounting-settings`

#### Panel 2 — Period list

| Column | Source |
|--------|--------|
| Period | `period_year` / `period_month` display name |
| Type badge | `period_type`: Monthly / Audit / Year-end |
| GL cutoff | `gl_cutoff_date` |
| TB reviewer | `trial_balance_reviewer` |
| Status | `open` \| `review` \| `closed` |

**Actions:**

| Button | Role | API |
|--------|------|-----|
| Generate periods | `require_finance_setup_access` | `POST /api/accounting-periods/generate?months=13` (current month + 12 forward) |
| Approve trial balance | `financial_analyst`, `finance_manager`, `cfo`, or `client_admin` | `POST .../approve-trial-balance` → status `review` |
| Close GL | `finance_manager`, `cfo`, or `client_admin` | `POST .../close` — requires TB approved; audit/year-end checkboxes per `period_type` |
| Reopen period | `cfo` or `client_admin` | `POST .../reopen` — only when status `closed`; 🔓 icon + confirmation modal (`0.14.5`) |

**Close GL modal:** For `audit` periods — `audit_adjustments_completed`; for `year_end` — `year_end_adjustments_completed`; optional `auditor_name`, `auditor_firm`, `sign_off_date` → `audit_metadata`.

**Reopen modal (`0.14.5`):** Copy: “Are you sure you want to reopen {Month YYYY}? This will allow new postings to this period. All previous postings will remain intact.” On confirm → `POST /api/accounting-periods/{id}/reopen` → refresh period table.

#### Panel 3 — GL cutoff reminder recipients

Table of `gl_cutoff_reminders` rows: email, display name, notify flags (7d / 3d / 1d / on date), active toggle. Add / edit / delete via `05` §4.16d.11.

**Dashboard check:** Section complete when ≥1 active recipient.

**Reminder job:** Daily **08:00 SGT** (`00:00 UTC`) — `POST /api/internal/jobs/gl-cutoff-reminders` (`05` §19.2, `11` §17.6). SMTP sender: `acc.mmlogistix@bp0.work`. Logs `finance_activity_log` action `gl_cutoff_reminder_sent`.

**Migrations (Client Admin band):** `049`–`053` — see `06` §13.2c and `11` §20.0.1 Gate E1.

---

### 8.25 Binding authority — Client Admin (`/binding-authority`)

**Purpose:** Configure binding authority approval tiers per document type (AP Invoice, AR Invoice, Expense Claim).

**Route:** `https://admin.mmlogistix.bp0.work/binding-authority`

**API:** `05` §4.16d.14 — `GET/PATCH /api/admin/binding-authority`

**Fields (per section, SGD unless noted):**

| Field | Description |
|-------|-------------|
| Tier 1 ceiling | Agent auto-posts without human approval |
| Tier 2 ceiling | Accounts Manager (`acc`) approval required |
| Tier 3 threshold | CFO/FD approval required (≥ this amount) |
| STP confidence minimum | Minimum extraction confidence for Tier 1 |
| Tier 2 SLA (hours) | Hours before auto-escalation to CFO |
| Tier 3 SLA (hours) | Hours before auto-escalation to CEO |

**Save:** One **Save** button per document-type card; PATCH only that policy’s thresholds.

**Permission:** `client_admin`.

---

### 8.21 GL period override (Approval UI — case detail)

**Purpose:** When AP/AR/expense workers block journal posting because the posting date falls in a **closed** GL period, finance leadership may authorize a one-time override and requeue processing (`0.14.4`, `17` §2.1.3).

**Surface:** Case detail `/cases/{id}` on `finance.mmlogistix.bp0.work`.

**Visibility:**

| Condition | Show control |
|-----------|--------------|
| User role `cfo` or `finance_manager` | Yes |
| Case `status = on_hold` **and** `workflow_metadata.reason_code` / `error_type` = `PERIOD_CLOSED` | Yes |
| Linked period still **`closed`** (`linked_gl_period_status` from `GET /cases/{id}`) | Yes — hide when period reopened |
| `workflow_metadata.gl_period_id` present | Required for API call |

**UI:**

| Element | Behaviour |
|---------|-----------|
| Banner | “GL period closed — posting blocked for {posting_date}” |
| **Override & Post** button | Opens modal |
| Modal | Required multiline `override_reason`; Confirm calls API |
| Success | Toast + case reload; worker reprocesses with `gl_period_override` |

**API:** `POST /api/accounting-periods/{period_id}/override-post` body `{ case_id, override_reason }` (`05` §4.16d.13).

**Manager email path:** Manager Approve on `PERIOD_CLOSED` escalation also requeues with override flags (`ExecutiveMailService`, `17` §10.4) — distinct from the finance-ui button but same worker behaviour.

#### Binding authority approval panel (`0.14.9`)

When `case.status = pending_approval` and `GET /cases/{id}` returns `pending_approval_id`:

| Role | Buttons |
|------|---------|
| `accounts_clerk` / `finance_officer` | **Approve**, **Reject**, **Escalate to CFO** — Tier 2 only, not after `binding_escalated_to_cfo` |
| `cfo` / `finance_manager` | **Approve**, **Reject** — Tier 2 (including escalated) and Tier 3 |

Calls `POST /approvals/{id}/approve`, `/reject`, `/escalate`. Reject requires reason (emailed to submitter). Approve posts journal via `BindingAuthorityService` (`10` §7).

**Approvals list (`/approvals`):** Tab **My queue** uses `GET /approvals?status=pending&binding_queue=acc|cfo` by role; **History** shows approved/rejected; **All cases** retains monitoring table.

**Audit:** `finance_activity_log.action = gl_period_override_post` with `override_reason` and `posted_by` in metadata.

#### Retry after period reopen (`0.14.5`)

When a case is **`on_hold`** with `PERIOD_CLOSED` and the linked GL period has been **reopened** (`linked_gl_period_status` ≠ `closed`):

| Element | Behaviour |
|---------|-----------|
| **Retry processing** button | Visible (same control as `exception` / `manual_review` retry) |
| Hint | “The GL period for this posting date has been reopened — you can reprocess without an override.” |
| API | `POST /api/cases/{id}/retry` (`05` §5.8a) — no override flags required |

**Override & Post** remains hidden once the period is no longer closed.

---

## 9. States, Errors & Empty UX


| State               | UX                                                       |
| ------------------- | -------------------------------------------------------- |
| **Loading**         | Skeleton rows for tables; avoid layout shift.            |
| **Empty queue**     | “No pending approvals” with link to `/cases`.            |
| **403 on action**   | Toast + inline message; remove optimistic UI updates.    |
| **409 / conflict**  | Show server message; refresh entity.                     |
| **Network offline** | Banner + queue user actions read-only until back.        |
| **Stale tab**       | On focus, soft-refresh counters and first page of lists. |


Optimistic UI for approve/reject is **discouraged**; prefer spinner until `200`/`201` to avoid contradictory state with SSE.

---

## 10. PII, Security & Client Hardening

- Minimize display of full email/phone; mask where BRD/PDPA requires (`13`).
- **CSP** and XSS: treat all API text as untrusted; sanitize or render as plain text unless a safe rich-text subset is approved.
- **CSRF**: if session-cookie auth is ever used, require anti-CSRF token pattern from `13`; for pure Bearer header from SPA on separate origin, document CORS expectations in deployment runbook.
- **Logging**: no console logging of tokens, full PAN, or passwords in production builds.

---

## 11. Accessibility & i18n Baseline

- Keyboard operability for queues (row focus, activate to open detail).
- WCAG **2.1 AA** target for colour contrast and focus indicators on primary actions.
- Date/time: display in user locale; store/transmit ISO-8601 UTC as per API.
- Copy is **English (SG)** for MVP unless product adds locale bundles later.

---

## 12. Testing Expectations

Align with `12_Testing_and_UAT_Strategy.md`:

- **Contract tests**: consumer tests against OpenAPI/`05` schemas for list/detail/approve/reject.
- **E2E**: critical paths — login, filter approvals, open case, approve and verify timeline entry (Playwright or equivalent).
- **SSE**: integration test with mocked stream or test harness subscribing to Redis-backed stream in staging.
- **RBAC matrix**: automated tests that `general_manager` session never successfully calls financial approve endpoints (expect `403`).

---

## 13. Frontend Architecture Reference

This section specifies the repository structure, dependency choices, Svelte store architecture, SSE reconnect state machine, and component conventions for the SvelteKit Approval UI. A developer must not have to infer these from `15` §2–7 alone — the choices here are made explicit so that the implementation is consistent and predictable from the start.

---

### 13.1 Repository Structure

```
finance-ui/
├── package.json
├── svelte.config.js
├── vite.config.ts
├── .env.example                  # UI-specific env vars (see §13.2)
├── .env                          # not committed
│
├── src/
│   ├── app.html                  # SvelteKit root HTML shell
│   ├── app.css                   # Global resets + Tailwind base imports
│   │
│   ├── lib/
│   │   ├── api/                  # Typed API client functions (one file per domain)
│   │   │   ├── client.ts         # Base fetch wrapper: auth headers, error parsing, refresh
│   │   │   ├── auth.ts           # login(), refresh(), logout(), setup2fa()
│   │   │   ├── approvals.ts      # listApprovals(), getApproval(), approve(), reject(), …
│   │   │   ├── cases.ts          # listCases(), getCase(), getTimeline(), addNote()
│   │   │   ├── notifications.ts  # listNotifications(), markRead()
│   │   │   └── users.ts          # getNotificationPrefs(), putNotificationPrefs()
│   │   │
│   │   ├── stores/               # Svelte stores (see §13.4)
│   │   │   ├── auth.ts           # session store: token, user, permissions
│   │   │   ├── approvals.ts      # approvalsStore, pendingCount
│   │   │   ├── cases.ts          # casesStore, activeCaseStore
│   │   │   ├── notifications.ts  # notificationsStore, unreadCount
│   │   │   └── sse.ts            # SSE connection store + reconnect state machine
│   │   │
│   │   ├── components/           # Reusable UI components (see §13.5)
│   │   │   ├── layout/
│   │   │   │   ├── AppShell.svelte
│   │   │   │   ├── Sidebar.svelte
│   │   │   │   └── TopBar.svelte
│   │   │   ├── approval/
│   │   │   │   ├── ApprovalCard.svelte
│   │   │   │   ├── ApprovalActions.svelte
│   │   │   │   ├── SlaCountdown.svelte
│   │   │   │   └── RiskFlagChips.svelte
│   │   │   ├── case/
│   │   │   │   ├── CaseMetaPanel.svelte
│   │   │   │   ├── TimelineEvent.svelte
│   │   │   │   └── AttachmentList.svelte
│   │   │   ├── notifications/
│   │   │   │   ├── NotificationBell.svelte
│   │   │   │   └── NotificationDrawer.svelte
│   │   │   └── shared/
│   │   │       ├── DataTable.svelte
│   │   │       ├── CursorPagination.svelte
│   │   │       ├── StatusBadge.svelte
│   │   │       ├── SkeletonRow.svelte
│   │   │       ├── ErrorBanner.svelte
│   │   │       └── ConfirmModal.svelte
│   │   │
│   │   └── utils/
│   │       ├── dates.ts          # formatDate(), formatRelative(), slaColour()
│   │       ├── permissions.ts    # hasPermission(), canApprove()
│   │       ├── currency.ts       # formatSGD(), formatAmount(value, currency)
│   │       └── eventTypeLabels.ts # Maps timeline event_type codes to display strings
│   │
│   └── routes/                   # SvelteKit file-based routing
│       ├── +layout.svelte        # Root layout: AppShell, SSE init, auth guard
│       ├── +layout.ts            # Load: verify session; redirect to /login if absent
│       ├── login/
│       │   └── +page.svelte
│       ├── dashboard/
│       │   └── +page.svelte
│       ├── approvals/
│       │   ├── +page.svelte      # Approvals queue list
│       │   └── [id]/
│       │       └── +page.svelte  # Approval detail
│       ├── cases/
│       │   ├── +page.svelte      # Cases list
│       │   └── [id]/
│       │       ├── +page.svelte  # Case workspace
│       │       └── audit/
│       │           └── +page.svelte
│       └── settings/
│           ├── notifications/
│           │   └── +page.svelte
│           └── security/
│               └── +page.svelte
│
└── tests/
    ├── unit/                     # Vitest unit tests for stores and utils
    ├── integration/              # Vitest + msw for API client tests
    └── e2e/                      # Playwright tests (see §12)
```

---

### 13.2 Dependencies and Rationale

All versions are minimum constraints. Pin exact versions in `package.json` before first deployment.


| Package                   | Version   | Role                 | Decision rationale                                                                                                        |
| ------------------------- | --------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `@sveltejs/kit`           | `>=2.0`   | Framework            | Specified in §2; file-based routing, SSR capable                                                                          |
| `svelte`                  | `>=5.0`   | UI runtime           | Runes syntax available from v5; use v4-compatible stores for MVP simplicity                                               |
| `vite`                    | `>=5.0`   | Build tool           | SvelteKit default; fast HMR in dev                                                                                        |
| `typescript`              | `>=5.3`   | Type safety          | Mandatory — all `.ts` and `.svelte` files typed                                                                           |
| `tailwindcss`             | `>=3.4`   | Utility CSS          | Chosen over component library to avoid opinionated component lock-in; finance UIs need precise control over table layouts |
| `@tailwindcss/forms`      | `>=0.5`   | Form resets          | Unstyled form elements by default with Tailwind                                                                           |
| `bits-ui`                 | `>=0.21`  | Headless components  | Accessible primitives (Dialog, Popover, Select, Tabs) without visual opinions; pairs with Tailwind                        |
| `lucide-svelte`           | `>=0.400` | Icons                | MIT-licensed, consistent set; replaces ad-hoc SVG                                                                         |
| `@tanstack/svelte-query`  | `>=5.0`   | Server state         | Cache, background refetch, and stale-while-revalidate for API calls; avoids manual loading/error state in every component |
| `zod`                     | `>=3.22`  | Schema validation    | Runtime validation of API responses; parse-don't-trust                                                                    |
| `@internationalized/date` | `>=3.5`   | Timezone-aware dates | SGD locale date formatting without pulling moment.js                                                                      |
| `vitest`                  | `>=1.6`   | Unit testing         | Native Vite integration                                                                                                   |
| `@sveltejs/adapter-node`  | `>=5.0`   | Production adapter   | Docker Node.js deployment                                                                                                 |
| `msw`                     | `>=2.3`   | API mocking          | Integration tests without live API                                                                                        |
| `@playwright/test`        | `>=1.44`  | E2E testing          | Required by §12                                                                                                           |


**Not included (and why):**

- `sveltestrap` / `skeleton-ui` / `shadcn-svelte` — all bring full component sets that conflict with the precise data-table and approval-card layouts needed. Use `bits-ui` headless primitives + Tailwind instead.
- `axios` — native `fetch` with the wrapper in `lib/api/client.ts` is sufficient and reduces bundle size.
- `socket.io` — the API exposes SSE (not WebSocket). Use the native `EventSource` API.
- `redux` / `zustand` — Svelte's reactive store primitives are sufficient for this app's complexity.

---

### 13.3 Environment Variables (UI)

The frontend `.env.example` lives in the `accounting/finance-ui/` directory root (monorepo `bp0work/accounting`). All variables are prefixed `PUBLIC_` (exposed to the browser by SvelteKit) or are build-time only.

```bash
# finance-ui/.env.example

# API base URL — same origin as Approval UI (Traefik → fastapi); no trailing slash
PUBLIC_API_BASE_URL=https://finance.mmlogistix.bp0.work

# SSE stream endpoint
PUBLIC_SSE_URL=https://finance.mmlogistix.bp0.work/events/stream

# Feature flags (mirror FINANCE_FEATURE__* from backend 14)
PUBLIC_ENABLE_AUDIT_VIEW=true
PUBLIC_ENABLE_NOTIFICATIONS=true

# App version (injected at build time by CI)
PUBLIC_APP_VERSION=0.0.0
```

Server-side env vars (not `PUBLIC_`), used only in `+layout.ts` server load functions if SSR is enabled, follow the same naming without the `PUBLIC_` prefix.

---

### 13.4 Svelte Store Architecture

The store layer is the single source of truth for all server state visible across routes. Components never fetch directly — they subscribe to stores and call store actions.

#### auth.ts — Session Store

```typescript
// src/lib/stores/auth.ts

import { writable, derived } from 'svelte/store';
import type { User } from '$lib/api/auth';

interface Session {
  accessToken: string | null;
  user: User | null;
  permissions: string[];
}

function createAuthStore() {
  const { subscribe, set, update } = writable<Session>({
    accessToken: null,
    user: null,
    permissions: [],
  });

  return {
    subscribe,
    setSession(token: string, user: User) {
      set({ accessToken: token, user, permissions: user.permissions });
    },
    clearSession() {
      set({ accessToken: null, user: null, permissions: [] });
    },
    updateToken(token: string) {
      update(s => ({ ...s, accessToken: token }));
    },
  };
}

export const auth = createAuthStore();

// Derived convenience: check a single permission code
export const hasPermission = (code: string) =>
  derived(auth, $auth => $auth.permissions.includes(code));

// Access token getter for use in API client (avoids circular import)
export function getAccessToken(): string | null {
  let token: string | null = null;
  auth.subscribe(s => { token = s.accessToken; })();
  return token;
}
```

**Key rules:**

- Access token is stored **in memory only** (store state) — never `localStorage` or `sessionStorage` for the access token per §4 and `13_Security_and_Compliance_Specification.md`.
- Refresh token handling follows the pattern chosen per `13` (httpOnly cookie preferred; if SPA origin separation requires header storage, document the CORS configuration in the deployment runbook).
- On page reload, the root `+layout.ts` server load function attempts a silent refresh via `POST /auth/refresh`. On failure, the user is redirected to `/login`.

#### approvals.ts — Approvals Store

```typescript
// src/lib/stores/approvals.ts

import { writable, derived } from 'svelte/store';
import { listApprovals, type Approval } from '$lib/api/approvals';

interface ApprovalsState {
  items: Approval[];
  loading: boolean;
  error: string | null;
  nextCursor: string | null;
  hasMore: boolean;
}

function createApprovalsStore() {
  const { subscribe, set, update } = writable<ApprovalsState>({
    items: [], loading: false, error: null, nextCursor: null, hasMore: false,
  });

  return {
    subscribe,
    async load(params: Record<string, string> = {}) {
      update(s => ({ ...s, loading: true, error: null }));
      try {
        const result = await listApprovals(params);
        update(s => ({
          ...s,
          loading: false,
          items: result.data,
          nextCursor: result.pagination.next_cursor,
          hasMore: result.pagination.has_more,
        }));
      } catch (e) {
        update(s => ({ ...s, loading: false, error: String(e) }));
      }
    },
    async loadMore() { /* append next page */ },
    // SSE mutations — called by sse.ts event handlers
    upsert(approval: Approval) {
      update(s => {
        const idx = s.items.findIndex(a => a.id === approval.id);
        if (idx >= 0) {
          const items = [...s.items];
          items[idx] = approval;
          return { ...s, items };
        }
        return { ...s, items: [approval, ...s.items] };
      });
    },
    remove(id: string) {
      update(s => ({ ...s, items: s.items.filter(a => a.id !== id) }));
    },
  };
}

export const approvalsStore = createApprovalsStore();
export const pendingCount = derived(
  approvalsStore,
  $a => $a.items.filter(a => a.status === 'pending').length
);
```

#### notifications.ts — Notification Inbox Store

```typescript
// src/lib/stores/notifications.ts
// Drives the notification bell badge and drawer.
// Populated on load + updated by SSE system.notification events.
// GET /notifications called on reconnect and page focus.

import { writable, derived } from 'svelte/store';
import { listNotifications, markRead, type Notification } from '$lib/api/notifications';

function createNotificationsStore() {
  const { subscribe, set, update } = writable<{
    items: Notification[];
    unreadCount: number;
    loading: boolean;
  }>({ items: [], unreadCount: 0, loading: false });

  return {
    subscribe,
    async load() {
      update(s => ({ ...s, loading: true }));
      const result = await listNotifications({ is_read: false, limit: 50 });
      set({ items: result.data, unreadCount: result.unread_count, loading: false });
    },
    async markAllRead() {
      await markRead({ mark_all: true });
      update(s => ({
        ...s,
        items: s.items.map(n => ({ ...n, is_read: true })),
        unreadCount: 0,
      }));
    },
    async markOneRead(id: string) {
      await markRead({ notification_ids: [id] });
      update(s => ({
        ...s,
        items: s.items.map(n => n.id === id ? { ...n, is_read: true } : n),
        unreadCount: Math.max(0, s.unreadCount - 1),
      }));
    },
    prepend(notification: Notification) {
      update(s => ({
        ...s,
        items: [notification, ...s.items],
        unreadCount: s.unreadCount + 1,
      }));
    },
  };
}

export const notificationsStore = createNotificationsStore();
export const unreadCount = derived(notificationsStore, $n => $n.unreadCount);
```

---

### 13.5 SSE Reconnect State Machine

This is the most complex client-side behaviour in the application. The store below manages the `EventSource` lifecycle, exponential backoff reconnect, post-reconnect data healing, and event routing to domain stores. It must not be reimplemented ad-hoc in a component.

```typescript
// src/lib/stores/sse.ts

import { writable, get } from 'svelte/store';
import { approvalsStore } from './approvals';
import { casesStore } from './cases';
import { notificationsStore } from './notifications';
import { getAccessToken } from './auth';
import { getApproval } from '$lib/api/approvals';
import { getCase } from '$lib/api/cases';

type SSEStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';

interface SSEState {
  status: SSEStatus;
  retryCount: number;
  lastEventAt: string | null;
  errorMessage: string | null;
}

const BASE_DELAY_MS  = 1_000;
const MAX_DELAY_MS   = 30_000;
const MAX_RETRIES    = 10;  // beyond this, give up and show persistent banner

function createSSEStore() {
  const { subscribe, update } = writable<SSEState>({
    status: 'disconnected',
    retryCount: 0,
    lastEventAt: null,
    errorMessage: null,
  });

  let es: EventSource | null = null;
  let retryTimeout: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    const token = getAccessToken();
    if (!token) return;  // not authenticated — do not connect

    const url = new URL(import.meta.env.PUBLIC_SSE_URL);
    // EventSource does not support Authorization header natively.
    // Pass token as query param — API must accept this on the SSE endpoint.
    // See 09 §15.1 for the token-via-query-param note.
    url.searchParams.set('token', token);

    update(s => ({ ...s, status: 'connecting', errorMessage: null }));
    es = new EventSource(url.toString());

    es.onopen = () => {
      update(s => ({ ...s, status: 'connected', retryCount: 0, errorMessage: null }));
      // Heal missed events: re-fetch affected lists on every (re-)connect
      _healOnReconnect();
    };

    es.onerror = () => {
      es?.close();
      es = null;
      update(s => {
        const retryCount = s.retryCount + 1;
        if (retryCount > MAX_RETRIES) {
          return { ...s, status: 'error', retryCount, errorMessage: 'SSE connection lost — please refresh.' };
        }
        const delay = Math.min(BASE_DELAY_MS * 2 ** (retryCount - 1), MAX_DELAY_MS);
        // Add jitter: ±20%
        const jitter = delay * 0.2 * (Math.random() * 2 - 1);
        retryTimeout = setTimeout(connect, delay + jitter);
        return { ...s, status: 'reconnecting', retryCount, errorMessage: null };
      });
    };

    // Route named SSE events to the correct store handler
    es.addEventListener('case.created',         e => _onCaseEvent(e));
    es.addEventListener('case.status_changed',  e => _onCaseEvent(e));
    es.addEventListener('approval.requested',   e => _onApprovalEvent(e));
    es.addEventListener('approval.approved',    e => _onApprovalEvent(e));
    es.addEventListener('approval.rejected',    e => _onApprovalEvent(e));
    es.addEventListener('approval.delegated',   e => _onApprovalDelegated(e));
    es.addEventListener('approval.sla_at_risk', e => _onSlaAtRisk(e));
    es.addEventListener('approval.escalated',   e => _onApprovalEvent(e));
    es.addEventListener('system.notification',  e => _onSystemNotification(e));
  }

  function disconnect() {
    if (retryTimeout) clearTimeout(retryTimeout);
    es?.close();
    es = null;
    update(s => ({ ...s, status: 'disconnected' }));
  }

  // ── Event handlers ──────────────────────────────────────────────────────

  async function _onApprovalEvent(e: MessageEvent) {
    const payload = JSON.parse(e.data);
    update(s => ({ ...s, lastEventAt: new Date().toISOString() }));
    // Re-fetch the approval rather than trusting partial SSE payload
    // — ensures the store always holds complete, authoritative data
    try {
      const approval = await getApproval(payload.approval_id ?? payload.data?.payload?.approval_id);
      approvalsStore.upsert(approval);
    } catch { /* if fetch fails, stale data remains until next heal */ }
  }

  async function _onApprovalDelegated(e: MessageEvent) {
    // On delegation, the original approver's item must disappear and
    // the delegate's queue must update. Re-fetch the full pending list.
    const payload = JSON.parse(e.data);
    const approvalId = payload.data?.payload?.approval_id;
    if (approvalId) approvalsStore.remove(approvalId);
    // Let the delegate's session pick it up via their own SSE stream
  }

  async function _onCaseEvent(e: MessageEvent) {
    const payload = JSON.parse(e.data);
    update(s => ({ ...s, lastEventAt: new Date().toISOString() }));
    try {
      const caseData = await getCase(payload.data?.payload?.case_id ?? payload.case_id);
      casesStore.upsert(caseData);
    } catch { /* ignore */ }
  }

  function _onSlaAtRisk(e: MessageEvent) {
    // Parsed payload drives SlaCountdown component directly via a custom event.
    // The component subscribes by approval_id; see §13.5 SlaCountdown.
    const payload = JSON.parse(e.data);
    const slaPayload = payload.data?.payload;
    if (!slaPayload) return;
    update(s => ({ ...s, lastEventAt: new Date().toISOString() }));
    // Dispatch a browser CustomEvent so SlaCountdown components can subscribe
    // without a per-approval-id Svelte store proliferation
    document.dispatchEvent(
      new CustomEvent('sla:at_risk', { detail: slaPayload })
    );
  }

  function _onSystemNotification(e: MessageEvent) {
    const payload = JSON.parse(e.data);
    notificationsStore.prepend(payload.data?.payload);
  }

  async function _healOnReconnect() {
    // Re-fetch the first page of pending approvals and unread notifications
    // to merge any events missed during the disconnected window.
    await Promise.allSettled([
      approvalsStore.load({ my_pending: 'true' }),
      notificationsStore.load(),
    ]);
  }

  return { subscribe, connect, disconnect };
}

export const sseStore = createSSEStore();
```

**Integration in root layout:**

```svelte
<!-- src/routes/+layout.svelte -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { sseStore } from '$lib/stores/sse';
  import { auth } from '$lib/stores/auth';

  // Start SSE when the session is established; tear down on logout
  let unsubscribe: (() => void) | null = null;

  onMount(() => {
    unsubscribe = auth.subscribe($auth => {
      if ($auth.accessToken) {
        sseStore.connect();
      } else {
        sseStore.disconnect();
      }
    });

    // Heal on tab focus (catches missed events when tab was backgrounded)
    const onFocus = () => {
      if ($sseStore.status === 'connected') {
        sseStore._healOnReconnect?.();
      }
    };
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  });

  onDestroy(() => {
    unsubscribe?.();
    sseStore.disconnect();
  });
</script>
```

---

### 13.6 SLA Countdown Component

The `SlaCountdown` component is one of the most behaviourally complex pieces in the UI — it must respond to SSE events and decrement client-side. Its implementation contract is specified here so it is not invented differently per screen.

```svelte
<!-- src/lib/components/approval/SlaCountdown.svelte -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  export let approvalId: string;
  export let slaDeadline: string;       // ISO-8601 UTC string from API
  export let initialMinutesRemaining: number | null = null;

  let minutesRemaining: number = initialMinutesRemaining
    ?? Math.max(0, Math.round((new Date(slaDeadline).getTime() - Date.now()) / 60_000));
  let ticker: ReturnType<typeof setInterval> | null = null;
  let slaListener: ((e: Event) => void) | null = null;

  // Colour thresholds per §8.4 (Approval detail)
  $: urgency = minutesRemaining <= 0    ? 'breached'
             : minutesRemaining <= (minutesRemaining / 0.2) * 0.2 ? 'urgent'   // percent_remaining <= 20
             : minutesRemaining <= (minutesRemaining / 0.5) * 0.5 ? 'warning'  // percent_remaining <= 50
             : 'ok';

  // Simpler: driven by minutes only (total not always available client-side)
  // Override urgency when SSE payload delivers percent_remaining
  let percentRemaining: number | null = null;
  $: cssClass = percentRemaining !== null
    ? (percentRemaining <= 20 ? 'sla-urgent' : percentRemaining <= 50 ? 'sla-warning' : 'sla-ok')
    : minutesRemaining <= 30 ? 'sla-urgent' : minutesRemaining <= 120 ? 'sla-warning' : 'sla-ok';

  function startTicker() {
    ticker = setInterval(() => {
      minutesRemaining = Math.max(0, minutesRemaining - 1);
    }, 60_000);
  }

  onMount(() => {
    startTicker();

    // Listen for approval.sla_at_risk events for THIS approval
    slaListener = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail.approval_id !== approvalId) return;
      minutesRemaining = detail.minutes_remaining;
      percentRemaining = detail.percent_remaining;
    };
    document.addEventListener('sla:at_risk', slaListener);
  });

  onDestroy(() => {
    if (ticker) clearInterval(ticker);
    if (slaListener) document.removeEventListener('sla:at_risk', slaListener);
  });

  function format(mins: number): string {
    if (mins <= 0) return 'Breached';
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  }
</script>

<span class="sla-badge {cssClass}" title="Deadline: {new Date(slaDeadline).toLocaleString('en-SG')}">
  {format(minutesRemaining)}
</span>
```

**Clearing the countdown:** when an `approval.approved`, `approval.rejected`, or `approval.delegated` SSE event arrives for this `approvalId`, the parent component removes `SlaCountdown` from the DOM (by removing the approval from the store), which triggers `onDestroy` automatically.

---

### 13.7 API Client Base

All API calls flow through a single base function that handles auth headers, 401 refresh, and error envelope parsing per `05` §16.

```typescript
// src/lib/api/client.ts

import { auth, getAccessToken } from '$lib/stores/auth';
import { goto } from '$app/navigation';

const BASE = import.meta.env.PUBLIC_API_BASE_URL;

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

let isRefreshing = false;
let refreshQueue: Array<(token: string) => void> = [];

async function refreshAccessToken(): Promise<string> {
  // Call POST /auth/refresh (cookie-based or body-based per 13 security decisions)
  const res = await fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include' });
  if (!res.ok) throw new Error('refresh_failed');
  const { access_token, user } = await res.json();
  auth.setSession(access_token, user);
  return access_token;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAccessToken();

  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
    credentials: 'include',
  });

  // 401 → attempt one silent refresh then retry
  if (response.status === 401 && !isRefreshing) {
    isRefreshing = true;
    try {
      const newToken = await refreshAccessToken();
      isRefreshing = false;
      refreshQueue.forEach(cb => cb(newToken));
      refreshQueue = [];
      return apiFetch<T>(path, options);  // retry once
    } catch {
      isRefreshing = false;
      auth.clearSession();
      goto(`/login?return=${encodeURIComponent(path)}`);
      throw new ApiError(401, 'SESSION_EXPIRED', 'Session expired');
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      body.error?.code ?? 'UNKNOWN_ERROR',
      body.error?.message ?? response.statusText
    );
  }

  return response.json() as Promise<T>;
}
```

---

### 13.8 Component Conventions


| Rule                                                                                                                                        | Rationale                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Every component that fetches data uses the `$lib/api/*` functions inside a store action, not directly inside `onMount`.                     | Keeps fetching logic testable in isolation; components only read stores.                                                                                  |
| No component calls `fetch` directly.                                                                                                        | Ensures auth headers, error parsing, and refresh logic apply universally.                                                                                 |
| All server-origin text rendered in `{@html}` must be sanitized first.                                                                       | XSS per §10. The only permitted use of `{@html}` is for pre-sanitized audit trail descriptions.                                                           |
| Permission checks in templates use `hasPermission('code')` derived store — never hard-code role slugs.                                      | Role slugs may be renamed; permission codes are stable. The server is authoritative — hide buttons the server would reject, but do not rely on hide-only. |
| Loading states: every data-loading section shows `<SkeletonRow>` during `loading: true` and `<ErrorBanner>` on `error !== null`.            | Required by §9.                                                                                                                                           |
| Optimistic UI is **prohibited** for approve/reject/delegate actions.                                                                        | Required by §9 — wait for 200 before updating state.                                                                                                      |
| Cursor pagination: pass the current `nextCursor` to `loadMore()` on the store; never reconstruct pagination from offset.                    | Cursor API per `05` §1.4.                                                                                                                                 |
| All monetary amounts pass through `formatAmount(value, currency)` from `$lib/utils/currency.ts`.                                            | Prevents raw decimal strings in the UI.                                                                                                                   |
| Timeline `event_type` codes are mapped to display labels via `eventTypeLabels.ts` (a simple `Record<string, string>`), never displayed raw. | API codes like `processing_completed` are not user-facing copy.                                                                                           |


---

### 13.9 Build and Development Commands

```bash
# Install dependencies
pnpm install

# Development server (http://localhost:5173)
pnpm dev

# Type-check
pnpm check

# Unit and integration tests
pnpm test

# E2E tests (requires running API or msw handlers)
pnpm test:e2e

# Production build
pnpm build

# Preview production build locally
pnpm preview
```

`pnpm` is the mandated package manager (lockfile: `pnpm-lock.yaml`). Do not commit `package-lock.json` or `yarn.lock`.

---

## 14. Out of Scope (All Phases — Permanently Excluded)

- Native mobile apps.
- Offline-first editing of approvals.
- Embedded accounting GL posting from the UI beyond what `05` explicitly exposes.
- Custom report builder.

> **Expense claim UI is MVP scope (Phase 11):** The expense claim submission form (`/expense-claims/new`) and expense claims list (`/expense-claims`) specified in §8.7–8.8 are **Phase 11 MVP deliverables**. They must be built as part of Phase 11 and are required for Phase 1 acceptance. They are not in the list above because they are not out of scope — they are in scope and sequenced after Phase 10. See `19_Expense_Worker_Specification.md` §1 and `05_API_Specification.md` §18 for the API contract.

Future revisions may add embedded analytics, mobile push, or richer notification channels once `05`/`09` define them.

---

## Version History


| Version | Date | Changes |
|---------|------|---------|
| 2.32 | 2026-05-27 | **`0.14.11-admin-ui-cleanup` (planned).** §8.13 Client Admin nav trimmed: Mailboxes removed from header. Dashboard tiles deleted: `payment_terms`, `tax_codes`, `vendor_contracts`, `mailboxes`, `calendar`, `gl_reminders` — these belong to finance-ui (§8.22–§8.24). `users` tile relabelled "Key Roles Email (Uses)". §8.14 Mailboxes screen still documented (route preserved; direct URL only). |
| 2.31 | 2026-05-26 | **`0.14.9-binding-authority`.** §8.25 Client Admin `/binding-authority`; §8.13 nav + Policies label; §8.21 binding approval panel; §2.1a approvals tabs (queue/history/cases). `05` §4.16d.14. |
| 2.30 | 2026-05-20 | **Finance UI setup screens (`e73c869`).** §8.22–§8.24 on finance.mmlogistix; §8.23 agreements; §8.13 Client Admin nav trimmed (no travel, no counterparty/calendar). §3.1 routes + header nav. |
| 2.29 | 2026-05-20 | **§8.22 subaccount inline edit.** Active rows: Edit/Save/Cancel for `payment_term_id` + credit limit via `PATCH /api/counterparty-accounts/{id}` (`9b0662e`). |
| 2.28 | 2026-05-20 | **§8.22 credit limit UI.** Subaccounts tab: `credit_limit_amount` + currency on create; table column; Tab 2 note (credit per subaccount, not on payment-terms catalog). Status → shipped. |
| 2.27 | 2026-05-20 | **`0.14.8` shipped.** §8.22 `/counterparty-accounts` live; nav includes Counterparty Accounts. Git `b1095c1`–`9350495`. |
| 2.26 | 2026-05-20 | **Counterparty accounts (`0.14.8`, planned).** §8.22: Client Admin `/counterparty-accounts` — subaccounts, payment terms, GST mapping; nav + dashboard checks. Cross-ref `06` §4.1a–c, `17` §3.2.1–§3.2.3. |
| 2.25 | 2026-05-20 | **COA build fix (`8d6bf6e`).** §8.10: Svelte 5 event-handler syntax requirement for production Docker build. |
| 2.24 | 2026-05-20 | **Tenant COA (`0.14.7-coa-tenant-import`).** §8.10: `/chart-of-accounts` import upsert, `replace_all`, filter/search/Clear, empty vs configured states. Cross-ref `05` §4.16d.3, `11` §4.5h. |
| 2.23 | 2026-05-20 | **Email signatures (`0.14.6`).** §8.17: `/company` signature fields + preview panel; cross-ref `18` §10.2 shipped implementation. |
| 2.22 | 2026-05-20 | **GL period reopen (`0.14.5`).** §8.24 Reopen button + modal; §8.21 retry after reopen, override only when period still closed. |
| 2.20 | 2026-05-25 | **Client Admin `0.14.4`.** §8.20 calendar UI; §8.21 finance-ui Override & Post for closed GL periods. |
| 2.19 | 2026-05-24 | **Manual review detail panel (`0.13.6`).** §8.5: case detail shows `missing_fields`, `extraction_confidence`, `extracted_fields` from `workflow_metadata`. Cross-ref `17` §10.4.1. |
| 2.18 | 2026-05-24 | **Login TOTP input fix.** §8.1: TOTP field uses `type="text"` + `maxlength="6"` only (no `pattern`/`inputmode`). Shipped `finance-ui@0.13.5-login-totp-input-fix`. |
| 2.17 | 2026-05-24 | **Login two-step 2FA.** §4.2, §8.1: `/login` shows TOTP field only after `TOTP_REQUIRED` from step 1; resubmit with `totp_code`. Shipped `finance-ui@0.13.4-login-2fa-step`. |
| 2.16 | 2026-05-20 | **Client Admin `0.14.2`.** §8.13: dashboard accuracy, signatures, policy/regulatory PDFs, travel-info, calendar generate forward; migration `051`. |
| 2.15 | 2026-05-20 | **Client Admin shipped (`0.14.1`).** §8.13: routes, `/api` admin API, Traefik. |
| 2.17 | 2026-05-24 | **Client Admin not built.** §8.13 implementation status: `client-admin-ui` README stub only; COA/tenant APIs not in `accfin` `0.13.8`. Cross-ref `Product_Overview` §9.1. |
| 2.16 | 2026-05-20 | **Security settings / 2FA.** §2.1a, §4, §8.5: `/settings/security` with QR setup (`qrcode`), verify, disable; nav **Security** link; mandatory-2FA banner for `cfo`/`finance_manager`. Package `0.13.3-security-2fa`. Deploy `0.13.6-finance-security-2fa`. |
| 2.15    | 2026-05-20 | **Case retry button.** §2.1a, §4: `POST /cases/{id}/retry` on case detail for `exception`/`manual_review`; finance-ui `0.13.1-case-retry`. |
| 2.14    | 2026-05-20 | **Silent JWT refresh.** §4: `localStorage` access + refresh tokens; proactive `POST /auth/refresh` within 2 min of expiry; deploy `0.12.8-finance-token-refresh`, package `0.12.5-finance-token-refresh`. |
| 2.13    | 2026-05-22 | **Deploy doc cross-ref.** §2.2 aligned with `11` §20.2 (`0.12.4-client-auth`). |
| 2.12    | 2026-05-20 | **Client auth.** §2.2: `ssr = false` on authenticated routes; `localStorage` JWT; `goto()` after login. Package `0.12.3-client-auth`. |
| 2.11    | 2026-05-20 | **Branding.** §2.1: product name **mmlogistix Finance** (replaces LogiScore Finance); `branding.ts` + shell header. Package `0.12.2-mmlogistix-branding`. |
| 2.10    | 2026-05-20 | **Production URLs.** Approval UI at `https://finance.mmlogistix.bp0.work`; §13.3 same-origin API/SSE; Client Admin `admin.mmlogistix.bp0.work` (shipped `0.14.1`). No `api.bp0.work`. |
| 2.9     | 2026-05-19 | **Companion Documents.** Added rows for `20_Git_Workflow_and_Prompt_Management.md` and `21_openapi.yaml` (suite-wide sync per `03` §15, `00` v2.32). |
| 2.8     | 2026-05-19 | **Monorepo deploy paths.** §8.11–§8.12, §13: SvelteKit apps live under `accounting/finance-ui/`, `accounting/platform-admin-ui/`, `accounting/client-admin-ui/` (single clone `bp0work/accounting`). Cross-ref `03` §17.1. |
| 2.7     | 2026-05-19 | **§8.19 pending client clarifications.** Manager preview, approve/reject with parsing reason codes; attachment-may-contain-data badge. |
| 2.6     | 2026-05-19 | **Email SOP DDL cross-refs.** §8.14: `pending_outbound_emails` (`06` §7.6), `case_escalations` (`06` §7.5). |
| 2.5     | 2026-05-19 | **Organizational hierarchy mailboxes.** §8.9/§8.14: CEO, CFO, Manager Accounts, Manager Finance, domain executives; help text for Approve/Reject/Escalate chain (`01` §3.2.3). |
| 2.4     | 2026-05-19 | **Executive email SOP — Client Admin mailboxes.** §8.14: per-role **Approve outbound to client** toggle (`requires_outbound_client_approval`); mode/escalation columns; SOP help text. Cross-ref `01` §6.8, `17` §10, `06` §7.3. |
| 2.3     | 2026-05-19 | **Financial Analyst role.** New §8.3: expense/cost/revenue analysis, financial reports, month-end close (`/finance/dashboard`, `/finance/reports`, `/finance/month-end`). Mailbox `finfa.mmlogistix@bp0.work` in §8.9. §5 RBAC row; no `approvals:approve`. Renumbered §8.4–8.18 (Approval detail was §8.3). Cross-ref `06` §19.1, `13` §5.6. |
| 2.2     | 2026-05-19 | **Client Admin: travel & expense policy.** §8.12 nav `/expense-policy`; §8.18: Tab 1 — edit `expense_policies` limits (meals, accommodation, airfare, global receipt/approval thresholds); Tab 2 — optional company policy PDF on `tenant_profiles`. §8.6: link to view policy PDF on expense claim submission when uploaded. APIs: `05` §4.16b.5, §4.16c. Cross-ref `13` §5.9, `06` §13.2b, `19` §3.4–§5. |
| 2.1     | 2026-05-19 | §13.3 build-time URLs (superseded by v2.10). |
| 2.0     | 2026-05-19 | **Two separate admin applications** (distinct from Approval UI). §8.11 Platform Admin UI (`platform-admin-ui`): dynamic tenant registry, edit Client Admin email only (`GET /platform/tenants`, `PATCH .../client-admin`). §8.12–8.16 Client Admin UI (`client-admin-ui`): mailboxes with sent-from names (§8.13), COA import (§8.9), company legal details for SOA (§8.14), logo (§8.15), email signature on all outbound mail (§8.16). §5 RBAC: `platform_admin` and `client_admin` rows. APIs: `05` §4.16a–b; data: `06` §13.2a–b; security: `13` §5.9.                                                                     |
| 1.7     | 2026-05-17 | Fix (Issue 2 from cross-document audit): Updated all expense claim UI permission gates from generic `cases:write` to dedicated `expenses:write` — §3.1 route table, §8.6 screen spec header, and §8.6 Permissions note. Aligns with `05_API_Specification.md` §18 (also updated), `13_Security_and_Compliance_Specification.md` §5.6 RBAC table, and `19_Expense_Worker_Specification.md` §3.4.                                                                                                                                                                                                                                |
| 1.6     | 2026-05-17 | Fix (M-3 from cross-document audit): Corrected stale `## Date:` header — was `16 May 2026`; updated to `17 May 2026` to match suite-wide date. Bumped version from `1.5` to `1.6`. Same class of stale-header bug previously fixed in `01` v4.3, `02` v5.5, and `00` v2.7. No content changes.                                                                                                                                                                                                                                                                                                                                 |
| 1.5     | 2026-05-16 | Scope consistency fix: Updated §14 heading from "Out of Scope (MVP — Phases 1–10)" to "Out of Scope (All Phases — Permanently Excluded)". Removed bullet "Expense claim submission UI — deferred to Phase 11" — this was incorrect because Phase 11 is MVP and the expense claim UI screens (§8.6–8.7) are MVP deliverables. Replaced with a callout box clarifying that the expense claim UI is Phase 11 MVP scope, required for Phase 1 acceptance, and not in the permanently-excluded list. Header date corrected from `15 May 2026` to `16 May 2026` (17 May 2026 housekeeping pass) to match this version history entry. |
| 1.4     | 2026-05-15 | Fix (INC-6 from audit): Corrected stale document header date from `11 May 2026` to `15 May 2026` to match the latest version history entry (v1.3, dated 2026-05-15). Header was not updated when versions 1.1, 1.2, and 1.3 were applied.                                                                                                                                                                                                                                                                                                                                                                                      |
| 1.3     | 2026-05-15 | Fix (INC-4 from audit): Added framework-agnostic note to §13 (Frontend Architecture Reference) clarifying that SvelteKit is recommended but not mandated; §13.1–13.5 are SvelteKit-specific while §13.3 and §13.6 are framework-agnostic. Teams choosing an alternative framework must adapt the SvelteKit-specific sections and document the framework decision in the `finance-ui` README. Fix (GAP-1 back-propagation): Updated §1 normative source note — expense claim endpoints are now fully incorporated into `05_API_Specification.md` §18 (v1.0.3); removed "pending incorporation" language.                        |
| 1.2     | 2026-05-15 | Fix (Issue 2 from audit): Added Phase 11 expense claim UI coverage throughout. §1 normative sources: added `19` §1 and §4 reference. §3.1 routes: added `/expense-claims/new` and `/expense-claims` (Phase 11). §6 API Consumption Map: added `POST /expense-claims`, `GET /expense-claims`, `GET /expense-claims/{id}` rows. §8.6 New screen spec: Expense claim submission form (field list, validation, idempotency, duplicate-409 handling, permission gate). §8.7 New screen spec: Expense claims list. §14 Out of Scope: made Phase 11 deferral explicit with pointer to `19` §1.                                        |
| 1.1     | 2026-05-14 | Fix (Issue 3): Extended normative REST contract reference in §1 from `05` §4.13–4.16 to §4.13–4.18 to include the notification inbox endpoints (§4.17 `GET /notifications`, §4.18 `POST /notifications/read`) which are the primary inbox endpoints consumed by the UI. Fix (Issue 4): Extended DB persistence reference in §1 from `06` §3.6–3.7 to §3.6–3.8 to include the `notifications` inbox table (§3.8) that backs `GET /notifications`.                                                                                                                                                                               |
| 1.0     | 2026-05-11 | Initial release                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |


