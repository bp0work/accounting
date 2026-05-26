# AI Finance Operations Platform

# API Specification

## Version 1.3.23

## Filename: 05_API_Specification.md

## Prepared For: mmlogistix

## Date: 25 May 2026

---

# Companion Documents

| Document | Filename |
|----------|----------|
| Project Overview | 00_Project_Overview.md |
| Business Requirements | 01_Business_Requirement_Document.md |
| Technical Architecture | 02_Technical_Architecture.md |
| Cursor Development Brief | 03_Cursor_Development_Brief.md |
| Hermes Integration Specification | 04_Hermes_Integration_Spec.md |
| API Specification | 05_API_Specification.md |
| Database Schema | 06_Database_Schema_Design.md |
| AI Runtime Sequences | 07_AI_Runtime_Sequence_Diagrams.md |
| Workflow State Machine | 08_Workflow_State_Machine.md |
| Event Model | 09_Event_Model_Specification.md |
| Policy Engine | 10_Policy_Engine_Specification.md |
| Deployment Runbook | 11_Deployment_Operations_Runbook.md |
| Testing Strategy | 12_Testing_and_UAT_Strategy.md |
| Security & Compliance Specification | 13_Security_and_Compliance_Specification.md |
| Environment & Configuration Reference | 14_Environment_and_Configuration_Reference.md |
| Approval UI Specification | 15_Approval_UI_Specification.md |
| Migration and ORM Specification | 16_Migration_and_ORM_Specification.md |
| Worker Specifications | 17_Worker_Specifications.md |
| Notification Service Specification | 18_Notification_Service_Specification.md |
| Expense Worker Specification | 19_Expense_Worker_Specification.md |
| Git Workflow and Prompt Management | 20_Git_Workflow_and_Prompt_Management.md |
| OpenAPI Contract | 21_openapi.yaml |

---

# Table of Contents

1. [API Design Principles](#1-api-design-principles)
2. [Base Configuration](#2-base-configuration)
3. [Authentication](#3-authentication)
4. [Users & RBAC](#4-users--rbac)
   - 4.1–4.12 User and Role management
   - 4.13–4.16 Notification preferences and templates
   - 4.16d Client Admin operational API (shipped)
   - 4.17–4.18 Notification inbox
5. [Cases](#5-cases)
6. [Workflow Engine](#6-workflow-engine)
7. [Approvals](#7-approvals)
8. [Mail Gateway](#8-mail-gateway)
9. [Queue Management](#9-queue-management)
9a. [Events & SSE](#9a-events--sse)
10. [Policies](#10-policies)
11. [Chart of Accounts](#11-chart-of-accounts)
12. [Journal Entries](#12-journal-entries)
13. [Reconciliation](#13-reconciliation)
14. [Audit Logs](#14-audit-logs)
15. [Dashboard & Metrics](#15-dashboard--metrics)
16. [Error Handling](#16-error-handling)
17. [Common Schemas](#17-common-schemas)
18. [Expense Claims (Phase 11)](#18-expense-claims-phase-11)
19. [Internal & Scheduled Jobs](#19-internal--scheduled-jobs)
   - 19.1 Finance daily activity log
   - 19.2 GL cutoff reminders

---

# 1. API Design Principles

## 1.1 RESTful Conventions

- Resource-oriented URLs using nouns, not verbs
- Plural resource names: `/cases`, `/policies`, `/journal-entries`
- Actions expressed via HTTP methods and sub-resources, not URL verbs

| Method | Action |
|--------|--------|
| GET | Retrieve resource(s) |
| POST | Create resource |
| PUT | Full update (replace) |
| PATCH | Partial update |
| DELETE | Remove resource |

## 1.2 URL Patterns

```
/cases                     # collection
/cases/{id}                # single resource
/cases/{id}/approvals      # sub-resource (related collection)
/cases/{id}/approve        # action sub-resource (POST only)
```

## 1.3 Request & Response Format

- Request body: JSON
- Response body: JSON
- Content-Type: `application/json` required for POST/PUT/PATCH
- Empty body responses return `204 No Content`

## 1.4 Pagination

List endpoints support cursor-based pagination:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Items per page (max 200) |
| `cursor` | string | none | Pagination cursor from previous response |

**Response envelope:**

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTIz...",
    "has_more": true,
    "total": 1547
  }
}
```

If no `cursor` provided, returns first page.
If `has_more` is false, `next_cursor` is omitted.

## 1.5 Sorting

| Parameter | Format | Example |
|-----------|--------|---------|
| `sort` | `field:direction` | `created_at:desc`, `priority:asc` |

Default sort: `created_at:desc` for most collections.

## 1.6 Filtering

| Parameter | Format | Example | Behavior |
|-----------|--------|---------|----------|
| `status` | exact or comma-list | `status=pending` or `status=pending,processing` | IN clause |
| `from_date` | ISO 8601 date | `from_date=2026-04-01` | >= comparison |
| `to_date` | ISO 8601 date | `to_date=2026-04-30` | <= comparison |
| `q` | string | `q=ACME+Corp` | Full-text search (case-insensitive) |

Multiple filters are combined with AND logic.

## 1.7 Field Selection

| Parameter | Format | Example |
|-----------|--------|---------|
| `fields` | comma-separated | `fields=id,status,created_at` |

If omitted, all readable fields returned.

## 1.8 Idempotency

Mutating endpoints support idempotency via header:

```
Idempotency-Key: <uuid>
```

Keys valid for 24 hours. Repeated requests with same key return cached response.

## 1.9 Common Headers

**Request:**

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes (except /auth) | `Bearer {jwt_token}` |
| `Content-Type` | POST/PUT/PATCH | `application/json` |
| `X-Request-ID` | Recommended | Client-generated UUID for tracing |
| `Idempotency-Key` | Recommended | UUID for idempotency |

**Response:**

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Echoed or server-generated request ID |
| `X-RateLimit-Limit` | Requests per minute allowed |
| `X-RateLimit-Remaining` | Requests remaining in window |
| `X-RateLimit-Reset` | Unix timestamp when limit resets |

## 1.10 Machine-Readable OpenAPI Contract

This document defines the API in prose and JSON examples, but the implementation MUST also include a machine-readable OpenAPI contract.

**Phase 2 mandatory first deliverable:** Generate `openapi.yaml` from this API specification before endpoint implementation begins. Once generated and reviewed, `openapi.yaml` becomes the source of truth for API contract tests, request/response validation, generated client stubs, and API documentation.

**Developer requirements:**

- Create `openapi.yaml` using OpenAPI 3.1 or later.
- Cover every operation listed in Appendix A (one row per HTTP method).
- Keep `21_openapi.yaml` in lockstep with Appendix A for schemathesis/contract CI; any drift is a build failure (see OBS-4 maintenance note under Appendix A).
- Define reusable schemas for common objects such as `Money`, `UserReference`, `Counterparty`, pagination envelopes, error responses, approval requests, cases, journal entries, policies, queues, and reconciliation objects.
- Include authentication, permissions, headers, path parameters, query parameters, request bodies, response bodies, and documented error responses.
- Add contract tests that validate implemented FastAPI routes against `openapi.yaml`.
- Treat any mismatch between implementation and `openapi.yaml` as a build/test failure unless the schema is intentionally updated.

The prose specification remains useful for explanation and business context, but the OpenAPI file is the technical contract used by developers and automated tests.

---

# 2. Base Configuration

| Property | Value |
|----------|-------|
| Public base URL | **None** — FastAPI is not exposed on a dedicated public hostname (`14` §9.0) |
| Internal base URL (Docker) | `http://fastapi:8000` — service name on Compose network `accfin_frontend` |
| Edge base URL (browser / signed email links) | `https://finance.mmlogistix.bp0.work` — Traefik forwards API path prefixes (`/auth`, `/mail`, `/approvals`, …) to FastAPI on the same host as the Approval UI |
| Protocol (edge) | HTTPS only |
| TLS Version | 1.3 minimum |
| Rate Limit | 300 requests/minute per API key |
| Request Timeout | 30 seconds (default), 120 seconds (file upload) |
| Max Request Body | 10 MB (JSON), 50 MB (multipart/file) |
| Max Page Size | 200 items |

---

# 3. Authentication

Base path: `/auth`

All endpoints except login require a valid JWT token.

## 3.1 Login

```
POST /auth/login
```

**Description:** Authenticate user and obtain JWT tokens.

**Request:**

```json
{
  "username": "string",     // required, 3-50 chars
  "password": "string",     // required, 8-100 chars
  "totp_code": "string"     // optional, 6 digits; required if 2FA enabled
}
```

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",    // JWT, expires 15 min
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",   // JWT, expires 7 days
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "username": "string",
    "display_name": "string",
    "email": "string",
    "role": "string",
    "permissions": ["cases:read", "cases:write", "approvals:read"],
    "two_factor_enabled": true
  }
}
```

**Errors:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `INVALID_CREDENTIALS` | Username or password incorrect |
| 401 | `TOTP_REQUIRED` | 2FA enabled but TOTP code missing |
| 401 | `INVALID_TOTP` | TOTP code invalid or expired |
| 429 | `RATE_LIMITED` | Too many login attempts; retry after 60s |

---

## 3.2 Refresh Token

```
POST /auth/refresh
```

**Description:** Obtain new access token using refresh token.

**Request:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Errors:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `INVALID_REFRESH_TOKEN` | Token invalid or expired |
| 401 | `REFRESH_TOKEN_REVOKED` | Token has been revoked (logout or security event) |

---

## 3.3 Logout

```
POST /auth/logout
```

**Description:** Revoke current session tokens.

**Headers:** `Authorization: Bearer {access_token}`

**Request:** Empty body. Token identified from Authorization header.

**Response (204):** No content.

**Errors:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `UNAUTHORIZED` | No valid token provided |

---

## 3.4 Setup 2FA

```
POST /auth/2fa/setup
```

**Description:** Initiate TOTP 2FA setup for authenticated user.

**Headers:** `Authorization: Bearer {access_token}`

**Response (200):**

```json
{
  "secret": "JBSWY3DPEHPK3PXP",              // base32 encoded secret
  "qr_code_uri": "otpauth://totp/mmlogistix:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=mmlogistix",
  "backup_codes": ["12345678", "87654321", "..."]   // 8 codes, single-use
}
```

---

## 3.5 Verify and Enable 2FA

```
POST /auth/2fa/verify
```

**Description:** Verify TOTP code and activate 2FA.

**Headers:** `Authorization: Bearer {access_token}`

**Request:**

```json
{
  "totp_code": "123456",
  "secret": "JBSWY3DPEHPK3PXP"
}
```

**Response (200):** 2FA enabled.

---

## 3.6 Disable 2FA

```
POST /auth/2fa/disable
```

**Headers:** `Authorization: Bearer {access_token}`

**Request:**

```json
{
  "totp_code": "123456"
}
```

**Response (204):** 2FA disabled.

**Errors:**

| Status | Code | Message |
|--------|------|---------|
| 403 | `ADMIN_REQUIRED` | Admin permission required to disable 2FA without verification |

---

# 4. Users & RBAC

Base path: `/users`

All endpoints require `users:read` or `users:write` permission.

## 4.1 List Users

```
GET /users
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | `active`, `inactive`, `locked` |
| `role` | string | Filter by role ID |
| `department` | string | Filter by department |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "username": "string",
      "display_name": "string",
      "email": "string",
      "role_id": "uuid",
      "role_name": "string",
      "department": "string",
      "status": "active",
      "two_factor_enabled": true,
      "last_login_at": "2026-05-10T09:30:00Z",
      "created_at": "2026-01-15T00:00:00Z",
      "updated_at": "2026-05-10T09:30:00Z"
    }
  ],
  "pagination": {
    "next_cursor": "...",
    "has_more": true,
    "total": 42
  }
}
```

---

## 4.2 Get User

```
GET /users/{id}
```

**Response (200):** Single user object (schema as above).

---

## 4.3 Create User

```
POST /users
```

**Request:**

```json
{
  "username": "string",         // required, 3-50 chars, unique
  "display_name": "string",     // required, 1-100 chars
  "email": "string",            // required, valid email, unique
  "password": "string",         // required, 8-100 chars
  "role_id": "uuid",            // required
  "department": "string",       // optional
  "is_active": true             // optional, default true
}
```

**Response (201):** Created user object (password excluded).

**Validation Errors:**

| Status | Code | Message |
|--------|------|---------|
| 400 | `USERNAME_EXISTS` | Username already taken |
| 400 | `EMAIL_EXISTS` | Email already registered |
| 400 | `INVALID_PASSWORD` | Password does not meet complexity requirements |
| 400 | `INVALID_ROLE` | Role ID does not exist |

---

## 4.4 Update User

```
PUT /users/{id}
```

**Request:** Same as Create, except all fields optional. `username` and `email` cannot be changed.

**Response (200):** Updated user object.

---

## 4.5 Lock/Unlock User

```
POST /users/{id}/lock
POST /users/{id}/unlock
```

**Description:** Lock (disable) or unlock a user account.

**Response (200):** Updated user with new status.

---

## 4.6 Change Password

```
POST /users/{id}/change-password
```

**Request:**

```json
{
  "current_password": "string",
  "new_password": "string"
}
```

**Response (204):** Password changed.

---

## 4.7 Reset Password (Admin)

```
POST /users/{id}/reset-password
```

**Description:** Admin-initiated password reset. Generates temporary password.

**Permissions Required:** `users:admin`

**Two-tier scope (`13` §5.9):** Callers with `users:admin` and `platform:admin` may reset passwords only for users whose role is `client_admin` or `platform_admin`. Finance-role password resets require a separate Finance Director workflow (not Platform Admin). `PUT /users/{id}` email changes for the Client System Administrator account follow the same guard.

---

## 4.8 List Roles

```
GET /roles
```

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "name": "finance_officer",
      "display_name": "Finance Officer",
      "description": "Standard finance team member",
      "permissions": [
        "cases:read",
        "cases:write",
        "approvals:read",
        "journal-entries:read"
      ],
      "is_system": false,
      "created_at": "2026-01-15T00:00:00Z"
    }
  ]
}
```

---

## 4.9 Create Role

```
POST /roles
```

**Request:**

```json
{
  "name": "string",             // required, unique, snake_case
  "display_name": "string",     // required
  "description": "string",      // optional
  "permissions": ["string"]     // required, array of permission strings
}
```

**Response (201):** Created role.

---

## 4.10 Update Role

```
PUT /roles/{id}
```

**Request:** Same as Create. System roles (`is_system: true`) cannot be modified.

**Response (200):** Updated role.

---

## 4.11 Delete Role

```
DELETE /roles/{id}
```

**Description:** Delete a role. Fails if users are assigned.

**Response (204):** Role deleted.

**Errors:**

| Status | Code | Message |
|--------|------|---------|
| 409 | `ROLE_IN_USE` | Cannot delete role with assigned users |
| 403 | `SYSTEM_ROLE_PROTECTED` | System roles cannot be deleted |

---

## 4.12 List Permissions

```
GET /permissions
```

**Response (200):**

```json
{
  "data": [
    {
      "code": "cases:read",
      "category": "cases",
      "action": "read",
      "description": "View cases and case details"
    },
    {
      "code": "cases:write",
      "category": "cases",
      "action": "write",
      "description": "Create and update cases"
    },
    {
      "code": "cases:delete",
      "category": "cases",
      "action": "delete",
      "description": "Delete cases"
    },
    {
      "code": "approvals:read",
      "category": "approvals",
      "action": "read",
      "description": "View approval requests and history"
    },
    {
      "code": "approvals:approve",
      "category": "approvals",
      "action": "approve",
      "description": "Approve or reject approval requests"
    },
    {
      "code": "approvals:admin",
      "category": "approvals",
      "action": "admin",
      "description": "Override approvals, manage approval rules"
    },
    {
      "code": "journal-entries:read",
      "category": "journal_entries",
      "action": "read",
      "description": "View journal entries"
    },
    {
      "code": "journal-entries:write",
      "category": "journal_entries",
      "action": "write",
      "description": "Create and post journal entries"
    },
    {
      "code": "policies:read",
      "category": "policies",
      "action": "read",
      "description": "View accounting and workflow policies"
    },
    {
      "code": "policies:write",
      "category": "policies",
      "action": "write",
      "description": "Create and update policies"
    },
    {
      "code": "queues:read",
      "category": "queues",
      "action": "read",
      "description": "View queue status and messages"
    },
    {
      "code": "queues:admin",
      "category": "queues",
      "action": "admin",
      "description": "Manage queue messages, retry, purge"
    },
    {
      "code": "reconciliation:read",
      "category": "reconciliation",
      "action": "read",
      "description": "View reconciliation data"
    },
    {
      "code": "reconciliation:write",
      "category": "reconciliation",
      "action": "write",
      "description": "Perform reconciliations, match/unmatch"
    },
    {
      "code": "audit-logs:read",
      "category": "audit_logs",
      "action": "read",
      "description": "View audit logs"
    },
    {
      "code": "users:read",
      "category": "users",
      "action": "read",
      "description": "View users"
    },
    {
      "code": "users:write",
      "category": "users",
      "action": "write",
      "description": "Create and update users"
    },
    {
      "code": "users:admin",
      "category": "users",
      "action": "admin",
      "description": "Full user management including password resets"
    },
    {
      "code": "settings:read",
      "category": "settings",
      "action": "read",
      "description": "View system settings"
    },
    {
      "code": "settings:write",
      "category": "settings",
      "action": "write",
      "description": "Modify system settings"
    },
    {
      "code": "mail:read",
      "category": "mail",
      "action": "read",
      "description": "View mail gateway messages and logs"
    },
    {
      "code": "mail:admin",
      "category": "mail",
      "action": "admin",
      "description": "Manage mail gateway configuration"
    }
  ]
}
```

---

## 4.13 Get My Notification Preferences

```
GET /users/me/notification-preferences
```

**Description:** Returns the signed-in user’s delivery preferences for workflow and approval notifications (persisted in `user_notification_preferences`; DDL in `06_Database_Schema_Design.md` §3.7; migration phase 9 — see `00_Project_Overview.md` §5.1).

**Permissions:** Authenticated user. The resource is always scoped to `current_user.id`.

**Response (200):**

```json
{
  "user_id": "uuid",
  "quiet_hours": {
    "enabled": false,
    "start_local": "22:00",
    "end_local": "07:00",
    "timezone": "Asia/Singapore"
  },
  "channels": {
    "email": true,
    "in_app": true
  },
  "subscriptions": [
    {
      "event_key": "approval.requested",
      "email": true,
      "in_app": true,
      "digest": "off"
    },
    {
      "event_key": "approval.sla_at_risk",
      "email": true,
      "in_app": true,
      "digest": "off"
    },
    {
      "event_key": "approval.escalated",
      "email": true,
      "in_app": true,
      "digest": "off"
    },
    {
      "event_key": "case.assigned",
      "email": false,
      "in_app": true,
      "digest": "off"
    }
  ],
  "updated_at": "2026-05-11T08:12:00Z"
}
```

**Response (404):** No row exists yet. The client SHOULD apply conservative defaults (for example `in_app: true` for approval events) and MAY `PUT` to persist explicit choices.

---

## 4.14 Replace My Notification Preferences

```
PUT /users/me/notification-preferences
```

**Permissions:** Authenticated user.

**Request:** Same logical shape as **§4.13**, omitting server-owned fields `user_id` and `updated_at`:

```json
{
  "quiet_hours": {
    "enabled": true,
    "start_local": "22:00",
    "end_local": "07:00",
    "timezone": "Asia/Singapore"
  },
  "channels": {
    "email": true,
    "in_app": true
  },
  "subscriptions": [
    {
      "event_key": "approval.requested",
      "email": true,
      "in_app": true,
      "digest": "off"
    }
  ]
}
```

| Field / rule | Description |
|--------------|-------------|
| `event_key` | MUST appear in `GET /notification-templates` (`§4.15`). |
| `digest` | `off` or `daily` (MVP implementations MAY accept only `off`). |

**Response (200):** Body as in **§4.13**.

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 400 | `INVALID_EVENT_KEY` | Unknown `event_key` |
| 400 | `INVALID_QUIET_HOURS` | Invalid local times or timezone identifier |

---

## 4.15 List Notification Templates (catalog)

```
GET /notification-templates
```

**Description:** Read-only catalog from `notification_templates` (`06_Database_Schema_Design.md` §3.6) for building the notification settings UI. Event keys SHOULD stay aligned with `09_Event_Model_Specification.md` where those events exist.

**Permissions:** Authenticated user.

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "event_key": "approval.requested",
      "display_name": "Approval requested",
      "description": "A new item requires your approval.",
      "default_email": true,
      "default_in_app": true,
      "user_overridable": true
    }
  ]
}
```

---

## 4.16 Update Notification Template (admin)

```
PATCH /admin/notification-templates/{template_id}
```

**Description:** Updates org-wide defaults and display metadata for a catalog row. Does not automatically rewrite per-user `user_notification_preferences` unless a documented batch job applies (out of scope for this endpoint).

**Permissions:** `settings:write`

**Request (partial):**

```json
{
  "default_email": false,
  "default_in_app": true,
  "display_name": "Approval requested (AR)"
}
```

**Response (200):** Updated template object (same fields as one element of **§4.15** `data`).

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 404 | `NOT_FOUND` | Unknown `template_id` |
| 403 | `FORBIDDEN` | Missing `settings:write` |

---

## 4.16a Platform Admin API (Platform Admin UI only)

Base path: `/platform`

**Audience:** Platform Administrator (`system@bp0.work`) only. Powers the **Platform Admin UI** (`15` §8.11). Primary capability: update Client Admin email addresses for any tenant. Client Admin receives `403` on all routes here.

### 4.16a.1 List Tenants with Client Administrators

```
GET /platform/tenants
```

**Permissions Required:** `platform:admin`

**Description:** Returns all tenants and their assigned Client System Administrator (dynamic list — grows as clients are onboarded).

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "slug": "mmlogistix",
      "display_name": "MM Logistix Pte Ltd",
      "is_active": true,
      "client_admin": {
        "user_id": "uuid",
        "email": "system.mmlogistix@bp0.work",
        "username": "system.mmlogistix",
        "status": "active",
        "two_factor_enabled": true
      }
    }
  ]
}
```

If a tenant has no `client_admin` user yet, `client_admin` is `null` (Platform Admin may provision via `POST /platform/tenants/{tenant_id}/client-admin` — post-MVP).

### 4.16a.2 Update Client Administrator Email

```
PATCH /platform/tenants/{tenant_id}/client-admin
```

**Permissions Required:** `platform:admin`, `users:admin`

**Description:** Updates the **email address** (and optionally `display_name`) of the `client_admin` user for the given tenant. This is the only routine mutation in the Platform Admin UI.

**Request:**

```json
{
  "email": "system.mmlogistix@bp0.work",
  "display_name": "mmlogistix System Administrator"
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `email` | string | Yes | Valid email; unique across `users` |
| `display_name` | string | No | Max 100 chars |

**Response (200):** Updated user object (password and 2FA unchanged).

**Errors:** `404` tenant or client_admin not found; `409` email already in use.

---

## 4.16b Tenant Profile API (Client Admin UI only)

Base path: `/tenant`

**Audience:** Client System Administrator (`tenant:admin`). Scoped to the authenticated user's `tenant_id`. Powers **Client Admin UI** company branding and policy screens (`15` §8.14–8.17).

### 4.16b.1 Get Tenant Profile

```
GET /tenant/profile
```

**Permissions Required:** `tenant:admin`

**Response (200):** Full `tenant_profiles` row plus `tenants.display_name` (`06` §13.2b).

### 4.16b.2 Update Tenant Profile

```
PUT /tenant/profile
```

**Permissions Required:** `tenant:admin`

**Description:** Company legal details used on SOA and formal documents.

**Request (partial):**

```json
{
  "legal_name": "MM Logistix Pte Ltd",
  "trading_name": "mmlogistix",
  "registration_number": "201234567A",
  "tax_id": "M12345678X",
  "address_line1": "1 Example Road",
  "city": "Singapore",
  "postal_code": "123456",
  "country": "SG",
  "phone": "+65 6123 4567",
  "company_email": "finance@mmlogistix.sg",
  "website": "https://www.mmlogistix.sg"
}
```

### 4.16b.3 Upload Tenant Logo

```
POST /tenant/profile/logo
```

**Permissions Required:** `tenant:admin`

**Request:** `multipart/form-data`, field `file` (PNG, JPEG, or SVG; max 2 MB).

**Response (200):** `{ "logo_storage_path": "...", "logo_content_type": "image/png" }`

### 4.16b.4 Update Email Signature

```
PUT /tenant/profile/email-signature
```

**Permissions Required:** `tenant:admin`

**Description:** Signature block appended to the bottom of **every outbound email** from tenant mailboxes (`18` §10.2). **Shipped `0.14.6`:** `OutboundMailService._load_tenant_signature()` reads `tenant_profiles`; `mail_template_renderer.append_tenant_signature()` applies footer to ack, escalation, clarification, daily log, and GL cutoff reminder bodies.

**Request:**

```json
{
  "email_signature_html": "<p>Regards,<br/>MM Logistix Finance</p>",
  "email_signature_plain": "Regards,\nMM Logistix Finance"
}
```

### 4.16b.5 Upload Travel & Expense Policy Document

```
POST /tenant/profile/expense-policy-document
```

**Permissions Required:** `tenant:admin`

**Description:** Optional PDF of the company’s written travel & expense policy (employee reference). Stored on `tenant_profiles` (`06` §13.2b). Distinct from numeric `expense_policies` rules (`4.16c`).

**Request:** `multipart/form-data`, field `file` (PDF only; max 10 MB).

**Response (200):**

```json
{
  "expense_policy_document_filename": "mmlogistix-travel-expense-policy-2026.pdf",
  "expense_policy_document_content_type": "application/pdf",
  "expense_policy_document_storage_path": "tenants/{tenant_id}/policies/expense-policy.pdf",
  "expense_policy_document_updated_at": "2026-05-19T10:00:00Z"
}
```

```
DELETE /tenant/profile/expense-policy-document
```

**Permissions Required:** `tenant:admin`

**Response (204):** Document fields cleared.

**Read metadata:** Included in `GET /tenant/profile` response. Finance users with `expenses:read` may request a time-limited signed download URL via `GET /tenant/expense-policy-document/url` (same pattern as logo signed URL).

---

## 4.16c Tenant Expense Policies API (Client Admin UI only)

Base path: `/tenant/expense-policies`

**Audience:** Client System Administrator (`tenant:admin`) for mutations; finance roles with `expenses:read` may list/read active policies for claim UI context.

**Data model:** `expense_policies` (`19` §3.3). Seeded by migration `044_seed_expense_policies.py` (`19` §13). Evaluated by the Expense Worker on each claim (`19` §5).

### 4.16c.1 List Expense Policies

```
GET /tenant/expense-policies
```

**Permissions Required:** `tenant:admin` **or** `expenses:read`

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `active_only` | bool | `false` | When `true`, return only `is_active = true` rows |

**Response (200):**

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "meals_daily_limit",
      "display_name": "Meals Daily Limit",
      "description": "Meal expenses capped at SGD 80 per day per claim.",
      "category": "meals",
      "applies_to_all_categories": false,
      "department": null,
      "applies_to_all_departments": true,
      "daily_limit": "80.00",
      "per_claim_limit": null,
      "requires_receipt_above": "30.00",
      "requires_approval_above": "500.00",
      "is_active": true,
      "effective_from": "2026-01-01",
      "effective_to": null,
      "version": "1.0.0",
      "updated_at": "2026-05-19T08:00:00Z"
    }
  ]
}
```

### 4.16c.2 Get Expense Policy

```
GET /tenant/expense-policies/{policy_id}
```

**Permissions Required:** `tenant:admin` **or** `expenses:read`

**Response (200):** Single policy object (same shape as list item).

**Errors:** `404` if not found.

### 4.16c.3 Update Expense Policy

```
PUT /tenant/expense-policies/{policy_id}
```

**Permissions Required:** `tenant:admin`

**Description:** Updates limits and metadata for an existing policy rule. Does **not** allow changing `name` or `category` (system keys). Server bumps `version` (patch segment) and writes audit `policy_updated` (`13` §9.1).

**Request:**

```json
{
  "display_name": "Meals Daily Limit",
  "description": "Meal expenses capped at SGD 80 per day per claim.",
  "daily_limit": "80.00",
  "per_claim_limit": null,
  "requires_receipt_above": "30.00",
  "requires_approval_above": "500.00",
  "is_active": true,
  "effective_from": "2026-01-01",
  "effective_to": null,
  "department": null,
  "applies_to_all_departments": true
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `display_name` | string | Yes | Max 200 chars |
| `description` | string | No | Max 2000 chars |
| `daily_limit` | decimal string | No | ≥ 0 if set |
| `per_claim_limit` | decimal string | No | ≥ 0 if set |
| `requires_receipt_above` | decimal string | Yes | ≥ 0 |
| `requires_approval_above` | decimal string | Yes | ≥ 0 |
| `is_active` | bool | Yes | Cannot deactivate last active global policy (`applies_to_all_categories`) |
| `effective_from` | date | Yes | ISO date |
| `effective_to` | date | No | ≥ `effective_from` if set |
| `department` | string | No | Max 100 chars; ignored when `applies_to_all_departments` is true |
| `applies_to_all_departments` | bool | Yes | — |

**Response (200):** Updated policy object.

**Errors:** `400` validation; `409` would leave no active global receipt/approval policy.

> **Post-MVP:** `POST /tenant/expense-policies` to author new `name` keys; `tenant_id` column on `expense_policies` when multi-tenant RLS lands (`13` §5.9.6).

---

## 4.16d Client Admin operational API (shipped — `0.14.10-counterparty-fixes`)

**Base path:** `/api` (Traefik `PathPrefix(/api)` on `admin.mmlogistix.bp0.work` and `finance.mmlogistix.bp0.work`).

**Audience:** `client_admin` JWT (`require_client_admin`) for tenant bootstrap; finance setup routes also accept **`require_finance_setup_access`** (`05` §4.16d.4/9/11–13). **Client Admin UI** (`15` §8.13); **Finance setup UI** (`15` §8.22–§8.24). Implementation: `accfin/app/api/routes/admin.py`, `admin_counterparty.py`.

### 4.16d.1 Dashboard

```
GET /api/admin/dashboard
```

**Response (200):** Completeness checklist (company profile, COA, mailboxes, users, expense limits, policy PDF, regulatory docs, GL reminder recipients, accounting periods, vendor contract expiry warnings).

### 4.16d.2 Tenant profile (company)

```
GET /api/tenants/{tenant_id}/profile
PATCH /api/tenants/{tenant_id}/profile
```

**Fields:** `legal_name`, `trading_name`, `uen`, `gst_registration_number`, `registered_address`, `contact_email`, `contact_phone`, `website`, `email_signature_html`, `email_signature_plain` (`06` §13.2b, migration `051`).

### 4.16d.3 Chart of accounts (Client Admin — shipped `0.14.7-coa-tenant-import`)

```
GET /api/coa
GET /api/coa/status
POST /api/coa
PATCH /api/coa/{account_id}
POST /api/coa/import
```

**Permission:** `client_admin` role (`require_client_admin()`); implied by `tenant:admin` / `coa:import`.

**List (`GET /api/coa`):**

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | — | Case-insensitive substring match on `account_code` or `account_name` |
| `active_only` | boolean | `true` | When `true`, only `is_active = true` rows |

Returns a JSON **array** of `CoaAccountResponse` (not wrapped in `{ "data": [...] }`).

**Status (`GET /api/coa/status`):** `{ "account_count": N, "empty": true|false }` — `empty` is `true` when no active accounts (dashboard + empty-state banner).

**Import (`POST /api/coa/import`):** `multipart/form-data`, field `file` (UTF-8 CSV).

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `replace_all` | boolean | `false` | When `true`, sets **all** existing `coa_accounts.is_active = false` before upserting CSV rows (tenant chart replaces any demo/legacy rows). Client Admin UI defaults this checkbox to **on** (`15` §8.10). |

**Required CSV columns:** `account_code`, `account_name`, `account_type` (`asset` \| `liability` \| `equity` \| `revenue` \| `expense`). Optional: `parent_code` (must exist in chart).

**Response (200):** `CoaImportResponse`:

```json
{
  "created": 12,
  "updated": 3,
  "skipped": 1,
  "active_count": 42
}
```

**Upsert behaviour:** Rows with an existing `account_code` update name, type, parent, and set `is_active = true`. Unknown `parent_code` leaves `parent_id` null. Invalid type or blank code/name increment `skipped`.

**Errors:** `400 INVALID_CSV` (missing headers or no data rows).

**Deactivate:** `PATCH /api/coa/{account_id}` with `{ "is_active": false }` (soft delete).

**Production data:** Migration `20260531_054` removes demo seed codes (`1200`, `1300`, `2000`, `2100`, `4100`, `5200`, `5500`, `1190`) when unused by journals, expense lines, or reconciliation runs (`06` §18.4). Fresh installs must import tenant COA via Client Admin — no prepopulated chart.

### 4.16d.4 Counterparty accounts & payment terms (`0.14.10-counterparty-fixes`, shipped)

**Permission:** **`require_finance_setup_access`** (`e73c869`) — `cfo`, `finance_manager`, `accounts_clerk`, `financial_analyst`, `ar_executive`, `ap_executive`, `general_manager`, `client_admin`, or `tenant:admin`. Same gate on §4.16d.8 (agreements) and §4.16d.11–§4.16d.13 (accounting calendar).

**UI host:** `https://finance.mmlogistix.bp0.work` (`15` §8.22–§8.24). Client Admin dashboard checklist links to finance URLs for payment terms, tax codes, and GL calendar (`GET /api/admin/dashboard`).

#### Counterparty master

```
GET /api/counterparties?type=customer|vendor|supplier&q=
POST /api/counterparties
PATCH /api/counterparties/{counterparty_id}
```

| Field | Notes |
|-------|-------|
| `name`, `code`, `type` | `type` ∈ `customer`, `vendor`, `supplier`, … (`06` §4.1). UI uses `vendor` wording; `supplier` is accepted for backward compatibility. |
| `contact_email`, `address` | Master-level defaults |
| Vendor contract fields *(optional)* | Applied to `type = vendor` (supplier legacy accepted). |
| `has_contract` | Boolean toggle for “Contract in place” |
| `contract_reference` | Contract number/description |
| `contract_start_date` | Contract start date |
| `contract_expiry_date` | Contract expiry date |
| `supplier_owner` | Supplier owner (free-text) |
| `contract_warning_days` | Integer warning window (default `30`) for “expiring soon” badge/warnings |

#### Counterparty accounts (subaccounts)

```
GET /api/counterparty-accounts?counterparty_id=&q=
POST /api/counterparty-accounts
PATCH /api/counterparty-accounts/{account_id}
```

**Body (create/update):** `counterparty_id`, `account_code`, `display_name`, `role`, `contact_email`, `address`, `payment_term_id`, `credit_limit_amount`, `credit_limit_currency`, `counterparty_gst_reg`, `is_active`.

| Field | Where set | Notes |
|-------|-----------|-------|
| `payment_term_id` | Subaccount | Links to catalog row for **due days** (`NET30`, etc.) |
| `credit_limit_amount` / `credit_limit_currency` | Subaccount | Max outstanding credit for this customer/supplier site — **not** on `payment_terms` |

**Finance UI:** Subaccounts tab captures payment terms + credit limit on create; **inline Edit** on active rows updates `payment_term_id`, `credit_limit_amount`, and `credit_limit_currency` via `PATCH` (`15` §8.22 v2.29, git `9b0662e`). Payment terms tab is catalog only (catalog rows: `PATCH /api/payment-terms/{term_id}` for `label`, `due_days`, discounts, `is_active` — `code` is immutable).

**Deactivate:** `PATCH` with `{ "is_active": false }` — blocked when open AR/AP balance exists for this subaccount.
**Reactivate:** `PATCH` with `{ "is_active": true }` — unblocks inactive subaccounts; UI refreshes list after patch.

#### Payment terms catalog

```
GET /api/payment-terms
POST /api/payment-terms
PATCH /api/payment-terms/{term_id}
```

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Unique key, e.g. `NET30` |
| `label` | string | Display name |
| `due_days` | int | Days after invoice date |
| `minimum_invoice_amount` | decimal \| null | Optional threshold |
| `discount_percent` | decimal \| null | Early payment discount % |
| `discount_if_paid_within_days` | int \| null | Discount window |

#### Tenant tax codes (GST mapping)

```
GET /api/tenant/tax-codes
POST /api/tenant/tax-codes
PATCH /api/tenant/tax-codes/{id}
```

Maps `code` (e.g. `SR`, `GST9`, `ZR`) → `rate`, `direction` (`output` \| `input` \| `both`), `output_gl_account_code`, `input_gl_account_code`. GL codes must exist in tenant COA (`06` §4.1c, `17` §3.2.3).

**Intake consumption:** Workers read resolved `counterparty_account_id`, `payment_term_id`, `tax_code` from `cases.workflow_metadata` / `extraction_output` (`06` Appendix B).

### 4.16d.5 Mail configuration

```
GET /api/mail/configuration
PATCH /api/mail/configuration/{mailbox_id}
```

**Note:** IMAP/SMTP credentials are provisioned by Platform Admin; Client Admin edits addresses, display names, and `requires_outbound_client_approval` (`15` §8.14).

### 4.16d.6 Users (role mailboxes)

```
GET /api/users
PATCH /api/users/{user_id}
```

**Ordering:** CEO → CFO → Finance Manager → Accounts Manager (display order in UI).

### 4.16d.7 Expense policy (limits + PDF)

```
GET /api/expense-policies/limits
PATCH /api/expense-policies/limits
GET|POST /api/expense-policies/document
GET /api/expense-policies/document/download
```

**Storage:** Travel & expense policy PDF on Wasabi (`tenant_profiles` or dedicated path per implementation).

### 4.16d.8 Regulatory documents

```
GET /api/regulatory-documents/catalog
GET /api/regulatory-documents
POST /api/regulatory-documents
GET /api/regulatory-documents/{document_id}/download
```

**Storage:** Wasabi `regulatory_documents.wasabi_path`; optional `document_key` for catalog slot (`051`).

### 4.16d.9 Agreements

```
GET|POST /api/agreements/rental
GET|POST /api/agreements/director-expense
```

**UI:** `https://finance.mmlogistix.bp0.work/agreements` (`15` §8.23). **Permission:** `require_finance_setup_access` (§4.16d.4).

### 4.16d.10 Travel requests (admin list)

```
GET /api/travel-requests
PATCH /api/travel-requests/{request_id}
```

**Note:** Employee travel approval is email-only to `accexp.mmlogistix@bp0.work`; no in-app travel UI on Client Admin or Finance UI (`e73c869` removed `/travel-info`).

### 4.16d.11 Accounting settings

```
GET /api/admin/accounting-settings
PATCH /api/admin/accounting-settings
```

**UI:** `https://finance.mmlogistix.bp0.work/accounting-calendar` (`15` §8.24). **Permission:** `require_finance_setup_access`.

**Keys** (`system_settings`, category `accounting`):

| Key | Values |
|-----|--------|
| `accounting_fye_month` | 1–12 (default 12) |
| `trial_balance_frequency` | `monthly` \| `weekly` |
| `audit_frequency` | `annual` \| `semi_annual` \| `quarterly` |
| `gl_cutoff_working_days` | integer (default 3; mirrors `gl_posting_cutoff_working_days`) |

### 4.16d.12 GL cutoff reminder recipients

```
GET /api/admin/gl-cutoff-reminders
POST /api/admin/gl-cutoff-reminders
PATCH /api/admin/gl-cutoff-reminders/{reminder_id}
DELETE /api/admin/gl-cutoff-reminders/{reminder_id}
```

**Table:** `gl_cutoff_reminders` (`06` §13.2c, migration `052`). Per-recipient flags: `notify_7_days`, `notify_3_days`, `notify_1_day`, `notify_on_date`.

### 4.16d.13 Accounting periods (calendar)

```
GET /api/accounting-periods
GET /api/accounting-periods/settings
POST /api/accounting-periods/generate?months=13
POST /api/accounting-periods/{period_id}/approve-trial-balance
POST /api/accounting-periods/{period_id}/close
POST /api/accounting-periods/{period_id}/reopen
```

**Generate:** Current calendar month + next 12 months (forward). Sets `period_type` (`monthly` \| `audit` \| `year_end`) from FYE + audit frequency; `gl_cutoff_date` = N **working days** after month-end (weekends + Singapore public holidays skipped).

**Approve trial balance:** `financial_analyst` or `client_admin` → sets `trial_balance_approved_at`, status `review`.

**Close GL:** `finance_manager` or `client_admin` → requires TB approved; `audit` periods require `audit_adjustments_completed`; `year_end` requires `year_end_adjustments_completed`; optional auditor fields → `audit_metadata` JSONB (`053`).

**Reopen GL:** `cfo` or `client_admin` (`require_period_reopen`) → only when `status = closed`; sets `status = open`, clears `gl_closed_at` and `gl_closed_by`; logs `finance_activity_log.action = gl_period_reopened` with `reopened_by` and `reopened_at` in metadata (`0.14.5`, `15` §8.20).

### 4.16d.14 Binding authority thresholds (`0.14.9-binding-authority`, shipped)

**Permission:** `client_admin` (`require_client_admin`).

```
GET  /api/admin/binding-authority
PATCH /api/admin/binding-authority
```

**Description:** Read/update approval tier ceilings and SLA hours stored in `policies` (`ap_approval_thresholds`, `ar_approval_thresholds`, `expense_approval_thresholds`). Rules JSON keys: `tier_1_ceiling`, `tier_2_ceiling`, `tier_3_threshold`, `stp_confidence_minimum`, `tier_2_sla_hours`, `tier_3_sla_hours` (SGD amounts unless noted). Defaults seeded in migration `060` (`16` §10).

**PATCH body (partial):**

```json
{
  "ap_approval_thresholds": { "tier_1_ceiling": 3000, "tier_2_ceiling": 10000 },
  "ar_approval_thresholds": { "tier_3_threshold": 10000 },
  "expense_approval_thresholds": { "stp_confidence_minimum": 0.9 }
}
```

**Response:** `{ ap_invoice, ar_invoice, expense_claim }` each with `document_key`, `label`, `thresholds` object.

**Worker integration:** After extraction, PO/travel, and GL period checks, `PolicyEngine.evaluate_approval_tier` (`10` §7) — Tier 1 auto-posts journal; Tier 2+ sets `pending_approval` and emails acc (`acc.mmlogistix@bp0.work`) or CFO (`cfo.mmlogistix@bp0.work`) with mail action links (`17` §5).

**Finance approvals:** `GET /approvals?binding_queue=acc|cfo` filters pending queue by role; `POST /approvals/{id}/escalate` (Tier 2 → CFO, acc only) — see §7 Approvals.

**UI:** Client Admin `/binding-authority` (`15` §8.25); finance-ui case detail + approvals list (`15` §2.1a, §8.21 binding panel).

### 4.16d.15 GL period override post (finance roles)

```
POST /api/accounting-periods/{period_id}/override-post
```

**Auth:** `cfo`, `finance_manager`, or `client_admin` (`require_gl_posting_override`).

**Request:**

```json
{
  "case_id": "uuid",
  "override_reason": "CFO approved year-end accrual posting"
}
```

**Description:** Authorizes journal posting into a **closed** period for the linked case, logs `gl_period_override_post` to `finance_activity_log`, and requeues the case for worker reprocessing with `gl_period_override=true` (`17` §2.1.3, `15` §8.21).

**Response (200):**

```json
{
  "case_id": "uuid",
  "case_number": "CAS-2026-00042",
  "period_id": "uuid",
  "status": "requeued"
}
```

---

## 4.17 List My Notifications (Inbox)

```
GET /notifications
```

**Description:** Returns the signed-in user's in-app notification inbox, ordered by `created_at` descending. Rows are written by the `NotificationDispatcher` (`18_Notification_Service_Specification.md` §6) when a domain event triggers a delivery to this user. The inbox table DDL, indexes, and retention policy are specified in `18_Notification_Service_Specification.md` §3.

**Permissions:** Authenticated user. Always scoped to `current_user.id` — users cannot read each other's notifications.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Items per page (max 200) |
| `cursor` | string | none | Cursor from previous response (cursor pagination per §1.4) |
| `is_read` | boolean | none | Filter by read status. Omit to return all. |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "event_key": "approval.requested",
      "title": "Approval required: INV-2026-0042",
      "body": "A supplier invoice for SGD 12,450.00 from Acme Logistics requires your approval by 14 May 2026.",
      "is_read": false,
      "read_at": null,
      "case_id": "uuid",
      "case_number": "INV-2026-0042",
      "action_url": "/approvals/uuid",
      "created_at": "2026-05-11T09:15:00Z"
    }
  ],
  "pagination": {
    "next_cursor": "eyJpZCI6MTIz...",
    "has_more": true,
    "total": 14
  },
  "unread_count": 5
}
```

**Field notes:**

| Field | Description |
|-------|-------------|
| `event_key` | Matches `notification_templates.event_key` — identifies the triggering event type |
| `title` | Short rendered title, suitable for a bell-icon notification badge |
| `body` | Plain-text summary (max 500 chars) — not HTML |
| `action_url` | Deep link to the relevant case or approval; may be null for system-level notifications |
| `unread_count` | Total unread notifications for this user — live count, not limited by `limit`/`cursor` |

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 401 | `UNAUTHORIZED` | Missing or invalid token |

---

## 4.18 Mark Notifications as Read

```
POST /notifications/read
```

**Description:** Marks one or more notification rows as read for the signed-in user. Sets `is_read = true` and `read_at = NOW()` on each matched row. Silently ignores IDs that are already read, do not exist, or belong to a different user (no error is returned — the operation is idempotent from the client's perspective).

**Permissions:** Authenticated user. Only the owning user may mark their own notifications as read.

**Request:**

```json
{
  "notification_ids": ["uuid", "uuid"]
}
```

| Field | Type | Rules |
|-------|------|-------|
| `notification_ids` | array of UUID strings | Required. 1–100 IDs per request. |

**Mark all unread as read:**

Pass `"all": true` instead of (or in addition to) `notification_ids` to mark every unread notification for the current user as read in a single operation:

```json
{
  "all": true
}
```

**Response (200):**

```json
{
  "marked_read": 3,
  "unread_count": 2
}
```

| Field | Description |
|-------|-------------|
| `marked_read` | Number of rows actually updated (excludes already-read rows) |
| `unread_count` | Remaining unread count after the operation |

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 400 | `INVALID_REQUEST` | `notification_ids` is empty and `all` is not `true` |
| 400 | `TOO_MANY_IDS` | More than 100 IDs supplied in a single request |
| 401 | `UNAUTHORIZED` | Missing or invalid token |

---

# 5. Cases

Base path: `/cases`

Cases are the central unit of work in the platform. Every inbound email or transaction creates a case that flows through classification, processing, approval, and completion.

## 5.1 Case Status Lifecycle

```
inbound -> classified -> processing -> pending_approval -> approved -> posted -> completed
                                              |
                                              -> rejected -> exception -> manual_review -> ...
```

| Status | Description |
|--------|-------------|
| `inbound` | Received, awaiting classification |
| `classified` | AI classified, awaiting processing |
| `processing` | Being processed by worker |
| `pending_approval` | Awaiting human approval |
| `approved` | Approved, awaiting posting |
| `posted` | Journal/posting completed |
| `completed` | Fully resolved |
| `rejected` | Rejected by approver |
| `exception` | Exception workflow triggered |
| `manual_review` | Escalated to human for manual handling |
| `on_hold` | Suspended, awaiting external input |

## 5.2 Case Priority Levels

| Level | SLA Target |
|-------|------------|
| `critical` | 1 business hour |
| `high` | 4 business hours |
| `medium` | 1 business day |
| `low` | 3 business days |

## 5.3 Case Types

| Type | Description | Worker |
|------|-------------|--------|
| `ar_invoice` | Accounts Receivable invoice | AR Worker |
| `ar_payment_advice` | Customer payment advice | AR Worker |
| `ar_credit_note` | Credit / debit note | AR Worker |
| `ar_soa_request` | Outbound Statement of Account generation (human-initiated, not inbound email) | AR Worker |
| `ap_invoice` | Supplier invoice | AP Worker |
| `ap_po_validation` | PO/GRN validation | AP Worker |
| `ap_payment_proposal` | Payment proposal | AP Worker |
| `treasury_reconciliation` | Bank reconciliation | Treasury Worker |
| `treasury_fx` | FX transaction | Treasury Worker |
| `treasury_suspense` | Suspense account item | Treasury Worker |
| `general_inquiry` | General finance inquiry | Accounts Worker |
| `expense_claim` | Employee expense reimbursement claim **(Phase 11)** | Expense Worker |

## 5.4 List Cases

```
GET /cases
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | One or more status values (comma-separated) |
| `type` | string | One or more case types (comma-separated) |
| `priority` | string | `critical`, `high`, `medium`, `low` |
| `assigned_to` | uuid | User ID assigned |
| `created_by` | uuid | User/system that created |
| `from_date` | date | Created on or after |
| `to_date` | date | Created on or before |
| `q` | string | Search case number, subject, counterparty |
| `needs_approval` | boolean | Filter cases pending current user's approval |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "case_number": "CAS-2026-0001542",
      "type": "ap_invoice",
      "type_display": "Supplier Invoice",
      "status": "pending_approval",
      "priority": "high",
      "confidence_score": 0.94,
      "stp_eligible": false,
      "subject": "Invoice INV-44521 from ACME Supplies Pte Ltd",
      "counterparty": {
        "id": "uuid",
        "name": "ACME Supplies Pte Ltd",
        "code": "SUPP-00124"
      },
      "amount": {
        "value": "15850.00",
        "currency": "SGD"
      },
      "assigned_to": {
        "id": "uuid",
        "name": "Jane Smith"
      },
      "current_approval_tier": 2,
      "email_id": "uuid",
      "parent_case_id": null,
      "tags": ["po-matched", "recurring-supplier"],
      "notes": "string",
      "created_at": "2026-05-10T14:30:00Z",
      "updated_at": "2026-05-10T15:45:00Z",
      "due_date": "2026-05-11T14:30:00Z",
      "completed_at": null
    }
  ],
  "pagination": {
    "next_cursor": "...",
    "has_more": true,
    "total": 847
  }
}
```

---

## 5.5 Get Case

```
GET /cases/{id}
```

**Response (200):** Full case object with embedded sub-resources:

```json
{
  "id": "uuid",
  "case_number": "CAS-2026-0001542",
  "type": "ap_invoice",
  "type_display": "Supplier Invoice",
  "status": "pending_approval",
  "priority": "high",
  "confidence_score": 0.94,
  "stp_eligible": false,
  "subject": "Invoice INV-44521 from ACME Supplies Pte Ltd",
  "description": "Detailed case description or AI-generated summary",
  "counterparty": {
    "id": "uuid",
    "name": "ACME Supplies Pte Ltd",
    "code": "SUPP-00124",
    "contact_email": "accounts@acmesupplies.sg",
    "contact_phone": "+65 6123 4567"
  },
  "amount": {
    "value": "15850.00",
    "currency": "SGD",
    "converted_amount": "15850.00",
    "converted_currency": "SGD",
    "exchange_rate": "1.0000"
  },
  "classification": {
    "ai_classified": true,
    "classified_as": "ap_invoice",
    "classification_confidence": 0.97,
    "classified_at": "2026-05-10T14:31:00Z",
    "human_verified": true,
    "human_verified_by": "uuid",
    "human_verified_at": "2026-05-10T14:35:00Z"
  },
  "assigned_to": {
    "id": "uuid",
    "name": "Jane Smith",
    "department": "Accounts Payable"
  },
  "workflow": {
    "current_stage": "approval",
    "current_approval_tier": 2,
    "sla_deadline": "2026-05-11T14:30:00Z",
    "sla_status": "on_track",
    "retry_count": 0
  },
  "email": {
    "id": "uuid",
    "message_id": "<abc123@mail.acmesupplies.sg>",
    "from": "accounts@acmesupplies.sg",
    "to": ["ap@mmlogistix.internal"],
    "subject": "Invoice INV-44521",
    "received_at": "2026-05-10T14:30:00Z",
    "attachment_count": 2
  },
  "attachments": [
    {
      "id": "uuid",
      "filename": "INV-44521.pdf",
      "file_size": 152400,
      "mime_type": "application/pdf",
      "content_hash": "sha256:abc123...",
      "extracted_text": "Invoice #44521...",
      "uploaded_at": "2026-05-10T14:30:00Z"
    }
  ],
  "parent_case_id": null,
  "related_cases": [
    {
      "id": "uuid",
      "case_number": "CAS-2026-0001489",
      "relation": "po_reference"
    }
  ],
  "tags": ["po-matched", "recurring-supplier"],
  "notes": "string",
  "created_at": "2026-05-10T14:30:00Z",
  "updated_at": "2026-05-10T15:45:00Z",
  "due_date": "2026-05-11T14:30:00Z",
  "completed_at": null,
  "created_by": {
    "id": "system",
    "name": "Mail Gateway"
  }
}
```

---

## 5.6 Create Case (Manual)

```
POST /cases
```

**Description:** Manually create a case. Most cases are auto-created by the Mail Gateway.

**Request:**

```json
{
  "type": "ap_invoice",
  "subject": "string",             // required
  "description": "string",         // optional
  "counterparty_id": "uuid",       // optional
  "counterparty_name": "string",   // required if counterparty_id not provided
  "amount": {
    "value": "15850.00",
    "currency": "SGD"
  },
  "priority": "medium",            // optional, default: medium
  "assigned_to": "uuid",           // optional
  "parent_case_id": "uuid",        // optional
  "tags": ["string"],              // optional
  "notes": "string",               // optional
  "attachments": [                 // optional
    {
      "filename": "document.pdf",
      "content_base64": "base64encoded...",
      "mime_type": "application/pdf"
    }
  ]
}
```

**Response (201):** Created case.

---

## 5.7 Update Case

```
PUT /cases/{id}
```

**Description:** Full update of case metadata. Limited fields are mutable once a case enters processing.

**Mutable Fields (any status):**
- `priority`
- `assigned_to`
- `tags`
- `notes`

**Mutable Fields (inbound/classified only):**
- `type`
- `subject`
- `description`
- `counterparty_id`
- `amount`

**Request:** Only include fields to update.

**Response (200):** Updated case.

---

## 5.8 Update Case Status

```
POST /cases/{id}/status
```

**Description:** Transition case to a new status. Valid transitions are enforced by the workflow engine.

**Request:**

```json
{
  "status": "manual_review",
  "reason": "AI classification ambiguous — vendor not in supplier master",
  "escalation_note": "string"
}
```

**Valid Transitions:**

| From Status | To Status | Who |
|-------------|-----------|-----|
| `inbound` | `classified` | System (AI) |
| `inbound` | `manual_review` | System (low confidence) or User |
| `classified` | `processing` | System |
| `classified` | `manual_review` | User |
| `processing` | `pending_approval` | System |
| `processing` | `exception` | System or User |
| `pending_approval` | `approved` | Approver |
| `pending_approval` | `rejected` | Approver |
| `pending_approval` | `on_hold` | Approver or User |
| `approved` | `posted` | System |
| `approved` | `exception` | System |
| `exception` | `manual_review` | System or User |
| `exception` | `processing` | User (retry) |
| `manual_review` | `processing` | User |
| `manual_review` | `on_hold` | User |
| `on_hold` | `processing` | User |
| `on_hold` | `completed` | User |
| `posted` | `completed` | System |
| `rejected` | `manual_review` | User |

**Response (200):** Updated case.

---

## 5.8a Retry Case Processing

```
POST /cases/{id}/retry
```

**Description:** Requeue a case stuck in **`exception`** or **`manual_review`** for domain-worker processing. Also allows **`on_hold`** when `workflow_metadata.reason_code` / `error_type` = `PERIOD_CLOSED` and the linked GL period (`workflow_metadata.gl_period_id`) is **no longer** `closed` (period reopened — `0.14.5`, `15` §8.21). Clears error fields in `workflow_metadata`, sets status to `classified`, appends a `case_retry` timeline entry, and enqueues a message on **`accounts_queue`** (`source: "case-retry"`).

**Permission:** `cases:write`

**`GET /cases/{id}` enrichment (`0.14.5`):** When `workflow_metadata.gl_period_id` is set, response includes `linked_gl_period_status` (`open` \| `review` \| `closed` \| null) for finance-ui retry/override visibility.

**Response (200):**

```json
{
  "case_id": "uuid",
  "case_number": "CAS-20260520-0001",
  "message_id": "uuid",
  "status": "classified",
  "previous_status": "manual_review"
}
```

**Errors:**

| Code | HTTP | When |
|------|------|------|
| `CASE_NOT_FOUND` | 404 | Unknown case id |
| `CASE_NOT_RETRYABLE` | 422 | Status not retryable (see description — includes `on_hold` + reopened period exception) |

**Deploy:** `0.13.3-case-retry-hermes-timeout`

---

## 5.9 Merge Cases

```
POST /cases/{id}/merge
```

**Description:** Merge another case into this case. Source case becomes a child.

**Request:**

```json
{
  "source_case_id": "uuid",
  "reason": "Duplicate email — same invoice resent"
}
```

**Response (200):** Updated case with `related_cases` populated.

---

## 5.10 Split Case

```
POST /cases/{id}/split
```

**Description:** Split a case into multiple child cases. Original case remains parent.

**Request:**

```json
{
  "split_reason": "Email contains two unrelated invoices",
  "new_cases": [
    {
      "type": "ap_invoice",
      "subject": "Invoice A",
      "attachments": ["uuid-of-attachment-1"]
    },
    {
      "type": "ap_invoice",
      "subject": "Invoice B",
      "attachments": ["uuid-of-attachment-2"]
    }
  ]
}
```

**Response (200):** Parent case with new child cases in `related_cases`.

---

## 5.11 Get Case Timeline / Activity

```
GET /cases/{id}/timeline
```

**Description:** Chronological activity log for a case.

**Response (200):**

```json
{
  "case_id": "uuid",
  "timeline": [
    {
      "id": "uuid",
      "event_type": "status_change",
      "description": "Case classified as ap_invoice (confidence: 0.97)",
      "from_status": "inbound",
      "to_status": "classified",
      "performed_by": {
        "id": "system",
        "name": "AI Classification Agent"
      },
      "metadata": {
        "confidence": 0.97,
        "model": "hermes-classifier-v2"
      },
      "created_at": "2026-05-10T14:31:00Z"
    },
    {
      "id": "uuid",
      "event_type": "approval_requested",
      "description": "Approval requested from Jane Smith (Tier 2)",
      "performed_by": {
        "id": "system",
        "name": "Workflow Engine"
      },
      "metadata": {
        "tier": 2,
        "approver_id": "uuid",
        "sla_deadline": "2026-05-11T14:30:00Z"
      },
      "created_at": "2026-05-10T14:32:00Z"
    }
  ]
}
```

**Event Types:**

| Type | Description |
|------|-------------|
| `created` | Case created |
| `status_change` | Status transitioned |
| `classification` | AI classification result |
| `human_verification` | Human confirmed/overrode classification |
| `processing_started` | Worker picked up case |
| `processing_completed` | Worker finished |
| `approval_requested` | Sent to approver |
| `approval_responded` | Approver action taken |
| `approval_escalated` | SLA breach escalation |
| `exception_raised` | Exception triggered |
| `exception_resolved` | Exception cleared |
| `note_added` | User added note |
| `merged` | Case merged |
| `split` | Case split |
| `attachment_added` | Attachment uploaded |
| `journal_linked` | Linked to journal entry |

---

## 5.12 Add Note to Case

```
POST /cases/{id}/notes
```

**Request:**

```json
{
  "content": "Customer called to confirm invoice amount. Verified correct.",
  "is_internal": true    // if true, not visible in customer communications
}
```

**Response (201):** Created note.

---

## 5.13 List Case Notes

```
GET /cases/{id}/notes
```

**Response (200):** Paginated list of notes.

---

## 5.14 Get Case Statistics

```
GET /cases/statistics
```

**Description:** Parameterised aggregate statistics over a configurable date range. This is a **reporting and analytics endpoint** — it is the authoritative source for case volume, processing rate, SLA, and exception metrics over any requested period.

**Consumer distinction:** this endpoint is consumed by: (a) reporting screens that need historical trend data over arbitrary date ranges; (b) `GET /dashboard/summary` (§15.1), which calls this endpoint internally for its `cases` section rather than reimplementing the aggregation query. Do not duplicate the aggregation logic between this endpoint and the dashboard. The dashboard service layer calls `CaseStatisticsService.get_statistics(from_date, to_date)` and includes its output as a sub-object — see §15.1 implementation note.

**Permissions:** `cases:read`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `from_date` | date | 30 days ago | Start of aggregation window (inclusive) |
| `to_date` | date | today | End of aggregation window (inclusive) |
| `group_by` | string | — | Optional breakdown dimension: `status`, `type`, `priority`, `assigned_to` |

**Response (200):**

```json
{
  "period": {
    "from": "2026-05-01",
    "to": "2026-05-10"
  },
  "totals": {
    "total_cases": 1547,
    "completed": 1289,
    "pending_approval": 142,
    "in_exception": 23,
    "in_manual_review": 45,
    "sla_breached": 8,
    "average_processing_time_hours": 3.2,
    "stp_rate": 0.68,
    "exception_rate": 0.038
  },
  "by_status": [
    { "status": "completed", "count": 1289 }
  ],
  "by_type": [
    { "type": "ap_invoice", "count": 634 }
  ],
  "by_priority": [
    { "priority": "high", "count": 312, "sla_breach_count": 4 }
  ],
  "trend": [
    { "date": "2026-05-01", "total": 120, "completed": 98, "exceptions": 3 }
  ]
}
```

---

# 6. Workflow Engine

Base path: `/workflow`

Endpoints for monitoring and managing workflow execution.

## 6.1 List Active Workflows

```
GET /workflow/active
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `case_id` | uuid | Filter by case |
| `workflow_type` | string | `classification`, `processing`, `approval`, `exception` |

**Response (200):**

```json
{
  "data": [
    {
      "workflow_id": "uuid",
      "case_id": "uuid",
      "case_number": "CAS-2026-0001542",
      "workflow_type": "approval",
      "status": "running",
      "current_stage": "tier_2_approval",
      "started_at": "2026-05-10T14:32:00Z",
      "sla_deadline": "2026-05-11T14:30:00Z",
      "sla_status": "on_track",
      "retry_count": 0,
      "worker_name": "approval-worker"
    }
  ]
}
```

---

## 6.2 Get Workflow Details

```
GET /workflow/{workflow_id}
```

**Response (200):** Full workflow with stage history.

---

## 6.3 Retry Workflow

```
POST /workflow/{workflow_id}/retry
```

**Description:** Retry a failed or exception workflow.

**Permissions Required:** `queues:admin` or case owner

**Request:**

```json
{
  "from_stage": "approval",      // optional, default: from failed stage
  "reason": "Retry after fixing supplier master data"
}
```

**Response (200):** Workflow restarted.

---

## 6.4 Cancel Workflow

```
POST /workflow/{workflow_id}/cancel
```

**Description:** Cancel a running workflow. Case moves to `manual_review`.

**Request:**

```json
{
  "reason": "string"
}
```

---

## 6.5 Get Workflow Definitions

```
GET /workflow/definitions
```

**Description:** List configured workflow types and their stages.

**Response (200):**

```json
{
  "data": [
    {
      "workflow_type": "ap_invoice",
      "name": "AP Invoice Processing",
      "description": "Full workflow for supplier invoice handling",
      "stages": [
        {
          "stage_id": "intake",
          "name": "Email Intake",
          "next_stages": ["classification"],
          "is_automatic": true,
          "timeout_minutes": 5
        },
        {
          "stage_id": "classification",
          "name": "AI Classification",
          "next_stages": ["processing", "manual_review"],
          "is_automatic": true,
          "timeout_minutes": 2
        },
        {
          "stage_id": "processing",
          "name": "Document Processing",
          "next_stages": ["validation", "exception"],
          "is_automatic": true,
          "timeout_minutes": 10
        },
        {
          "stage_id": "validation",
          "name": "Policy Validation",
          "next_stages": ["approval", "stp_release"],
          "is_automatic": true,
          "timeout_minutes": 2
        },
        {
          "stage_id": "stp_release",
          "name": "STP Posting",
          "next_stages": ["completed"],
          "is_automatic": true,
          "timeout_minutes": 5
        },
        {
          "stage_id": "approval",
          "name": "Approval",
          "next_stages": ["posting", "rejected"],
          "is_automatic": false,
          "timeout_minutes": 240,
          "escalation": {
            "on_timeout": "escalate_tier",
            "escalation_tier": 3,
            "notify": ["cfo", "finance_manager"]
          }
        },
        {
          "stage_id": "posting",
          "name": "Journal Posting",
          "next_stages": ["completed"],
          "is_automatic": true,
          "timeout_minutes": 5
        },
        {
          "stage_id": "exception",
          "name": "Exception Handling",
          "next_stages": ["manual_review", "processing"],
          "is_automatic": false,
          "timeout_minutes": 0
        },
        {
          "stage_id": "manual_review",
          "name": "Manual Review",
          "next_stages": ["processing", "completed", "on_hold"],
          "is_automatic": false,
          "timeout_minutes": 0
        }
      ]
    }
  ]
}
```

---

## 6.6 Workflow SLA Summary

```
GET /workflow/sla-summary
```

**Description:** Dashboard summary of SLA performance.

**Response (200):**

```json
{
  "total_active": 142,
  "on_track": 128,
  "at_risk": 9,           // SLA < 50% remaining
  "breached": 5,          // SLA exceeded
  "breached_today": 2,
  "by_tier": [
    { "tier": 1, "total": 85, "breached": 1 },
    { "tier": 2, "total": 42, "breached": 3 },
    { "tier": 3, "total": 15, "breached": 1 }
  ]
}
```

---

# 7. Approvals

Base path: `/approvals`

## 7.1 Approval Status Values

| Status | Description |
|--------|-------------|
| `pending` | Awaiting approver action |
| `approved` | Approved by assigned approver |
| `rejected` | Rejected by assigned approver |
| `escalated` | Escalated due to SLA breach |
| `delegated` | Delegated to alternate approver |
| `overridden` | Admin override applied |

## 7.2 List Approval Requests

```
GET /approvals
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status |
| `tier` | integer | `1`, `2`, `3` |
| `case_id` | uuid | Filter by case |
| `requested_from` | uuid | Filter by approver user ID |
| `my_pending` | boolean | Show only current user's pending approvals |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "case_id": "uuid",
      "case_number": "CAS-2026-0001542",
      "case_type": "ap_invoice",
      "tier": 2,
      "status": "pending",
      "requested_by": {
        "id": "system",
        "name": "Workflow Engine"
      },
      "requested_from": {
        "id": "uuid",
        "name": "Jane Smith",
        "email": "jane.smith@mmlogistix.internal"
      },
      "delegated_to": null,
      "subject": "Supplier Invoice INV-44521 — SGD 15,850.00",
      "description": "Auto-generated approval request for AP invoice above SGD 10,000 threshold",
      "amount": {
        "value": "15850.00",
        "currency": "SGD"
      },
      "risk_flags": ["above_threshold", "new_supplier_30_days"],
      "sla_deadline": "2026-05-11T14:30:00Z",
      "sla_status": "on_track",
      "created_at": "2026-05-10T14:32:00Z",
      "responded_at": null,
      "response_note": null
    }
  ],
  "pagination": { ... }
}
```

---

## 7.3 Get Approval Request

```
GET /approvals/{id}
```

**Response (200):** Full approval request with case summary.

---

## 7.4 Approve

```
POST /approvals/{id}/approve
```

**Description:** Approve a pending approval request.

**Request:**

```json
{
  "note": "Verified against PO #4521 and GRN. Approved.",
  "journal_entry_id": "uuid"      // optional, if journal pre-prepared
}
```

**Response (200):** Updated approval with `status: approved`.

**Errors:**

| Status | Code | Message |
|--------|------|---------|
| 409 | `ALREADY_RESPONDED` | Approval already has a response |
| 403 | `UNAUTHORIZED_APPROVER` | Current user is not the designated approver |

---

## 7.5 Reject

```
POST /approvals/{id}/reject
```

**Request:**

```json
{
  "reason": "string",           // required
  "rejection_category": "insufficient_documentation",
  "return_to": "manual_review"  // optional: where to send case after rejection
}
```

**Rejection Categories:**

| Category | Description |
|----------|-------------|
| `insufficient_documentation` | Missing or incomplete supporting documents |
| `amount_mismatch` | Amount does not match PO/contract |
| `policy_violation` | Violates accounting policy |
| `duplicate_submission` | Identified as duplicate |
| `fraud_suspected` | Fraud indicators detected |
| `other` | Other reason |

**Response (200):** Updated approval with `status: rejected`.

---

## 7.6 Delegate Approval

```
POST /approvals/{id}/delegate
```

**Description:** Delegate approval to another authorized user.

**Request:**

```json
{
  "delegate_to": "uuid",
  "reason": "Out of office — delegated to backup approver"
}
```

**Response (200):** Updated approval with `status: delegated`.

---

## 7.7 Override Approval (Admin)

```
POST /approvals/{id}/override
```

**Description:** Force approve or reject. Requires `approvals:admin` permission.

**Request:**

```json
{
  "action": "approve",
  "reason": "Urgent payment — supplier on credit hold",
  "authorization_reference": "email-cfo-20260510"
}
```

**Response (200):** Updated approval with `status: overridden`.

---

## 7.8 Escalate Approval

```
POST /approvals/{id}/escalate
```

**Description:** Manually escalate to next tier. Requires `approvals:admin` or automatic SLA trigger.

**Request:**

```json
{
  "escalation_reason": "Approver unresponsive — past SLA deadline",
  "escalate_to_tier": 3
}
```

**Response (200):** New approval request at higher tier.

---

## 7.9 Get Approval Configuration

```
GET /approvals/configuration
```

**Response (200):**

```json
{
  "tiers": [
    {
      "tier": 1,
      "name": "Auto-Release",
      "description": "Low risk, STP eligible",
      "conditions": [
        "confidence_score >= 0.90",
        "amount < 5000",
        "no_risk_flags",
        "recurring_counterparty"
      ],
      "approvers": [],
      "auto_release": true,
      "sla_minutes": 0
    },
    {
      "tier": 2,
      "name": "Standard Approval",
      "description": "Medium risk, requires department approval",
      "conditions": [
        "amount < 50000",
        "few_risk_flags"
      ],
      "approvers": [
        {
          "role": "finance_officer",
          "fallback_role": "finance_manager"
        }
      ],
      "auto_release": false,
      "sla_minutes": 240
    },
    {
      "tier": 3,
      "name": "Executive Approval",
      "description": "High risk, requires executive sign-off",
      "conditions": [
        "amount >= 50000",
        "high_risk_flags",
        "policy_override_requested"
      ],
      "approvers": [
        {
          "role": "cfo",
          "fallback_role": "finance_manager"
        }
      ],
      "auto_release": false,
      "sla_minutes": 480
    }
  ]
}
```

---

## 7.10 Update Approval Configuration

```
PUT /approvals/configuration
```

**Permissions Required:** `approvals:admin`

**Request:** Approval configuration object (schema as above).

**Response (200):** Updated configuration.

---

## 7.11 Approval Statistics

```
GET /approvals/statistics
```

**Response (200):**

```json
{
  "period": { "from": "2026-05-01", "to": "2026-05-10" },
  "total_requests": 312,
  "by_status": {
    "approved": 278,
    "rejected": 18,
    "pending": 12,
    "escalated": 4
  },
  "by_tier": {
    "tier_1": 198,
    "tier_2": 89,
    "tier_3": 25
  },
  "average_response_time_hours": 1.8,
  "sla_breach_count": 4,
  "top_rejection_reasons": [
    { "category": "insufficient_documentation", "count": 8 }
  ]
}
```

---

# 8. Mail Gateway

Base path: `/mail`

## 8.1 List Inbound Emails

```
GET /mail
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | `received`, `classified`, `queued`, `failed`, `duplicate` |
| `from_address` | string | Sender email |
| `to_address` | string | Recipient email |
| `has_attachments` | boolean | Filter by attachment presence |
| `from_date` | date | Received on or after |
| `to_date` | date | Received on or before |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "message_id": "<abc123@mail.acmesupplies.sg>",
      "from_address": "accounts@acmesupplies.sg",
      "from_name": "ACME Supplies Accounts",
      "to_addresses": ["ap@mmlogistix.internal"],
      "cc_addresses": [],
      "subject": "Invoice INV-44521 — May 2026",
      "body_preview": "Please find attached invoice for...",
      "body_text": "full text content...",
      "body_html": "<html>...",
      "status": "classified",
      "classification": {
        "classified_as": "ap_invoice",
        "confidence": 0.97,
        "classified_at": "2026-05-10T14:31:00Z"
      },
      "spf_result": "pass",
      "dkim_result": "pass",
      "dmarc_result": "pass",
      "duplicate_check": {
        "is_duplicate": false,
        "matched_message_id": null,
        "matched_content_hash": null
      },
      "attachment_count": 2,
      "attachments": [
        {
          "id": "uuid",
          "filename": "INV-44521.pdf",
          "size": 152400,
          "mime_type": "application/pdf",
          "content_hash": "sha256:abc123..."
        }
      ],
      "case_id": "uuid",
      "case_number": "CAS-2026-0001542",
      "received_at": "2026-05-10T14:30:00Z",
      "processed_at": "2026-05-10T14:31:00Z",
      "created_at": "2026-05-10T14:30:00Z"
    }
  ]
}
```

---

## 8.2 Get Email

```
GET /mail/{id}
```

**Response (200):** Full email with body content and attachments.

---

## 8.3 Get Attachment

```
GET /mail/{id}/attachments/{attachment_id}
```

**Response:** Raw file content with `Content-Type` and `Content-Disposition` headers.

---

## 8.4 Reprocess Email

```
POST /mail/{id}/reprocess
```

**Description:** Re-trigger classification and case creation for an email.

**Permissions Required:** `mail:admin`

**Request:**

```json
{
  "force_reclassification": true,
  "override_type": "ap_invoice"
}
```

**Response (200):** New or updated case.

---

## 8.5 Get Mail Gateway Status

```
GET /mail/status
```

**Response (200):**

```json
{
  "connection_status": "connected",
  "mailbox": "ap@mmlogistix.internal",
  "server": "imap.mailserver.com:993",
  "last_poll_at": "2026-05-10T15:45:00Z",
  "emails_last_hour": 23,
  "emails_today": 187,
  "classification_stats": {
    "total_processed": 187,
    "auto_classified": 165,
    "manual_review": 22,
    "failed": 0
  },
  "spf_failures": 0,
  "dkim_failures": 1,
  "dmarc_failures": 0,
  "duplicates_blocked": 3,
  "queue_depth": 8
}
```

---

## 8.6 Get Mail Gateway Configuration

```
GET /mail/configuration
```

**Response (200):**

```json
{
  "mailboxes": [
    {
      "id": "uuid",
      "role": "AR Executive",
      "email_address": "accar.mmlogistix@bp0.work",
      "display_name": "mmlogistix Account Receivables",
      "server": "bp0.work",
      "port": 993,
      "use_ssl": true,
      "poll_interval_seconds": 60,
      "is_active": true,
      "default_case_type": "ar_invoice",
      "routing_rules": [
        {
          "condition": "subject contains 'payment advice'",
          "route_to": "ar_payment_advice"
        }
      ]
    }
  ],
  "security": {
    "require_spf_pass": true,
    "require_dkim_pass": false,
    "require_dmarc_pass": true,
    "block_suspicious_attachments": true,
    "max_attachment_size_mb": 25,
    "allowed_attachment_types": [
      "application/pdf",
      "image/png",
      "image/jpeg",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ]
  }
}
```

---

## 8.7 Update Mail Gateway Configuration

```
PUT /mail/configuration
```

**Permissions Required:** `tenant:admin` or `mail:admin`

**Request:** Mail gateway configuration (schema as above).

**Request body** (full configuration schema as per `GET /mail/configuration`).

**Response (200):** Updated configuration.

---

## 8.8 Update Mailbox Email Address and Display Name

```
PATCH /mail/configuration/mailboxes/{id}
```

**Description:** Updates the `email_address` and/or `display_name` for a specific mailbox entry in `mail_gateway_config`. The role assignment of each mailbox is fixed (set at seed time and not editable). This endpoint is the backing API for the Client Admin mailbox settings table (`15` §8.14). Platform SMTP sender identity (`system.mmlogistix@bp0.work`) is **not** editable here — use platform settings (`13` §5.9).

**Permissions Required:** `tenant:admin` or `mail:admin`

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | `mail_gateway_config.id` |

**Request Body:**

```json
{
  "email_address": "accar.mmlogistix@bp0.work",
  "display_name": "mmlogistix Account Receivables",
  "requires_outbound_client_approval": true
}
```

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `email_address` | string (email) | O | Valid email format; must be `@bp0.work`; unique across `mail_gateway_config` |
| `display_name` | string | O | Max 255 chars; used as the `From:` display name in outbound emails from this mailbox |
| `requires_outbound_client_approval` | bool | O | Client Admin toggle — hold client-facing SMTP until manager approves (`17` §10.5.2) |

At least one field must be present. `mailbox_mode` and `escalation_manager_email` are seed-managed (not editable via this endpoint in MVP).

**Response (200):**

```json
{
  "id": "uuid",
  "role": "AR Executive",
  "mailbox_mode": "executive_agent",
  "escalation_manager_email": "acc.mmlogistix@bp0.work",
  "email_address": "accar.mmlogistix@bp0.work",
  "display_name": "mmlogistix Account Receivables",
  "requires_outbound_client_approval": true,
  "updated_at": "2026-05-19T10:00:00Z"
}
```

### 8.8a Respond to Manager Escalation (email action links)

```
GET  /mail/escalations/{escalation_id}/respond
POST /mail/escalations/{escalation_id}/respond
```

**Description:** Handles manager **Approve**, **Reject**, and **Escalate** actions from escalation emails (`17` §10.4, `01` §3.2.3, sequence diagram `07` §13). This is **not** the Approval UI SLA escalation in `07` §9 — it operates on `case_escalations` rows for executive email SOP and always keeps the **same** `cases.id` (Escalate creates a **child** escalation row, not a new case).

**Authentication:** No JWT. Caller must present a valid HMAC-signed `token` query parameter bound to `escalation_id` (see **Token format** below).

#### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `escalation_id` | UUID | `case_escalations.id` (`06` §7.5) |

#### Query parameters

| Name | Required | Description |
|------|----------|-------------|
| `action` | Yes | `approve` \| `reject` \| `escalate` |
| `token` | Yes | URL-safe signed token (see below) |
| `comment` | No | Manager note (GET one-click links; prefer POST form for long text) |

#### POST body (optional)

`Content-Type: application/x-www-form-urlencoded`

| Field | Required | Description |
|-------|----------|-------------|
| `comment` | No | Manager free-text (max 4000 chars) |

`Idempotency-Key` header (§1.8) is **optional**; the signed `token` is the primary idempotency key (see below).

#### Signed token format

Tokens are generated when the escalation email is sent (`17` §10.4). Raw tokens are **never** stored; only `SHA-256(token)` in `case_escalations.response_token_hash` (`06` §7.5).

**Payload** (JSON, before signing):

```json
{
  "typ": "case_escalation",
  "escalation_id": "550e8400-e29b-41d4-a716-446655440000",
  "case_id": "660e8400-e29b-41d4-a716-446655440001",
  "iat": 1747632000,
  "exp": 1748236800,
  "jti": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
}
```

**Wire format:** `{base64url(payload)}.{base64url(HMAC-SHA256(payload, secret))}`

| Property | Value |
|----------|-------|
| Signing secret | `FINANCE_MAIL_ACTION__SECRET` (dedicated) or `FINANCE_HASH_SECRET` fallback (`14` §2) |
| Expiry | 7 days from `iat`; must match `case_escalations.token_expires_at` |
| Validation | Recompute HMAC; constant-time compare; hash token and match `response_token_hash`; reject if `exp` &lt; now or row `status` ≠ `pending` |

**Email link examples** (production edge host `https://finance.mmlogistix.bp0.work`; paths mount at service root per §2):

```
GET /mail/escalations/{escalation_id}/respond?action=approve&token=eyJ...
GET /mail/escalations/{escalation_id}/respond?action=reject&token=eyJ...
GET /mail/escalations/{escalation_id}/respond?action=escalate&token=eyJ...
```

#### Action semantics

| `action` | DB effect | Case effect |
|----------|-----------|-------------|
| `approve` | Parent row `status='approved'`, `responded_at`, `responded_by_email`, `manager_comment` | Resume executive worker; `workflow_metadata.manager_decision='approved'` (`17` §10.4) |
| `reject` | Parent row `status='rejected'`, same response fields | Case → `rejected` or closed `manual_review`; notify executive mailbox |
| `escalate` | Parent row `status='escalated'`; **insert child** `case_escalations` with `parent_escalation_id`, new `response_token_hash`, `target_email` from responding manager mailbox’s `escalation_manager_email` (`06` §7.3) | **Same** `case_id` remains on hold; send `manager.escalation.request` to next tier (`18` §7.7). Routing: `acc`/`fin` executives → manager → **CFO**; `cfo` → **CEO** (`01` §3.2.3). **Does not** create a new `cases` row or Approval UI `approvals` record. |

**Escalate preconditions:**

- Responding mailbox `mailbox_mode` must be `manager_human` (`acc`, `fin`, `cfo`).
- `escalation_manager_email` on that mailbox must be non-null (422 `ESCALATION_TIER_EXHAUSTED` when CFO/CEO has no further tier).
- Child escalation `target_email` is resolved at click time from `mail_gateway_config.escalation_manager_email` of the manager mailbox that received the email (not from the executive row).

#### Idempotency

| Scenario | Behaviour |
|----------|-----------|
| Repeat GET/POST with **same** valid `token` and `action` after success | **200** HTML confirmation (or redirect) with **no duplicate** side effects — row already terminal; return cached outcome page |
| Same token, **different** `action` query than first successful action | **409** `ESCALATION_ALREADY_RESPONDED` |
| Expired or bad signature | **400** `INVALID_ESCALATION_TOKEN` |
| Valid token, wrong `escalation_id` in path | **400** `TOKEN_ESCALATION_MISMATCH` |

`Idempotency-Key` on POST: if present, cached in Redis 24h (§1.8) in addition to token semantics.

#### Response (200) — success

`Content-Type: text/html` (browser from email client)

Minimal HTML confirmation page with action taken, `case_id` (read-only), and link to Approval UI case detail when the responder has a finance login (optional).

**JSON variant** (only when `Accept: application/json` — automation/tests):

```json
{
  "escalation_id": "550e8400-e29b-41d4-a716-446655440000",
  "case_id": "660e8400-e29b-41d4-a716-446655440001",
  "action": "escalate",
  "status": "escalated",
  "child_escalation_id": "770e8400-e29b-41d4-a716-446655440002",
  "target_email": "cfo.mmlogistix@bp0.work",
  "responded_at": "2026-05-19T14:30:00Z",
  "message": "Escalated to CFO. A new email has been sent."
}
```

For `approve` / `reject`, `child_escalation_id` is omitted.

#### Error responses

| HTTP | `error.code` | When |
|------|--------------|------|
| 400 | `INVALID_ESCALATION_TOKEN` | Missing `token`, bad signature, or expired |
| 400 | `TOKEN_ESCALATION_MISMATCH` | Token `escalation_id` claim ≠ path param |
| 400 | `ESCALATION_NOT_PENDING` | Row not in `pending` (includes replay after terminal state without idempotent 200 path) |
| 404 | `ESCALATION_NOT_FOUND` | Unknown `escalation_id` |
| 409 | `ESCALATION_ALREADY_RESPONDED` | Token valid but action conflicts with prior response |
| 422 | `INVALID_ESCALATION_ACTION` | `action` not in enum |
| 422 | `ESCALATION_TIER_EXHAUSTED` | `action=escalate` but no `escalation_manager_email` on manager mailbox (e.g. CEO) |
| 422 | `COMMENT_REQUIRED` | Policy requires `comment` on reject (tenant setting — optional MVP) |

All errors use the envelope in §16.1 with `request_id` when `X-Request-ID` is sent.

#### Side effects (all successful actions)

1. Update `case_escalations` as per action table.
2. `INSERT finance_activity_log` — `manager_approved`, `manager_rejected`, or `escalated_to_manager` (`06` §7.4).
3. `INSERT audit_logs` tamper-evident row (`13` §9).
4. On `escalate`: enqueue notification for child escalation email via `18` §7.7 `manager.escalation.request`.

**Rate limit:** 30 requests/minute per IP (unsigned public surface).

### 8.8b Respond to Pending Client Outbound (clarification approval)

```
GET /mail/outbound/{pending_id}/respond
POST /mail/outbound/{pending_id}/respond
```

**Query:** `action=approve|reject`, `token` (signed HMAC).

**POST body (optional):** `comment` (text), `rejection_reason_code` (required when `action=reject`). Same fields may be supplied on GET query for one-click links; POST is used when the manager submits the HTML form with a comment.

| `rejection_reason_code` | When to use |
|-------------------------|-------------|
| `data_present_in_attachment` | Required fields were in PDF/DOC/XLS attachment but not extracted |
| `data_present_in_email` | Required fields were in email body |
| `parsing_incomplete` | Partial extraction — retry Hermes |
| `other` | Manager free-text in `comment` |

**Description:** Manager **Approve** / **Reject** for client clarification held in `pending_outbound_emails` (`17` §10.5.4–§10.5.5, `01` §6.8.4). **Approve** sends the drafted message (including quoted email thread per `17` §10.5.3). **Reject** does **not** SMTP to the client; triggers worker re-extraction and case re-queue. Writes `finance_activity_log`.

**Permissions:** Valid signed token scoped to `pending_outbound_emails.id` and 7-day expiry (`06` §7.6).

**Response (200):** HTML confirmation page or redirect to case detail.

**Response (400):** Invalid/expired token, or row not in `awaiting_manager_approval`.

**Response (404):** Unknown `pending_id`.

**Response (422):** Missing `rejection_reason_code` on reject, or invalid enum value.

---

## 8.9 Get Duplicate Detection Results

```
GET /mail/{id}/duplicates
```

**Response (200):**

```json
{
  "is_duplicate": false,
  "checks": [
    {
      "method": "message_id",
      "matched": false,
      "match_id": null
    },
    {
      "method": "content_hash",
      "matched": false,
      "match_id": null,
      "similarity": 0.12
    },
    {
      "method": "attachment_hash",
      "matched": false,
      "match_id": null
    }
  ]
}
```

---

# 9. Queue Management

Base path: `/queues`

## 9.1 List Queues

```
GET /queues
```

**Response (200):**

```json
{
  "data": [
    {
      "name": "intake_queue",
      "description": "New inbound emails awaiting classification",
      "depth": 12,
      "messages_processed_last_hour": 45,
      "messages_failed_last_hour": 1,
      "consumer_count": 2,
      "oldest_message_age_seconds": 180
    },
    {
      "name": "accounts_queue",
      "description": "Classified cases ready for worker processing",
      "depth": 8,
      "messages_processed_last_hour": 38,
      "messages_failed_last_hour": 0,
      "consumer_count": 3,
      "oldest_message_age_seconds": 90
    },
    {
      "name": "dead_letter_queue",
      "description": "Messages that failed max retry attempts",
      "depth": 3,
      "messages_processed_last_hour": 0,
      "messages_failed_last_hour": 0,
      "consumer_count": 0,
      "oldest_message_age_seconds": 86400
    }
  ]
}
```

---

## 9.2 Get Queue Messages

```
GET /queues/{queue_name}/messages
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | `pending`, `processing`, `failed` |
| `limit` | integer | Max messages to return |

**Response (200):**

```json
{
  "queue": "accounts_queue",
  "messages": [
    {
      "id": "uuid",
      "case_id": "uuid",
      "case_number": "CAS-2026-0001543",
      "type": "ar_invoice",
      "status": "pending",
      "attempt_count": 0,
      "payload_preview": { "email_id": "uuid", "classification": "ar_invoice" },
      "created_at": "2026-05-10T15:45:00Z",
      "scheduled_at": "2026-05-10T15:45:00Z"
    }
  ]
}
```

---

## 9.3 Retry Failed Message

```
POST /queues/{queue_name}/messages/{message_id}/retry
```

**Description:** Move a failed message back to pending for reprocessing.

**Permissions Required:** `queues:admin`

**Response (200):** Message queued for retry.

---

## 9.4 Purge Queue

```
POST /queues/{queue_name}/purge
```

**Description:** Remove all pending messages from a queue.

**Permissions Required:** `queues:admin`

**Request:**

```json
{
  "confirm": true,
  "reason": "Emergency queue reset after worker deployment"
}
```

**Response (200):**

```json
{
  "purged_count": 12,
  "queue": "intake_queue"
}
```

---

## 9.5 Move Message

```
POST /queues/{queue_name}/messages/{message_id}/move
```

**Description:** Move a message to a different queue.

**Permissions Required:** `queues:admin`

**Request:**

```json
{
  "target_queue": "dead_letter_queue",
  "reason": "Manual move — awaiting bug fix"
}
```

---

# 9a. Events & SSE

Base path: `/events`

This section specifies the real-time event endpoints consumed by the Approval UI and other clients. The authoritative event model, payload schemas, SSE event types, channel subscription rules, and dead letter schema are defined in `09_Event_Model_Specification.md` §15–§16. This section provides the HTTP contract for Cursor implementation.

## 9a.1 SSE Stream

```
GET /events/stream
```

**Description:** Server-Sent Events endpoint for real-time UI notifications. Subscribes to Redis Pub/Sub channels based on the authenticated user's role and permissions, then streams matching events. See `09_Event_Model_Specification.md` §15.1–§15.5 for full implementation detail including the `generate()` coroutine, channel subscription logic, and SSE format.

**Permissions Required:** `cases:read` (channels filtered per role — see `09` §15.4)

**Response:** `text/event-stream` (streaming, no JSON envelope)

```
event: case.status_changed
id: evt-007
data: {"case_id": "...", "case_number": "CAS-2026-0001542", "previous_status": "classified", "new_status": "processing"}

```

**SSE Event Types:**

| Event | Trigger |
|-------|---------|
| `case.created` | New case created |
| `case.assigned` | Case assigned to user |
| `case.status_changed` | Any case status transition |
| `approval.requested` | New approval requested |
| `approval.approved` | Approval granted |
| `approval.rejected` | Approval rejected |
| `approval.delegated` | Approval delegated |
| `approval.sla_at_risk` | Approval crossed 50% SLA window and still pending |
| `approval.escalated` | Approval escalated to higher tier |
| `workflow.completed` | Workflow finished |
| `system.notification` | System alert |

**Response Headers:**

| Header | Value |
|--------|-------|
| `Content-Type` | `text/event-stream` |
| `Cache-Control` | `no-cache` |
| `Connection` | `keep-alive` |

---

## 9a.2 List Dead Letter Events

```
GET /events/dead-letter
```

**Description:** List events that have been moved to the dead letter channel after exhausting retries. See `09_Event_Model_Specification.md` §16.1–§16.3 for dead letter triggers and Redis key schema.

**Permissions Required:** `queues:admin`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Max results (default 50) |
| `cursor` | string | Pagination cursor |

**Response (200):**

```json
{
  "data": [
    {
      "dead_letter_id": "dl-uuid-001",
      "original_event": { },
      "dead_lettered_at": "2026-05-10T16:00:00Z",
      "reason": "consumer_rejected",
      "retry_count": 3,
      "last_error": "KeyError: 'amount_value' not found in payload",
      "channel": "events:case:*"
    }
  ],
  "pagination": {
    "next_cursor": null,
    "has_more": false
  }
}
```

---

## 9a.3 Retry Dead Letter Event

```
POST /events/dead-letter/{id}/retry
```

**Description:** Re-publish a dead letter event to its original channel for reprocessing.

**Permissions Required:** `queues:admin`

**Response (200):**

```json
{
  "dead_letter_id": "dl-uuid-001",
  "status": "requeued",
  "requeued_at": "2026-05-10T16:30:00Z"
}
```

---

## 9a.4 Discard Dead Letter Event

```
DELETE /events/dead-letter/{id}
```

**Description:** Permanently remove an event from the dead letter channel. Irreversible.

**Permissions Required:** `queues:admin`

**Response (204):** No content.

---

# 10. Policies

Base path: `/policies`

## 10.1 List Policies

```
GET /policies
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | `accounting`, `approval`, `tax`, `reconciliation` |
| `is_active` | boolean | Only active policies |
| `version` | string | Filter by version |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "name": "revenue_recognition_standard",
      "display_name": "Revenue Recognition Standard",
      "description": "Defines when revenue should be recognized in the general ledger",
      "category": "accounting",
      "version": "2.1.0",
      "is_active": true,
      "effective_from": "2026-01-01",
      "effective_to": null,
      "created_by": "uuid",
      "created_at": "2026-01-15T00:00:00Z",
      "updated_at": "2026-03-01T00:00:00Z",
      "superseded_by": null,
      "rules_count": 12
    }
  ]
}
```

---

## 10.2 Get Policy

```
GET /policies/{id}
```

**Response (200):** Full policy with rules.

```json
{
  "id": "uuid",
  "name": "ap_approval_thresholds",
  "display_name": "AP Approval Thresholds",
  "description": "Approval tier assignment based on invoice amount",
  "category": "approval",
  "version": "1.2.0",
  "is_active": true,
  "effective_from": "2026-01-01",
  "effective_to": null,
  "rules": [
    {
      "rule_id": "uuid",
      "name": "tier_1_auto_release",
      "priority": 1,
      "conditions": [
        {
          "field": "amount",
          "operator": "less_than",
          "value": "5000"
        },
        {
          "field": "counterparty.recurring",
          "operator": "equals",
          "value": "true"
        },
        {
          "field": "risk_flags",
          "operator": "is_empty"
        }
      ],
      "action": {
        "type": "auto_release",
        "approval_tier": 1
      },
      "is_active": true
    },
    {
      "rule_id": "uuid",
      "name": "tier_2_standard",
      "priority": 2,
      "conditions": [
        {
          "field": "amount",
          "operator": "less_than",
          "value": "50000"
        }
      ],
      "action": {
        "type": "require_approval",
        "approval_tier": 2
      },
      "is_active": true
    },
    {
      "rule_id": "uuid",
      "name": "tier_3_executive",
      "priority": 3,
      "conditions": [
        {
          "field": "amount",
          "operator": "greater_than_or_equal",
          "value": "50000"
        }
      ],
      "action": {
        "type": "require_approval",
        "approval_tier": 3
      },
      "is_active": true
    }
  ],
  "created_by": "uuid",
  "created_at": "2026-01-15T00:00:00Z",
  "updated_at": "2026-03-01T00:00:00Z",
  "change_log": [
    {
      "version": "1.1.0",
      "changed_by": "uuid",
      "changed_at": "2026-02-15T00:00:00Z",
      "change_summary": "Increased Tier 2 threshold from 30k to 50k"
    }
  ]
}
```

---

## 10.3 Create Policy

```
POST /policies
```

**Request:**

```json
{
  "name": "string",             // required, snake_case, unique
  "display_name": "string",     // required
  "description": "string",      // optional
  "category": "string",         // required: accounting, approval, tax, reconciliation
  "effective_from": "date",     // optional, default: today
  "rules": [                    // optional, can add later
    {
      "name": "string",
      "priority": 1,
      "conditions": [
        {
          "field": "string",
          "operator": "string",
          "value": "any"
        }
      ],
      "action": {
        "type": "string",
        ...
      }
    }
  ]
}
```

**Response (201):** Created policy with version `1.0.0`.

---

## 10.4 Update Policy

```
PUT /policies/{id}
```

**Description:** Updating an active policy creates a new version. Previous version remains available.

**Request:** Same as Create.

**Response (200):** Updated policy with incremented version.

---

## 10.5 Deactivate Policy

```
POST /policies/{id}/deactivate
```

**Request:**

```json
{
  "effective_to": "2026-06-01",
  "reason": "Superseded by new policy"
}
```

**Response (200):** Deactivated policy.

---

## 10.6 Validate Against Policies

```
POST /policies/validate
```

**Description:** Run a case or transaction against active policies and return matched rules.

**Request:**

```json
{
  "case_data": {
    "type": "ap_invoice",
    "amount": {
      "value": "15850.00",
      "currency": "SGD"
    },
    "counterparty": {
      "id": "uuid",
      "recurring": true
    },
    "risk_flags": []
  }
}
```

**Response (200):**

```json
{
  "case_data": { ... },
  "matched_rules": [
    {
      "policy_id": "uuid",
      "policy_name": "ap_approval_thresholds",
      "rule_id": "uuid",
      "rule_name": "tier_2_standard",
      "priority": 2,
      "action": {
        "type": "require_approval",
        "approval_tier": 2
      },
      "matched_conditions": [
        { "field": "amount", "operator": "less_than", "value": "50000", "matched": true }
      ]
    }
  ],
  "final_action": {
    "type": "require_approval",
    "approval_tier": 2
  },
  "violations": []
}
```

---

## 10.7 Get Policy Categories

```
GET /policies/categories
```

**Response (200):**

```json
{
  "data": [
    {
      "code": "accounting",
      "name": "Accounting",
      "description": "General accounting treatment policies",
      "active_policies_count": 5
    },
    {
      "code": "approval",
      "name": "Approval",
      "description": "Approval thresholds and routing rules",
      "active_policies_count": 3
    },
    {
      "code": "tax",
      "name": "Tax",
      "description": "Tax handling and GST rules",
      "active_policies_count": 4
    },
    {
      "code": "reconciliation",
      "name": "Reconciliation",
      "description": "Reconciliation tolerances and matching rules",
      "active_policies_count": 2
    }
  ]
}
```

---

# 11. Chart of Accounts

Base path: `/chart-of-accounts`

## 11.1 List Accounts

```
GET /chart-of-accounts
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `account_type` | string | `asset`, `liability`, `equity`, `revenue`, `expense` |
| `is_active` | boolean | Only active accounts |
| `parent_id` | uuid | Filter by parent account |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "account_code": "2100",
      "account_name": "Trade Creditors",
      "account_type": "liability",
      "account_subtype": "current_liability",
      "parent_id": null,
      "is_active": true,
      "is_bank_account": false,
      "currency": "SGD",
      "description": "Amounts owing to trade suppliers",
      "created_at": "2026-01-15T00:00:00Z",
      "updated_at": "2026-01-15T00:00:00Z"
    }
  ]
}
```

---

## 11.2 Get Account

```
GET /chart-of-accounts/{id}
```

**Response (200):** Account with child accounts and recent activity.

---

## 11.3 Import Chart of Accounts (bulk)

```
POST /chart-of-accounts/import
```

> **Shipped Client Admin path (`0.14.7`):** `POST /api/coa/import` with query `replace_all` — authoritative contract in §4.16d.3. Legacy path below retained for naming consistency with finance API surface.

**Description:** Replaces or merges the tenant Chart of Accounts from an uploaded CSV file. Intended for Client System Administrator use (`13` §5.9); not for day-to-day account creation (use §11.4).

**Permissions Required:** `coa:import` (included in `tenant:admin`)

**Request:** `multipart/form-data` with field `file` (`.csv`; UTF-8 with optional BOM). Query `replace_all=true` deactivates all existing accounts before upsert.

**Response (200):** `{ "created", "updated", "skipped", "active_count" }` — see §4.16d.3.

**Response (400):** `INVALID_CSV` when headers or rows are invalid.

---

## 11.4 Create Account

```
POST /chart-of-accounts
```

**Request:**

```json
{
  "account_code": "2100",           // required, unique
  "account_name": "string",         // required
  "account_type": "string",         // required
  "account_subtype": "string",      // optional
  "parent_id": "uuid",              // optional
  "is_active": true,                // optional, default true
  "is_bank_account": false,         // optional, default false
  "currency": "SGD",                // optional, default SGD
  "description": "string"           // optional
}
```

---

## 11.5 Update Account

```
PUT /chart-of-accounts/{id}
```

**Note:** `account_code` cannot be changed if journal entries exist.

---

## 11.6 Deactivate Account

```
POST /chart-of-accounts/{id}/deactivate
```

**Description:** Deactivate account. Fails if account has activity in last 90 days.

---

# 12. Journal Entries

Base path: `/journal-entries`

## 12.1 List Journal Entries

```
GET /journal-entries
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | `draft`, `pending`, `posted`, `reversed` |
| `case_id` | uuid | Filter by originating case |
| `from_date` | date | Entry date on or after |
| `to_date` | date | Entry date on or before |
| `posted_by` | uuid | Filter by posting user |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "entry_number": "JE-2026-000892",
      "case_id": "uuid",
      "case_number": "CAS-2026-0001542",
      "status": "posted",
      "entry_date": "2026-05-10",
      "description": "AP Invoice — ACME Supplies INV-44521",
      "reference": "INV-44521",
      "currency": "SGD",
      "total_debit": "15850.00",
      "total_credit": "15850.00",
      "is_balanced": true,
      "lines": [
        {
          "line_number": 1,
          "account_id": "uuid",
          "account_code": "5200",
          "account_name": "Office Supplies",
          "description": "Office supplies — May 2026",
          "debit": "15850.00",
          "credit": "0.00",
          "cost_center": "CC-001",
          "project_code": null
        },
        {
          "line_number": 2,
          "account_id": "uuid",
          "account_code": "2100",
          "account_name": "Trade Creditors",
          "description": "ACME Supplies INV-44521",
          "debit": "0.00",
          "credit": "15850.00",
          "cost_center": null,
          "project_code": null
        }
      ],
      "posted_by": {
        "id": "uuid",
        "name": "Jane Smith"
      },
      "posted_at": "2026-05-10T16:00:00Z",
      "approval_id": "uuid",
      "reversal_of": null,
      "created_at": "2026-05-10T15:50:00Z"
    }
  ]
}
```

---

## 12.2 Get Journal Entry

```
GET /journal-entries/{id}
```

**Response (200):** Full journal entry with all lines.

---

## 12.3 Create Journal Entry

```
POST /journal-entries
```

**Description:** Create a journal entry draft. Does not post to ledger.

**Request:**

```json
{
  "case_id": "uuid",                // optional, link to originating case
  "entry_date": "2026-05-10",       // required
  "description": "string",          // required
  "reference": "string",            // optional, external reference
  "currency": "SGD",                // optional, default SGD
  "lines": [                        // required, min 2 lines
    {
      "account_id": "uuid",         // required
      "description": "string",      // optional, line description
      "debit": "0.00",              // required, numeric string
      "credit": "0.00",             // required, numeric string
      "cost_center": "string",      // optional
      "project_code": "string"      // optional
    }
  ]
}
```

**Validation:**
- Total debits must equal total credits
- At least 2 lines required
- All accounts must be active

**Response (201):** Created journal entry with `status: draft`.

---

## 12.4 Update Journal Entry

```
PUT /journal-entries/{id}
```

**Description:** Update a draft journal entry. Cannot modify posted entries.

**Errors:**

| Status | Code | Message |
|--------|------|---------|
| 409 | `ENTRY_ALREADY_POSTED` | Cannot modify a posted journal entry |

---

## 12.5 Post Journal Entry

```
POST /journal-entries/{id}/post
```

**Description:** Post a draft journal entry to the ledger.

**Request:**

```json
{
  "posting_date": "2026-05-10",
  "note": "string"
}
```

**Permissions Required:** `journal-entries:write`

**Response (200):** Journal entry with `status: posted`.

---

## 12.6 Reverse Journal Entry

```
POST /journal-entries/{id}/reverse
```

**Description:** Create a reversing entry. Original entry remains; new reversing entry created.

**Request:**

```json
{
  "reversal_date": "2026-05-11",
  "reason": "Invoice cancelled — credit note received"
}
```

**Response (201):** New reversing journal entry.

---

## 12.7 Get Journal Entry Attachments

```
GET /journal-entries/{id}/attachments
```

**Response (200):** List of linked attachments.

---

# 13. Reconciliation

Base path: `/reconciliation`

## 13.1 List Reconciliation Runs

```
GET /reconciliation
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `account_id` | uuid | Bank/ledger account |
| `status` | string | `in_progress`, `completed`, `failed` |
| `from_date` | date | Statement date from |
| `to_date` | date | Statement date to |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "account_id": "uuid",
      "account_name": "DBS Operating Account",
      "account_code": "1200",
      "statement_period_from": "2026-04-01",
      "statement_period_to": "2026-04-30",
      "status": "completed",
      "opening_balance": "145230.50",
      "closing_balance": "189450.25",
      "statement_balance": "189450.25",
      "matched_count": 156,
      "unmatched_count": 3,
      "match_rate": 0.981,
      "auto_matched_count": 148,
      "manual_matched_count": 8,
      "started_by": {
        "id": "uuid",
        "name": "System"
      },
      "started_at": "2026-05-01T02:00:00Z",
      "completed_at": "2026-05-01T02:15:00Z"
    }
  ]
}
```

---

## 13.2 Get Reconciliation Details

```
GET /reconciliation/{id}
```

**Response (200):** Full reconciliation with match groups.

---

## 13.3 Start Reconciliation

```
POST /reconciliation/start
```

**Description:** Initiate a reconciliation run for an account.

**Request:**

```json
{
  "account_id": "uuid",             // required
  "statement_period_from": "date",  // required
  "statement_period_to": "date",    // required
  "statement_balance": "189450.25", // optional, for variance checking
  "bank_statement_file": "uuid",    // optional, uploaded file ID
  "auto_match_rules": [             // optional, override default rules
    "exact_amount_date",
    "exact_amount_tolerance_3days",
    "reference_match"
  ]
}
```

**Response (202):** Reconciliation started.

```json
{
  "reconciliation_id": "uuid",
  "status": "in_progress",
  "estimated_completion": "2026-05-01T02:20:00Z"
}
```

---

## 13.4 Get Unmatched Items

```
GET /reconciliation/{id}/unmatched
```

**Response (200):**

```json
{
  "reconciliation_id": "uuid",
  "unmatched_count": 3,
  "items": [
    {
      "id": "uuid",
      "side": "bank",               // or "ledger"
      "transaction_date": "2026-04-28",
      "description": "Bank charges — April 2026",
      "reference": "BC-0426",
      "amount": "25.00",
      "currency": "SGD",
      "suggested_matches": [
        {
          "ledger_entry_id": "uuid",
          "confidence": 0.85,
          "match_reason": "amount_within_tolerance"
        }
      ]
    }
  ]
}
```

---

## 13.5 Manual Match

```
POST /reconciliation/{id}/match
```

**Description:** Manually match bank and ledger items.

**Request:**

```json
{
  "bank_item_id": "uuid",
  "ledger_item_id": "uuid",
  "match_type": "manual",
  "note": "Bank charges — matched to accrual"
}
```

---

## 13.6 Unmatch

```
POST /reconciliation/{id}/unmatch
```

**Request:**

```json
{
  "match_id": "uuid",
  "reason": "Incorrect auto-match"
}
```

---

## 13.7 Get Reconciliation Summary

```
GET /reconciliation/summary
```

**Description:** Dashboard summary across all reconciliation accounts.

**Response (200):**

```json
{
  "accounts": [
    {
      "account_id": "uuid",
      "account_name": "DBS Operating Account",
      "last_reconciled_date": "2026-04-30",
      "last_reconciliation_status": "completed",
      "match_rate": 0.981,
      "unreconciled_count": 3,
      "outstanding_balance": "189450.25"
    }
  ],
  "overall": {
    "total_accounts": 4,
    "reconciled_this_month": 4,
    "average_match_rate": 0.975,
    "total_unreconciled": 7
  }
}
```

---

# 14. Audit Logs

Base path: `/audit-logs`

## 14.1 List Audit Logs

```
GET /audit-logs
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `entity_type` | string | `case`, `journal_entry`, `approval`, `user`, `policy` |
| `entity_id` | uuid | Specific entity |
| `action` | string | `create`, `update`, `delete`, `approve`, `reject`, `post`, `login`, `logout` |
| `user_id` | uuid | Filter by acting user |
| `from_date` | datetime | On or after |
| `to_date` | datetime | On or before |

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid",
      "timestamp": "2026-05-10T16:00:00Z",
      "action": "approve",
      "entity_type": "approval",
      "entity_id": "uuid",
      "case_id": "uuid",
      "case_number": "CAS-2026-0001542",
      "user": {
        "id": "uuid",
        "name": "Jane Smith",
        "ip_address": "192.168.1.45"
      },
      "before_state": { "status": "pending" },
      "after_state": { "status": "approved" },
      "metadata": {
        "approval_id": "uuid",
        "tier": 2,
        "note": "Verified against PO #4521 and GRN. Approved."
      },
      "correlation_id": "req-uuid-123",
      "tamper_hash": "sha256:def456..."
    }
  ]
}
```

---

## 14.2 Get Audit Log Entry

```
GET /audit-logs/{id}
```

**Response (200):** Full audit log entry.

---

## 14.3 Export Audit Logs

```
POST /audit-logs/export
```

**Description:** Export audit logs to file.

**Request:**

```json
{
  "format": "csv",                  // csv, json, xlsx
  "from_date": "2026-04-01T00:00:00Z",
  "to_date": "2026-04-30T23:59:59Z",
  "entity_type": "case",
  "actions": ["approve", "reject"]
}
```

**Response (202):**

```json
{
  "export_id": "uuid",
  "status": "processing",
  "download_url": null,
  "estimated_ready": "2026-05-11T10:00:00Z"
}
```

---

## 14.4 Check Log Integrity

```
GET /audit-logs/integrity-check
```

**Description:** Verify tamper-proof hash chain integrity.

**Response (200):**

```json
{
  "integrity_status": "valid",
  "total_entries_checked": 15420,
  "first_entry_date": "2026-01-15T00:00:00Z",
  "last_entry_date": "2026-05-10T23:59:59Z",
  "violations": []
}
```

If violations exist:

```json
{
  "integrity_status": "compromised",
  "violations": [
    {
      "entry_id": "uuid",
      "expected_hash": "sha256:abc...",
      "actual_hash": "sha256:def...",
      "violation_type": "hash_mismatch"
    }
  ]
}
```

---

# 15. Dashboard & Metrics

Base path: `/dashboard`

## 15.1 Get Dashboard Summary

```
GET /dashboard/summary
```

**Description:** Fixed-window multi-domain operational snapshot for the live operations dashboard. Returns a single screen's worth of current-state data across cases, approvals, reconciliation, and system health. Designed for a single API call to populate the dashboard on page load and on SSE-triggered refresh.

**Consumer distinction:** this endpoint is consumed exclusively by the Approval UI dashboard screen (`15_Approval_UI_Specification.md` §8.1). It is **not** a general-purpose analytics endpoint — use `GET /cases/statistics` (§5.14) for historical trend data and configurable date ranges.

**Delegation rule (implementation):** the `cases` sub-object in this response is produced by calling `CaseStatisticsService.get_statistics(from_date=today, to_date=today)` — the same service method called by `GET /cases/statistics`. Do not write a second aggregation query. The dashboard handler assembles the response by calling:
- `CaseStatisticsService.get_statistics(today, today)` → `cases` section
- `ApprovalService.get_pending_summary(user_id)` → `approvals` section  
- `ReconciliationService.get_daily_summary()` → `reconciliation` section
- `MailGatewayService.get_status()` → `mail_gateway` section

**Permissions:** `cases:read`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `today` | Window for the `cases` and `processing` sections: `today`, `week`, `month`. Does not affect `approvals`, `reconciliation`, or `mail_gateway` sections which are always current-state. |

**Response (200):**

```json
{
  "period": "today",
  "cases": {
    "new": 23,
    "completed": 18,
    "pending_approval": 12,
    "in_exception": 2,
    "in_manual_review": 3,
    "sla_breached": 0
  },
  "processing": {
    "stp_rate": 0.72,
    "average_classification_confidence": 0.93,
    "average_processing_time_minutes": 4.5,
    "emails_processed": 23,
    "duplicates_detected": 1
  },
  "approvals": {
    "pending_count": 12,
    "responded_today": 15,
    "average_response_time_hours": 1.2,
    "escalated_today": 0
  },
  "reconciliation": {
    "accounts_reconciled": 1,
    "average_match_rate": 0.981,
    "unreconciled_items": 7
  },
  "mail_gateway": {
    "status": "connected",
    "last_poll": "2026-05-10T15:59:00Z",
    "queue_depth": 5
  }
}
```

**How this differs from `GET /cases/statistics`:**

| Dimension | `GET /cases/statistics` (§5.14) | `GET /dashboard/summary` (§15.1) |
|-----------|--------------------------------|----------------------------------|
| Date range | Any range via `from_date`/`to_date` | Today (or `period` param: today/week/month) |
| Domains covered | Cases only | Cases + approvals + reconciliation + mail gateway |
| Trend data | Yes — daily data points | No — single totals only |
| `group_by` dimension | Yes | No |
| Primary consumer | Reporting screens, analytics | Operations dashboard (single screen) |
| Implementation | Single `CaseStatisticsService` call | Assembles 4 service calls |

---

## 15.2 Get Processing Metrics

```
GET /dashboard/metrics/processing
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `period` | string | `hour`, `day`, `week`, `month` |
| `from_date` | date | Start date |
| `to_date` | date | End date |

**Response (200):**

```json
{
  "period": "day",
  "data_points": [
    {
      "timestamp": "2026-05-10T00:00:00Z",
      "cases_received": 23,
      "cases_completed": 18,
      "stp_count": 16,
      "exception_count": 1,
      "manual_review_count": 2,
      "average_confidence": 0.93,
      "average_processing_minutes": 4.5,
      "classification_accuracy": 0.98
    }
  ],
  "totals": {
    "cases_received": 23,
    "cases_completed": 18,
    "stp_rate": 0.72,
    "exception_rate": 0.043
  }
}
```

---

## 15.3 Get Worker Health

```
GET /dashboard/workers
```

**Response (200):**

```json
{
  "workers": [
    {
      "name": "accounts-worker",
      "status": "healthy",
      "version": "1.0.0",
      "uptime_seconds": 86400,
      "messages_processed": 452,
      "messages_failed": 3,
      "average_processing_time_ms": 1200,
      "last_heartbeat": "2026-05-10T15:59:30Z",
      "current_jobs": 1
    },
    {
      "name": "ar-worker",
      "status": "healthy",
      "version": "1.0.0",
      "uptime_seconds": 86400,
      "messages_processed": 289,
      "messages_failed": 1,
      "average_processing_time_ms": 2400,
      "last_heartbeat": "2026-05-10T15:59:45Z",
      "current_jobs": 0
    },
    {
      "name": "ap-worker",
      "status": "healthy",
      "version": "1.0.0",
      "uptime_seconds": 86400,
      "messages_processed": 312,
      "messages_failed": 2,
      "average_processing_time_ms": 1800,
      "last_heartbeat": "2026-05-10T15:59:15Z",
      "current_jobs": 1
    },
    {
      "name": "treasury-worker",
      "status": "healthy",
      "version": "1.0.0",
      "uptime_seconds": 86400,
      "messages_processed": 156,
      "messages_failed": 0,
      "average_processing_time_ms": 3200,
      "last_heartbeat": "2026-05-10T15:59:50Z",
      "current_jobs": 2
    }
  ]
}
```

---

## 15.4 Get System Health

```
GET /health
```

**Description:** Public health check endpoint (no auth required).

**Response (200):**

```json
{
  "status": "healthy",
  "timestamp": "2026-05-10T16:00:00Z",
  "version": "1.0.0",
  "checks": {
    "database": { "status": "ok", "response_time_ms": 12 },
    "redis": { "status": "ok", "response_time_ms": 3 },
    "mail_gateway": { "status": "ok", "last_poll_seconds_ago": 30 },
    "ollama": { "status": "ok", "response_time_ms": 245 }
  }
}
```

---

## 15.5 Get Readiness Check

```
GET /ready
```

**Description:** Kubernetes-style readiness probe.

**Response (200):**

```json
{
  "ready": true,
  "dependencies": {
    "database": true,
    "redis": true,
    "mail_gateway": true
  }
}
```

**Response (503):** Not ready — one or more dependencies unavailable.

---

# 16. Error Handling

## 16.1 Error Response Format

All errors follow a consistent envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "amount.value",
        "issue": "Invalid numeric format",
        "value": "15,850.00"
      }
    ],
    "request_id": "req-uuid-123",
    "timestamp": "2026-05-10T16:00:00Z"
  }
}
```

## 16.2 HTTP Status Codes

| Status | Meaning | Usage |
|--------|---------|-------|
| 200 | OK | Successful GET, PUT, POST, PATCH |
| 201 | Created | Resource created successfully |
| 204 | No Content | Successful DELETE, no body |
| 400 | Bad Request | Validation error, malformed request |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Authenticated but insufficient permissions |
| 404 | Not Found | Resource does not exist |
| 409 | Conflict | Resource state conflict (e.g., already processed) |
| 422 | Unprocessable Entity | Business rule violation |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |
| 503 | Service Unavailable | Dependency unavailable |

## 16.3 Error Codes by Domain

### Authentication (`/auth`)

| Code | HTTP | Description |
|------|------|-------------|
| `INVALID_CREDENTIALS` | 401 | Username or password incorrect |
| `TOTP_REQUIRED` | 401 | 2FA code required |
| `INVALID_TOTP` | 401 | TOTP code invalid |
| `RATE_LIMITED` | 429 | Too many login attempts |
| `INVALID_REFRESH_TOKEN` | 401 | Refresh token invalid |
| `REFRESH_TOKEN_REVOKED` | 401 | Refresh token revoked |

### Cases (`/cases`)

| Code | HTTP | Description |
|------|------|-------------|
| `CASE_NOT_FOUND` | 404 | Case ID does not exist |
| `INVALID_STATUS_TRANSITION` | 422 | Status change not allowed |
| `CASE_LOCKED` | 409 | Case is being processed by another user |

### Approvals (`/approvals`)

| Code | HTTP | Description |
|------|------|-------------|
| `ALREADY_RESPONDED` | 409 | Approval already has a response |
| `UNAUTHORIZED_APPROVER` | 403 | User is not the designated approver |
| `APPROVAL_SLA_BREACHED` | 422 | Approval past SLA deadline |

### Journal Entries (`/journal-entries`)

| Code | HTTP | Description |
|------|------|-------------|
| `ENTRY_ALREADY_POSTED` | 409 | Cannot modify posted entry |
| `UNBALANCED_ENTRY` | 422 | Debits do not equal credits |
| `INVALID_ACCOUNT` | 422 | Account inactive or does not exist |

### Policies (`/policies`)

| Code | HTTP | Description |
|------|------|-------------|
| `POLICY_VERSION_CONFLICT` | 409 | Version mismatch on update |
| `RULE_VALIDATION_FAILED` | 422 | Rule syntax or logic error |

### Queues (`/queues`)

| Code | HTTP | Description |
|------|------|-------------|
| `MESSAGE_NOT_FOUND` | 404 | Message ID not in queue |
| `QUEUE_OPERATION_FAILED` | 422 | Redis operation failed |

### Mail — escalation respond (`/mail/escalations/{escalation_id}/respond`)

| Code | HTTP | Description |
|------|------|-------------|
| `INVALID_ESCALATION_TOKEN` | 400 | Missing, invalid, or expired signed token |
| `TOKEN_ESCALATION_MISMATCH` | 400 | Token `escalation_id` ≠ path parameter |
| `ESCALATION_NOT_PENDING` | 400 | Row not in `pending` status |
| `ESCALATION_NOT_FOUND` | 404 | Unknown `escalation_id` |
| `ESCALATION_ALREADY_RESPONDED` | 409 | Conflicting second action on same token |
| `INVALID_ESCALATION_ACTION` | 422 | `action` not `approve` \| `reject` \| `escalate` |
| `ESCALATION_TIER_EXHAUSTED` | 422 | No further `escalation_manager_email` (e.g. CEO) |
| `COMMENT_REQUIRED` | 422 | Required `comment` missing on reject |

### Internal jobs (`/internal/jobs`)

| Code | HTTP | Description |
|------|------|-------------|
| `INVALID_CRON_TOKEN` | 401 | Scheduler bearer token invalid |
| `SMTP_UNAVAILABLE` | 503 | Digest send failed — mail dependency down |

## 16.4 Retry Guidelines

| Status | Client Should |
|--------|---------------|
| 429 | Retry after `Retry-After` header, with exponential backoff |
| 503 | Retry with exponential backoff, max 3 retries |
| 500 | Retry once after 5 seconds, then surface error |
| 409 | Do not retry without user intervention |
| 422 | Do not retry — fix request and resubmit |

---

# 17. Common Schemas

## 17.1 Money Object

```json
{
  "value": "15850.00",        // Decimal as string, 2 decimal places
  "currency": "SGD"           // ISO 4217 currency code
}
```

## 17.2 User Reference

```json
{
  "id": "uuid",
  "name": "Jane Smith",
  "email": "jane.smith@mmlogistix.internal"
}
```

## 17.3 Counterparty

```json
{
  "id": "uuid",
  "name": "ACME Supplies Pte Ltd",
  "code": "SUPP-00124",
  "type": "supplier",
  "contact_email": "accounts@acmesupplies.sg",
  "contact_phone": "+65 6123 4567",
  "is_recurring": true
}
```

## 17.4 Risk Flags

| Flag Code | Description | Triggers Tier |
|-----------|-------------|---------------|
| `above_threshold` | Amount exceeds standard threshold | 2 or 3 |
| `new_counterparty` | First transaction with counterparty | 2 |
| `new_supplier_30_days` | Supplier added within 30 days | 2 |
| `duplicate_suspected` | Possible duplicate detected | 2 |
| `amount_anomaly` | Amount deviates from historical pattern | 2 |
| `policy_override_requested` | Explicit policy override | 3 |
| `high_value_transaction` | Above executive threshold | 3 |
| `suspicious_pattern` | Matches fraud pattern | 3 |

## 17.5 Webhook Event (Future)

```json
{
  "event_id": "uuid",
  "event_type": "case.status_changed",
  "timestamp": "2026-05-10T16:00:00Z",
  "payload": {
    "case_id": "uuid",
    "case_number": "CAS-2026-0001542",
    "previous_status": "pending_approval",
    "new_status": "approved"
  }
}
```

**Event Types (Future):**

| Event Type | Trigger |
|------------|---------|
| `case.created` | New case created |
| `case.status_changed` | Case status transition |
| `case.assigned` | Case assigned to user |
| `approval.requested` | New approval request |
| `approval.approved` | Approval granted |
| `approval.rejected` | Approval rejected |
| `approval.escalated` | Approval escalated |
| `journal.posted` | Journal entry posted |
| `exception.raised` | Exception triggered |
| `reconciliation.completed` | Reconciliation finished |

---

# 18. Expense Claims (Phase 11)

> **Phase 11 endpoints.** These routes are implemented during Phase 11 (Expense Management) and are not available in earlier phases. The authoritative implementation contract — including the full request/response schemas, DB writes, and event emissions — is `19_Expense_Worker_Specification.md` §1. The schemas below are normative summaries; `19` §1 takes precedence on any detail not specified here.

## 18.1 Submit Expense Claim

```
POST /expense-claims
```

**Auth:** Required | **Permission:** `expenses:write`

Submit a new expense reimbursement claim. The claim is enqueued as `case_type = 'expense_claim'` on `accounts_queue` and processed by the Expense Worker.

**Request body:**

```json
{
  "category": "transport",
  "merchant": "Grab",
  "amount_value": "45.00",
  "amount_currency": "SGD",
  "receipt_date": "2026-05-10",
  "purpose": "Client meeting at Marina Bay — transport to/from venue",
  "attachment_ids": ["uuid-of-pre-uploaded-receipt"]
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `category` | string enum | Yes | `transport`, `meals`, `accommodation`, `office`, `entertainment` |
| `merchant` | string | Yes | max 200 chars |
| `amount_value` | string (Decimal) | Yes | > 0, max 2 decimal places |
| `amount_currency` | string (ISO 4217) | Yes | default `SGD` |
| `receipt_date` | date (ISO 8601) | Yes | not in future |
| `purpose` | string | Yes | min 10 chars, max 500 chars |
| `attachment_ids` | array of UUIDs | Yes | at least 1; each must reference a previously uploaded attachment |

**Idempotency:** Supports `Idempotency-Key` header (UUID). Repeated submissions with the same key return the original `201` response. Generate the key on form load, not on submit.

**Responses:**

| Status | Meaning |
|--------|---------|
| `201 Created` | Claim accepted; body contains `case_id`, `case_number`, `expense_claim_id` |
| `409 Conflict` | Duplicate claim detected (same claimant, merchant, date, amount as an existing claim); body includes `duplicate_case_number` |
| `422 Unprocessable Entity` | Validation failure; `error.details` array lists field-level errors |

**Response body (201):**

```json
{
  "data": {
    "expense_claim_id": "uuid",
    "case_id": "uuid",
    "case_number": "CAS-2026-0001542",
    "status": "processing",
    "created_at": "2026-05-15T09:00:00Z"
  }
}
```

## 18.2 List Expense Claims

```
GET /expense-claims
```

**Auth:** Required | **Permission:** `expenses:read`

Returns expense claims visible to the authenticated user. Finance Officers and Accounts Clerks see their own claims only (`claimant_id` automatically scoped to `auth.uid()`). Finance Managers with `expenses:read` on the team scope can pass `claimant_id=all` to view all claims.

**Query parameters:** Standard cursor pagination (`limit`, `cursor`), plus:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by claim status: `processing`, `pending_approval`, `approved`, `rejected`, `manual_review` |
| `category` | string | Filter by expense category |
| `from_date` | ISO 8601 date | Receipt date range start |
| `to_date` | ISO 8601 date | Receipt date range end |
| `claimant_id` | UUID or `me` | Default `me`; `all` requires elevated permission |

**Response:** Standard paginated envelope; each item contains `expense_claim_id`, `case_number`, `merchant`, `category`, `amount_value`, `amount_currency`, `receipt_date`, `status`, `risk_flags`, `created_at`.

## 18.3 Get Expense Claim

```
GET /expense-claims/{id}
```

**Auth:** Required | **Permission:** `expenses:read`; claimant or approver only (RLS enforced)

Returns full expense claim detail including line items, policy evaluation results, risk flags, and the linked case ID.

**Response body:**

```json
{
  "data": {
    "id": "uuid",
    "case_id": "uuid",
    "case_number": "CAS-2026-0001542",
    "claimant_user_id": "uuid",
    "category": "transport",
    "merchant": "Grab",
    "amount_value": "45.00",
    "amount_currency": "SGD",
    "receipt_date": "2026-05-10",
    "purpose": "Client meeting at Marina Bay",
    "status": "approved",
    "risk_flags": [],
    "policy_violations": [],
    "partial_extraction": false,
    "line_items": [],
    "created_at": "2026-05-15T09:00:00Z",
    "updated_at": "2026-05-15T09:05:00Z"
  }
}
```

## 18.4 Update Expense Claim Status

```
PATCH /expense-claims/{id}/status
```

**Auth:** Required | **Permission:** `expenses:write` (claimant may withdraw; approver may approve/reject via `/approvals` instead)

Allows a claimant to withdraw a pending claim before it reaches `pending_approval`. All other status transitions flow through the approvals workflow at `POST /approvals/{id}/approve` or `POST /approvals/{id}/reject`.

**Request body:**

```json
{
  "status": "withdrawn",
  "note": "Submitted in error — duplicate of CAS-2026-0001540"
}
```

| Allowed transition | Who |
|-------------------|-----|
| `processing` → `withdrawn` | Claimant only |
| `pending_approval` → `withdrawn` | Claimant only (before approver acts) |

---

# 19. Internal & Scheduled Jobs

Endpoints invoked by **infrastructure schedulers** (systemd timer, APScheduler, Kubernetes CronJob) — not by finance users. Mounted on the same FastAPI app as public routes (`11` §17.5).

## 19.1 Trigger finance daily activity log

```
POST /internal/jobs/finance-daily-log
```

**Description:** Compiles `finance_activity_log` rows for the current Singapore business day (`FINANCE_DAILY_LOG_TIMEZONE`, default `Asia/Singapore`), builds a **CSV export** per `06` §7.4.1 (`finance_daily_{business_date}.csv`), SMTP-sends template `finance.daily_log` (`18` §7.7) to `FINANCE_DAILY_LOG_RECIPIENT` (default `cfo.mmlogistix@bp0.work`) **with that CSV attached**, and **uploads the same file** to Wasabi `s3://{FINANCE_WASABI__BUCKET}/logs/finance_daily_{business_date}.csv` — bucket `bp0workacc` (`06` §7.5, `14` §2.9). Updates `system_settings.last_finance_log_sent_at` to prevent duplicate sends for the same calendar day (`17` §10.7).

**Authentication:** `Authorization: Bearer {FINANCE_INTERNAL_CRON__TOKEN}` — static service token, not a user JWT (`14` §2). Requests without this header receive **401**.

**Request body:** None (empty body) or optional JSON:

```json
{
  "business_date": "2026-05-19",
  "force": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `business_date` | date (ISO 8601) | No | Defaults to **today** in `FINANCE_DAILY_LOG_TIMEZONE` |
| `force` | boolean | No | Default `false`. If `true`, send even when `last_finance_log_sent_at` is already today (ops recovery only) |

**Idempotency:** **Required** behaviour without header — if digest for `business_date` was already sent and `force=false`, return **200** with `skipped: true` and do not send duplicate email. Optional `Idempotency-Key` header (§1.8) for scheduler retries.

**Response (200) — sent:**

```json
{
  "status": "sent",
  "business_date": "2026-05-19",
  "recipient": "cfo.mmlogistix@bp0.work",
  "row_count": 42,
  "smtp_message_id": "<msg-id@bp0.work>",
  "sent_at": "2026-05-19T13:00:05Z",
  "wasabi_log_path": "logs/finance_daily_2026-05-19.csv",
  "attachment_filename": "finance_daily_2026-05-19.csv"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `wasabi_log_path` | string | Object key within `FINANCE_WASABI__BUCKET` (`bp0workacc`) under prefix `logs/` — always `.csv` |
| `attachment_filename` | string | Filename used on the SMTP `Content-Disposition` attachment (same basename as Wasabi object) |

**Response (200) — skipped (idempotent):**

```json
{
  "status": "skipped",
  "business_date": "2026-05-19",
  "reason": "already_sent",
  "last_sent_at": "2026-05-19T13:00:02Z"
}
```

**Response (200) — no rows:**

```json
{
  "status": "sent",
  "business_date": "2026-05-19",
  "recipient": "cfo.mmlogistix@bp0.work",
  "row_count": 0,
  "message": "No finance activity for this date; empty digest sent."
}
```

| HTTP | `error.code` | When |
|------|--------------|------|
| 401 | `INVALID_CRON_TOKEN` | Missing or wrong bearer token |
| 503 | `SMTP_UNAVAILABLE` | Outbound mail dependency down after retries |

**Schedule:** Daily **21:00 Asia/Singapore** (`11` §17.5). Example invocation:

```bash
curl -sS -X POST \
  -H "Authorization: Bearer ${FINANCE_INTERNAL_CRON__TOKEN}" \
  -H "X-Request-ID: $(uuidgen)" \
  http://fastapi:8000/internal/jobs/finance-daily-log
```

> **Note:** Scheduled jobs call the **internal** Docker URL (`FINANCE_INTERNAL__API_BASE_URL`, default `http://fastapi:8000`). There is **no** public `api.bp0.work` hostname. Browser and manager email links use `https://finance.mmlogistix.bp0.work` with path-based forwarding to FastAPI (`14` §9.0). Paths match the `05` path table (no `/api/v1` prefix).

## 19.2 Trigger GL cutoff reminders

```
POST /internal/jobs/gl-cutoff-reminders
```

**Description:** For each active row in `gl_cutoff_reminders`, evaluates open `accounting_periods` whose `gl_cutoff_date` is exactly 7, 3, or 1 calendar days ahead, or **today**. Sends SMTP reminders from `acc.mmlogistix@bp0.work` to configured recipients. Writes `finance_activity_log` rows with `action = gl_cutoff_reminder_sent` (`06` §7.4, `15` §8.20).

**Authentication:** Same as §19.1 — `Authorization: Bearer {FINANCE_INTERNAL_CRON__TOKEN}`.

**Request body:** None, or optional `{ "force": false }` for ops recovery.

**Response (200):**

```json
{
  "status": "completed",
  "reminders_sent": 3,
  "periods_evaluated": 13
}
```

**Schedule:** Daily **08:00 Asia/Singapore** (`00:00 UTC`) — `11` §17.6.

```bash
curl -sS -X POST \
  -H "Authorization: Bearer ${FINANCE_INTERNAL_CRON__TOKEN}" \
  -H "X-Request-ID: $(uuidgen)" \
  http://fastapi:8000/api/internal/jobs/gl-cutoff-reminders
```

---

# Appendix A: Endpoint Summary

| Method | Endpoint | Auth Required | Permissions |
|--------|----------|---------------|-------------|
| POST | `/auth/login` | No | — |
| POST | `/auth/refresh` | No | — |
| POST | `/auth/logout` | Yes | — |
| POST | `/auth/2fa/setup` | Yes | — |
| POST | `/auth/2fa/verify` | Yes | — |
| POST | `/auth/2fa/disable` | Yes | — |
| GET | `/users` | Yes | `users:read` |
| GET | `/users/{id}` | Yes | `users:read` |
| POST | `/users` | Yes | `users:write` |
| PUT | `/users/{id}` | Yes | `users:write` |
| POST | `/users/{id}/lock` | Yes | `users:admin` |
| POST | `/users/{id}/unlock` | Yes | `users:admin` |
| POST | `/users/{id}/change-password` | Yes | Own account |
| POST | `/users/{id}/reset-password` | Yes | `users:admin` |
| GET | `/roles` | Yes | `users:read` |
| POST | `/roles` | Yes | `users:admin` |
| PUT | `/roles/{id}` | Yes | `users:admin` |
| DELETE | `/roles/{id}` | Yes | `users:admin` |
| GET | `/permissions` | Yes | `users:read` |
| GET | `/users/me/notification-preferences` | Yes | Own account |
| PUT | `/users/me/notification-preferences` | Yes | Own account |
| GET | `/notification-templates` | Yes | Authenticated |
| PATCH | `/admin/notification-templates/{template_id}` | Yes | `settings:write` |
| GET | `/platform/tenants` | Yes | `platform:admin` |
| PATCH | `/platform/tenants/{tenant_id}/client-admin` | Yes | `platform:admin`, `users:admin` |
| GET | `/tenant/profile` | Yes | `tenant:admin` |
| PUT | `/tenant/profile` | Yes | `tenant:admin` |
| POST | `/tenant/profile/logo` | Yes | `tenant:admin` |
| PUT | `/tenant/profile/email-signature` | Yes | `tenant:admin` |
| POST | `/tenant/profile/expense-policy-document` | Yes | `tenant:admin` |
| DELETE | `/tenant/profile/expense-policy-document` | Yes | `tenant:admin` |
| GET | `/tenant/expense-policy-document/url` | Yes | `tenant:admin`, `expenses:read` |
| GET | `/tenant/expense-policies` | Yes | `tenant:admin`, `expenses:read` |
| GET | `/tenant/expense-policies/{policy_id}` | Yes | `tenant:admin`, `expenses:read` |
| PUT | `/tenant/expense-policies/{policy_id}` | Yes | `tenant:admin` |
| GET | `/coa` | Yes | `client_admin` / `tenant:admin` (`0.14.7` shipped) |
| GET | `/coa/status` | Yes | `client_admin` / `tenant:admin` |
| POST | `/coa` | Yes | `client_admin` / `tenant:admin` |
| PATCH | `/coa/{account_id}` | Yes | `client_admin` / `tenant:admin` |
| POST | `/coa/import` | Yes | `client_admin` / `tenant:admin`; query `replace_all` |
| GET | `/counterparties` | Yes | `client_admin` (`0.14.8` shipped) |
| POST | `/counterparties` | Yes | `client_admin` |
| PATCH | `/counterparties/{counterparty_id}` | Yes | `client_admin` |
| GET | `/counterparty-accounts` | Yes | `client_admin` |
| POST | `/counterparty-accounts` | Yes | `client_admin` |
| PATCH | `/counterparty-accounts/{account_id}` | Yes | `client_admin` |
| GET | `/payment-terms` | Yes | `client_admin` |
| POST | `/payment-terms` | Yes | `client_admin` |
| PATCH | `/payment-terms/{term_id}` | Yes | `client_admin` |
| GET | `/tenant/tax-codes` | Yes | `client_admin` |
| POST | `/tenant/tax-codes` | Yes | `client_admin` |
| PATCH | `/tenant/tax-codes/{id}` | Yes | `client_admin` |
| GET | `/notifications` | Yes | Own account |
| POST | `/notifications/read` | Yes | Own account |
| GET | `/cases` | Yes | `cases:read` |
| GET | `/cases/{id}` | Yes | `cases:read` |
| POST | `/cases` | Yes | `cases:write` |
| PUT | `/cases/{id}` | Yes | `cases:write` |
| POST | `/cases/{id}/status` | Yes | `cases:write` |
| POST | `/cases/{id}/merge` | Yes | `cases:write` |
| POST | `/cases/{id}/split` | Yes | `cases:write` |
| GET | `/cases/{id}/timeline` | Yes | `cases:read` |
| POST | `/cases/{id}/notes` | Yes | `cases:write` |
| GET | `/cases/{id}/notes` | Yes | `cases:read` |
| GET | `/cases/statistics` | Yes | `cases:read` |
| GET | `/workflow/active` | Yes | `cases:read` |
| GET | `/workflow/{id}` | Yes | `cases:read` |
| POST | `/workflow/{id}/retry` | Yes | `queues:admin` |
| POST | `/workflow/{id}/cancel` | Yes | `queues:admin` |
| GET | `/workflow/definitions` | Yes | `cases:read` |
| GET | `/workflow/sla-summary` | Yes | `cases:read` |
| GET | `/approvals` | Yes | `approvals:read` |
| GET | `/approvals/{id}` | Yes | `approvals:read` |
| POST | `/approvals/{id}/approve` | Yes | `approvals:approve` |
| POST | `/approvals/{id}/reject` | Yes | `approvals:approve` |
| POST | `/approvals/{id}/delegate` | Yes | `approvals:approve` |
| POST | `/approvals/{id}/override` | Yes | `approvals:admin` |
| POST | `/approvals/{id}/escalate` | Yes | `approvals:admin` |
| GET | `/approvals/configuration` | Yes | `approvals:read` |
| PUT | `/approvals/configuration` | Yes | `approvals:admin` |
| GET | `/approvals/statistics` | Yes | `approvals:read` |
| GET | `/mail` | Yes | `mail:read` |
| GET | `/mail/{id}` | Yes | `mail:read` |
| GET | `/mail/{id}/attachments/{aid}` | Yes | `mail:read` |
| POST | `/mail/{id}/reprocess` | Yes | `mail:admin` |
| GET | `/mail/status` | Yes | `mail:read` |
| GET | `/mail/configuration` | Yes | `mail:admin` |
| PUT | `/mail/configuration` | Yes | `mail:admin` |
| PATCH | `/mail/configuration/mailboxes/{id}` | Yes | `mail:admin` |
| GET | `/mail/{id}/duplicates` | Yes | `mail:read` |
| GET | `/mail/escalations/{escalation_id}/respond` | No | Signed token (`17` §10.4) |
| POST | `/mail/escalations/{escalation_id}/respond` | No | Signed token (`17` §10.4); form body `comment` |
| GET | `/mail/outbound/{pending_id}/respond` | No | Signed token (`17` §10.5.5) |
| POST | `/mail/outbound/{pending_id}/respond` | No | Signed token (`17` §10.5.5); form body `comment`, `rejection_reason_code` |
| GET | `/queues` | Yes | `queues:read` |
| GET | `/queues/{name}/messages` | Yes | `queues:read` |
| POST | `/queues/{name}/messages/{id}/retry` | Yes | `queues:admin` |
| POST | `/queues/{name}/purge` | Yes | `queues:admin` |
| POST | `/queues/{name}/messages/{id}/move` | Yes | `queues:admin` |
| GET | `/policies` | Yes | `policies:read` |
| GET | `/policies/{id}` | Yes | `policies:read` |
| POST | `/policies` | Yes | `policies:write` |
| PUT | `/policies/{id}` | Yes | `policies:write` |
| POST | `/policies/{id}/deactivate` | Yes | `policies:write` |
| POST | `/policies/validate` | Yes | `policies:read` |
| GET | `/policies/categories` | Yes | `policies:read` |
| GET | `/chart-of-accounts` | Yes | `journal-entries:read` |
| GET | `/chart-of-accounts/{id}` | Yes | `journal-entries:read` |
| POST | `/chart-of-accounts/import` | Yes | `coa:import` |
| POST | `/chart-of-accounts` | Yes | `journal-entries:write` |
| PUT | `/chart-of-accounts/{id}` | Yes | `journal-entries:write` |
| POST | `/chart-of-accounts/{id}/deactivate` | Yes | `journal-entries:write` |
| GET | `/journal-entries` | Yes | `journal-entries:read` |
| GET | `/journal-entries/{id}` | Yes | `journal-entries:read` |
| POST | `/journal-entries` | Yes | `journal-entries:write` |
| PUT | `/journal-entries/{id}` | Yes | `journal-entries:write` |
| POST | `/journal-entries/{id}/post` | Yes | `journal-entries:write` |
| POST | `/journal-entries/{id}/reverse` | Yes | `journal-entries:write` |
| GET | `/journal-entries/{id}/attachments` | Yes | `journal-entries:read` |
| GET | `/reconciliation` | Yes | `reconciliation:read` |
| GET | `/reconciliation/{id}` | Yes | `reconciliation:read` |
| POST | `/reconciliation/start` | Yes | `reconciliation:write` |
| GET | `/reconciliation/{id}/unmatched` | Yes | `reconciliation:read` |
| POST | `/reconciliation/{id}/match` | Yes | `reconciliation:write` |
| POST | `/reconciliation/{id}/unmatch` | Yes | `reconciliation:write` |
| GET | `/reconciliation/summary` | Yes | `reconciliation:read` |
| GET | `/audit-logs` | Yes | `audit-logs:read` |
| GET | `/audit-logs/{id}` | Yes | `audit-logs:read` |
| POST | `/audit-logs/export` | Yes | `audit-logs:read` |
| GET | `/audit-logs/integrity-check` | Yes | `audit-logs:read` |
| GET | `/dashboard/summary` | Yes | `cases:read` |
| GET | `/dashboard/metrics/processing` | Yes | `cases:read` |
| GET | `/dashboard/workers` | Yes | `queues:read` |
| GET | `/health` | No | — |
| GET | `/ready` | No | — |
| GET | `/events/stream` | Yes | `cases:read` (role-filtered channels — see `09_Event_Model_Specification.md` §15.4) |
| GET | `/events/dead-letter` | Yes | `queues:admin` |
| POST | `/events/dead-letter/{id}/retry` | Yes | `queues:admin` |
| DELETE | `/events/dead-letter/{id}` | Yes | `queues:admin` |
| POST | `/expense-claims` | Yes | `expenses:write` (Phase 11) |
| GET | `/expense-claims` | Yes | `expenses:read` (Phase 11) |
| GET | `/expense-claims/{id}` | Yes | `expenses:read` (Phase 11) |
| PATCH | `/expense-claims/{id}/status` | Yes | `expenses:write` (Phase 11) |
| POST | `/internal/jobs/finance-daily-log` | Yes | `FINANCE_INTERNAL_CRON__TOKEN` (scheduler only) |
| **—** | **Total: 144 shipped operations** | **—** | **—** |

> **Counting rules (v1.3.20):** **144 shipped** = prior **132** operations + **12** Client Admin counterparty routes (`§4.16d.4`, `0.14.8`). All rows are in `21_openapi.yaml` v1.0.14 and schemathesis contract CI (`20` §4.3, `scripts/validate_openapi_yaml.py`). Finance UI continues to use `/chart-of-accounts` (legacy paths in this table); Client Admin uses `/coa` under `/api` prefix at runtime (`14` §9.0).

> **Maintenance note (OBS-4):** When adding API operations in future phases, update **four** locations together: (1) the Appendix A table and this footer count (one row per HTTP method), (2) `00_Project_Overview.md` §4.1 document map operation count, (3) `02_Technical_Architecture.md` §12 API surface summary, and (4) `21_openapi.yaml` (contract/schemathesis CI — **shipped operations only**). Failure to update all four simultaneously causes count drift that is hard to detect later.

---

# Appendix B: Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.3.24 | 2026-05-26 | **`0.14.9-binding-authority`.** §4.16d.14 `GET/PATCH /admin/binding-authority`; approvals `binding_queue` filter; case fields `pending_approval_id`, `binding_escalated_to_cfo`. Renumber GL override → §4.16d.15. `10` §7, `15` v2.31. |
| 1.3.23 | 2026-05-20 | **Finance setup API access.** §4.16d.4/9/11–13: `require_finance_setup_access`; UI on finance.mmlogistix (`e73c869`). Renumber §4.16d.9 agreements (was duplicate §4.16d.8). `15` v2.30. |
| 1.3.22 | 2026-05-20 | **§4.16d.4 subaccount PATCH in UI.** Client Admin inline edit for `payment_term_id` + credit fields; payment-terms catalog PATCH note. `15` §8.22 v2.29 (`9b0662e`). |
| 1.3.21 | 2026-05-20 | **§4.16d.4 credit limit placement.** Document `credit_limit_*` on subaccount only; payment-terms catalog = due days. Cross-ref `15` §8.22 v2.28. |
| 1.3.20 | 2026-05-20 | **`0.14.8` shipped.** Appendix A: 12 counterparty/payment-terms/tax-code rows moved from planned → shipped; footer **144** operations. `21_openapi` v1.0.14; `validate_openapi_yaml.py` locks count + version. Git `b1095c1`–`9350495`. |
| 1.3.19 | 2026-05-20 | **Appendix A COA + planned `0.14.8`.** +5 shipped `/coa/*` rows; +12 planned counterparty/payment-terms/tax-code rows; footer **132 shipped + 12 planned**. `21_openapi` adds shipped COA only until implementation. Cross-ref `04` §17, `12` UAT-012–015. |
| 1.3.11 | 2026-05-19 | **`POST /internal/jobs/finance-daily-log` — CSV export.** Job compiles `finance_activity_log` to RFC 4180 CSV (`06` §7.4.1); emails `finance.daily_log` with `finance_daily_{business_date}.csv` attached; uploads same object to Wasabi `logs/`; response adds `attachment_filename`; `wasabi_log_path` ends in `.csv`. Supersedes JSON/HTML Wasabi digest. Cross-ref `17` §10.7, `18` §7.7, `14` §2.7. |
| 1.3.10 | 2026-05-19 | **§19 finance-daily-log.** Writes digest JSON to Wasabi `bp0workacc/logs/`; response `wasabi_log_path`. Cross-ref `06` §7.5. |
| 1.3.9 | 2026-05-19 | **API contract depth.** §8.8a: full token format, idempotency, per-action semantics (`escalate` child row, same case), JSON/HTML responses, error codes. §19: `POST /internal/jobs/finance-daily-log` (scheduler token, idempotent digest). §16.3 mail + internal error codes. Appendix A **127** operations. Cross-ref `07` §13, `11` §17.5. |
| 1.3.8 | 2026-05-19 | **Appendix A + OpenAPI parity.** Footer corrected to **126** operations (row total). Added `POST` rows for mail SOP respond paths (form POST with comment). §1.10: `21_openapi.yaml` must match Appendix A for contract CI. OBS-4: fourth sync target `21_openapi.yaml`. Aligned with `21_openapi.yaml` v1.0.10 (platform/tenant, events, COA import; Admin UI paths removed). |
| 1.3.7 | 2026-05-19 | **Appendix A sync.** Added `/mail/escalations/{escalation_id}/respond` and `/mail/outbound/{pending_id}/respond` GET rows; footer stated **117** (superseded by v1.3.8 recount **126**). |
| 1.3.6 | 2026-05-19 | **§8.8b pending client outbound.** Manager Approve/Reject for clarification queue (`pending_outbound_emails`); reject reason codes for attachment/body re-parse (`17` §10.5.5). |
| 1.3.5 | 2026-05-19 | **§8.8a response codes.** Replaced erroneous 409 mailbox-conflict copy with escalation-specific 200/400/404/422; cross-ref `case_escalations` (`06` §7.5). |
| 1.3.4 | 2026-05-19 | **Organizational hierarchy — escalation API.** §8.8a: added `action=escalate` (Manager Accounts/Finance → CFO; CFO → CEO). Example `escalation_manager_email` → `acc.mmlogistix`. Cross-ref `01` §3.2.3, `17` §10.4. |
| 1.3.3 | 2026-05-19 | **Executive email SOP APIs.** §8.8: `requires_outbound_client_approval` on mailbox PATCH; response includes `mailbox_mode`, `escalation_manager_email`. §8.8a: manager escalation Approve/Reject via signed URL. Cross-ref `17` §10, `01` §6.8. |
| 1.3.18 | 2026-05-20 | **Counterparty accounts (`0.14.8`, planned).** §4.16d.4: subaccounts, payment terms, tenant tax codes; renumbered §4.16d.5–§4.16d.14. Cross-ref `06` §4.1a–c, `15` §8.22, `17` §3.2.1–§3.2.3. |
| 1.3.17 | 2026-05-20 | **Tenant COA import (`0.14.7-coa-tenant-import`).** §4.16d.3: `GET /api/coa?q=`, upsert import `replace_all`, `CoaImportResponse`; migration `054` removes demo seed. §11.3 aligned to shipped API. Cross-ref `06` §10.1, `15` §8.10, `11` §4.5h. |
| 1.3.16 | 2026-05-20 | **Email signatures (`0.14.6`).** §4.16b.4: outbound footer wired via `OutboundMailService` + `mail_template_renderer`. Cross-ref `18` §10.2, `15` §8.17, `11` §4.5g. |
| 1.3.15 | 2026-05-20 | **GL period reopen (`0.14.5`).** §4.16d.12: `POST .../reopen` (CFO / Client Admin); `gl_period_reopened` activity log. §5.8a: retry `on_hold` + `PERIOD_CLOSED` when period reopened; `GET /cases/{id}` `linked_gl_period_status`. Cross-ref `15` §8.20–§8.21, `11` §4.5g. |
| 1.3.14 | 2026-05-25 | **Client Admin + GL calendar (`0.14.4`).** §4.16d: shipped `/api/admin/*`, COA, mail, users, policies, regulatory docs, agreements, accounting settings, periods, override-post. §19.2: `POST /internal/jobs/gl-cutoff-reminders`. Cross-ref `06` §13.2c, `15` §8.20–§8.21, `11` §4.5g. |
| 1.3.13 | 2026-05-20 | **Case retry.** §5.8a: `POST /cases/{id}/retry` for `exception`/`manual_review`; requeues to `accounts_queue`. Deploy `0.13.3-case-retry-hermes-timeout`. |
| 1.3.12 | 2026-05-20 | **URL structure.** §2: no public API host; internal `http://fastapi:8000`; edge paths on `https://finance.mmlogistix.bp0.work`. Removed `api.bp0.work`. §19.1 cron uses internal URL. |
| 1.3.2 | 2026-05-19 | **Production base URL.** §1 overview table: Base URL `https://api.bp0.work` (superseded by v1.3.12 — no public API host). |
| 1.3.1 | 2026-05-19 | **Client Admin: travel & expense policy.** §4.16b.5: upload/delete optional expense policy PDF on `tenant_profiles`. §4.16c: `GET`/`PUT /tenant/expense-policies` (numeric rules in `expense_policies`, `19` §3.3). Signed URL for document download. Appendix A +7 endpoints (115 total). See `15` §8.18, `13` §5.9, `19` §3.4. |
| 1.3.0 | 2026-05-19 | **Two-tier administration APIs.** §4.16a Platform Admin API: `GET /platform/tenants` (dynamic tenant + Client Admin email list), `PATCH /platform/tenants/{tenant_id}/client-admin` (email update only). §4.16b Client Admin API: `GET`/`PUT /tenant/profile` (company legal details for SOA), `POST /tenant/profile/logo`, `PUT /tenant/profile/email-signature`. §11.3 `POST /chart-of-accounts/import` (`coa:import`). Mail endpoints accept `tenant:admin`. §4.7 password reset scoped to Platform Admin for `client_admin` users. Appendix A updated with platform and tenant profile routes. See `13` §5.9, `15` §8.11–8.16. |
| 1.0.9 | 2026-05-19 | Added §9a Events & SSE — prose endpoint specification for `GET /events/stream`, `GET /events/dead-letter`, `POST /events/dead-letter/{id}/retry`, and `DELETE /events/dead-letter/{id}`. These four endpoints were present in Appendix A since v1.0.2 (sourced from `09_Event_Model_Specification.md` §15–§16) but had no body section, leaving Cursor without HTTP contract detail. Added §9a to Table of Contents. No new endpoints added; Appendix A count remains 108. Aligned with `21_openapi.yaml` v1.0.9 which adds the same four endpoints and removes nine prototype/Admin UI paths that had no spec basis (`/`, `/login`, `/login/request-code`, `/login/verify`, `/logout`, `/settings`, `POST /chart-of-accounts/upload`, `GET /chart-of-accounts/download`, `POST /journal-entries/{id}/deactivate`). |
| 1.0.8 | 2026-05-18 | Fix (OBS-4 from cross-document audit): Added maintenance reminder callout below the Appendix A `Total: 108 endpoints` footer row. The note specifies the three locations that must be updated together when endpoints are added: (1) Appendix A table and footer count, (2) `00_Project_Overview.md` §4.1 document map, (3) `02_Technical_Architecture.md` §12 API surface summary. Omitting any of the three causes silent count drift. The current count of 108 is confirmed correct and includes all four Phase 11 expense endpoints. Fix (OBS-5 from cross-document audit): Confirmed all `b`/`c`-suffix migration files (`006b`, `026b`, `026c`, `035b`, `039b`) are fully documented in `16` §10, `06` §18.4, and `19` §11 with no gaps or orphans. No content changes required — acknowledged here for audit traceability. |
| 1.0.7 | 2026-05-17 | Fix (Issue 2 from cross-document audit): Changed all four expense claim endpoint permissions from generic `cases:*` to dedicated `expenses:*` permission codes — `POST /expense-claims` and `PATCH /expense-claims/{id}/status` now require `expenses:write`; `GET /expense-claims` and `GET /expense-claims/{id}` now require `expenses:read`. Updated §18.1–18.4 endpoint headers and Appendix A rows. Aligns with `13_Security_and_Compliance_Specification.md` §5.6 RBAC table and `19_Expense_Worker_Specification.md` §3.4 permission table. Also corrected `GET /expense-claims` description which referenced `cases:read` scope in the body text. |
| 1.0.6 | 2026-05-17 | Fix (M-2 from cross-document audit): Added explicit **Total: 108 endpoints** footer row to Appendix A. Previously the authoritative count existed only in the v1.0.5 changelog text, meaning future additions could go undetected if `00` §4.1 and `02` §12 cross-references were not updated simultaneously. The footer row makes count drift immediately visible. |
| 1.0.5 | 2026-05-15 | Fix (INC-2 from audit): Corrected Appendix A endpoint count. Actual count of rows in Appendix A is 108 (not 104 as previously stated). The discrepancy arose from the v1.0.2 count being stated as 104 when the prior base was 100 (not 100 after adding 4 = 104, but subsequent additions brought the total to 108). Updated v1.0.2 changelog note to remove the stale "104" claim. The authoritative count is the number of rows in Appendix A itself. |
| 1.0.4 | 2026-05-15 | Fix (Audit GAPs 2 & 4): Added `ar_soa_request` and `expense_claim` to §5.3 Case Types table. `ar_soa_request` was added to `17_Worker_Specifications.md` §2.3 routing table in v1.5 of that document but had not been back-propagated to the canonical case types table here. `expense_claim` is the Phase 11 case type defined in `19_Expense_Worker_Specification.md` §2 and consumed from `accounts_queue` by the Expense Worker. |
| 1.0.3 | 2026-05-15 | Fix (Issue 4 from audit): Added §18 Expense Claims (Phase 11) — four endpoints (`POST /expense-claims`, `GET /expense-claims`, `GET /expense-claims/{id}`, `PATCH /expense-claims/{id}/status`) with full request/response schemas, validation rules, idempotency note, and status-transition table. Added all four to Appendix A. Added §18 to Table of Contents. Authoritative implementation contract remains `19_Expense_Worker_Specification.md` §1. |
| 1.0.2 | 2026-05-14 | Added SSE endpoint (`GET /events/stream`) and three dead-letter event endpoints (`GET /events/dead-letter`, `POST /events/dead-letter/{id}/retry`, `DELETE /events/dead-letter/{id}`) to Appendix A. These were specified in `09_Event_Model_Specification.md` §14–15 but omitted from the endpoint summary. Updated headline endpoint count from 93 to 100. |
| 1.0.1 | 2026-05-13 | Added §4.17 (GET /notifications) and §4.18 (POST /notifications/read) — notification inbox endpoints referenced by `06_Database_Schema_Design.md` §3.8 and `18_Notification_Service_Specification.md`. Added missing notification endpoints to Appendix A. |
| 1.0.0 | 2026-05-11 | Initial release — full endpoint specification covering all Phase 1 (MVP) functional areas |

---

# Appendix C: Implementation Notes for Cursor

1. **Use FastAPI dependency injection** for authentication and permission checks. Create reusable `require_permission()` dependencies.

2. **Consistent request/response models** — Define Pydantic models for all request bodies and responses. Keep schemas in a dedicated `app/schemas/` module.

3. **Service layer pattern** — All API routes should be thin. Business logic belongs in `app/services/`. Routes call services, services use repositories.

4. **Repository pattern** — Database access goes through repository classes in `app/repositories/`. Never use raw SQL in routes or services.

5. **Audit logging** — Use a middleware or dependency to automatically log all state-changing operations to the audit log table. Compute tamper hashes sequentially.

6. **Error handling** — Use FastAPI exception handlers to convert domain exceptions into the standard error envelope format.

7. **Idempotency** — Implement idempotency key checking in a middleware or dependency. Cache responses in Redis with TTL 86400.

8. **Pagination** — Implement cursor pagination as a reusable utility. Use base64-encoded cursors containing the last seen sort value.

9. **Rate limiting** — Use Redis-backed rate limiting. Different limits for different permission levels.

10. **Transaction boundaries** — Case status changes, approval responses, and journal postings must be atomic. Use database transactions that span the service operation and audit log insertion.

11. **OpenAPI contract first** — At the start of Phase 2, generate `openapi.yaml` from this specification and commit it before implementing routes. Use it as the source of truth for contract tests and ensure FastAPI route behavior, Pydantic schemas, and documented examples remain aligned with it.
