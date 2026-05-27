# AI Finance Operations Platform

# Deployment & Operations Runbook

## Version 2.53

## Filename: 11_Deployment_Operations_Runbook.md

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

> **Documentation vs deployment:** This runbook targets the **`bp0work/accounting`** monorepo (clone `/opt/bp0work/accounting`; run `docker compose` from **`accfin/`**), not the `platform_dox/` specification folder. UI apps live in `finance-ui/`, `platform-admin-ui/`, `client-admin-ui/` at the monorepo root (`README.md`, `00` §2.6).

# Table of Contents

1. [Infrastructure Overview](#1-infrastructure-overview)
2. [Prerequisites](#2-prerequisites)
3. [Initial Deployment](#3-initial-deployment)
4. [Docker Compose Stack](#4-docker-compose-stack)
5. [Traefik Configuration](#5-traefik-configuration)
6. [Supabase Configuration](#6-supabase-configuration)
7. [Redis Configuration](#7-redis-configuration)
8. [Ollama Configuration](#8-ollama-configuration)
9. [Application Deployment](#9-application-deployment)
10. [SSL/TLS Certificates](#10-ssltls-certificates)
11. [Environment Configuration](#11-environment-configuration)
12. [Database Migrations](#12-database-migrations)
13. [CI/CD Pipeline](#13-cicd-pipeline)
14. [Monitoring & Alerting](#14-monitoring--alerting)
15. [Backup & Recovery](#15-backup--recovery)
16. [Disaster Recovery](#16-disaster-recovery)
17. [Operational Procedures](#17-operational-procedures)
18. [Security Hardening](#18-security-hardening)
19. [Troubleshooting Guide](#19-troubleshooting-guide)
20. [Appendix: Complete docker-compose.yml](#20-appendix-complete-docker-composeyml)

---

# 1. Infrastructure Overview

## 1.1 Architecture Diagram

```
                              Internet
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     Cloudflare DNS      │
                    │ (finance.mmlogistix.bp0.work, │
                    │  admin.* — see §5 / `14` §9.0) │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │    Traefik (reverse     │
                    │    proxy, SSL, WAF)     │
                    │    Port: 80, 443        │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
    ┌─────────▼────────┐ ┌──────▼──────┐ ┌───────▼───────┐
    │   FastAPI App    │ │  Supabase   │ │   Ollama      │
    │   (API Gateway)  │ │  (PostgreSQL│ │   (AI Model   │
    │   Port: 8000     │ │   + Auth)   │ │   Server)     │
    └─────────┬────────┘ │  Port: 5432 │ │  Port: 11434  │
              │          └─────────────┘ └───────────────┘
              │
    ┌─────────▼────────┐
    │   Redis          │
    │  (Queue + Cache) │
    │   Port: 6379     │
    └──────────────────┘
```

## 1.2 Host Specifications

| Component | Specification |
|-----------|--------------|
| **Cloud Provider** | Hostinger VPS (or equivalent) |
| **OS** | Ubuntu 24.04 LTS |
| **vCPU** | 8 cores minimum (4 for app, 2 for Ollama, 2 for system) |
| **RAM** | 32 GB minimum (16 for Ollama, 8 for app/db, 8 for system/cache) |
| **Storage** | 200 GB SSD minimum (100 for database, 50 for attachments, 50 for system) |
| **Network** | 1 Gbps, Singapore data center |

## 1.3 Port Allocation

| Port | Service | Purpose | External Access |
|------|---------|---------|-----------------|
| 80 | Traefik | HTTP redirect to HTTPS | Yes |
| 443 | Traefik | HTTPS API endpoint | Yes |
| 5432 | PostgreSQL | Database (via Supabase) | No (internal only) |
| 6379 | Redis | Cache + queue | No (internal only) |
| 8000 | FastAPI | Application API | No (Traefik only) |
| 8001 | Hermes | AI orchestration layer | No (internal only) |
| 8002 | Mail Gateway | IMAP polling, intake queue push | No (internal only) |
| 8003 | Orchestrator | Workflow routing, SLA tracking, queue dispatch | No (internal only) |
| 11434 | Ollama | AI model inference | No (internal only) |
| 8080 | Traefik | Dashboard (admin only) | Restricted by IP |
| 9090 | Prometheus | Metrics collection | No (internal only) |

---

# 2. Prerequisites

## 2.1 Host Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    docker.io \
    docker-compose-plugin \
    git \
    curl \
    wget \
    vim \
    htop \
    fail2ban \
    ufw \
    certbot \
    jq \
    postgresql-client \
    redis-tools

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Enable Docker on boot
sudo systemctl enable docker
sudo systemctl start docker

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable

# Configure fail2ban
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

## 2.2 Directory Structure

```bash
sudo mkdir -p /opt/mmlogistix/{app,traefik,supabase,redis,ollama,backups,logs}
sudo mkdir -p /opt/mmlogistix/traefik/{certs,dynamic-config}
sudo mkdir -p /opt/mmlogistix/backups/{database,attachments}
sudo mkdir -p /opt/mmlogistix/ollama/models
sudo chown -R $USER:$USER /opt/mmlogistix
```

---

# 3. Initial Deployment

## 3.1 Deployment Checklist

| Step | Task | Document Reference |
|------|------|-------------------|
| 1 | Provision VPS and configure OS | Section 2 |
| 2 | Install Docker and prerequisites | Section 2 |
| 3 | Clone application repository | Cursor Development Brief |
| 4 | Create directory structure | Section 2.2 |
| 5 | Configure environment variables | Section 11 |
| 6 | Deploy Traefik | Section 5 |
| 7 | Deploy Supabase | Section 6 |
| 8 | Deploy Redis | Section 7 |
| 9 | Deploy Ollama + pull models | Section 8 |
| 10 | Run database migrations | Section 12 |
| 11 | Deploy FastAPI application | Section 9 |
| 12 | Configure SSL certificates | Section 10 |
| 13 | Verify health endpoints | Section 14 |
| 14 | Seed initial data (roles, policies) | Database Schema Section 18 |
| 15 | Configure monitoring | Section 14 |

## 3.2 Deployment Order

Infrastructure must be deployed in this order:

```
1. Traefik (reverse proxy must be up first)
2. Supabase (database — all services depend on it)
3. Redis (queue + cache)
4. Ollama (AI models)
5. FastAPI Application
6. Verify + Monitoring
```

---

# 4. Docker Compose Stack

## 4.1 Stack Philosophy

- **Single-host deployment** using Docker Compose
- **Internal networking** — only Traefik exposes ports to the internet
- **Named volumes** for persistent data
- **Read-only containers** where possible
- **Resource limits** on all containers to prevent runaway consumption

## 4.2 Network Configuration

```yaml
# docker-compose.yml networks section
networks:
  frontend:
    driver: bridge
    internal: false
  backend:
    driver: bridge
    internal: true
  database:
    driver: bridge
    internal: true
```

| Network | Purpose | Connected Services |
|---------|---------|-------------------|
| `frontend` | External traffic | Traefik |
| `backend` | Service-to-service | FastAPI, Redis, Ollama, Supabase Kong |
| `database` | Database access | Supabase PostgreSQL, Supabase services |

## 4.3 Resource Limits

| Service | CPU Limit | Memory Limit | Swap |
|---------|-----------|-------------|------|
| Traefik | 1.0 | 256 MB | 0 |
| FastAPI | 2.0 | 4 GB | 512 MB |
| Supabase DB | 2.0 | 8 GB | 1 GB |
| Supabase services | 1.0 | 2 GB | 512 MB |
| Redis | 1.0 | 1 GB | 0 |
| Ollama | 4.0 | 16 GB | 0 |
| Hermes | 1.0 | 1 GB | 0 |
| Mail Gateway | 1.0 | 512 MB | 0 |
| Orchestrator | 1.0 | 512 MB | 0 |
| Worker — Accounts | 1.0 | 1 GB | 0 |
| Worker — AR | 1.0 | 1 GB | 0 |
| Worker — AP | 1.0 | 1 GB | 0 |
| Worker — Treasury | 1.0 | 1 GB | 0 |
| Worker — Expense *(Phase 11)* | 1.0 | 1 GB | 0 |

> **Phase 11 pre-production gate (OBS-3):** Before the Expense Worker is promoted to production, confirm all three of the following: (a) the `worker-expense` stub in Appendix 20 is replaced with the full `workers/expense/Dockerfile`-based build per `19_Expense_Worker_Specification.md`; (b) `depends_on:` includes both `hermes` and `redis` with `condition: service_healthy`; (c) the resource limits row above is updated if actual load testing reveals different requirements. See `19` §1 for the MVP scope declaration and Phase 1 acceptance criteria.

## 4.4 Health Checks

Every container must define a health check:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

## 4.5 Mail Gateway (`gateway`) — compose-only poll flag

Inbound IMAP polling is controlled by `FINANCE_MAIL__POLL_ENABLED`. In production this variable is set **directly in `accfin/docker-compose.yml`** on the `gateway` service — **not** in `.env`:

```yaml
  gateway:
    env_file:
      - .env
    environment:
      FINANCE_MAIL__POLL_ENABLED: "true"   # required in production
      FINANCE_MAIL__ATTACHMENT_STORAGE_PATH: /data/attachments
```

**Must be `"true"` on VPS** so the Mail Gateway starts its polling loop for `executive_agent` mailboxes (`14` §2.5, §7.3). If polling is disabled, no mail is enqueued to `intake_queue`. Do not move this flag into `.env`; operators change it only via compose when intentionally stopping poll (e.g. local debugging).

**IMAP poller implementation (`gateway/imap/poller.py`, deploy `0.12.6-gateway-imap-poller`):** All database access uses `async with session_factory() as session` — one session per mailbox poll plus a short session to list pollable IDs. Blocking IMAP runs in `asyncio.to_thread` with a plain `MailboxImapSettings` dataclass (decrypted credentials read in the async greenlet first). Never pass SQLAlchemy ORM instances into worker threads (avoids `sqlalchemy.exc.MissingGreenlet`).

**Intake enqueue (`0.13.18-gateway-intake-enqueue-logging`):** Ingest persists email as `parsed`; poller calls `_enqueue_intake_for_email()` separately. Confirm gateway logs `Enqueued email … to intake_queue` after each message. If Redis push fails, search logs for `Failed to enqueue email` and requeue with `email_id` via `enqueue_intake()`. Stuck emails: `status=parsed` + `processing_metadata.intake_enqueue_failed=true`.

After pull: `docker compose build gateway && docker compose up -d gateway` and confirm logs show `Polled <mailbox>` and `Enqueued email` without ORM errors.

## 4.5b Shared attachment volume — domain workers (`0.13.13` / `0.13.19`)

Gateway and FastAPI write/read inbound attachments on Docker volume `attachment-data` mounted at `/data/attachments`. **Workers that read files for Wasabi archive, ack re-attach, or manager escalation re-attach must use the same mount:** `accounts-worker` (`0.13.13`), `ap-worker`, `ar-worker`, `expense-worker` (`0.13.19`).

```yaml
  ap-worker:   # same pattern for ar-worker, expense-worker, accounts-worker
    environment:
      FINANCE_MAIL__ATTACHMENT_STORAGE_PATH: /data/attachments
    volumes:
      - attachment-data:/data/attachments
```

After pull: `docker compose up -d accounts-worker ap-worker ar-worker expense-worker` (no image rebuild required). Verify:

```bash
docker exec ap-worker ls /data/attachments/
docker exec accounts-worker ls /data/attachments/
```

If logs show `Attachment file missing for Wasabi archive` or `outbound reattach` while DB rows exist, the worker container is missing this volume.

## 4.5c AP missing-fields manager escalation (`0.13.15-ap-missing-fields-escalation`)

When AP extraction routes a case to `manual_review` (critical `missing_fields` or confidence &lt; 0.70), the worker must escalate to the executive mailbox’s `escalation_manager_email` (typically `acc.mmlogistix@bp0.work`).

**Verify after deploy:**

```bash
curl -s http://localhost:8000/health | jq .version
# → "0.13.15-ap-missing-fields-escalation"

docker compose logs ap-worker --tail 30 | grep -E 'escalated_to_manager|Routed|missing'
```

**Manager email checks:** Subject `[CAS-…] Action required — missing invoice fields`; body lists extracted vs missing fields; **original inbound PDF attached**; Approve / Request More Info / Reject links resolve (`05` §8.8a).

**finance-ui:** Rebuild `finance-ui` for `0.13.6-manual-review-detail`; case detail `/cases/{id}` shows **Manual review details** panel from `workflow_metadata`.

## 4.5d DOCX, PO gate, and travel controls (`0.13.20-docx-po-travel-controls`)

**Migration `048`:** creates `travel_requests`; adds DOCX MIME to `mail_gateway_config.allowed_attachment_types` on executive mailboxes.

```bash
cd accfin && alembic upgrade head && alembic current   # → 20260530_048

docker compose build gateway ap-worker expense-worker hermes fastapi
docker compose up -d gateway ap-worker expense-worker hermes fastapi
curl -s http://localhost:8000/health | jq .version
# → "0.13.20-docx-po-travel-controls"
```

**Verify DOCX / accexp:**

- Send employee reimbursement DOCX to `accexp.mmlogistix@bp0.work` (e.g. Invoice HO-202512-01, SGD 282.00)
- Case type `expense_claim` (not `ap_invoice`)
- `email_attachments.extracted_text` populated at ingest

**Verify AP PO gate:**

- AP invoice **without** PO reference → manager email: *No PO found for this invoice…*
- `cases.workflow_metadata.po_validation.match_status` = `not_found`
- Invoice with matching PO → `exact` or `partial`; journal created

**Verify travel matching:**

- Seed approved row in `travel_requests` for employee + claim period before travel expense claims
- Travel claim (hotel/flight/taxi) without overlapping request → manager escalation

## 4.5e AP vendor extraction and Client/Vendor display (`0.13.21-ap-vendor-extraction-display`)

**Hermes prompt:** `ap_invoice_extract-v2` in `agents/hermes/llm_extract.py` — vendor is issuer; receipt/ref/ARN labels; paid receipt `due_date = invoice_date`.

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin
docker compose build hermes fastapi finance-ui
docker compose up -d hermes fastapi finance-ui
curl -s http://localhost:8000/health | jq .version
# → "0.13.21-ap-vendor-extraction-display"
```

**Verify:**

- ACRA receipt: `extracted_fields.vendor_name` = ACRA / Accounting and Corporate Regulatory Authority (not MMLOGISTIX PTE LTD payer)
- Paid receipt: `due_date` equals `invoice_date`
- `GET /cases` → `client_vendor_name` populated for AP cases; finance-ui **Client / Vendor** column shows vendor

## 4.5e.1 finance-ui Client/Vendor by case type (`0.13.10-ap-client-vendor-column-fix`)

**UI only** (`finance-ui/src/lib/case-labels.ts` → `clientVendorColumnValue`): AP case types use `client_vendor_name` (fallback `counterparty_name`); AR case types use `counterparty_name` only.

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin
docker compose build finance-ui
docker compose up -d finance-ui
```

**Verify:**

- Approvals table: AP invoice row **Client / Vendor** = extracted vendor (`client_vendor_name`)
- Approvals table: AR invoice row **Client / Vendor** = classified customer (`counterparty_name`), not extracted customer field

## 4.5g Client Admin UI (`0.14.6-email-signature`)

**Host:** `https://admin.mmlogistix.bp0.work` — **mmlogistix Client Admin** (`client-admin-ui/`).  
**Auth:** `system.mmlogistix@bp0.work` / `client_admin` JWT; all API calls `/api/*`.  
**Authoritative spec:** `15` §8.13–§8.21, `05` §4.16b.4, `18` §10.2, `06` §13.2b.

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin
docker compose build fastapi client-admin-ui
docker compose up -d --force-recreate fastapi client-admin-ui
curl -s http://localhost:8000/api/health | jq .version
# → "0.14.6-email-signature" (until config version bump; COA features ship in 0.14.7 commits)
```

**`0.14.6` delta (no new migration):** Tenant `email_signature_html` / `email_signature_plain` appended to all outbound SMTP via `OutboundMailService` + `mail_template_renderer` (`18` §10.2). Client Admin `/company` — signature preview. Rebuild **`fastapi`** (required); **`client-admin-ui`** (preview UI).

**Prior releases (same stack):** `0.14.7` tenant COA import (§4.5h); `0.14.5` GL period reopen; `0.14.4` GL posting gate — see §20.2.

## 4.5h Client Admin — tenant COA import (`0.14.7-coa-tenant-import`)

**Commits:** `5a2b441` (upsert CSV, `replace_all`, migration `054`), `7502b3e` (COA filter/search UX — Svelte 5 `$state`), `8d6bf6e` (COA page: Svelte 5 `onclick` / `onchange` only — **required** for `npm run build` in Docker).

```bash
cd /opt/bp0work/accounting && git pull origin main
# expect through 8d6bf6e (or later)

cd accfin
docker compose run --rm fastapi alembic upgrade head
# → head includes 20260531_054

docker compose build --no-cache fastapi client-admin-ui
docker compose up -d --force-recreate fastapi client-admin-ui
```

**Delta:**

| Area | Change |
|------|--------|
| **DB** | `054_remove_seed_coa_accounts` — removes demo codes `1200`, `1300`, `2000`, `2100`, `4100`, `5200`, `5500`, `1190` when unused (`06` §10.1) |
| **API** | `POST /api/coa/import?replace_all=true` upserts by `account_code`; `GET /api/coa?q=` filters code/name (`05` §4.16d.3) |
| **UI** | `/chart-of-accounts`: **Replace entire chart on import** (default on); green import summary; **Filter by code or name** + Search / Clear (`15` §8.10) |

**Verify (Client Admin):**

- Hard refresh (Ctrl+Shift+R) on `https://admin.mmlogistix.bp0.work/chart-of-accounts`
- Empty or post-migration: no demo `1200`/`1300` rows unless still referenced
- Import CSV with required columns → message `Import complete: N created, M updated…`
- Navigate away and back → only tenant accounts remain
- Filter field → partial code/name → **Search** narrows table; **Clear** restores full list

**Note:** AP/AR/expense workers still reference fixed GL codes in handler logic (`17` §5.1.1) — tenant COA must include mapped codes or workers escalate `COA_ACCOUNT_NOT_FOUND`.

**Build failure (`mixed_event_handler_syntaxes`):** If `docker compose build client-admin-ui` fails on `chart-of-accounts/+page.svelte` with “Mixing old (on:change) and new syntaxes”, pull **`8d6bf6e`** or later. Client Admin UI (Svelte 5) must use **`onclick` / `onchange` / `onkeydown`** on a page — not `on:click` / `on:change` mixed with the new form (`15` §8.10). A failed build leaves the **previous** image running; do not assume `up -d` deployed new UI until build succeeds.

## 4.5i Counterparty accounts + GST mapping (`0.14.8-counterparty-accounts`) — shipped

**Status:** Shipped (`b1095c1` feature, `386c89f` deploy/UAT script, `b749e64` admin write commit fix).

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin

# 1) Rebuild images (must be before alembic for 055–058 on first deploy)
docker compose build --no-cache fastapi client-admin-ui ar-worker ap-worker

# 2) Migrate (expect 054 → 055 → 056 → 057 → 058)
docker compose run --rm fastapi alembic upgrade head

# 3) Optional UAT
./scripts/uat_phase13.sh

# 4) Recreate running services
docker compose up -d --force-recreate fastapi client-admin-ui ar-worker ap-worker
```

| Component | Why rebuild |
|-----------|-------------|
| `fastapi` | Admin counterparty routes; `TaxCodeResolver`; migrations `055`–`058` in image |
| `finance-ui` | `/counterparty-accounts`, `/agreements`, `/accounting-calendar` (moved from Client Admin `e73c869`) |
| `ar-worker`, `ap-worker` | Subaccount resolution, due date from terms, GST GL from `tenant_tax_codes` |

**Note:** Compose service names are **`ar-worker`** and **`ap-worker`** (not `worker-ar` / `worker-ap`).

**Pre-deploy (Client Admin):**

1. COA imported (`0.14.7`) with dedicated GST output + input account codes (not only `2100`/`1190` unless those are your real GST accounts).
2. **Tax codes** tab: map `SR` / `GST9` → those GL codes.
3. **Payment terms** tab: at least `NET30` active.
4. **Subaccounts** tab: create subaccounts with **payment terms** (due days) and **credit limit** amount + currency for top customers/suppliers before bulk intake (credit is per subaccount — not on Payment terms catalog).
5. **Update existing subaccounts:** Subaccounts tab → **Edit** on an active row → change payment terms and/or credit limit → **Save** (`PATCH /api/counterparty-accounts/{id}`; shipped `9b0662e`).

**UI-only patch (`9b0662e` — subaccount edit):**

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin
docker compose build --no-cache client-admin-ui
docker compose up -d --force-recreate client-admin-ui
```

**Verify:**

- `GET /api/payment-terms` → seeded terms
- `GET /api/tenant/tax-codes` → SR row with valid GL codes
- POST test subaccount linked to existing `counterparty`
- Ingest sample AR invoice → `workflow_metadata` contains `counterparty_account_ref`, `due_date_source`, `tax_resolution`
- Journal lines use mapped GST accounts (not hard-coded creditors code for tax)

**Traefik:** `client-admin-ui` router priority **1** on `admin.mmlogistix.bp0.work`; `client-admin-api` `PathPrefix(/api)` priority **100** → FastAPI.

**Verify (Client Admin):**

- Login → header nav: Dashboard | Company | Chart of Accounts | Users | Policies | Binding Authority (no Mailboxes, Counterparty, Agreements, Calendar, or Travel — Mailboxes was removed from header in `0.14.12-admin-ui-cleanup`; the `/mailboxes` page is still reachable via direct URL)
- `GET https://admin.mmlogistix.bp0.work/api/admin/dashboard` → checklist JSON, **7 sections** after `0.14.12-admin-ui-cleanup`: `company`, `signature`, `coa`, `users` (label "Key Roles Email (Uses)"), `travel_policy`, `expense_limits`, `regulatory`. The six removed sections (`payment_terms`, `tax_codes`, `vendor_contracts`, `mailboxes`, `calendar`, `gl_reminders`) are now surfaced on **finance.mmlogistix** (`§4.5j`, `§4.5e`)
- Company (`/company`): email signature HTML/plain saves (`051`); **Preview signature in email** shows HTML + plain footer (`0.14.6`)
- Outbound SMTP (ack / escalation / clarification / daily log / GL cutoff): footer matches configured signature when set (`18` §10.2)
- Policies: travel & expense policy PDF upload; regulatory PDF catalog (`Wasabi`)

## 4.5k Binding authority approval tiers (`0.14.9-binding-authority`) — shipped

**Status:** Shipped (migration `060`, Client Admin `/binding-authority`, worker tier routing, finance-ui role queues).

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin

# 1) Rebuild images (policy engine + workers + both UIs)
docker compose build --no-cache fastapi client-admin-ui finance-ui ar-worker ap-worker expense-worker

# 2) Migrate (expect 059 → 060)
docker compose run --rm fastapi alembic upgrade head

# 3) Recreate running services
docker compose up -d --force-recreate fastapi client-admin-ui finance-ui ar-worker ap-worker expense-worker
```

| Component | Why rebuild |
|-----------|-------------|
| `fastapi` | `PolicyEngine.evaluate_approval_tier`; `GET/PATCH /api/admin/binding-authority`; `POST /api/approvals/{id}/escalate`; cases expose `pending_approval_id` |
| `client-admin-ui` | `/binding-authority` thresholds per document type (AP, AR, expense) |
| `finance-ui` | Role-based approval queue; case detail Approve / Reject / Escalate to CFO |
| `ar-worker`, `ap-worker`, `expense-worker` | Post-extraction tier: T1 STP journal; T2+ `pending_approval` + email to acc / CFO |

**Default thresholds (migration `060`, SGD):**

| Field | Default |
|-------|---------|
| Tier 1 ceiling | 3,000 (STP auto-post) |
| Tier 2 ceiling | 10,000 (Accounts Manager) |
| Tier 3 threshold | 10,000 (CFO/FD) |
| STP confidence minimum | 0.90 |
| Tier 2 SLA (hours) | 4 |
| Tier 3 SLA (hours) | 8 |

**Policies table:** `ap_approval_thresholds`, `ar_approval_thresholds`, `expense_approval_thresholds` (`10` §7, `16` §10 migration `060`).

**Verify:**

- `GET /api/health` → `0.14.9-binding-authority`
- Client Admin → **Binding Authority** — edit/save per document type
- Submit AP invoice &gt; Tier 1 ceiling → case `pending_approval`; acc mailbox email with Approve / Reject / Escalate
- Finance UI → **Cases & Approvals** → **My queue** (acc: Tier 2; CFO: Tier 3 + escalated Tier 2)
- acc **Escalate to CFO** → CFO queue; CFO **Approve** → journal posted + submitter ack

**Client Admin nav:** Dashboard | Company | Chart of Accounts | Users | Policies | **Binding Authority** | Logout (`15` §8.13; Mailboxes removed from header in `0.14.12-admin-ui-cleanup` — see §4.5l).

## 4.5l Client Admin UI cleanup (`0.14.12-admin-ui-cleanup`) — planned

**Status:** Planned (UI-only change; no DB migration, no worker rebuild). Affected images: `fastapi`, `client-admin-ui`.

**Scope:** Drop six finance-domain tiles from `GET /api/admin/dashboard` (`05` §4.16d.1) and remove the **Mailboxes** entry from the `client-admin-ui` header. Rename the role-emails tile from "Key role emails" to **"Key Roles Email (Uses)"**.

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin
docker compose build --no-cache fastapi client-admin-ui
docker compose up -d --force-recreate fastapi client-admin-ui
```

| Component | Why rebuild |
|-----------|-------------|
| `fastapi` | `admin_dashboard` returns 7 sections instead of 13; orphaned imports/helper removed |
| `client-admin-ui` | Top-nav drops `<a href="/mailboxes">` |

**Removed dashboard tiles (now finance-ui only — `15` §8.22–§8.24, `05` §4.16d.4 / §4.16d.11–13):**

| `section` | Replaces with |
|-----------|---------------|
| `payment_terms` | finance-ui `/counterparty-accounts` Tab 2 |
| `tax_codes` | finance-ui `/counterparty-accounts` Tab 3 |
| `vendor_contracts` | finance-ui counterparty master expiry badge |
| `mailboxes` | direct URL only (`/mailboxes` page preserved) |
| `calendar` | finance-ui `/accounting-calendar` |
| `gl_reminders` | finance-ui `/accounting-calendar` reminder recipients |

**Verify:**

- `GET https://admin.mmlogistix.bp0.work/api/admin/dashboard` → JSON has `total_count = 7`; sections are exactly `company`, `signature`, `coa`, `users`, `travel_policy`, `expense_limits`, `regulatory`
- `users` tile `label == "Key Roles Email (Uses)"`
- Client Admin header nav has no **Mailboxes** entry; `https://admin.mmlogistix.bp0.work/mailboxes` still loads when typed directly
- `GET /api/health` → `0.14.12-admin-ui-cleanup`
- finance-ui setup screens unchanged (still authoritative for the six dropped concerns)

**No DB migration; no worker restart.**

## 4.5j Finance UI — setup screens (`e73c869`)

**Moved from Client Admin:** Counterparty accounts, agreements, accounting calendar now on **finance.mmlogistix** for finance roles (`cfo`, `finance_manager`, `accounts_clerk`, etc.). APIs use `require_finance_setup_access` (`05` §4.16d.4).

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin
docker compose build --no-cache fastapi finance-ui
docker compose up -d --force-recreate fastapi finance-ui
```

| Component | Why rebuild |
|-----------|-------------|
| `fastapi` | `require_finance_setup_access` on counterparty, agreements, calendar routes |
| `finance-ui` | New routes + `finance-setup.ts` API client |

**Verify (finance-ui):**

- Login as `cfo.mmlogistix` or `fin.mmlogistix` (not `system.mmlogistix` — that user is Client Admin only)
- Header nav: Dashboard | Cases & Approvals | **Counterparty accounts** | **Agreements** | **Accounting calendar** | Export | …
- **Counterparty accounts** → Subaccounts: **Edit** / **Save** for payment terms + credit limit (`9b0662e`)
- **Agreements** → add rental / director expense rows
- **Accounting calendar** → settings, generate periods, TB approve, GL close, reopen, reminder recipients

**Verify (GL period posting — finance-ui):**

- Post journal into **closed** period → case `on_hold`, `workflow_metadata.reason_code = PERIOD_CLOSED`
- CFO or Finance Manager on case detail → **Override & Post** with mandatory reason → case requeued; `gl_period_override_post` in `finance_activity_log`
- Finance UI **Accounting calendar** **Reopen** period → case detail shows **Retry processing** (no override); `gl_period_reopened` in `finance_activity_log`

**GL cutoff reminders cron (VPS crontab, 08:00 SGT = 00:00 UTC):**

```bash
0 0 * * * curl -s -X POST http://localhost:8000/api/internal/jobs/gl-cutoff-reminders \
  -H "Authorization: Bearer $FINANCE_INTERNAL_CRON__TOKEN" \
  -H "Content-Type: application/json" >> /var/log/gl-cutoff-reminders.log 2>&1
```

Sender: `acc.mmlogistix@bp0.work`. See `05` §19.2, `11` §17.6.

## 4.5f Escalation respond comment form (`0.13.22-escalation-respond-flow`)

**Routes:** `app/api/routes/mail_actions.py` — `GET/POST /mail/escalations/{id}/respond`

```bash
cd /opt/bp0work/accounting && git pull origin main
cd accfin
docker compose build fastapi ap-worker
docker compose up -d fastapi ap-worker
curl -s http://localhost:8000/health | jq .version
# → "0.13.22-escalation-respond-flow"
```

**Verify:**

- Manager email Approve link → HTML form with case number + comment field (not immediate action)
- POST with comment → confirmation page; `case_escalations.manager_comment` populated
- Approve on PO-blocked AP case → case reprocessed with `override_po_check`; submitter receives ack email
- Reject → submitter receives rejection email with manager comment

## 4.6 Hermes extraction (MVP production — `0.12.7-ollama-extraction`)

Invoice, expense claim, and payment advice extraction run through **Hermes → Ollama** (`qwen2.5:7b`), not regex stubs alone. Rebuild and restart after deploy:

```bash
docker compose build hermes worker-accounts worker-ar worker-ap worker-expense fastapi
docker compose up -d hermes worker-accounts worker-ar worker-ap worker-expense fastapi
```

**Ollama models required on VPS** (see §8.2):

```bash
docker exec ollama ollama pull qwen2.5:7b        # primary extraction model (HERMES_EXTRACTION_MODEL)
docker exec ollama ollama pull qwen2.5vl:7b      # optional — receipt/invoice image OCR (HERMES_VISION_MODEL)
```

**Hermes container env** (`docker-compose.yml` `hermes` service — not `.env`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `HERMES_OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama API inside Docker network |
| `HERMES_EXTRACTION_MODEL` | `qwen2.5:7b` | `/extract/invoice`, `/extract/expense-claim`, `/extract/payment-advice` |
| `HERMES_VISION_MODEL` | `qwen2.5vl:7b` | `/extract/document-text` (JPEG/PNG attachments) |

**Pipeline:** Gateway ingests mail → **`sanitize_text()` on all parsed fields** (`0.13.1-mail-text-sanitize`) → PDF text via `pypdf` → accounts worker classifies → **sender ack** with `[CAS-…]` for external mail → domain workers → on failure **manager escalation first** (`ExecutiveMailService`; `0.13.0-executive-mail-sop`) → failure notify to sender **only after manager reject**. **Manual retry:** `POST /cases/{id}/retry` (`0.13.3`). **Ollama healthcheck:** `ollama list` in compose (`0.13.5`). **Finance UI:** `/settings/security` 2FA (`0.13.6`). Current deploy **`0.13.6-finance-security-2fa`**. Regex stubs remain fallback if Ollama is unreachable (`04` §4.2, `17` §2.1.2, §10.4).

---

# 5. Traefik Configuration

Public HTTPS hostnames and Let's Encrypt email are defined in `14_Environment_and_Configuration_Reference.md` §9.0 (`FINANCE_PUBLIC__*`, `FINANCE_LETS_ENCRYPT_EMAIL`). **Authoritative defaults:**

| Host | Surface | MVP |
|------|---------|-----|
| `finance.mmlogistix.bp0.work` | Finance Approval UI (`finance-ui`); edge API paths to FastAPI | Yes |
| `admin.bp0.work` | Platform Admin UI (`platform-admin-ui`) | Post-MVP |
| `admin.mmlogistix.bp0.work` | Client Admin UI (`client-admin-ui`) — `0.14.6` |
| *(none)* | FastAPI — `http://fastapi:8000` internal Docker only | Yes |

ACME email default `system@bp0.work`. **No** public `api.bp0.work` hostname. Legacy reference code used only `ADMIN_BASE_PATH=/mmlogistixadmin` (path prefix).

**API path routing (MVP):** `accfin/traefik/dynamic/api-routes.yml` (mounted at `/etc/traefik/dynamic`). Router `finance-api`: **single-line** `rule` with listed API `PathPrefix`es only — **never** `PathPrefix(\`/\`)` (that matches all paths and breaks `/` → UI). Priority **100**. `finance-ui` Docker router: `Host(finance.mmlogistix.bp0.work)` priority **1** — serves `/` and app routes. **Traefik image:** `traefik:v2.11` in `accfin/docker-compose.yml` (not v3 on VPS). Current deploy version **`0.14.6-email-signature`** — see **§20.2**.

## 5.1 Static Configuration

```yaml
# /opt/mmlogistix/traefik/traefik.yml
global:
  checkNewVersion: false
  sendAnonymousUsage: false

api:
  dashboard: true
  insecure: false  # Use basic auth middleware

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
          permanent: true

  websecure:
    address: ":443"
    http:
      tls:
        certResolver: letsencrypt
      middlewares:
        - "security-headers@file"

  traefik:
    address: ":8080"

providers:
  docker:
    exposedByDefault: false
    network: frontend
    watch: true
  file:
    directory: /dynamic-config
    watch: true

certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@bp0.work
      storage: /letsencrypt/acme.json
      tlsChallenge: {}

log:
  level: INFO
  format: json
  filePath: /var/log/traefik/traefik.log

accessLog:
  format: json
  filePath: /var/log/traefik/access.log
  filters:
    statusCodes:
      - "400-599"
```

## 5.2 Dynamic Configuration

```yaml
# /opt/mmlogistix/traefik/dynamic-config/security.yml
http:
  middlewares:
    security-headers:
      headers:
        customFrameOptionsValue: "SAMEORIGIN"
        contentTypeNosniff: true
        browserXssFilter: true
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        stsPreload: true
        forceSTSHeader: true
        customResponseHeaders:
          X-Robots-Tag: "noindex, nofollow"

    rate-limit:
      rateLimit:
        average: 300
        burst: 100
        period: 1m

    api-auth:
      basicAuth:
        users:
          # Generate with: htpasswd -nB admin
          - "admin:$2y$10$..."

  routers:
    # Dashboard — restricted by IP
    dashboard:
      rule: "Host(`traefik.bp0.work`)"
      service: api@internal
      middlewares:
        - "api-auth"
        - "security-headers"
      entryPoints:
        - traefik

    # Finance Approval UI (public)
    finance-ui:
      rule: "Host(`finance.mmlogistix.bp0.work`)"
      service: finance-ui
      middlewares:
        - "security-headers"
      entryPoints:
        - websecure
      tls:
        certResolver: letsencrypt

    # API paths on Approval UI host (FastAPI internal; no api.bp0.work)
    # Deployed as accfin/traefik/dynamic/api-routes.yml — single-line rule; service name matches http.services key.
    finance-api:
      rule: "Host(`finance.mmlogistix.bp0.work`) && (PathPrefix(`/auth`) || PathPrefix(`/mail`) || PathPrefix(`/approvals`) || PathPrefix(`/cases`) || PathPrefix(`/audit-logs`) || PathPrefix(`/events`) || PathPrefix(`/health`) || PathPrefix(`/metrics`) || PathPrefix(`/internal`) || PathPrefix(`/expense-claims`) || PathPrefix(`/reconciliation`) || PathPrefix(`/notification`) || PathPrefix(`/users`) || PathPrefix(`/workflow`) || PathPrefix(`/policies`))"
      service: finance-api
      middlewares:
        - "security-headers"
      priority: 100
      entryPoints:
        - websecure
      tls:
        certResolver: letsencrypt

  services:
    finance-ui:
      loadBalancer:
        servers:
          - url: "http://finance-ui:3000"
    finance-api:
      loadBalancer:
        servers:
          - url: "http://fastapi:8000"
        healthCheck:
          path: "/health"
          interval: "10s"
          timeout: "5s"
```

## 5.3 Traefik Container

```yaml
services:
  traefik:
    image: traefik:v3.0
    container_name: traefik
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    read_only: true
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - /opt/mmlogistix/traefik/traefik.yml:/etc/traefik/traefik.yml:ro
      - /opt/mmlogistix/traefik/dynamic-config:/dynamic-config:ro
      - /opt/mmlogistix/traefik/letsencrypt:/letsencrypt
      - /opt/mmlogistix/logs/traefik:/var/log/traefik
    networks:
      - frontend
      - backend
    labels:
      - "traefik.enable=true"
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
```

---

# 6. Supabase Configuration

## 6.1 Supabase Cloud (Managed)

This project uses **Supabase Cloud** — not self-hosted. **Production finance data** (cases, emails, escalations, audit logs) lives in Supabase PostgreSQL via `FINANCE_DATABASE_URL`.

## 6.1.1 Compose `db` service vs Supabase (VPS troubleshooting)

`accfin/docker-compose.yml` includes a **`db`** service (`postgres:15-alpine`, database name **`postgres`**) so local stacks can satisfy `depends_on` health checks and support optional dev workflows. **On production VPS this container is empty** — it does not receive Alembic migrations or case data when `FINANCE_DATABASE_URL` points at Supabase.

| Check | Local compose `db` | Supabase (production) |
|-------|-------------------|------------------------|
| `docker compose exec db psql … -c '\dt cases'` | Relation missing or empty | Tables present |
| `FINANCE_DATABASE_URL` host | Often unused | `*.pooler.supabase.com` or `db.*.supabase.co` |
| Query case `CAS-…` | Use app connection (below) | Authoritative |

**Correct production diagnostics:**

```bash
# Masked URL — confirm Supabase pooler/direct host
docker compose exec fastapi python -c "
import re; from app.core.config import get_settings
u=get_settings().database_url
print(re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', u))
"

# Query via same DB the app uses (Supabase)
docker compose exec fastapi python -c "
import asyncio
from sqlalchemy import text
from app.core.database import get_session_factory
async def q():
    async with get_session_factory()() as s:
        r=await s.execute(text(\"SELECT count(*) FROM cases\"))
        print('cases:', r.scalar())
asyncio.run(q())
"
```

Do **not** use `docker compose exec db psql … accfin` — database name is **`postgres`**, not `accfin`, and that container is not the finance store on Supabase deployments.

| Detail | Value |
|--------|-------|
| **Hosting** | Supabase Cloud (managed) |
| **Project URL** | `https://ehsoeyfopazodvmpkkpy.supabase.co` |
| **Project Ref** | `ehsoeyfopazodvmpkkpy` |
| **PostgreSQL version** | 17.6.1.121 |
| **PostgREST version** | 14.5 |
| **GoTrue (Auth) version** | 2.189.0 |
| **Storage bucket** | `finance-attachments` (private) |

## 6.2 Connection Details

**Direct connection string (for Alembic migrations and server-side queries):**

```
postgresql://postgres:[YOUR-PASSWORD]@db.ehsoeyfopazodvmpkkpy.supabase.co:5432/postgres
```

**Async connection string (application runtime — SQLAlchemy/asyncpg):**

```
postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.ehsoeyfopazodvmpkkpy.supabase.co:5432/postgres
```

> The database password is set in the Supabase dashboard under **Project Settings → Database → Database password**. Store it in `.env` as part of `FINANCE_DATABASE_URL`. Never commit the password to the repository.

## 6.3 Application Environment Variables

```bash
# FINANCE_* variables for the application stack (.env)
FINANCE_DATABASE_URL=postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.ehsoeyfopazodvmpkkpy.supabase.co:5432/postgres

FINANCE_SUPABASE__URL=https://ehsoeyfopazodvmpkkpy.supabase.co
FINANCE_SUPABASE__SERVICE_KEY=[Supabase Dashboard → Project Settings → API → service_role key]
FINANCE_SUPABASE__JWT_SECRET=[Supabase Dashboard → Project Settings → API → JWT Secret]
FINANCE_SUPABASE__STORAGE_BUCKET=finance-attachments

# FINANCE_SUPABASE__ANON_KEY is NOT required — server-side only platform.
# Anon key is reserved for future client-side use only.
```

> **Key scope reminder:** `FINANCE_SUPABASE__JWT_SECRET` is Supabase's own JWT signing secret — it is distinct from the application's `FINANCE_JWT__SECRET`. Both are required and must never be conflated. Generate them independently.

## 6.4 Supabase CLI Setup (for migrations and storage management)

```bash
# Install Supabase CLI
npm install -g supabase

# Authenticate
supabase login

# Initialise local config (run once in repo root — creates supabase/ directory)
supabase init

# Link to the cloud project
supabase link --project-ref ehsoeyfopazodvmpkkpy
```

Migration files are managed exclusively by **Alembic** (see `16_Migration_and_ORM_Specification.md`). The Supabase CLI is used for storage bucket management and dashboard sync only — **never** for running database migrations or schema changes.

## 6.5 Storage Bucket Setup

The `finance-attachments` bucket must be created and set to **private** before the application can store email attachments. Create via CLI:

```bash
# After supabase link
supabase storage create finance-attachments --project-ref ehsoeyfopazodvmpkkpy
```

Or via the Supabase dashboard: **Storage → New bucket → Name: `finance-attachments` → Private**.

All attachment access is server-side via the service role key. No public URLs.

## 6.6 Row Level Security (Phase 2+)

```sql
-- Enable RLS after initial deployment and role configuration
-- Run via Alembic migration, not via the Supabase dashboard SQL editor
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
```

> **Important:** RLS policies use `app_user_id()` — a PostgreSQL session variable wrapper set by FastAPI middleware. Do NOT use `auth.uid()` (Supabase PostgREST function) — it is unavailable in this FastAPI + asyncpg architecture. See `06_Database_Schema_Design.md` §16.0 and `13_Security_and_Compliance_Specification.md` §5.8.

## 6.7 Database Backups

Supabase Cloud provides automatic daily backups on Pro plan. For additional coverage, use `pg_dump` against the direct connection string:

```bash
pg_dump "postgresql://postgres:[YOUR-PASSWORD]@db.ehsoeyfopazodvmpkkpy.supabase.co:5432/postgres" \
  --format=custom \
  --no-password \
  > /opt/mmlogistix/backups/supabase_$(date +%Y%m%d_%H%M%S).dump
```

> PostgreSQL tuning (shared_buffers, work_mem, etc.) is managed by Supabase Cloud infrastructure and cannot be configured directly. Contact Supabase support for compute tier upgrades if performance tuning is required.

---

# 7. Redis Configuration

Redis on this platform is a **self-hosted** Docker container on your VPS. Unlike Supabase or SendGrid, there is **no external dashboard** that issues a Redis password — you generate one and configure the server and application to use the **same** value.

Environment variables (see `14_Environment_and_Configuration_Reference.md` §5, `env.example` §3):

| Variable | Production example | Purpose |
|----------|-------------------|---------|
| `FINANCE_REDIS__HOST` | `redis` | Docker Compose service name (internal network) |
| `FINANCE_REDIS__PORT` | `6379` | TCP port |
| `FINANCE_REDIS__DB` | `0` | Logical database index (0 is standard) |
| `FINANCE_REDIS__PASSWORD` | *(you generate)* | Must match `requirepass` in `redis.conf` |

## 7.1 First-Time Setup (Password and Application Config)

Complete these steps **once** before starting the stack in production, or whenever you rotate the Redis password.

### Step 1 — Generate a password

Choose **one** method:

```bash
# Option A — single secret
openssl rand -base64 32

# Option B — all platform secrets (includes FINANCE_REDIS__PASSWORD)
python scripts/generate-keys.py

# Option C — runbook helper (§11.2 excerpt)
REDIS_PASSWORD=$(openssl rand -base64 32)
echo "FINANCE_REDIS__PASSWORD=$REDIS_PASSWORD"
```

Copy the generated string. Treat it like any other production secret — do not commit it to git.

### Step 2 — Configure the Redis server (`redis.conf`)

Edit `/opt/mmlogistix/redis/redis.conf` (see §7.2 for the full file). Set **`requirepass`** to the password from Step 1:

```bash
# Authentication — must match FINANCE_REDIS__PASSWORD in .env
requirepass YOUR_GENERATED_PASSWORD_HERE
```

Replace the placeholder `<generate-strong-password>` in §7.2 with your real value.

### Step 3 — Configure the application (`.env`)

On the host where Docker Compose runs (e.g. `/opt/bp0work/accounting/accfin`), edit `.env`:

```bash
FINANCE_REDIS__HOST=redis
FINANCE_REDIS__PORT=6379
FINANCE_REDIS__DB=0
FINANCE_REDIS__PASSWORD=YOUR_GENERATED_PASSWORD_HERE
```

Use the **same** password as in Step 2. The FastAPI gateway, orchestrator, and workers read these variables at startup.

### Step 4 — Restart Redis and dependent services

```bash
cd /opt/bp0work/accounting/accfin   # monorepo backend; compose project directory

docker compose restart redis
docker compose up -d     # ensure app services pick up .env if changed
```

### Step 5 — Verify connectivity

From the VPS (password required when `requirepass` is set):

```bash
# Replace with your actual password
redis-cli -h 127.0.0.1 -p 6379 -a 'YOUR_GENERATED_PASSWORD_HERE' ping
# Expected: PONG
```

From inside the Redis container on the Docker network:

```bash
docker compose exec redis redis-cli -a "$FINANCE_REDIS__PASSWORD" ping
```

If the app is up, confirm the platform health check passes (see §17 operational procedures) and that queue workers connect without `NOAUTH` or `WRONGPASS` errors in logs.

### Step 6 — Update the Docker healthcheck (production)

The default healthcheck in §7.3 runs `redis-cli ping` **without** a password. After enabling `requirepass`, change the `redis` service healthcheck so Compose can mark the container healthy:

```yaml
healthcheck:
  test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
  interval: 10s
  timeout: 5s
  retries: 3
```

Pass `REDIS_PASSWORD` into the container via `env_file: .env` or an `environment:` entry sourced from the same value as `FINANCE_REDIS__PASSWORD`. Do not hard-code the password in `docker-compose.yml`.

### Local development (optional)

For a **local-only** Redis without authentication:

- Run Redis without `requirepass` in a dev `redis.conf`, and
- Omit `FINANCE_REDIS__PASSWORD` in your local `.env` (development only).

Production and staging **must** use a password (`14` §5). Never deploy with an open Redis port on the public internet.

### Password rotation

When rotating:

1. Generate a new password (Step 1).
2. Update `requirepass` in `redis.conf` (Step 2).
3. Update `FINANCE_REDIS__PASSWORD` in `.env` (Step 3).
4. Restart Redis, then restart all services that connect to Redis (Step 4).
5. Re-verify (Step 5).

See `14_Environment_and_Configuration_Reference.md` §18.1 for the quarterly rotation schedule.

## 7.2 Redis Configuration File

```bash
# /opt/mmlogistix/redis/redis.conf

# Network
bind 0.0.0.0
protected-mode yes
port 6379

# Authentication
requirepass <generate-strong-password>

# Memory
maxmemory 1gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG "CONFIG_a1b2c3"

# Logging
loglevel notice
logfile /var/log/redis/redis-server.log

# Slow query log
slowlog-log-slower-than 10000
slowlog-max-len 128
```

## 7.3 Redis Container

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - /opt/mmlogistix/redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
      - redis-data:/data
      - /opt/mmlogistix/logs/redis:/var/log/redis
    networks:
      - backend
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"
```

## 7.4 Redis Persistence Strategy

| Method | Frequency | Use Case |
|--------|-----------|----------|
| **RDB snapshot** | Every 15 min (if 1+ key changed) | Full point-in-time recovery |
| **AOF** | Every second (fsync) | Durability, minimal data loss |
| **Manual BGSAVE** | Before deployments | Known-good snapshot |

---

# 8. Ollama Configuration

> **Legacy:** `accounting_agent.py` used `http://127.0.0.1:11434` with model `qwen2.5:0.5b` (no Hermes). **Target:** Docker service `ollama` at `http://ollama:11434`; pull `hermes3`, `qwen2.5:7b`, `qwen2.5:0.5b` per §8.2. Env detail: `14` §6.0.

## 8.1 Ollama Container

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    volumes:
      - ollama-models:/root/.ollama
    networks:
      - backend
    deploy:
      resources:
        limits:
          cpus: "4.0"
          memory: 16G
    environment:
      - OLLAMA_ORIGINS=*
      - OLLAMA_HOST=0.0.0.0:11434
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
```

## 8.2 Model Management

> **Authoritative model list:** The three models below are the canonical set defined in `04_Hermes_Integration_Spec.md` §14 (`hermes_config.yaml`) and `env.example`. Do not pull additional models (`llama3.1`, `nomic-embed-text`, etc.) — they are not part of the configured fallback chain and will consume RAM without being used.
>
> **MVP production extraction (`0.12.7-ollama-extraction`):** Hermes uses **`qwen2.5:7b`** as the primary extraction model (`HERMES_EXTRACTION_MODEL` on the Hermes container). Pull **`qwen2.5vl:7b`** additionally for receipt/invoice image OCR (`HERMES_VISION_MODEL`). See `04` §4.2, `11` §4.6.
>
> Fallback chain: `hermes3` → `qwen2.5:7b` (extraction/reconciliation) or `qwen2.5:0.5b` (classification fallback). See `04` §14 for the full `model_fallbacks` configuration.

```bash
# Pull required models after Ollama is running
docker exec -it ollama ollama pull hermes3          # Primary — classification
docker exec -it ollama ollama pull qwen2.5:7b       # MVP extraction — invoice, expense, payment advice
docker exec -it ollama ollama pull qwen2.5:0.5b     # Classification fallback
docker exec -it ollama ollama pull qwen2.5vl:7b     # Optional — image OCR via Hermes /extract/document-text

# Verify models are loaded
docker exec -it ollama ollama list

# Expected output:
# NAME                   ID              SIZE      MODIFIED
# hermes3:latest         abc123...       4.1 GB    5 minutes ago
# qwen2.5:7b             def456...       4.4 GB    5 minutes ago
# qwen2.5:0.5b           ghi789...      394 MB    5 minutes ago
```

## 8.3 Model Warm-Up Script

```bash
#!/bin/bash
# /opt/mmlogistix/ollama/warmup.sh
# Run after deployment to pre-load models into memory
# Models match the fallback chain in 04_Hermes_Integration_Spec.md §14

echo "Warming up AI models..."

# Primary model (hermes3 — classification + extraction + reconciliation)
curl -s http://localhost:11434/api/generate -d '{
  "model": "hermes3",
  "prompt": "Classify: Invoice from ACME Supplies for office equipment",
  "stream": false,
  "options": {"num_predict": 10}
}' > /dev/null
echo "hermes3 model warmed up"

# Extraction/reconciliation fallback (qwen2.5:7b)
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b",
  "prompt": "Extract invoice data: INV-12345, amount $500",
  "stream": false,
  "options": {"num_predict": 10}
}' > /dev/null
echo "qwen2.5:7b fallback model warmed up"

# Classification fallback (qwen2.5:0.5b)
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:0.5b",
  "prompt": "Classify: payment advice",
  "stream": false,
  "options": {"num_predict": 10}
}' > /dev/null
echo "qwen2.5:0.5b fallback model warmed up"

echo "All models ready"
```

## 8.4 Model Update Procedure

```bash
# 1. Pull updated model (keeps old version)
docker exec -it ollama ollama pull hermes3

# 2. Verify new version
docker exec -it ollama ollama list

# 3. Test inference
curl http://localhost:11434/api/generate -d '{
  "model": "hermes3",
  "prompt": "test",
  "stream": false
}'

# 4. If issues, rollback to previous
docker exec -it ollama ollama run hermes3:previous

# 5. Remove old version after 48h stable
docker exec -it ollama ollama rm hermes3:old-version
```

---

# 9. Application Deployment

## 9.1 FastAPI Container

> **Note:** The application reads all configuration via `FINANCE_`-prefixed environment variables (with `__` for nested settings) as defined in `14_Environment_and_Configuration_Reference.md`. Use `env_file` to inject the full `.env` rather than listing individual variables — this avoids the risk of using stale bare names like `DATABASE_URL` or `JWT_SECRET` which the Pydantic Settings loader does not recognise.

```yaml
services:
  fastapi:
    build:
      context: /opt/mmlogistix/app
      dockerfile: Dockerfile
    container_name: fastapi
    restart: unless-stopped
    env_file:
      - /opt/mmlogistix/.env
    networks:
      - frontend
      - backend
    depends_on:
      supabase-db:
        condition: service_healthy
      redis:
        condition: service_healthy
      ollama:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=accfin_frontend"
      - "traefik.http.routers.finance-api.rule=Host(`finance.mmlogistix.bp0.work`) && (PathPrefix(`/auth`) || PathPrefix(`/mail`) || PathPrefix(`/approvals`) || PathPrefix(`/cases`) || PathPrefix(`/events`) || PathPrefix(`/health`))"
      - "traefik.http.routers.finance-api.priority=100"
      - "traefik.http.routers.finance-api.entrypoints=websecure"
      - "traefik.http.routers.finance-api.tls.certresolver=letsencrypt"
      - "traefik.http.services.finance-api.loadbalancer.server.port=8000"
```

## 9.2 Dockerfile

```dockerfile
# /opt/mmlogistix/app/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## 9.3 Uvicorn Worker Count

```
workers = 2 * CPU_CORES + 1

For 2 CPU cores allocated:
workers = 2 * 2 + 1 = 5 (use 4 for memory efficiency)
```

## 9.4 Application Startup Order

```python
# app/main.py — lifespan context manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AI Finance Operations Platform...")
    
    # 1. Verify database connectivity
    await verify_database()
    
    # 2. Verify Redis connectivity
    await verify_redis()
    
    # 3. Verify Ollama availability
    await verify_ollama()
    
    # 4. Load active policies into memory cache
    await load_policies()
    
    # 5. Start background tasks
    asyncio.create_task(sla_monitor())
    asyncio.create_task(retry_scheduler())
    asyncio.create_task(health_reporter())
    
    logger.info("All services verified. Platform ready.")
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await close_connections()
```

---

# 10. SSL/TLS Certificates

## 10.1 Let's Encrypt (Production)

```yaml
# Already configured in Traefik static config
certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@bp0.work
      storage: /letsencrypt/acme.json
      tlsChallenge: {}
```

## 10.2 Certificate Verification

```bash
# Check certificate status
curl -vI https://finance.mmlogistix.bp0.work 2>&1 | grep -E "(subject|issuer|expire)"

# Test SSL rating
nmap --script ssl-enum-ciphers -p 443 finance.mmlogistix.bp0.work

# Renew check (Traefik auto-renews, but verify)
docker exec traefik cat /letsencrypt/acme.json | jq
```

## 10.3 Certificate Renewal

Traefik handles automatic renewal. Monitor with:

```bash
# Check certificate expiry date
echo | openssl s_client -servername finance.mmlogistix.bp0.work \
    -connect finance.mmlogistix.bp0.work:443 2>/dev/null | \
    openssl x509 -noout -dates
```

Alert if expiry < 7 days.

---

# 11. Environment Configuration

## 11.1 Environment Variables

Create `/opt/mmlogistix/.env`:

```bash
# =============================================================================
# AI Finance Operations Platform — Production Environment
# Copy from .env.example; fill all [REQUIRED] values.
# Authoritative variable reference: 14_Environment_and_Configuration_Reference.md
# ALL variables use the FINANCE_ prefix. Nested settings use __ delimiter.
# =============================================================================

# Application
FINANCE_APP_ENV=production
FINANCE_DEBUG=false
FINANCE_LOG_LEVEL=WARNING
FINANCE_HOST=0.0.0.0
FINANCE_PORT=8000
FINANCE_WORKERS=4

# Database (Supabase PostgreSQL)
FINANCE_DATABASE_URL=postgresql+asyncpg://postgres:<password>@db.ehsoeyfopazodvmpkkpy.supabase.co:5432/postgres
FINANCE_DATABASE__POOL_SIZE=20
FINANCE_DATABASE__MAX_OVERFLOW=10
POSTGRES_PASSWORD=<generate: openssl rand -base64 32>

# Redis
FINANCE_REDIS__HOST=redis
FINANCE_REDIS__PORT=6379
FINANCE_REDIS__DB=0
FINANCE_REDIS__PASSWORD=<generate: openssl rand -base64 32>

# Ollama / Hermes — see 14 §6.0 (legacy: 127.0.0.1:11434, qwen2.5:0.5b, no Hermes)
# Ollama defaults: http://ollama:11434, hermes3 — override in .env only if needed
FINANCE_HERMES_API_KEY=<generate: openssl rand -hex 32>   # same value as HERMES_API_KEY in compose (14 §6b.1)

# JWT & Authentication
FINANCE_JWT__SECRET=<generate: openssl rand -hex 32>
FINANCE_JWT__ALGORITHM=HS256
FINANCE_JWT__ACCESS_TOKEN_EXPIRE_MINUTES=15
FINANCE_JWT__REFRESH_TOKEN_EXPIRE_DAYS=7

# Mail — per-mailbox config in mail_gateway_config (Client Admin UI), not .env
# FINANCE_MAIL__POLL_ENABLED: set in docker-compose.yml gateway service only — must be true in production (14 §2.5, 11 §4.5)
# See 14 §7.3, env.example section 6

# Supabase
FINANCE_SUPABASE__URL=https://ehsoeyfopazodvmpkkpy.supabase.co
FINANCE_SUPABASE__SERVICE_KEY=<generate from Supabase dashboard>
FINANCE_SUPABASE__JWT_SECRET=<generate from Supabase dashboard>
FINANCE_SUPABASE__STORAGE_BUCKET=finance-attachments

# Encryption & Privacy
FINANCE_PRIVACY_ENCRYPTION_KEY=<generate: python scripts/generate-keys.py>
FINANCE_BACKUP_ENCRYPTION_KEY=<generate: python scripts/generate-keys.py>
FINANCE_HASH_SECRET=<generate: openssl rand -hex 32>

# Monitoring
FINANCE_PROMETHEUS__ENABLED=true
FINANCE_GRAFANA__ENABLED=true
FINANCE_GRAFANA__ADMIN_PASSWORD=<generate: openssl rand -base64 32>
GRAFANA_ADMIN_PASSWORD=<same value as FINANCE_GRAFANA__ADMIN_PASSWORD>

# Outbound SMTP relay (optional overrides — defaults bp0.work:465 per 14 §7b)
# Per-mailbox auth + From: mail_gateway_config via Client Admin UI — not .env
FINANCE_NOTIFICATION__ENABLED=true
FINANCE_SENDGRID__API_KEY=<sendgrid api key>

# Feature Flags
FINANCE_FEATURE__ENABLE_STP=true
FINANCE_FEATURE__ENABLE_AI_CLASSIFICATION=true
FINANCE_FEATURE__ENABLE_GUARDRAILS=true

# Rate Limiting
FINANCE_RATE_LIMIT__ENABLED=true

# Traefik & SSL
FINANCE_TRAEFIK__ENABLED=true
FINANCE_TRAEFIK__DASHBOARD_ENABLED=false
FINANCE_LETS_ENCRYPT_EMAIL=admin@bp0.work
```

> **Important:** The authoritative and complete variable list — including types, defaults, and generation commands — is `14_Environment_and_Configuration_Reference.md` §19 and the committed `env.example` at the repository root. Do **not** copy-paste this summary as a complete `.env`; use `cp .env.example .env` and fill in the `[REQUIRED]` values instead.

## 11.2 Secret Generation

```bash
#!/bin/bash
# /opt/mmlogistix/generate-secrets.sh
# Generates all required secrets for the .env file.
# Alternatively run: python scripts/generate-keys.py  (handles Fernet keys automatically)

echo "Generating secrets..."

# PostgreSQL password (consumed by supabase-db container as POSTGRES_PASSWORD)
POSTGRES_PASSWORD=$(openssl rand -base64 32)
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"

# JWT secret (256-bit) → FINANCE_JWT__SECRET
JWT_SECRET=$(openssl rand -hex 32)
echo "FINANCE_JWT__SECRET=$JWT_SECRET"

# Redis password → FINANCE_REDIS__PASSWORD
REDIS_PASSWORD=$(openssl rand -base64 32)
echo "FINANCE_REDIS__PASSWORD=$REDIS_PASSWORD"

# Hermes internal API key → FINANCE_HERMES_API_KEY
HERMES_KEY=$(openssl rand -hex 32)
echo "FINANCE_HERMES_API_KEY=$HERMES_KEY"

# Audit chain hash secret → FINANCE_HASH_SECRET
HASH_SECRET=$(openssl rand -hex 32)
echo "FINANCE_HASH_SECRET=$HASH_SECRET"

# Grafana admin password (set both variables to the same value)
GRAFANA_PASS=$(openssl rand -base64 32)
echo "FINANCE_GRAFANA__ADMIN_PASSWORD=$GRAFANA_PASS"
echo "GRAFANA_ADMIN_PASSWORD=$GRAFANA_PASS"

# Fernet encryption key for PII → FINANCE_PRIVACY_ENCRYPTION_KEY
# Requires Python cryptography library
PRIVACY_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "FINANCE_PRIVACY_ENCRYPTION_KEY=$PRIVACY_KEY"

# Backup encryption key → FINANCE_BACKUP_ENCRYPTION_KEY
BACKUP_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "FINANCE_BACKUP_ENCRYPTION_KEY=$BACKUP_KEY"

echo ""
echo "Copy the output above into your .env file."
echo "Store all secret values in your password manager."
echo "Note: POSTGRES_PASSWORD must match the password embedded in FINANCE_DATABASE_URL."
```

> **Preferred alternative:** Run `python scripts/generate-keys.py` instead. It generates all secrets above in one step and outputs them in `.env` paste format. See `14_Environment_and_Configuration_Reference.md` §11.2 for the script source.

---

# 12. Database Migrations

## 12.1 Alembic Setup

```bash
# Initialize Alembic (first time only)
cd /opt/mmlogistix/app
alembic init alembic

# Configure alembic.ini
# sqlalchemy.url = postgresql+asyncpg://...
```

## 12.2 Migration Execution

```bash
# Check current revision
alembic current

# Check if migrations needed
alembic check

# Run migrations (upgrade to latest)
alembic upgrade head

# Or run in Docker
docker exec -it fastapi alembic upgrade head

# Verify
alembic history --verbose
```

## 12.3 Phase-Based Migration Order

| Phase | Migrations | Description |
|-------|-----------|-------------|
| Phase 2 | 001–006 | Users, roles, permissions, refresh tokens, seed roles & permissions |
| Phase 3 | 007–009 | Emails, attachments, mail gateway config |
| Phase 4 | 010–024 | Counterparty, cases, workflow engine, policies, approvals (core) |
| Phase 5 | 025–026 | Seed default policies, queue messages |
| Phase 6–7 | 026b | Purchase orders table (AP Worker prerequisite) |
| Phase 8 | 027–033 | Chart of accounts, journal entries, reconciliation tables |
| Phase 9 | 034–036 | Notification templates, user preferences, seed notification templates |
| Phase 10 | 037–039 | Audit logs, system settings, audit log partitioning |
| Phase 11 | 039b + 040–044 | ENUM extension (`expense_claim` case type) + expense claims, line items, expense policies, permissions, seed (see `19` §11) |

> **Authoritative source:** `06_Database_Schema_Design.md` §18.4 and `16_Migration_and_ORM_Specification.md` §10 are the single sources of truth for migration numbering and file names. This table is a deployment summary only.

## 12.4 Migration Safety Checklist

Before running any migration:

| Check | Command | Expected Result |
|-------|---------|-----------------|
| Database is reachable | `pg_isready -h localhost -p 5432` | `localhost:5432 - accepting connections` |
| Backup exists | `ls -la /opt/mmlogistix/backups/database/` | File < 24h old |
| No long-running transactions | `SELECT count(*) FROM pg_stat_activity WHERE state = 'active';` | 0-2 |
| Disk space > 20% free | `df -h` | > 20% free |
| Migration is tested locally | `alembic upgrade +1` in staging | Success |

---

# 13. CI/CD Pipeline

## 13.1 Pipeline Stages

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Build   │──▶│   Test   │──▶│  Stage   │──▶│  Deploy  │──▶│  Verify  │
│          │   │          │   │          │   │          │   │          │
│ • Docker │   │ • Unit   │   │ • Migrations│ • Pull  │   │ • Health │
│   build  │   │ • Integration│ • Smoke  │   │   image │   │ • E2E    │
│ • Lint   │   │ • Security   │ • Policy │   │ • Up    │   │ • Rollback│
│   check  │   │   scan    │   │   validate   │   compose │   │   ready  │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

## 13.2 GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Lint
        run: |
          ruff check .
          mypy app/
      
      - name: Unit tests
        run: pytest tests/unit -v --cov=app --cov-report=xml
      
      - name: Build Docker image
        run: docker build -t mmlogistix/finance-api:${{ github.sha }} .
      
      - name: Push to registry
        run: |
          docker login ghcr.io -u ${{ github.actor }} -p ${{ secrets.GITHUB_TOKEN }}
          docker tag mmlogistix/finance-api:${{ github.sha }} ghcr.io/mmlogistix/finance-api:${{ github.sha }}
          docker push ghcr.io/mmlogistix/finance-api:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/mmlogistix
            
            # Backup before deploy
            ./scripts/backup.sh pre-deploy
            
            # Pull new image
            docker pull ghcr.io/mmlogistix/finance-api:${{ github.sha }}
            
            # Update docker-compose with new tag
            sed -i "s|image:.*finance-api.*|image: ghcr.io/mmlogistix/finance-api:${{ github.sha }}|" docker-compose.yml
            
            # Run migrations
            docker compose run --rm fastapi alembic upgrade head
            
            # Rolling update
            docker compose up -d --no-deps --build fastapi
            
            # Verify
            sleep 10
            curl -f http://localhost:8000/health || exit 1
            curl -f http://localhost:8000/ready || exit 1
            
            # Cleanup old images
            docker image prune -f
```

## 13.3 Deployment Verification

```bash
#!/bin/bash
# /opt/mmlogistix/scripts/verify-deploy.sh

echo "=== Deployment Verification ==="

# 1. Container status
echo "1. Container status:"
docker compose ps

# 2. Health checks
echo -e "\n2. Health endpoints:"
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/ready | jq .

# 3. Database connectivity
echo -e "\n3. Database connectivity:"
docker compose exec -T supabase-db pg_isready -U postgres

# 4. Redis connectivity
echo -e "\n4. Redis connectivity:"
docker compose exec -T redis redis-cli ping

# 5. Ollama availability
echo -e "\n5. Ollama availability:"
curl -s http://localhost:11434/api/tags | jq '.models | length'

# 6. SSL certificate
echo -e "\n6. SSL certificate:"
echo | openssl s_client -connect finance.mmlogistix.bp0.work:443 -servername finance.mmlogistix.bp0.work 2>/dev/null | openssl x509 -noout -dates

# 7. API response time
echo -e "\n7. API response time:"
curl -o /dev/null -s -w "Total time: %{time_total}s\nHTTP code: %{http_code}\n" https://finance.mmlogistix.bp0.work/health

echo -e "\n=== Verification Complete ==="
```

## 13.4 Rollback Procedure

```bash
#!/bin/bash
# /opt/mmlogistix/scripts/rollback.sh
# Usage: ./rollback.sh <previous-image-tag>

PREVIOUS_TAG=${1:-"stable"}

echo "Rolling back to image: $PREVIOUS_TAG"

# 1. Update docker-compose
cd /opt/mmlogistix
sed -i "s|image:.*finance-api.*|image: ghcr.io/mmlogistix/finance-api:$PREVIOUS_TAG|" docker-compose.yml

# 2. Restart with previous image
docker compose up -d --no-deps fastapi

# 3. Verify
echo "Waiting for service to start..."
sleep 15

if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "Rollback successful — health check passed"
    
    # Tag the rolled-back image as stable
    docker tag ghcr.io/mmlogistix/finance-api:$PREVIOUS_TAG ghcr.io/mmlogistix/finance-api:stable
else
    echo "Rollback failed — health check failed!"
    echo "Investigate immediately. Previous container may still be running."
    docker compose logs --tail=50 fastapi
    exit 1
fi
```

---

# 14. Monitoring & Alerting

## 14.1 Health Endpoint Monitoring

```bash
# /opt/mmlogistix/scripts/health-monitor.sh
# Run via cron every 1 minute

#!/bin/bash
HEALTH_URL="http://localhost:8000/health"
READY_URL="http://localhost:8000/ready"
ALERT_WEBHOOK="${ALERT_WEBHOOK_URL}"  # Slack/Teams webhook

check_endpoint() {
    local url=$1
    local name=$2
    
    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url")
    
    if [ "$response" != "200" ]; then
        echo "$(date): $name check FAILED (HTTP $response)"
        
        # Send alert (rate limited: max 1 alert per 15 min)
        if [ ! -f "/tmp/alert_${name}.sent" ] || \
           [ "$(find /tmp/alert_${name}.sent -mmin +15)" ]; then
            curl -s -X POST "$ALERT_WEBHOOK" \
                -H "Content-Type: application/json" \
                -d "{\"text\":\"ALERT: $name check failed (HTTP $response) on $(hostname)\"}" \
                > /dev/null 2>&1
            touch "/tmp/alert_${name}.sent"
        fi
        
        return 1
    fi
    
    # Clear alert state on success
    rm -f "/tmp/alert_${name}.sent"
    return 0
}

check_endpoint "$HEALTH_URL" "health"
check_endpoint "$READY_URL" "ready"
```

Cron entry:
```
* * * * * /opt/mmlogistix/scripts/health-monitor.sh >> /opt/mmlogistix/logs/health-monitor.log 2>&1
```

## 14.2 Key Metrics and Alert Thresholds

| Metric | Prometheus Expression | Warning | Critical | Action |
|--------|----------------------|---------|----------|--------|
| API response time p95 | `histogram_quantile(0.95, http_request_duration_seconds_bucket)` | > 2s | > 5s | Alert + investigate slow queries |
| API error rate (5xx) | `rate(http_requests_total{status=~"5.."}[5m])` | > 1% | > 5% | Alert + potential rollback |
| Database connections active | `db_connections_active / db_connections_max` | > 70% | > 90% | Alert + connection tuning |
| Redis memory usage | `redis_memory_used_bytes / redis_memory_max_bytes` | > 70% | > 90% | Alert + memory analysis |
| Ollama inference time p95 | `histogram_quantile(0.95, ai_inference_duration_seconds_bucket)` | > 10s | > 30s | Alert + check CPU/model |
| Ollama queue depth | `queue_depth{queue="ollama_pending"}` | > 5 | > 20 | Alert + circuit break consideration |
| Disk space free | `node_filesystem_avail_bytes / node_filesystem_size_bytes` | < 30% | < 10% | Alert + cleanup/expand |
| SSL certificate expiry | `ssl_certificate_expiry_seconds` | < 14 days | < 7 days | Alert + manual renewal check |
| Failed login attempts | `rate(auth_failures_total[1m])` | > 10/min | > 50/min | Alert + fail2ban review |
| Case processing backlog | `queue_depth{queue="accounts_queue"}` | > 50 | > 200 | Alert + worker scale-up (see `17` §2.8) |
| Dead letter queue depth | `queue_depth{queue="dead_letter_queue"}` | > 10 | > 50 | Alert — indicates bug; do not auto-scale |
| Worker heartbeat missing | `time() - worker_heartbeat_timestamp` | > 90s | — | Auto-restart + alert |
| Approval SLA breach rate | `rate(approval_sla_breaches_total[1h])` | > 5/hr | > 20/hr | Alert + escalation review |

### Prometheus Alert Rules

```yaml
# /opt/mmlogistix/prometheus/alert-rules.yml

groups:
  - name: mmlogistix-application
    rules:
      - alert: APIHighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "API error rate above 5%"
          description: "5xx rate is {{ $value | humanizePercentage }} over last 5 minutes."

      - alert: APIHighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "API p95 latency above 5 seconds"
          description: "p95 latency is {{ $value }}s."

      - alert: QueueBacklogWarning
        expr: queue_depth{queue="accounts_queue"} > 50
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "accounts_queue backlog growing"
          description: "Queue depth is {{ $value }}. Consider adding worker replicas."

      - alert: QueueBacklogCritical
        expr: queue_depth{queue="accounts_queue"} > 200
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "accounts_queue critically overloaded"
          description: "Queue depth is {{ $value }}. Scale workers immediately."

      - alert: DeadLetterAccumulating
        expr: queue_depth{queue="dead_letter_queue"} > 10
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Dead letter queue accumulating"
          description: "{{ $value }} messages in dead letter queue. Indicates a recurring processing error."

      - alert: WorkerHeartbeatMissing
        expr: (time() - worker_heartbeat_timestamp) > 90
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Worker heartbeat missing"
          description: "Worker {{ $labels.worker_name }} has not sent a heartbeat for over 90 seconds."

      - alert: OllamaHighLatency
        expr: histogram_quantile(0.95, ai_inference_duration_seconds_bucket) > 30
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "Ollama inference critically slow"
          description: "AI inference p95 latency is {{ $value }}s. Workers may be timing out."

      - alert: HermesCircuitOpen
        expr: hermes_circuit_breaker_state == 2
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Hermes circuit breaker is OPEN"
          description: "AI classification and extraction are unavailable. Cases will fail to process."

  - name: mmlogistix-infrastructure
    rules:
      - alert: DiskSpaceLow
        expr: node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} < 0.10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Disk space critically low"
          description: "Only {{ $value | humanizePercentage }} disk space remaining on {{ $labels.instance }}."

      - alert: DatabaseConnectionsHigh
        expr: db_connections_active / db_connections_max > 0.90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool near exhaustion"
          description: "{{ $value | humanizePercentage }} of connections in use."

      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Redis memory near limit"
          description: "Redis is using {{ $value | humanizePercentage }} of available memory."

      - alert: SSLCertExpiringSoon
        expr: ssl_certificate_expiry_seconds < 604800
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "SSL certificate expires in less than 7 days"
          description: "Certificate for {{ $labels.domain }} expires in {{ $value | humanizeDuration }}."

      - alert: BackupFailed
        expr: time() - backup_last_success_timestamp > 86400
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Database backup has not succeeded in 24 hours"
          description: "Last successful backup was {{ $value | humanizeDuration }} ago."
```

### Alertmanager Routing

Alerts are sent to the operations Slack/Teams webhook configured in `ALERT_WEBHOOK_URL`. Critical alerts page immediately; warnings batch into a 15-minute digest.

```yaml
# /opt/mmlogistix/prometheus/alertmanager.yml
route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'ops-webhook'
  routes:
    - match:
        severity: critical
      group_wait: 0s
      repeat_interval: 30m
      receiver: 'ops-webhook'
    - match:
        severity: warning
      group_wait: 15m
      repeat_interval: 4h
      receiver: 'ops-webhook'

receivers:
  - name: 'ops-webhook'
    webhook_configs:
      - url: '${ALERT_WEBHOOK_URL}'
        send_resolved: true
```

## 14.3 Log Aggregation

```yaml
# docker-compose logging configuration
# All services use json-file driver with rotation

logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "10"
    labels: "service,environment"
    tag: "{{.ImageName}}|{{.Name}}|{{.ImageFullID}}|{{.FullID}}"
```

View logs:
```bash
# All services
docker compose logs --tail=100 -f

# Specific service
docker compose logs --tail=100 -f fastapi

# Since specific time
docker compose logs --since=2026-05-10T14:00:00 fastapi

# Search for errors
docker compose logs fastapi 2>&1 | grep -i "error\|exception\|critical"
```

## 14.4 Application Metrics Endpoint

```python
# Prometheus metrics exposed at /metrics
# Key metrics:

# Request latency histogram
http_request_duration_seconds_bucket{method="POST",path="/cases",status="201",le="0.1"}

# Request count
http_requests_total{method="POST",path="/cases",status="201"}

# Active cases by status
cases_total{status="pending_approval"} 142

# AI inference time
ai_inference_duration_seconds{model="hermes-classifier-v2"} 2.45

# Approval SLA breaches
approval_sla_breaches_total{tier="2"} 3

# Worker queue depth
queue_depth{queue="accounts_queue"} 8

# Database connection pool
db_connections_active 12
db_connections_idle 8
```

---

# 15. Backup & Recovery

## 15.1 Backup Strategy

| Data | Method | Frequency | Local Retention | Offsite (Wasabi) Retention |
|------|--------|-----------|----------------|---------------------------|
| PostgreSQL database | `pg_dump` | Daily at 02:00 SGT | 30 days | 30 days (lifecycle rule) |
| PostgreSQL WAL | Continuous archiving | Real-time | 7 days | 7 days |
| Redis RDB | BGSAVE | Hourly | 24 hours | 7 days (lifecycle rule) |
| Attachments | Supabase Storage sync → `bp0workacc/backups/attachments/` | Daily | — | 90 days (lifecycle rule) |
| Finance daily log export | `POST /internal/jobs/finance-daily-log` | Daily 21:00 SGT | — | 7 years (logs prefix; align with audit retention) |
| Configuration | Git repository | On change | Permanent | Git remote (permanent) |

All offsite storage uses Wasabi Hot Cloud Storage (`ap-southeast-1`). See §15.4 for Wasabi configuration, bucket structure, and lifecycle rules.

## 15.2 Database Backup Script

```bash
#!/bin/bash
# /opt/mmlogistix/scripts/backup-database.sh

BACKUP_DIR="/opt/mmlogistix/backups/database"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="mmlogistix_db_${DATE}.sql.gz"
RETENTION_DAYS=30

# Create backup
docker compose exec -T supabase-db pg_dump \
    -U postgres \
    -d postgres \
    --clean \
    --if-exists \
    --verbose \
    2>/dev/null | gzip > "${BACKUP_DIR}/${BACKUP_FILE}"

# Verify backup
if [ -f "${BACKUP_DIR}/${BACKUP_FILE}" ] && [ -s "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
    echo "$(date): Backup successful — ${BACKUP_FILE} (${SIZE})"
    
    # Upload to Wasabi offsite storage
    /opt/mmlogistix/scripts/wasabi-upload.sh "${BACKUP_DIR}/${BACKUP_FILE}" "backups/database/"
    
    # Clean old local backups
    find "$BACKUP_DIR" -name "mmlogistix_db_*.sql.gz" -mtime +$RETENTION_DAYS -delete
    echo "$(date): Removed backups older than $RETENTION_DAYS days"
else
    echo "$(date): Backup FAILED — file missing or empty"
    # Send alert
    exit 1
fi
```

Cron entry:
```
0 2 * * * /opt/mmlogistix/scripts/backup-database.sh >> /opt/mmlogistix/logs/backup.log 2>&1
```

## 15.3 Redis Backup Script

```bash
#!/bin/bash
# /opt/mmlogistix/scripts/backup-redis.sh

BACKUP_DIR="/opt/mmlogistix/backups/redis"
DATE=$(date +%Y%m%d_%H%M%S)

# Trigger BGSAVE
docker compose exec -T redis redis-cli BGSAVE

# Wait for save to complete
sleep 5

# Copy RDB file
docker compose cp redis:/data/dump.rdb "${BACKUP_DIR}/dump_${DATE}.rdb"

# Upload to Wasabi
/opt/mmlogistix/scripts/wasabi-upload.sh "${BACKUP_DIR}/dump_${DATE}.rdb" "backups/redis/"

# Clean old backups (keep 24 hours locally)
find "$BACKUP_DIR" -name "dump_*.rdb" -mtime +1 -delete

echo "$(date): Redis backup completed"
```

## 15.4 Wasabi object storage (`bp0workacc`)

All **backups**, **daily finance log exports**, and **per-transaction document archives** use the bp0.work accounts Wasabi bucket. Supabase Storage (`finance-attachments`) remains the **hot** store for the running app; Wasabi is the **authoritative long-term** store for logs, backups, and transaction files (`06` §7.5, `14` §2.9).

**Application (`0.13.8-wasabi-attachment-archive`):** When `FINANCE_WASABI__ARCHIVE_ON_INTAKE=true`, `WasabiArchiveService` (`accfin/app/services/wasabi_archive.py`) uploads local attachments from `FINANCE_MAIL__ATTACHMENT_STORAGE_PATH/{email_id}/{filename}` to `s3://bp0workacc/transactions/{case_number}/{filename}` via boto3 after intake classification links the email to a case (`CaseService.on_case_linked_to_email`). Sets `email_attachments.wasabi_archive_path` to the object key.

### Wasabi Configuration

| Setting | Value |
|---------|-------|
| Provider | Wasabi Hot Cloud Storage |
| Region | `ap-southeast-1` (Singapore) |
| Bucket | **`bp0workacc`** |
| Bucket access | Private — no public ACL |
| Encryption in transit | TLS 1.3 (Wasabi endpoint enforced) |
| Encryption at rest | Wasabi server-side encryption (SSE) enabled on bucket |
| Versioning | Enabled — retain 5 versions per object |
| Object Lock | Governance mode on `backups/database/` dumps (90-day minimum) |

### Required Environment Variables

Add to `/opt/bp0work/accounting/accfin/.env` (see `14` §2.9):

```bash
FINANCE_WASABI__ACCESS_KEY_ID=your_wasabi_access_key
FINANCE_WASABI__SECRET_ACCESS_KEY=your_wasabi_secret_key
FINANCE_WASABI__BUCKET=bp0workacc
FINANCE_WASABI__ENDPOINT_URL=https://s3.ap-southeast-1.wasabisys.com
FINANCE_WASABI__REGION=ap-southeast-1
FINANCE_WASABI__PREFIX_LOGS=logs/
FINANCE_WASABI__PREFIX_BACKUPS=backups/
FINANCE_WASABI__PREFIX_TRANSACTIONS=transactions/
```

Legacy shell scripts may use `WASABI_*` aliases — map to the same bucket and prefixes.

Credentials are rotated quarterly (see §18.3). IAM policy MUST allow `s3:*` only on `arn:aws:s3:::bp0workacc` and `arn:aws:s3:::bp0workacc/*`.

### Wasabi Upload Script

```bash
#!/bin/bash
# /opt/mmlogistix/scripts/wasabi-upload.sh
# Usage: ./wasabi-upload.sh <local-file> <remote-prefix>
# Example: ./wasabi-upload.sh /opt/mmlogistix/backups/db.sql.gz backups/database/

LOCAL_FILE=$1
REMOTE_PREFIX=$2

if [ -z "$LOCAL_FILE" ] || [ -z "$REMOTE_PREFIX" ]; then
    echo "Usage: $0 <local-file> <remote-prefix>"
    exit 1
fi

# Load env if not already set
source /opt/mmlogistix/.env 2>/dev/null || true

FILENAME=$(basename "$LOCAL_FILE")
REMOTE_KEY="${REMOTE_PREFIX}${FILENAME}"

echo "$(date): Uploading ${FILENAME} to Wasabi s3://${WASABI_BUCKET}/${REMOTE_KEY}"

# Use AWS CLI (compatible with Wasabi S3 API)
AWS_ACCESS_KEY_ID="$WASABI_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$WASABI_SECRET_ACCESS_KEY" \
aws s3 cp "$LOCAL_FILE" \
    "s3://${WASABI_BUCKET}/${REMOTE_KEY}" \
    --endpoint-url "$WASABI_ENDPOINT_URL" \
    --region "$WASABI_REGION" \
    --sse AES256 \
    --no-progress

if [ $? -eq 0 ]; then
    echo "$(date): Upload successful — s3://${WASABI_BUCKET}/${REMOTE_KEY}"
else
    echo "$(date): Upload FAILED — ${FILENAME}"
    # Alert operations
    curl -s -X POST "${ALERT_WEBHOOK_URL}" \
        -H "Content-Type: application/json" \
        -d "{\"text\":\"ALERT: Wasabi backup upload failed for ${FILENAME} on $(hostname)\"}" \
        > /dev/null 2>&1
    exit 1
fi
```

### Bucket Structure

```
bp0workacc/
├── logs/
│   ├── finance_daily_2026-05-19.csv       # finance_activity_log export (9pm SGT job; RFC 4180)
│   └── ...
├── backups/
│   ├── database/
│   │   ├── bp0work_db_20260519_020001.sql.gz
│   │   └── ...  (30 days retention via lifecycle rule)
│   ├── redis/
│   │   ├── dump_20260519_020005.rdb
│   │   └── ...  (7 days retention)
│   └── attachments/
│       └── ...  (synced from Supabase Storage — 90 days retention)
└── transactions/
    └── CAS-2026-0001542/                  # transaction number = cases.case_number
        ├── supplier_invoice.pdf
        ├── receipt.jpg
        └── ...
```

### Wasabi Lifecycle Rules

Configure in Wasabi console or via AWS CLI after bucket creation:

```bash
# Apply lifecycle policy
AWS_ACCESS_KEY_ID="$WASABI_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$WASABI_SECRET_ACCESS_KEY" \
aws s3api put-bucket-lifecycle-configuration \
    --bucket bp0workacc \
    --endpoint-url "$WASABI_ENDPOINT_URL" \
    --lifecycle-configuration '{
        "Rules": [
            {
                "ID": "database-retention",
                "Filter": {"Prefix": "backups/database/"},
                "Status": "Enabled",
                "Expiration": {"Days": 30},
                "NoncurrentVersionExpiration": {"NoncurrentDays": 7}
            },
            {
                "ID": "redis-retention",
                "Filter": {"Prefix": "backups/redis/"},
                "Status": "Enabled",
                "Expiration": {"Days": 7}
            },
            {
                "ID": "attachments-retention",
                "Filter": {"Prefix": "backups/attachments/"},
                "Status": "Enabled",
                "Expiration": {"Days": 90}
            },
            {
                "ID": "logs-retention",
                "Filter": {"Prefix": "logs/"},
                "Status": "Enabled",
                "Expiration": {"Days": 2555}
            },
            {
                "ID": "transactions-retention",
                "Filter": {"Prefix": "transactions/"},
                "Status": "Enabled",
                "Expiration": {"Days": 2555}
            }
        ]
    }'
```

### Wasabi Restore Procedure

```bash
#!/bin/bash
# /opt/mmlogistix/scripts/wasabi-restore.sh
# Usage: ./wasabi-restore.sh <remote-key>
# Example: ./wasabi-restore.sh database/mmlogistix_db_20260519_020001.sql.gz

REMOTE_KEY=$1
LOCAL_DIR="/opt/mmlogistix/backups/restore"
mkdir -p "$LOCAL_DIR"

source /opt/mmlogistix/.env 2>/dev/null || true

FILENAME=$(basename "$REMOTE_KEY")
LOCAL_FILE="${LOCAL_DIR}/${FILENAME}"

echo "$(date): Downloading s3://${WASABI_BUCKET}/${REMOTE_KEY}"

AWS_ACCESS_KEY_ID="$WASABI_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$WASABI_SECRET_ACCESS_KEY" \
aws s3 cp \
    "s3://${WASABI_BUCKET}/${REMOTE_KEY}" \
    "$LOCAL_FILE" \
    --endpoint-url "$WASABI_ENDPOINT_URL" \
    --region "$WASABI_REGION"

if [ $? -eq 0 ]; then
    echo "$(date): Downloaded to ${LOCAL_FILE}"
    echo "Run: ./scripts/restore-database.sh ${LOCAL_FILE}"
else
    echo "$(date): Download FAILED"
    exit 1
fi
```

### Backup Verification (Monthly)

```bash
#!/bin/bash
# /opt/mmlogistix/scripts/verify-wasabi-backup.sh
# Run monthly — verifies most recent Wasabi database backup is intact

source /opt/mmlogistix/.env 2>/dev/null || true

# List most recent backup
LATEST=$(AWS_ACCESS_KEY_ID="$WASABI_ACCESS_KEY_ID" \
    AWS_SECRET_ACCESS_KEY="$WASABI_SECRET_ACCESS_KEY" \
    aws s3 ls "s3://${WASABI_BUCKET}/database/" \
    --endpoint-url "$WASABI_ENDPOINT_URL" \
    --region "$WASABI_REGION" | sort | tail -1 | awk '{print $4}')

echo "Verifying: $LATEST"

# Download to temp location
./scripts/wasabi-restore.sh "database/$LATEST"
RESTORE_FILE="/opt/mmlogistix/backups/restore/$LATEST"

# Verify it's a valid gzip
gunzip -t "$RESTORE_FILE" && echo "PASS: gzip integrity OK" || echo "FAIL: gzip corrupt"

# Check it contains expected SQL
gunzip -c "$RESTORE_FILE" | head -20 | grep -q "PostgreSQL database dump" \
    && echo "PASS: SQL header found" \
    || echo "FAIL: SQL header not found"

# Clean up
rm -f "$RESTORE_FILE"
echo "Backup verification complete"
```

Cron entry (monthly verification):
```
0 3 1 * * /opt/mmlogistix/scripts/verify-wasabi-backup.sh >> /opt/mmlogistix/logs/backup-verify.log 2>&1
```

## 15.5 Database Restore Procedure

```bash
#!/bin/bash
# /opt/mmlogistix/scripts/restore-database.sh
# Usage: ./restore-database.sh <backup-file>

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    exit 1
fi

echo "WARNING: This will REPLACE the current database!"
echo "Backup file: $BACKUP_FILE"
read -p "Type 'RESTORE' to continue: " confirm

if [ "$confirm" != "RESTORE" ]; then
    echo "Restore cancelled"
    exit 0
fi

# 1. Stop application (prevent writes)
docker compose stop fastapi

# 2. Pre-restore backup
./scripts/backup-database.sh

# 3. Drop and recreate database
docker compose exec -T supabase-db psql -U postgres -c "DROP DATABASE IF EXISTS postgres_backup;"
docker compose exec -T supabase-db psql -U postgres -c "CREATE DATABASE postgres_backup TEMPLATE postgres;"
docker compose exec -T supabase-db psql -U postgres -c "DROP DATABASE postgres;"
docker compose exec -T supabase-db psql -U postgres -c "CREATE DATABASE postgres;"

# 4. Restore from backup
gunzip -c "$BACKUP_FILE" | docker compose exec -T supabase-db psql -U postgres -d postgres

# 5. Verify
ROW_COUNT=$(docker compose exec -T supabase-db psql -U postgres -t -c "SELECT count(*) FROM cases;" | tr -d ' ')
echo "Restored database has $ROW_COUNT cases"

# 6. Restart application
docker compose start fastapi

# 7. Verify health
curl -f http://localhost:8000/health

echo "Restore completed"
```

---

# 16. Disaster Recovery

## 16.1 Recovery Objectives

| Metric | Target | Measurement |
|--------|--------|-------------|
| **RPO (Recovery Point Objective)** | 1 hour | Maximum data loss acceptable |
| **RTO (Recovery Time Objective)** | 4 hours | Maximum downtime acceptable |
| **RTO (Database)** | 2 hours | Database restore time |
| **RTO (Application)** | 1 hour | Application redeploy time |

## 16.2 Disaster Scenarios

### Scenario 1: Database Corruption

```
1. Stop application     → docker compose stop fastapi
2. Assess corruption    → docker compose exec supabase-db psql -c "..."
3. Restore from backup  → ./scripts/restore-database.sh <latest-valid-backup>
4. Verify data          → Run health checks, spot-check cases
5. Restart application  → docker compose start fastapi
6. Notify users         → If > 1 hour downtime
```

### Scenario 2: Complete VPS Failure

```
1. Provision new VPS (same or different host)
2. Install Docker and prerequisites (Section 2)
3. Restore configuration from Git
4. Restore database from latest cloud backup
5. Restore attachments from cloud storage
6. Deploy application (docker compose up -d)
7. Verify SSL, DNS, health endpoints
8. Notify users
```

### Scenario 3: Ollama AI Service Down

```
1. Circuit breaker opens automatically (application layer)
2. System falls back to rule-based classification
3. Alert operations team
4. Investigate: docker compose logs ollama
5. Common fixes:
   - Restart: docker compose restart ollama
   - OOM: Check memory, reduce model quantization
   - Model corruption: Re-pull model
6. Verify: curl http://localhost:11434/api/tags
7. Circuit breaker closes after 3 consecutive successes
```

### Scenario 4: Security Breach

```
1. Isolate affected containers: docker compose stop <service>
2. Preserve logs: cp /opt/mmlogistix/logs /opt/mmlogistix/logs-incident-$(date +%s)
3. Rotate all secrets:
   - JWT secret
   - Database password
   - Redis password
   - API keys
4. Review audit logs for unauthorized access
5. Patch vulnerability
6. Redeploy with rotated secrets
7. Notify stakeholders per BRD Section 14
```

## 16.3 DR Testing Schedule

| Test | Frequency | Last Tested | Next Test |
|------|-----------|-------------|-----------|
| Database restore from backup | Monthly | — | 1st of month |
| Full VPS rebuild from scratch | Quarterly | — | Jan/Apr/Jul/Oct |
| Ollama failover to rule-based | Monthly | — | 15th of month |
| SSL certificate renewal | Continuous | — | Auto (monitor) |
| Secret rotation | Quarterly | — | Jan/Apr/Jul/Oct |

---

# 17. Operational Procedures

## 17.1 Daily Checks

```bash
#!/bin/bash
# /opt/mmlogistix/scripts/daily-check.sh
# Run every morning at 08:00 SGT

echo "=== Daily Operations Check — $(date) ==="

# 1. System resources
echo "1. System resources:"
echo "   CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
echo "   RAM: $(free -h | grep Mem | awk '{print $3"/"$2}')"
echo "   Disk: $(df -h /opt | tail -1 | awk '{print $5}') used"

# 2. Container status
echo -e "\n2. Container status:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"

# 3. Case processing status
echo -e "\n3. Case processing:"
docker compose exec -T supabase-db psql -U postgres -c "
    SELECT status, count(*) 
    FROM cases 
    WHERE created_at > NOW() - INTERVAL '24 hours'
    GROUP BY status;
"

# 4. Approval queue
echo -e "\n4. Approval queue:"
docker compose exec -T supabase-db psql -U postgres -c "
    SELECT tier, status, count(*) 
    FROM approvals 
    WHERE created_at > NOW() - INTERVAL '24 hours'
    GROUP BY tier, status;
"

# 5. AI inference metrics
echo -e "\n5. AI metrics (last 24h):"
docker compose exec -T supabase-db psql -U postgres -c "
    SELECT 
        classification_metadata->>'model' as model,
        count(*) as inferences,
        avg((classification_metadata->>'inference_time_ms')::float)::int as avg_ms
    FROM cases
    WHERE created_at > NOW() - INTERVAL '24 hours'
    GROUP BY model;
"

# 6. Errors in last 24h
echo -e "\n6. Errors (last 24h):"
docker compose logs --since=24h fastapi 2>&1 | grep -ci "error\|exception" || echo "   0 errors found"

echo -e "\n=== Daily Check Complete ==="
```

## 17.2 Scaling Operations

### Vertical Scaling (Same VPS, more resources)

```bash
# 1. Resize VPS in Hostinger control panel
# 2. Update resource limits in docker-compose.yml
deploy:
  resources:
    limits:
      cpus: "4.0"      # Increase
      memory: 8G       # Increase

# 3. Restart affected service
docker compose up -d --no-deps fastapi
```

### Horizontal Scaling (Worker instances)

```bash
# Scale FastAPI workers
docker compose up -d --scale fastapi=2

# Note: Requires load balancer configuration in Traefik
# For single-host, vertical scaling is preferred
```

## 17.3 Log Rotation

```bash
# Manual log cleanup
docker system prune --volumes -f
find /opt/mmlogistix/logs -name "*.log" -size +100M -exec gzip {} \;
find /opt/mmlogistix/logs -name "*.gz" -mtime +30 -delete
```

## 17.4 Scheduled Maintenance Window

| Maintenance | Schedule | Duration | User Impact |
|-------------|----------|----------|-------------|
| Database backup | Daily 02:00 SGT | 5-30 min | None (online backup) |
| Log rotation | Daily 03:00 SGT | 2 min | None |
| OS updates | Sunday 04:00 SGT | 15-30 min | Brief API unavailability |
| Ollama model updates | Monthly 1st Sat 06:00 | 10-30 min | AI processing may queue |
| SSL renewal check | Daily | < 1 min | None |
| Full DR test | Quarterly | 2-4 hours | Plan for maintenance window |
| Finance activity log email | Daily **21:00 SGT** (9pm) | 1 min | None — digest to CFO (`cfo.mmlogistix`) |
| GL cutoff reminders | Daily **08:00 SGT** | 1 min | None — SMTP to `gl_cutoff_reminders` recipients |

## 17.5 Finance activity log — daily digest (9pm SGT)

Sends compiled `finance_activity_log` rows for the Singapore business day to the CFO / Finance Director (`cfo.mmlogistix@bp0.work`). **HTTP contract:** `05` §19.1 `POST /internal/jobs/finance-daily-log`. Spec: `17` §10.7, `01` §6.8.5.

**Schedule:** `21:00 Asia/Singapore` every day. In UTC (SGT = UTC+8): **13:00 UTC** → cron `0 13 * * *`.

**Implementation options:**

1. **APScheduler** job inside FastAPI or a dedicated `scheduler` container.
2. **systemd timer** on the VPS calling a script.

```bash
# Example: systemd timer (host)
# /etc/systemd/system/finance-daily-log.timer
[Timer]
OnCalendar=*-*-* 21:00:00
Timezone=Asia/Singapore
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
# Invoke API or script
curl -sS -X POST \
  -H "Authorization: Bearer ${FINANCE_INTERNAL_CRON__TOKEN}" \
  -H "X-Request-ID: $(uuidgen)" \
  http://fastapi:8000/internal/jobs/finance-daily-log
```

**Env:** `FINANCE_INTERNAL_CRON__TOKEN` (required), `FINANCE_DAILY_LOG_RECIPIENT` (default `cfo.mmlogistix@bp0.work`), `FINANCE_DAILY_LOG_TIMEZONE=Asia/Singapore` (`14` §2, `05` §19.1).

**Verify:** After deploy, check `system_settings.last_finance_log_sent_at` and inbox at `cfo` for template `finance.daily_log`.

## 17.6 GL cutoff reminders — daily (8am SGT)

Sends reminder emails to active `gl_cutoff_reminders` recipients when an open period’s `gl_cutoff_date` is 7, 3, or 1 days away, or **today**. **HTTP contract:** `05` §19.2 `POST /api/internal/jobs/gl-cutoff-reminders`.

**Schedule:** `08:00 Asia/Singapore` every day. In UTC (SGT = UTC+8): **00:00 UTC** → cron `0 0 * * *`.

```bash
curl -sS -X POST \
  -H "Authorization: Bearer ${FINANCE_INTERNAL_CRON__TOKEN}" \
  -H "X-Request-ID: $(uuidgen)" \
  http://fastapi:8000/api/internal/jobs/gl-cutoff-reminders
```

**Verify:** `finance_activity_log` rows with `action = gl_cutoff_reminder_sent`; recipient inbox; Client Admin dashboard “GL reminder recipients” check passes when ≥1 active recipient.

---

# 18. Security Hardening

## 18.1 Host-Level Security

```bash
# SSH hardening
sudo sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/#MaxAuthTries 6/MaxAuthTries 3/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Automatic security updates
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# Firewall (already configured in Section 2)
sudo ufw status verbose

# Disable unused services
sudo systemctl disable --now snapd
```

## 18.2 Container Security

```yaml
# Security options applied to all containers
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE  # Only if binding to port < 1024
read_only: true
tmpfs:
  - /tmp:noexec,nosuid,size=100m
```

## 18.3 Secret Management

| Secret | Storage | Rotation Frequency |
|--------|---------|-------------------|
| PostgreSQL password | `.env` file (600 permissions) | Quarterly |
| JWT secret | `.env` file | Quarterly |
| Redis password | `.env` file | Quarterly |
| API service keys | `.env` file | Quarterly |
| SSL certificates | Traefik `/letsencrypt` | Auto (90 days) |
| TOTP secrets | Database (encrypted) | Per user |

## 18.4 Network Security

| Rule | Implementation |
|------|---------------|
| Only Traefik exposed externally | Docker networks: `frontend` only for Traefik |
| Internal services not reachable | Docker networks: `backend`, `database` are internal |
| Rate limiting | Traefik middleware: 300 req/min per IP |
| Request size limit | Traefik: 50 MB max body |
| CORS | FastAPI: `https://finance.mmlogistix.bp0.work` (and post-MVP admin hosts per `14` §9.0) |
| Security headers | Traefik: HSTS, CSP, X-Frame-Options |

---

# 19. Troubleshooting Guide

## 19.1 FastAPI Application

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `502 Bad Gateway` | FastAPI container down | `docker compose ps`, `docker compose logs fastapi` |
| Slow API responses | Database connection pool exhausted | Increase `DATABASE_POOL_SIZE`, check for connection leaks |
| Memory error (OOM) | Memory limit too low | Increase container memory limit or reduce workers |
| Import errors after deploy | Missing dependency | Check `requirements.txt`, rebuild image |
| Alembic migration fails | Schema conflict | Run `alembic history`, identify conflict, manual fix |

## 19.2 Database

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `database "accfin" does not exist` on `docker compose exec db` | Wrong service or DB name — production uses Supabase **`postgres`** DB, not local `accfin` | Query via `fastapi` + `get_session_factory()` (§6.1.1) or Supabase SQL Editor |
| `relation "cases" does not exist` on compose `db` | Inspected empty local Postgres, not Supabase | See §6.1.1 |
| Connection refused | PostgreSQL / pooler unreachable | Verify `FINANCE_DATABASE_URL`; Supabase dashboard status |
| Slow queries | Missing index | Check `pg_stat_statements`, add indexes per API Spec Section 14 |
| Disk full | WAL accumulation | `VACUUM`, `pg_archivecleanup`, expand storage |
| Lock timeout | Long-running transaction | `SELECT * FROM pg_locks`, identify blocker, kill if safe |
| Replication lag | N/A (single node) | N/A |

## 19.3 Redis

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Connection timeout | Redis down | `docker compose ps redis`, restart if needed |
| Out of memory | Memory limit reached | Increase `maxmemory`, review key TTLs, evict old keys |
| High latency | Large values or slow commands | Check `SLOWLOG GET 10`, optimize commands |

## 19.4 Ollama

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Inference timeout | Model not loaded | Check `ollama list`, pull model if missing |
| OOM during inference | Insufficient memory | Reduce model quantization (Q4_K_S instead of Q4_K_M) |
| Slow inference | CPU inference instead of GPU | Check `nvidia-smi`, verify GPU passthrough |
| Connection refused | Ollama container down | `docker compose ps ollama`, `docker compose start ollama` |
| Model not found | Model not pulled | `docker exec ollama ollama pull <model>` |
| **`HERMES_TIMEOUT` on AP/AR after classify OK** | Ollama `/extract/invoice` exceeded **120s** (`HermesClient` + `ollama_client.generate_json`) | Check `docker compose logs hermes` for `ReadTimeout`; ensure PDF `extracted_text` at ingest; increase extraction timeout or use faster hardware; manager escalation is DB-only until SMTP ships (`17` §10.4.1) |

## 19.4a Executive mail — escalation logged but no manager email

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Dashboard shows “Escalated to acc.mmlogistix@bp0.work” but **no email in manager inbox** | **`ExecutiveMailService.escalate_to_manager`** persists `case_escalations` + `finance_activity_log` only — **SMTP send not implemented** in `accfin` `0.13.8` (`17` §10.4.1) | Manager acts via signed URL in `case_escalations.context.notification` (query Supabase) or Approval UI; implement outbound SMTP dispatcher per `18` |
| `pending_outbound_emails.smtp_message_id` always NULL | Ack/clarification rows queued, not sent | Same — requires SMTP outbound worker + `FINANCE_SMTP__ENABLED=true` |

## 19.5 Traefik

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `404 Not Found` | Router rule mismatch | Check dynamic config, verify Host rule |
| SSL certificate error | Let's Encrypt rate limit or failure | Check `acme.json`, verify DNS, wait 1 hour |
| High memory usage | Access log accumulation | Enable log rotation, check middleware chain |

## 19.6 Quick Diagnostic Commands

```bash
# Full system status
docker compose ps
docker stats --no-stream
free -h
df -h

# Recent errors across all services
docker compose logs --since=1h 2>&1 | grep -i "error\|exception\|fatal" | tail -20

# Database connections
docker compose exec supabase-db psql -U postgres -c "
    SELECT state, count(*) 
    FROM pg_stat_activity 
    WHERE datname = 'postgres' 
    GROUP BY state;
"

# Redis memory
docker compose exec redis redis-cli INFO memory

# Ollama status
curl http://localhost:11434/api/tags | jq

# API health
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/ready | jq
```

---

# 20. Appendix: Complete docker-compose.yml

## 20.0 Pre-production deployment gates (read before go-live)

> **Mandatory for implementers and operators.** Do not point production traffic at this stack until **all** gates below pass. This appendix is the authoritative `docker-compose.yml`; gates reference services defined here.

| Gate | Owner | Requirement | Reference |
|------|-------|-------------|-----------|
| **A — Business sign-off** | Sponsor / compliance | All five governance checkboxes complete (Compliance, CFO, Business Owner UAT, Technical Lead, CEO) | `01_Business_Requirement_Document.md` Document Governance |
| **B — Phase acceptance** | Technical Lead | Phases **1–11** acceptance criteria satisfied in staging (Phase 11 Expense Management is **MVP**, not optional) | `03_Cursor_Development_Brief.md` §6 |
| **C — Expense Worker (OBS-3)** | DevOps / backend | `worker-expense` below is **not** production-ready until: (a) dedicated `workers/expense/Dockerfile` build replaces stub image/command; (b) `depends_on` includes `hermes` + `redis` with `service_healthy`; (c) resource limits validated under load | `19_Expense_Worker_Specification.md` §1, §11; compose comment on `worker-expense` |
| **D — Mail transport** | Backend | Mail Gateway uses **IMAP only** (`bp0.work:993` SSL) for `executive_agent` mailboxes | `14` §7, `17` §2.1.1–§2.1.2 |
| **E — Migrations & secrets** | DevOps | Alembic chain `001`–`060` applied (`alembic current` → `20260531_060`); `.env` secrets from `env.example` / `14` §2; no prototype Admin UI on port 8080; `GET /api/health` → `0.14.9-binding-authority` (or later); Client Admin COA + binding authority per §4.5h–§4.5k; finance counterparty per §4.5j; outbound-mail smoke per §4.5g | `16` §10, `11` §4.5g–§4.5k, `06` §18.4 |

**Staging vs production:** Gates A–B apply to production launch. Gate C allows the `worker-expense` stub in **dev/staging** stacks for early integration testing, but production deploy **must** fail checklist C.

### 20.0.1 Production deployment checklist (operator worksheet)

**Target version (shipped):** `0.14.9-binding-authority` (see §4.5k)  
**Migrations (shipped):** `001`–`060` (`alembic current` → `20260531_060`)  
**Package versions (informational):** `accfin` health `0.14.9-binding-authority`; `client-admin-ui/package.json` (see repo); `finance-ui/package.json` `0.13.12-api-prefix-routing`  
**Deploy procedure:** §4.5k (binding authority) | §4.5j (finance setup UI) | §4.5i (counterparty) | §4.5h (COA) | **Version timeline:** §20.2 below

#### Gate A — Business sign-off

| # | Item | Owner | Done |
|---|------|-------|------|
| A1 | Compliance sign-off recorded | Compliance | ☐ |
| A2 | CFO sign-off recorded | CFO | ☐ |
| A3 | Business Owner UAT sign-off (`12` UAT-010/011) | Business Owner | ☐ |
| A4 | Technical Lead sign-off | Technical Lead | ☐ |
| A5 | CEO sign-off recorded | CEO | ☐ |

Reference: `01` Document Governance.

#### Gate B — Phase acceptance (staging)

| # | Item | Done |
|---|------|------|
| B1 | Phases **1–10** acceptance criteria met in staging | ☐ |
| B2 | Phase **11** Expense Management (MVP) — APIs, worker, policies | ☐ |
| B3 | Phase **11b** Executive Email SOP — `finance_activity_log`, escalations, daily log job | ☐ |
| B4 | Full pytest suite green on staging DB after `alembic upgrade head` | ☐ |

Reference: `03` §6.

#### Gate C — Expense Worker (OBS-3) — production only

| # | Item | Done |
|---|------|------|
| C1 | `worker-expense` uses dedicated `workers/expense/Dockerfile` (not stub) | ☐ |
| C2 | `depends_on`: `hermes` + `redis` with `service_healthy` | ☐ |
| C3 | Resource limits validated under load | ☐ |

Reference: `19` §1, §11. Staging may use stub; production **must not** pass Gate C until complete.

#### Gate D — Mail transport

| # | Item | Done |
|---|------|------|
| D1 | Mail Gateway polls **IMAP only** (`bp0.work:993` SSL) for `executive_agent` mailboxes | ☐ |
| D1a | `FINANCE_MAIL__POLL_ENABLED: "true"` on `gateway` in `docker-compose.yml`; gateway rebuilt | ☐ |
| D1a1 | Gateway logs `Enqueued email {id} ({subject}) to intake_queue` (`0.13.18`) | ☐ |
| D1b | Gateway poll — no `MissingGreenlet` / async SQLAlchemy errors | ☐ |
| D1c | Accounts worker classification — no `MissingGreenlet` (`0.13.11`) | ☐ |
| D1d | Intake ack SMTP — no `MissingGreenlet` (`0.13.12`) | ☐ |
| D1e | Outbound-mail workers mount `attachment-data` at `/data/attachments` (`0.13.13`, `0.13.19`) | ☐ |
| D1f | Classified cases on `accounts_queue`; AP/AR/expense consume (`0.13.14`) | ☐ |
| D1g | AP `manual_review` escalates with extracted/missing detail (`0.13.15`) | ☐ |
| D1h | Manager escalation includes inbound attachments (`0.13.16`) | ☐ |
| D1i | DOCX on accexp; `expense_claim` classification (`0.13.20`) | ☐ |
| D1j | AP without PO escalates; `po_validation` in metadata (`0.13.20`) | ☐ |
| D1k | Travel expense without `travel_requests` escalates (`0.13.20`) | ☐ |
| D1l | AP vendor = issuer; Client/Vendor column (`0.13.21`, `0.13.10`) | ☐ |
| D1m | Escalation respond: comment form; approve → `override_po_check` (`0.13.22`) | ☐ |
| D2 | Manager mailboxes (`acc`, `fin`, `cfo`, `ceo`) **not** on intake poller | ☐ |
| D3 | `requires_outbound_client_approval` backfill (migration `045`) | ☐ |
| D4 | Escalation / outbound emails include `[CAS-…]` in Subject | ☐ |
| D5 | Outbound SMTP when `FINANCE_SMTP__ENABLED=true`; ack re-attach (`0.13.10`); `POST /api/internal/jobs/flush-outbound-mail` | ☐ |

Reference: `17` §2.1.1–§10.

#### Gate E — Migrations, secrets, infrastructure

**E1 — Database migrations**

```bash
cd accfin && alembic upgrade head
alembic current   # expect head: 20260531_053
```

| Migration band | Purpose |
|----------------|---------|
| `001`–`039` | Core platform through audit |
| `039b` | Expense `case_type` enum |
| `040`–`044` | Expense management |
| `045` | `finance_activity_log`, SOP seeds |
| `046` | `case_escalations`, `pending_outbound_emails` |
| `047` | mmlogistix CFO + Finance Manager users |
| `048` | `travel_requests`, DOCX MIME |
| `049`–`051` | Client Admin tables, seed, signatures (`06` §13.2c) |
| `052` | `gl_cutoff_reminders` |
| `053` | `accounting_periods.period_type`, `audit_metadata` |

**E1a — Production database (Supabase)**

Production data via `FINANCE_DATABASE_URL` — **not** compose `db` (`11` §6.1.1). Do **not** use `docker compose exec db psql`.

**E2 — Required secrets** (from `platform_dox/env.example` → `accfin/.env`)

| Variable | Purpose |
|----------|---------|
| `FINANCE_DATABASE_URL` | PostgreSQL (Supabase) |
| `FINANCE_REDIS__PASSWORD` | Redis auth |
| `FINANCE_JWT__SECRET` | User sessions |
| `FINANCE_PRIVACY_ENCRYPTION_KEY` | Fernet field encryption |
| `FINANCE_HASH_SECRET` | Audit hash chain |
| `FINANCE_INTERNAL_CRON__TOKEN` | Daily log + GL cutoff cron jobs |
| `FINANCE_MAIL_ACTION__SECRET` | Escalation signed links |
| `FINANCE_HERMES_API_KEY` | Hermes auth |
| `FINANCE_WASABI__ACCESS_KEY_ID` / `SECRET_ACCESS_KEY` | `bp0workacc` |
| `FINANCE_INTERNAL__API_BASE_URL` | `http://fastapi:8000` |
| `FINANCE_PUBLIC__APP_HOST` | `finance.mmlogistix.bp0.work` |
| `FINANCE_PUBLIC__CLIENT_ADMIN_HOST` | `admin.mmlogistix.bp0.work` |
| `FINANCE_LETS_ENCRYPT_EMAIL` | `system@bp0.work` |

Generate: `python scripts/generate-keys.py`

**E3 — Scheduled jobs**

| Job | Schedule | Endpoint |
|-----|----------|----------|
| Finance daily activity digest | **21:00 Asia/Singapore** | `POST /api/internal/jobs/finance-daily-log` (`05` §19.1, `11` §17.5) |
| GL cutoff reminders | **08:00 Asia/Singapore** (`00:00 UTC`) | `POST /api/internal/jobs/gl-cutoff-reminders` (`05` §19.2, `11` §17.6) |

**E4 — Smoke tests**

| # | Check | Expected |
|---|-------|----------|
| E4.1 | `GET /api/health` | `200`, version **`0.14.10-counterparty-fixes`** |
| E4.1b | `GET https://finance.mmlogistix.bp0.work/` | finance-ui HTML |
| E4.1c | Browser session >15 min | Silent JWT refresh (`0.12.8`) |
| E4.1d | `/approvals` after login | Loads (no SSR 401; `0.13.12`) |
| E4.2 | `GET /metrics` (if enabled) | Prometheus OK |
| E4.3 | `GET /mail/status` | Mailbox counts |
| E4.4 | Cron dry-run (`force=true` staging only) | CSV `row_count` |
| E4.5 | Expense worker `:8014/health` | Healthy after Gate C |
| E4.6 | `docker compose ps ollama` | **healthy** (`ollama list`; `0.13.5`) |
| E4.7 | `docker compose ps hermes` | **healthy** |
| E4.8 | `/settings/security` | 2FA QR flow (`0.13.6`) |
| E4.8a | `/login` + 2FA user | TOTP step (`0.13.5`) |
| E4.9 | PDF intake → case | Wasabi `transactions/{case_number}/` (`0.13.8`) |

**E5 — Explicit exclusions / rebuilds**

| # | Item | Done |
|---|------|------|
| E5.1 | No prototype Admin UI on port **8080** | ☐ |
| E5.2 | Traefik v2.11; `/` → finance-ui; API prefixes only (`0.13.12`) | ☐ |
| E5.2a | DNS + TLS for `finance.mmlogistix.bp0.work` | ☐ |
| E5.3 | Wasabi `logs/finance_daily_{date}.csv` | ☐ |
| E5.3a | Wasabi `transactions/{case_number}/` on intake | ☐ |
| E5.4 | SMTP daily digest to CFO | ☐ |
| E5.5 | Outbound SMTP: escalation, ack, clarification | ☐ |
| E5.6 | finance-ui manual review panel (`0.13.6`) | ☐ |
| E5.7 | Approvals Client/Vendor column (`0.13.10`) | ☐ |
| E5.8 | Rebuild after `0.13.20` (`python-docx`) | ☐ |
| E5.9 | Rebuild finance-ui + fastapi + traefik (`0.13.12`) | ☐ |
| E5.10 | Rebuild after `0.13.22` escalation respond | ☐ |
| E5.11 | Client Admin: dashboard, signatures, policies, regulatory PDFs, travel-info, calendar, GL recipients (`0.14.2`+) | ☐ |
| E5.11a | DNS `admin.mmlogistix.bp0.work`; `system.mmlogistix` login; nav after login | ☐ |
| E5.12 | GL period: closed period blocks post; finance-ui **Override & Post** (`0.14.4`; `15` §8.21) | ☐ |
| E5.13 | Rebuild `ap-worker`, `ar-worker`, `expense-worker`, `finance-ui` after `0.14.4` | ☐ |
| E5.14 | GL period **Reopen** on Finance UI accounting calendar; finance-ui **Retry** after reopen (`0.14.5`; `15` §8.24, §8.21) | ☐ |
| E5.15 | Rebuild `fastapi`, `client-admin-ui`, `finance-ui` after `0.14.5` | ☐ |
| E5.16 | Outbound email signature: set on `/company`, preview, verify ack/clarification footer (`0.14.6`; `18` §10.2) | ☐ |
| E5.17 | Rebuild `fastapi` (+ `client-admin-ui` for preview) after `0.14.6` | ☐ |
| E5.18 | `alembic current` → `20260531_058` after `0.14.8` deploy | ☐ |
| E5.22 | `alembic current` → `20260527_061` after `0.14.10` deploy | ☐ |
| E5.19 | `./scripts/uat_phase13.sh` — 4/4 integration UAT (incl. UAT-012 subaccount create) | ☐ |
| E5.19 | Client Admin COA: import CSV with **Replace entire chart**; green summary; accounts persist after navigation (`15` §8.10) | ☐ |
| E5.20 | Client Admin COA: **Filter by code or name** → Search narrows table; Clear restores list (`7502b3e`) | ☐ |
| E5.21 | `client-admin-ui` image built successfully after `8d6bf6e` (no `mixed_event_handler_syntaxes` on COA page) | ☐ |

#### Post-deploy sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Technical Lead | | | |
| DevOps | | | |
| CFO (operational) | | | |

---

## 20.2 Deployment version history

Authoritative smoke-test version: `GET /api/health` → `version` from `accfin/app/core/config.py`.  
UI package versions: `finance-ui/package.json`, `client-admin-ui/package.json`.

| Deploy version | Date | Git (main) | Summary |
|----------------|------|------------|---------|
| **0.14.10-counterparty-fixes** | 2026-05-27 | `036ac82` | **Counterparty fixes:** Reactivate inactive subaccounts on `/counterparty-accounts`; vendor contract fields + expiry warning badge; Client Admin dashboard adds vendor-contract expiring-within-30-days warning. Migration `061` adds vendor contract columns to `counterparty`. Rebuild `fastapi`, `finance-ui`, `client-admin-ui`, `ar-worker`, `ap-worker`, `expense-worker`. §4.5l. |
| **0.14.9-binding-authority** | 2026-05-26 | `c757aff` | **Binding authority:** migration `060` seeds approval threshold policies; workers route T1 STP / T2 acc / T3 CFO; Client Admin `/binding-authority`; finance-ui role queues + case approve/reject/escalate. Rebuild `fastapi`, `client-admin-ui`, `finance-ui`, `ar-worker`, `ap-worker`, `expense-worker`. §4.5k. |
| **0.14.8-counterparty-accounts** (UI routing) | 2026-05-20 | `e73c869` | **Finance UI:** counterparty, agreements, accounting calendar on `finance.mmlogistix`; Client Admin nav trimmed (no Travel). Rebuild `fastapi` + `finance-ui`. §4.5j. |
| **0.14.8-counterparty-accounts** (company profile fix) | 2026-05-20 | `a45a31e` | **FastAPI:** `TenantProfileResponse.from_attributes`; **Client Admin** `/company` load fix. Rebuild `fastapi` + `client-admin-ui`. |
| **0.14.8-counterparty-accounts** (UI patch) | 2026-05-20 | `9b0662e` | **Finance UI:** Subaccounts tab **Edit/Save** (`15` §8.22 v2.29). Rebuild `finance-ui`. |
| **0.14.8-counterparty-accounts** (UI patch) | 2026-05-20 | `17ed4bd` | **Client Admin:** subaccount **credit limit** on create + table column (`15` §8.22 v2.28). Rebuild `client-admin-ui` only. |
| **0.14.8-counterparty-accounts** | 2026-05-20 | `9350495` | **Shipped:** migrations `055`–`058`; subaccounts, payment terms, tenant tax codes; worker GST resolver; Client Admin `/counterparty-accounts`; UAT `uat_phase13.sh`. Fixes `b749e64` (commit), `541c434`/`9350495` (UAT idempotency). §4.5i. |
| **0.14.7-coa-tenant-import** | 2026-05-20 | `054` | **Tenant COA:** migration removes demo seed accounts; `POST /api/coa/import?replace_all` upsert; Client Admin import summary + filter/search (`7502b3e`); Docker build fix `8d6bf6e` (Svelte 5 event syntax). Rebuild `fastapi` + `client-admin-ui`; `alembic upgrade head`. §4.5h. |
| **0.14.6-email-signature** | 2026-05-20 | — | **Outbound email signatures:** `tenant_profiles` HTML/plain footer appended to ack, escalation, clarification, daily log, GL cutoff reminders via `mail_template_renderer` + `OutboundMailService`; Client Admin Company page preview. Rebuild `fastapi` (+ `client-admin-ui` optional). |
| **0.14.5-reopen-period** | 2026-05-20 | — | **GL period reopen:** `POST /api/accounting-periods/{id}/reopen` (CFO / Client Admin); `gl_period_reopened` activity log; Client Admin 🔓 Reopen; finance-ui Retry when period reopened; `linked_gl_period_status` on `GET /cases/{id}`. Rebuild: `fastapi`, `client-admin-ui`, `finance-ui`. |
| **0.14.4-gl-period-posting-controls** | 2026-05-25 | — | **GL period posting gate:** `assert_period_allows_posting` with override; AP/AR/expense workers; bootstrap when no periods; `POST /api/accounting-periods/{id}/override-post`; finance-ui Override & Post (`15` §8.21). |
| **0.14.3-gl-cutoff-reminders** | 2026-05-25 | — | **GL cutoff reminders:** `gl_cutoff_reminders` (`052`); `period_type` + `audit_metadata` (`053`); accounting settings API; enhanced period generate (FYE/audit/cutoff); cron `POST /api/internal/jobs/gl-cutoff-reminders`; calendar UI settings + recipients (`15` §8.20). |
| **0.14.2-client-admin-fixes** | 2026-05-20 | — | **Client Admin fixes:** live dashboard checks; company email signatures (`051`); COA empty state; mailbox credential note; users CEO→acc order; Travel & Expense Policy PDF + regulatory uploads (Wasabi); `/travel-info` replaces travel UI; calendar generate forward 13 months. |
| **0.14.1-client-admin-ui** | 2026-05-20 | `5580f55` | **Client Admin (shipped):** `admin.mmlogistix.bp0.work` — SvelteKit + adapter-node, `/api/*`, nav Dashboard→Accounting Calendar; reactive `client_admin_access_token` nav fix. **API** (`admin.py`, `require_client_admin`): dashboard, tenant profile, COA+CSV, mail config, users, expense limits, agreements, travel-requests, accounting-periods, regulatory docs. **Traefik:** `client-admin-ui` p1; `client-admin-api` `PathPrefix(/api)` p100. Migrations `049`/`050`. See `15` §8.13. |
| **0.14.0-client-admin-ui** | 2026-05-20 | `3f15219` | Initial Client Admin UI + admin API (superseded by `0.14.1` nav fix). |
| **0.13.12-api-prefix-routing** (finance-ui + accfin + traefik) | 2026-05-20 | `713be98` | **API under `/api`:** Traefik `PathPrefix(/api)` only; FastAPI routers mounted at `/api`; finance-ui `apiUrl()` + vite proxy `/api`. UI owns `/approvals`, `/cases/{id}`. Layout `isLoggedIn` sync from localStorage; one-step login TOTP field. |
| **0.13.11-approvals-page-auth-routing** (finance-ui + traefik) | 2026-05-20 | `60741ce` | **/approvals 401 fix (superseded by 0.13.12):** `loadCases()` awaits `ensureValidAccessToken()`; `+page.ts`/`+layout.ts` `ssr = false`. Traefik `finance-ui-html-overlap` (priority 110) sends browser document navigations on `/approvals` and `/cases/{id}` to finance-ui; vite dev proxy bypasses HTML for `/approvals`. |
| **0.13.10-ap-client-vendor-column-fix** (finance-ui) | 2026-05-20 | `cbd834f` | Approvals + case detail **Client / Vendor**: AP → `client_vendor_name`; AR → `counterparty_name` only (`case-labels.ts`). Requires API `client_vendor_name` (`0.13.21`). |
| **0.13.22-escalation-respond-flow** | 2026-05-24 | `13a1531` | **Escalation respond:** GET shows comment form; POST stores `manager_comment`. Approve → requeue with `override_po_check` + submitter ack; Reject → email submitter with comment; Escalate → forward to next tier with comment. Routes in `mail_actions.py` (`05` §8.8a). |
| **0.13.21-ap-vendor-extraction-display** | 2026-05-24 | `1d0075b` | **Hermes AP:** `ap_invoice_extract-v2` — vendor is issuer (not payer); receipt/ref/ARN invoice numbers; paid receipt `due_date` = `invoice_date`. **API/UI:** `GET /cases` `client_vendor_name` from `extracted_fields.vendor_name` for AP; finance-ui Client/Vendor column (`0.13.9`). |
| **0.13.9-ap-vendor-column-display** (finance-ui) | 2026-05-24 | `1d0075b` | Approvals + case detail use `client_vendor_name` for Client / Vendor column. |
| **0.13.20-docx-po-travel-controls** | 2026-05-24 | `791a9f1` | DOCX attachment text extraction; AP due_date + PO gate escalation; expense travel-request matching; `travel_requests` table (migration `048`). |
| **0.13.19-domain-worker-attachment-volumes** | 2026-05-24 | `7c80047` | `docker-compose.yml`: mount shared `attachment-data` on `ap-worker`, `ar-worker`, `expense-worker` (+ `FINANCE_MAIL__ATTACHMENT_STORAGE_PATH`) so escalation SMTP can re-attach inbound files. Extends `0.13.13` (accounts-worker only). |
| **0.13.18-gateway-intake-enqueue-logging** | 2026-05-24 | `f439577` | Gateway IMAP poller: `_enqueue_intake_for_email()` with success/failure logging; ingest leaves email `parsed` until Redis RPUSH succeeds; `intake_enqueue_failed` metadata on failure for manual requeue. |
| **0.13.17-approvals-list-from-address** | 2026-05-24 | `9ed2002` | `GET /cases` includes `from_address` (from linked `emails` row) and existing `counterparty_name` for finance-ui approvals table. |
| **0.13.8-approvals-client-vendor-column** (finance-ui) | 2026-05-24 | `912715d` | Approvals table column header **Client / Vendor** (was Issued By/To). |
| **0.13.7-approvals-table-columns** (finance-ui) | 2026-05-24 | `9ed2002` | Cases & Approvals table: Document Type labels, Submitted By, counterparty column; Stage column removed. |
| **0.13.16-escalation-inbound-attachments** | 2026-05-24 | `d9bf736` | Manager escalation SMTP re-attaches inbound files: `pending_outbound_emails.metadata.reattach_inbound_attachments` + `_load_reattach_attachments` in `_build_send_plan` for `manager.escalation.*` templates (`17` §10.4). |
| **0.13.6-manual-review-detail** (finance-ui) | 2026-05-24 | `c1cd3bd` | Case detail `/cases/{id}`: **Manual review details** panel — `workflow_metadata.missing_fields`, `extraction_confidence`, `extracted_fields` when status is `manual_review` or `on_hold`. |
| **0.13.15-ap-missing-fields-escalation** | 2026-05-24 | `c1cd3bd` | AP worker escalates `manual_review` (missing fields) via `route_missing_fields_to_manager()` → `case_escalations` + SMTP with extracted/missing field detail; `request_info` manager action queues client clarification (`mail.clarification.request`). |
| **0.13.14-classification-accounts-queue-route** | 2026-05-24 | `78f83b1` | After intake classification, `route_case_to_queue()` pushes to `accounts_queue` **after** DB commit so AP/AR/expense workers see the case. New helper in `queue_router.py`. |
| **0.13.13-accounts-worker-attachment-volume** | 2026-05-24 | `a5cc05d` | `docker-compose.yml`: mount shared `attachment-data` volume on `accounts-worker` (+ `FINANCE_MAIL__ATTACHMENT_STORAGE_PATH`). Fixes Wasabi archive and ack re-attach when gateway wrote files but worker had no `/data/attachments` access. |
| **0.13.12-outbound-mail-greenlet-fix** | 2026-05-24 | `3341f3c` | Outbound ack SMTP: `AckSourceData` + `selectinload(Email.attachments)` in `_build_send_plan`; phased `send_pending_outbound_email()` for flush cron (load → SMTP → persist). Fixes `MissingGreenlet` from lazy `source_email.attachments` in `_ack_template_context`. |
| **0.13.11-accounts-classification-greenlet-fix** | 2026-05-24 | `55e3e80` | Accounts intake classification: phased `async with session_factory()` around Hermes HTTP; `EmailSnapshot` before external awaits; Wasabi archive re-fetches attachment after `asyncio.to_thread`. |
| **0.13.5-login-totp-input-fix** (finance-ui) | 2026-05-24 | `6471356` | Login TOTP field: `type="text"`, `maxlength="6"` only — removed `pattern` / `inputmode` that triggered browser “match the requested format” errors. |
| **0.13.4-login-2fa-step** (finance-ui) | 2026-05-24 | `0eb3d4b` | Login two-step flow: username/password first; on `TOTP_REQUIRED` show 6-digit authenticator field and resubmit with `totp_code`. Package `finance-ui@0.13.4-login-2fa-step`. |
| **0.13.10-ack-context-attachments** | 2026-05-24 | `1520583` | Ack email (`mail.intake.acknowledged`): lists inbound attachment filenames, quotes original message body, re-attaches files when present; `In-Reply-To` threading unchanged. |
| **0.13.9-outbound-smtp** | 2026-05-20 | — | Outbound SMTP: `SmtpMailService` + `OutboundMailService` (`aiosmtplib`, Jinja templates); `FINANCE_SMTP__*` relay settings in `config.py`; manager escalation, ack, and failure notify sent after queue; daily log CSV attachment; `POST /internal/jobs/flush-outbound-mail` catch-up. |
| **0.13.8-wasabi-attachment-archive** | 2026-05-20 | `5f4de39` | `WasabiArchiveService` (`app/services/wasabi_archive.py`): boto3 upload to `transactions/{case_number}/{filename}` on `bp0workacc`; sets `email_attachments.wasabi_archive_path`. Triggered from `CaseService.on_case_linked_to_email()` after intake classification links email → case when `FINANCE_WASABI__ARCHIVE_ON_INTAKE=true`. Dependency: `boto3`. |
| **0.13.7-worker-blpop-idle-fix** | 2026-05-20 | `beef354` | `QueueConsumer` default BLPOP block timeout 5s (`workers/base.py`) — reduces idle CPU spin on empty queues (accounts, AR, AP, expense). |
| **0.13.6-finance-security-2fa** | 2026-05-20 | `9d3fac0` | finance-ui `/settings/security`: 2FA setup (QR via `qrcode`), verify, disable; mandatory-2FA banner for `cfo`/`finance_manager`. Retry button on case detail. Package `0.13.3-security-2fa`. Feature `47c0f57`. |
| **0.13.5-ollama-healthcheck-cli** | 2026-05-20 | `6927279` | Ollama Docker healthcheck: `ollama list` via bundled CLI (image has neither `curl` nor `wget`). Supersedes `0.13.4` wget attempt. Feature `e99848b`. |
| **0.13.4-ollama-healthcheck-wget** | 2026-05-20 | `a405f86` | *(superseded)* Ollama healthcheck used `wget` — unavailable in image. Compose fix `d6bd61d`. |
| **0.13.3-case-retry-hermes-timeout** | 2026-05-20 | `8b2475d` | Hermes client default timeout 120s (slow Ollama CPU). `POST /cases/{id}/retry` requeues `exception`/`manual_review` to `accounts_queue`; Retry button on case detail. finance-ui `0.13.1-case-retry`. Feature `8d049a1`. |
| **0.13.2-case-visibility** | 2026-05-20 | `0286578` | Case timeline audit trail on detail page; error reason + processing stage on list/dashboard; dedupe Message-ID only. finance-ui `0.13.0-case-dashboard`. |
| **0.13.1-mail-text-sanitize** | 2026-05-20 | `be0d1e0` | Sanitize all mail text fields at ingest (`body_text`, `body_html`, `body_preview`, `subject`, `extracted_text`) — strip NUL and invalid UTF-8 before PostgreSQL insert. |
| **0.13.0-executive-mail-sop** | 2026-05-20 | `4bf72a5` | Manager-first processing failure escalation (`ExecutiveMailService`); sender ack with `[CAS-…]` after case_number; failure notify only on manager reject; `finance_activity_log` at ingest/classify/workers. |
| **0.12.9-mail-pdf-sanitize** | 2026-05-20 | `a4717ce` | Strip NUL bytes from PDF `extracted_text` before DB insert (`sanitize_extracted_text` in ingest + email_context). Fixes PostgreSQL `CharacterNotInRepertoireError`. |
| **0.12.8-finance-token-refresh** | 2026-05-20 | `2dfe475` | finance-ui silent JWT refresh: store access + refresh in `localStorage`; proactive `POST /auth/refresh` within 2 min of expiry; redirect `/login` on failure. Package `0.12.5-finance-token-refresh`. |
| **0.12.7-ollama-extraction** | 2026-05-20 | `e3e0a1f` | Hermes Ollama extraction (`qwen2.5:7b`): `/extract/invoice`, `/extract/expense-claim`, `/extract/document-text`; mailbox-first classification (`accar`/`accap`/`accexp`); PDF text at ingest via pypdf. |
| **0.12.6-gateway-imap-poller** | 2026-05-20 | `0669e6f` | Mail Gateway: enable `FINANCE_MAIL__POLL_ENABLED` in compose; fix IMAP poller async SQLAlchemy sessions (`gateway/imap/poller.py` — per-mailbox `async with session_factory()`, plain IMAP settings for `asyncio.to_thread`). Migration head `20260530_047`. |
| **0.12.5-finance-dashboard** | 2026-05-22 | `51b30d4` | Finance oversight UI: dashboard, all-cases list, CSV `GET /cases/export`, branding **mmlogistix Finance Operations**. finance-ui `0.12.4-finance-dashboard`. |
| **0.12.4-client-auth** | 2026-05-22 | `353f9a9`, `4adfb9d` | finance-ui: `ssr = false` on authenticated routes; `goto()` after login (`localStorage` JWT). |
| **0.12.3-mmlogistix-branding** | 2026-05-20 | `dc3d0b0` | Product name **mmlogistix Finance** (replaces LogiScore Finance). finance-ui `0.12.2-mmlogistix-branding`. |
| **0.12.2-traefik-ui-root** | 2026-05-20 | `d354943` | `/` → finance-ui (priority 1); API prefixes only in `api-routes.yml` (no `PathPrefix('/')`). |
| **0.12.1-traefik-routes** | 2026-05-20 | `9eb45a8`, `eed8255`, `1a45276` | `traefik/dynamic/api-routes.yml`: `finance-api` service; single-line `rule`. |
| **0.12.0-url-structure** | 2026-05-20 | `a2531e0` | MVP host `finance.mmlogistix.bp0.work` (UI + edge API); FastAPI internal only; no `api.bp0.work`. |
| *(infra, same API)* | 2026-05-19 | `51b0652` | Traefik Docker label `traefik.docker.network=accfin_frontend`. |
| *(infra, same API)* | 2026-05-19 | `eccf320` | Traefik **v2.11** (VPS Docker API incompatible with v3). |
| *(infra, same API)* | 2026-05-19 | `8a8564e` | Production Traefik HTTPS, Let's Encrypt, finance-ui + fastapi routing (superseded by 0.12.0+). |
| **0.11.0-phase11b** | 2026-05-19 | `43430d2` | Phase 11b: executive email SOP, migrations `045`–`046`, daily log job, escalations. |

**Spec alignment (current):** `11` v2.42+, `14` v2.30+, `04` v2.8+, `17` v2.33+, `15` v2.21+, `05` v1.3.14+, `00` v2.54+.

**Production checklist:** §20.0.1 (Gate E).

---

```yaml
version: "3.8"

services:
  # =========================================================================
  # Reverse Proxy
  # =========================================================================
  traefik:
    image: traefik:v3.0
    container_name: traefik
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    read_only: true
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - /opt/mmlogistix/traefik/traefik.yml:/etc/traefik/traefik.yml:ro
      - /opt/mmlogistix/traefik/dynamic-config:/dynamic-config:ro
      - /opt/mmlogistix/traefik/letsencrypt:/letsencrypt
      - /opt/mmlogistix/logs/traefik:/var/log/traefik
    networks:
      - frontend
      - backend
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 256M
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  # =========================================================================
  # Application
  # =========================================================================
  fastapi:
    image: ghcr.io/mmlogistix/finance-api:latest
    container_name: fastapi
    restart: unless-stopped
    env_file:
      - /opt/mmlogistix/.env
    networks:
      - frontend
      - backend
    depends_on:
      supabase-db:
        condition: service_healthy
      redis:
        condition: service_healthy
      ollama:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=accfin_frontend"
      - "traefik.http.routers.finance-api.rule=Host(`finance.mmlogistix.bp0.work`) && (PathPrefix(`/auth`) || PathPrefix(`/mail`) || PathPrefix(`/approvals`) || PathPrefix(`/cases`) || PathPrefix(`/events`) || PathPrefix(`/health`))"
      - "traefik.http.routers.finance-api.priority=100"
      - "traefik.http.routers.finance-api.entrypoints=websecure"
      - "traefik.http.routers.finance-api.tls.certresolver=letsencrypt"
      - "traefik.http.services.finance-api.loadbalancer.server.port=8000"

  finance-ui:
    image: ghcr.io/mmlogistix/finance-ui:latest
    container_name: finance-ui
    restart: unless-stopped
    networks:
      - frontend
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=accfin_frontend"
      - "traefik.http.routers.finance-ui.rule=Host(`finance.mmlogistix.bp0.work`)"
      - "traefik.http.routers.finance-ui.entrypoints=websecure"
      - "traefik.http.routers.finance-ui.tls.certresolver=letsencrypt"
      - "traefik.http.services.finance-ui.loadbalancer.server.port=3000"

  # =========================================================================
  # AI Orchestration Layer (Hermes)
  # See: 04_Hermes_Integration_Spec.md §2
  # =========================================================================
  hermes:
    build:
      context: /opt/mmlogistix/app
      dockerfile: agents/Dockerfile
    container_name: hermes
    restart: unless-stopped
    env_file:
      - /opt/mmlogistix/.env
    environment:
      - HERMES_OLLAMA_BASE_URL=http://ollama:11434
      - HERMES_EXTRACTION_MODEL=qwen2.5:7b
      - HERMES_VISION_MODEL=qwen2.5vl:7b
      - HERMES_API_KEY=${FINANCE_HERMES_API_KEY}
      - HERMES_DEFAULT_MODEL=${FINANCE_AI__OLLAMA_MODEL}
      - HERMES_LOG_LEVEL=INFO
    volumes:
      - /opt/mmlogistix/app/prompts:/app/prompts:ro
      - /opt/mmlogistix/app/agents/config:/app/config:ro
    networks:
      - backend
    depends_on:
      ollama:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  # =========================================================================
  # Mail Gateway — Phase 3
  # See: 02_Technical_Architecture.md §7, 17_Worker_Specifications.md §2.1
  # Responsibilities: IMAP polling (executive_agent mailboxes only),
  #   SPF/DKIM/DMARC validation, dedup, attachments, intake_queue push.
  # FINANCE_MAIL__POLL_ENABLED: compose environment only (11 §4.5) — true in production.
  # =========================================================================
  gateway:
    build:
      context: /opt/mmlogistix/app
      dockerfile: gateway/Dockerfile
    container_name: gateway
    restart: unless-stopped
    env_file:
      - /opt/mmlogistix/.env
    environment:
      FINANCE_MAIL__POLL_ENABLED: "true"   # compose only — not .env; required in production (11 §4.5)
      FINANCE_MAIL__ATTACHMENT_STORAGE_PATH: /data/attachments
    networks:
      - backend
    depends_on:
      supabase-db:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  # =========================================================================
  # Workflow Orchestrator — Phase 4
  # See: 02_Technical_Architecture.md §9, 17_Worker_Specifications.md §2.1
  # Responsibilities: case routing, retry_queue dispatch, SLA tracking,
  #   dead_letter_queue management, accounts_queue production
  # =========================================================================
  orchestrator:
    build:
      context: /opt/mmlogistix/app
      dockerfile: orchestrator/Dockerfile
    container_name: orchestrator
    restart: unless-stopped
    env_file:
      - /opt/mmlogistix/.env
    networks:
      - backend
    depends_on:
      supabase-db:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  # =========================================================================
  # Domain Workers — one container per worker type
  # See: 17_Worker_Specifications.md §2 (Shared Infrastructure)
  # Phase 5: worker-accounts | Phase 6: worker-ar | Phase 7: worker-ap
  # Phase 8: worker-treasury | Phase 11: worker-expense
  # =========================================================================
  worker-accounts:
    image: ghcr.io/mmlogistix/finance-api:latest
    container_name: worker-accounts
    command: ["python", "-m", "workers.accounts.main"]
    restart: unless-stopped
    env_file:
      - /opt/mmlogistix/.env
    networks:
      - backend
    depends_on:
      supabase-db:
        condition: service_healthy
      redis:
        condition: service_healthy
      hermes:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  worker-ar:
    image: ghcr.io/mmlogistix/finance-api:latest
    container_name: worker-ar
    command: ["python", "-m", "workers.ar.main"]
    restart: unless-stopped
    env_file:
      - /opt/mmlogistix/.env
    networks:
      - backend
    depends_on:
      supabase-db:
        condition: service_healthy
      redis:
        condition: service_healthy
      hermes:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  worker-ap:
    image: ghcr.io/mmlogistix/finance-api:latest
    container_name: worker-ap
    command: ["python", "-m", "workers.ap.main"]
    restart: unless-stopped
    env_file:
      - /opt/mmlogistix/.env
    networks:
      - backend
    depends_on:
      supabase-db:
        condition: service_healthy
      redis:
        condition: service_healthy
      hermes:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  worker-treasury:
    image: ghcr.io/mmlogistix/finance-api:latest
    container_name: worker-treasury
    command: ["python", "-m", "workers.treasury.main"]
    restart: unless-stopped
    env_file:
      - /opt/mmlogistix/.env
    networks:
      - backend
    depends_on:
      supabase-db:
        condition: service_healthy
      redis:
        condition: service_healthy
      hermes:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  # =========================================================================
  # Expense Worker — Phase 11
  # Implementation contract: 19_Expense_Worker_Specification.md
  # ⚠️  PRE-PRODUCTION GATE (OBS-3): This service is a stub. Before go-live:
  #   (a) Replace image + command with a dedicated workers/expense/Dockerfile build.
  #   (b) Verify depends_on includes hermes (service_healthy) and redis (service_healthy).
  #   (c) Update §4.3 resource limits if load testing reveals different requirements.
  #   See 19_Expense_Worker_Specification.md §1 for MVP scope and Phase 1 acceptance criteria.
  # =========================================================================
  worker-expense:
    image: ghcr.io/mmlogistix/finance-api:latest
    container_name: worker-expense
    command: ["python", "-m", "workers.expense.main"]
    restart: unless-stopped
    env_file:
      - /opt/mmlogistix/.env
    networks:
      - backend
    depends_on:
      supabase-db:
        condition: service_healthy
      redis:
        condition: service_healthy
      hermes:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  # =========================================================================
  # Database (Supabase)
  # =========================================================================
  supabase-db:
    image: supabase/postgres:15.1.1.61
    container_name: supabase-db
    restart: unless-stopped
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: postgres
    volumes:
      - supabase-db-data:/var/lib/postgresql/data
      - /opt/mmlogistix/supabase/postgresql.conf:/etc/postgresql/postgresql.conf:ro
    networks:
      - database
      - backend
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 8G
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 60s
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"

  supabase-kong:
    image: kong:2.8.1
    container_name: supabase-kong
    restart: unless-stopped
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /var/lib/kong/kong.yml
      KONG_DNS_ORDER: LAST,A,CNAME
    volumes:
      - /opt/mmlogistix/supabase/volumes/api/kong.yml:/var/lib/kong/kong.yml:ro
    networks:
      - backend
    depends_on:
      - supabase-db
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"

  # =========================================================================
  # Cache & Queue
  # =========================================================================
  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - /opt/mmlogistix/redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
      - redis-data:/data
      - /opt/mmlogistix/logs/redis:/var/log/redis
    networks:
      - backend
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"

  # =========================================================================
  # AI Model Server
  # =========================================================================
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    volumes:
      - ollama-models:/root/.ollama
    networks:
      - backend
    deploy:
      resources:
        limits:
          cpus: "4.0"
          memory: 16G
    environment:
      - OLLAMA_ORIGINS=*
      - OLLAMA_HOST=0.0.0.0:11434
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  # =========================================================================
  # Monitoring (Optional — Phase 10+)
  # =========================================================================
  prometheus:
    image: prom/prometheus:v2.51
    container_name: prometheus
    restart: unless-stopped
    volumes:
      - /opt/mmlogistix/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    networks:
      - backend
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_SERVER_ROOT_URL: "https://finance.mmlogistix.bp0.work/grafana"
    volumes:
      - grafana-data:/var/lib/grafana
      - /opt/mmlogistix/monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - /opt/mmlogistix/monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
    networks:
      - backend
    depends_on:
      - prometheus
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"

# =========================================================================
# Networks
# =========================================================================
networks:
  frontend:
    driver: bridge
    internal: false
  backend:
    driver: bridge
    internal: true
  database:
    driver: bridge
    internal: true

# =========================================================================
# Volumes
# =========================================================================
volumes:
  supabase-db-data:
    driver: local
  redis-data:
    driver: local
  ollama-models:
    driver: local
  prometheus-data:
    driver: local
  grafana-data:
    driver: local
```

---

# Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.53 | 2026-05-27 | **`0.14.12-admin-ui-cleanup` planned.** §4.5l: UI-only deploy (`fastapi` + `client-admin-ui`); dashboard 13 → 7 sections; six finance-domain tiles removed (`payment_terms`, `tax_codes`, `vendor_contracts`, `mailboxes`, `calendar`, `gl_reminders`); `users` tile relabelled "Key Roles Email (Uses)"; Mailboxes removed from header nav (`/mailboxes` page preserved). Cross-ref `05` v1.3.25, `15` v2.32. |
| 2.52 | 2026-05-26 | **`0.14.9-binding-authority` shipped.** §4.5k deploy (migration `060`, workers, Client Admin `/binding-authority`, finance approval queues); §20.0.1/E → `060`. Cross-ref `10` §7, `05` v1.3.24, `15` v2.31, `16` v2.7. |
| 2.51 | 2026-05-20 | **§4.5j finance-ui setup screens.** Counterparty/agreements/calendar moved from Client Admin; `require_finance_setup_access`; §20.2 `e73c869`. Cross-ref `15` v2.30, `05` v1.3.23. |
| 2.50 | 2026-05-20 | **§8.22 subaccount edit UI.** §4.5i: Edit/Save on Subaccounts; UI-only deploy `9b0662e`; §20.2 row. Cross-ref `15` v2.29, `05` v1.3.22. |
| 2.49 | 2026-05-20 | **§8.22 credit limit UI.** §4.5i pre-deploy: credit on Subaccounts tab; §20.2 UI patch row. Cross-ref `15` v2.28, `05` v1.3.21. |
| 2.48 | 2026-05-20 | **`0.14.8` shipped.** §4.5i deploy order (build → migrate → UAT → up); correct `ar-worker`/`ap-worker` names; §20.0.1/E gate → `058`; §20.2 git `9350495`. |
| 2.47 | 2026-05-20 | **Counterparty accounts deploy (`0.14.8`, planned).** §4.5i implementation deploy; §20.0.1 planned migrations `055`–`058`. |
| 2.42 | 2026-05-25 | **Authoritative ops docs in suite.** §20.0.1 full production checklist (was `accfin/docs/PRODUCTION_DEPLOYMENT_CHECKLIST.md`); §20.2 deployment version history (was `accfin/docs/DEPLOYMENT_VERSION_HISTORY.md`). |
| 2.46 | 2026-05-20 | **COA Docker build fix (`8d6bf6e`).** §4.5h: Svelte 5 event-syntax note + commit; checklist E5.21; failed build leaves old UI image. |
| 2.45 | 2026-05-20 | **Tenant COA (`0.14.7-coa-tenant-import`).** §4.5h deploy (migration `054`, upsert import, search UX); fix §4.5g git path `/opt/bp0work/accounting`; §20.0.1 → `054`. Cross-ref `05` §4.16d.3, `15` §8.10. |
| 2.44 | 2026-05-20 | **Email signatures (`0.14.6`).** §4.5g: `OutboundMailService` + `mail_template_renderer`; Company preview; §20.0.1 target `0.14.6`; checklist E5.16–E5.17. Cross-ref `18` §10.2, `15` §8.17. |
| 2.43 | 2026-05-20 | **GL period reopen (`0.14.5`).** §4.5g reopen + retry smoke; §20.0.1 target `0.14.5`; §20.2 history row; checklist E5.14–E5.15. |
| 2.41 | 2026-05-25 | **Client Admin `0.14.4`.** §4.5g: GL period posting gate, override-post, finance-ui rebuild; §17.6 GL cutoff cron; Appendix §20.0 Gate E through `053`. |
| 2.40 | 2026-05-20 | **Client Admin `0.14.2`.** §4.5g: dashboard, signatures, PDF uploads, travel-info, calendar forward generate; migration `051`. |
| 2.39 | 2026-05-20 | **Client Admin deploy (`0.14.1`).** §4.5g: `admin.mmlogistix.bp0.work`, migrations `049`–`050`, Traefik UI p1 / API p100; `accfin/docs/CLIENT_ADMIN_UI.md`. |
| 2.38 | 2026-05-24 | **Escalation respond deploy (`0.13.22`).** §4.5f: comment form GET/POST; rebuild fastapi/ap-worker. |
| 2.38 | 2026-05-20 | **finance-ui Client/Vendor column fix (`0.13.10`).** §4.5e.1: AP → `client_vendor_name`; AR → `counterparty_name`; rebuild finance-ui only. |
| 2.37 | 2026-05-24 | **AP vendor extraction deploy (`0.13.21`).** §4.5e: Hermes v2 prompt; `client_vendor_name`; rebuild hermes/fastapi/finance-ui. |
| 2.36 | 2026-05-24 | **DOCX + PO/travel deploy (`0.13.20`).** §4.5d: migration `048`, rebuild gateway/ap/expense/hermes; verification steps. |
| 2.35 | 2026-05-24 | **Domain worker attachment volumes (`0.13.19`).** §4.5b: `ap-worker`, `ar-worker`, `expense-worker` mount `attachment-data`. |
| 2.34 | 2026-05-24 | **Gateway intake enqueue logging (`0.13.18`).** §4.5: poller `_enqueue_intake_for_email`; success/failure logs; manual requeue via `email_id`. |
| 2.33 | 2026-05-24 | **Supabase vs compose `db`; SMTP escalation gap.** §6.1.1: production data on Supabase pooler — compose `db` is empty. §19.2/§19.4/§19.4a: troubleshooting `HERMES_TIMEOUT`, escalation logged but no manager email (`17` §10.4.1). |
| 2.32 | 2026-05-20 | **Wasabi attachment archive on intake.** §15.4: `WasabiArchiveService` + `FINANCE_WASABI__ARCHIVE_ON_INTAKE`; deploy `0.13.8-wasabi-attachment-archive`. |
| 2.31 | 2026-05-20 | **Worker BLPOP idle fix.** §4.6: `DEFAULT_QUEUE_BLOCK_TIMEOUT_SEC = 5`; deploy `0.13.7-worker-blpop-idle-fix`. |
| 2.30 | 2026-05-20 | **Finance UI 2FA.** §4.6: `/settings/security`; deploy `0.13.6-finance-security-2fa`; finance-ui `0.13.3-security-2fa`. |
| 2.29 | 2026-05-20 | **Ollama CLI healthcheck.** Compose `ollama list`; deploy `0.13.5-ollama-healthcheck-cli`; supersedes v2.28 wget attempt. |
| 2.28 | 2026-05-20 | **Ollama healthcheck (superseded).** Compose `wget --spider` — wget unavailable in `ollama/ollama` image; deploy `0.13.4-ollama-healthcheck-wget`. |
| 2.27 | 2026-05-20 | **Case retry + Hermes timeout.** §4.6: manual `POST /cases/{id}/retry`; Hermes client 120s default; deploy `0.13.3-case-retry-hermes-timeout`. |
| 2.26 | 2026-05-20 | **Mail text sanitization.** §4.6: `sanitize_text()` at ingest on all parsed fields; deploy `0.13.1-mail-text-sanitize`. |
| 2.25 | 2026-05-20 | **Executive mail SOP.** §4.6: manager-first failure flow, sender ack, `finance_activity_log`; deploy `0.13.0-executive-mail-sop`. |
| 2.24 | 2026-05-20 | **PDF NUL sanitization.** §4.6 pipeline note; deploy version `0.12.9-mail-pdf-sanitize`. |
| 2.23 | 2026-05-20 | **Ollama extraction MVP.** §4.6: Hermes extract endpoints, model pull, container env; deploy `0.12.7-ollama-extraction`. §8.2: `qwen2.5vl:7b` for image OCR. Appendix 20 Hermes env aligned. |
| 2.22 | 2026-05-20 | **Gateway IMAP poller fix.** §4.5: per-mailbox async sessions, plain IMAP settings for `to_thread`; deploy `0.12.6-gateway-imap-poller`. |
| 2.21 | 2026-05-20 | **Mail Gateway poll.** §4.5: `FINANCE_MAIL__POLL_ENABLED` in `docker-compose.yml` (`gateway`), not `.env`; must be `true` in production. Appendix 20 `gateway` block aligned. |
| 2.20 | 2026-05-22 | **Deploy version index.** §5: Traefik v2.11; current `0.12.4-client-auth`; `accfin/docs/DEPLOYMENT_VERSION_HISTORY.md`. |
| 2.19 | 2026-05-20 | **Traefik UI root.** §5: no `PathPrefix('/')` in api-routes; `/` → finance-ui (priority 1); API prefixes priority 100; `0.12.2-traefik-ui-root`. |
| 2.6a | 2026-05-19 | **Production Traefik on VPS.** HTTPS + Let's Encrypt; `traefik:v2.11` (Docker API); `traefik.docker.network=accfin_frontend`. Commits `8a8564e`, `eccf320`, `51b0652`. |
| 2.18 | 2026-05-20 | **Traefik api-routes.yml.** §5: single-line `rule` in `accfin/traefik/dynamic/api-routes.yml`; `finance-api` service; deploy `0.12.1-traefik-routes`. |
| 2.17 | 2026-05-20 | **Final URL structure.** §5/§18/Appendix 20: `finance.mmlogistix.bp0.work` (UI + edge API paths); `admin.bp0.work` / `admin.mmlogistix.bp0.work` (post-MVP); FastAPI internal only; removed `api.bp0.work`. |
| 2.16 | 2026-05-19 | **Wasabi daily log — CSV only.** §15.4 `bp0workacc/logs/`: store `finance_daily_{YYYY-MM-DD}.csv` from 9pm SGT job (RFC 4180); removed `.json` and optional `.html` objects. Email digest attaches same file (`17` §10.7, `06` §7.4.1). |
| 2.15 | 2026-05-19 | **Wasabi `bp0workacc`.** §15.4: bucket `bp0workacc` with `logs/`, `backups/`, `transactions/`; daily log export; transaction-number folders. Supersedes `mmlogistix-backups`. |
| 2.14 | 2026-05-19 | **Monorepo paths.** Clone `/opt/bp0work/accounting`; compose from `accfin/`. UI dirs at monorepo root. |
| 2.13 | 2026-05-19 | **Deploy path.** `/opt/bp0work/accounting` (repo `bp0work/accounting`; was `accfin`). |
| 2.12 | 2026-05-19 | **Docs vs deployment.** Intro note: runbook applies to backend repo on host, not `platform_dox/` folder. |
| 2.11 | 2026-05-19 | **Mail transport.** Appendix §20.0 Gate D and gateway compose comment: IMAP-only; removed Microsoft Graph references. |
| 2.9 | 2026-05-19 | **Hierarchy-aligned daily log.** §17.5: digest recipient `cfo.mmlogistix@bp0.work` (CFO / Finance Director per `01` §3). §17.4 maintenance row unchanged. |
| 2.8 | 2026-05-19 | **Finance daily log (9pm SGT).** §17.4 maintenance row; new §17.5: cron/timer for `finance_activity_log` digest (`17` §10.7). |
| 2.7 | 2026-05-19 | **Public hostnames on bp0.work.** Traefik examples, SSL checks, CORS, and §11.1 template use `api.bp0.work`, `finance.bp0.work`, `traefik.bp0.work`; ACME email `admin@bp0.work`. §5 intro cross-ref `14` §9.0 and legacy `ADMIN_BASE_PATH`. Replaces `*.finance.mmlogistix.sg` / `admin@mmlogistix.sg`. |
| 2.6 | 2026-05-19 | **Ollama/Hermes legacy mapping.** §8 intro and §11.1: legacy direct Ollama vs target Docker/Hermes; `FINANCE_HERMES_API_KEY` only in deploy template. Cross-ref `14` §6.0–§6b, `04` §14.1. |
| 2.5 | 2026-05-19 | **§7.1 First-time Redis setup.** Step-by-step: generate password, set `requirepass` in `redis.conf`, set `FINANCE_REDIS__*` in `.env`, restart, verify with `redis-cli`, update healthcheck for authenticated Redis, dev vs production notes, password rotation. Introductory table for host/port/db/password. Renumbered §7.2–§7.4. |
| 2.4 | 2026-05-19 | §11.1: Redis — explicit `FINANCE_REDIS__HOST`, `PORT`, `DB`, `PASSWORD` (aligned with `14` §5, `env.example` §3). |
| 2.3 | 2026-05-19 | **Production `.env` template (§11.1).** Removed per-mailbox `FINANCE_MAIL__USER`/`PASSWORD` and global `FINANCE_SMTP__USERNAME`/`PASSWORD`/`FROM_ADDRESS` — credentials and From identity are per row in `mail_gateway_config` (Client Admin UI). Added `FINANCE_SENDGRID__API_KEY` only for admin UI OTP. Cross-ref `14` §1.4, §7b–§7c, `env.example`. |
| 2.2 | 2026-05-19 | Added §15.4 Wasabi Offsite Backup — full configuration (bucket, region, SSE, versioning, Object Lock), required env vars, wasabi-upload.sh and wasabi-restore.sh scripts, bucket structure, lifecycle rules (database 30d, Redis 7d, attachments 90d), monthly backup verification script. Updated §15.1 backup strategy table to show local vs Wasabi retention columns. Updated §15.2 and §15.3 to invoke wasabi-upload.sh on backup success. Expanded §14.2 Key Metrics to include Prometheus alert expression column, dead letter queue, worker heartbeat, and approval SLA breach rate. Added full §14.2 Prometheus alert rules YAML (10 alerting rules across application and infrastructure groups) and Alertmanager routing configuration. |
| 2.10 | 2026-05-19 | **Pre-production gates.** Appendix §20.0: five-gate go-live checklist (business sign-off, Phases 1–11, Expense Worker OBS-3, IMAP-only mail MVP, migrations). Gateway compose comment: IMAP-only for MVP; Graph deferred. |
| 2.1 | 2026-05-18 | Fix (OBS-3 from cross-document audit): Expanded §4.3 Resource Limits table to include all worker and infrastructure services that were previously absent (Hermes, Mail Gateway, Orchestrator, Workers — Accounts/AR/AP/Treasury/Expense). Added a pre-production gate callout under §4.3 documenting the three Phase 11 go-live conditions for the Expense Worker: (a) replace stub with full `workers/expense/Dockerfile`-based build, (b) confirm `depends_on` includes `hermes` and `redis` with `service_healthy`, (c) revisit resource limits post load-testing. Strengthened the `worker-expense` stub comment in Appendix 20 with the same three-point gate checklist and a reference to `19_Expense_Worker_Specification.md` §1. Fix (OBS-5 from cross-document audit): Confirmed migration chain `001`–`044` (including all `b`/`c`-suffix files `006b`, `026b`, `026c`, `035b`, `039b`) is complete and consistent across `06` §18.4, `16` §10, and `19` §11. No gaps or orphans found. No content changes required for OBS-5 — acknowledged in this entry for audit traceability. |
| 2.0 | 2026-05-18 | Fix (GAP-1, GAP-2 from audit): Added missing `gateway` service (Mail Gateway — Phase 3) and `orchestrator` service (Workflow Orchestrator — Phase 4) to Appendix 20 docker-compose.yml. Both services are fully documented in `02` §7/§9, `03` §2, and `17` §2.1 but were absent from the compose stack, meaning the `intake_queue` producer and `accounts_queue` dispatcher could not run from a standard `docker-compose up`. Each service uses a separate `Dockerfile` under its top-level directory (`gateway/Dockerfile`, `orchestrator/Dockerfile`), depends on `supabase-db` and `redis`, and exposes an internal health endpoint (gateway: 8002, orchestrator: 8003). Added both ports to §1.3 Port Allocation table. |
| 1.9 | 2026-05-17 | Fix (Issue 3 from cross-document audit): Updated §12.3 Phase-Based Migration Order table — Phase 11 row changed from `040–044` to `039b + 040–044` to include the mandatory ENUM extension migration `039b_add_expense_claim_case_type.py`. This migration runs between Phase 10 (`039`) and Phase 11 proper and must be applied before any Phase 11 table migrations. Aligns with `06_Database_Schema_Design.md` §14.2, `16_Migration_and_ORM_Specification.md` §10, and `19_Expense_Worker_Specification.md` §11 (all of which already listed `039b`). |
| 1.8 | 2026-05-17 | Fix: Corrected `FINANCE_AI__OLLAMA_MAX_RETRIES` in §11.1 production environment template from `5` → `3`. The value `5` was inconsistent with `env.example` (authoritative, `=3`), `14` §2.4 default (`3`), and `14` §19 template (`3`). No intentional production override was documented; aligning to the canonical default. |
| 1.7 | 2026-05-16 | Fix (Issue 1 from audit): Corrected §8.2 model pull list and §8.3 warm-up script — replaced `llama3.1` and `nomic-embed-text` with the canonical fallback chain from `04_Hermes_Integration_Spec.md` §14: `hermes3` (primary), `qwen2.5:7b` (extraction/reconciliation fallback), `qwen2.5:0.5b` (classification fallback). Added advisory note in §8.2 citing `04` §14 as the authoritative model list. `llama3.1` was a stale model name corrected in `07` v1.1; `nomic-embed-text` has no defined use in the specification suite. |
| 1.6 | 2026-05-16 | Fix (audit): Replaced stale bare env names (`DATABASE_URL`, `REDIS_URL`, `OLLAMA_URL`, `JWT_SECRET`) in §9.1 FastAPI container compose excerpt with `env_file` pattern consistent with Appendix 20 and `14` §19. Added advisory note in §9.1 explaining why `env_file` is preferred over explicit `environment:` for `FINANCE_*` variables. Added clarifying advisory block to §6.2 — explicitly flags that Supabase-internal variables (`JWT_SECRET`, `POSTGRES_PASSWORD`, etc.) are distinct from the application's `FINANCE_*` variables and must not be confused or conflated. |
| 1.5 | 2026-05-15 | Fix (Audit Issues 2 & 5): Rewrote §11.1 production environment template — replaced bare variable names (e.g. `DATABASE_URL`, `JWT_SECRET`) with correct `FINANCE_`-prefixed, `__`-delimited names matching `14_Environment_and_Configuration_Reference.md` §19 and `env.example`. Added advisory note directing developers to use `cp .env.example .env` rather than the summary block. Rewrote §11.2 secret generation script — replaced bare output variable names with correct `FINANCE_` names, added `FINANCE_PRIVACY_ENCRYPTION_KEY` and `FINANCE_BACKUP_ENCRYPTION_KEY` (Fernet, require Python cryptography), `FINANCE_HASH_SECRET`, `FINANCE_HERMES_API_KEY`, `FINANCE_GRAFANA__ADMIN_PASSWORD`/`GRAFANA_ADMIN_PASSWORD` pair. Added advisory note recommending `python scripts/generate-keys.py` as the preferred alternative. |
| 1.4.0 | 2026-05-15 | Fix (Issue 2.2): Corrected §12.3 Phase-Based Migration Order table — previous numbers were ~12 migrations out of sync with authoritative `06` §18.4 / `16` §10. Updated all phase ranges, added Phase 11 row, added authoritative-source note. Fix (Issue 2.8): Removed stale "remove this comment" warning from `worker-expense` service in Appendix 20 (now that `19_Expense_Worker_Specification.md` is authored). |
| 1.3.0 | 2026-05-14 | Updated `worker-expense` service comment in Appendix 20: replaced startup warning with active implementation reference to `19_Expense_Worker_Specification.md`. Updated Companion Documents table. |
| 1.2.0 | 2026-05-14 | Fix 3: Added startup warning comment to `worker-expense` Docker service stub in Appendix 20 — `workers.expense.main` does not exist until Phase 11; prevents developer confusion during early stack bring-up. |
| 1.1.0 | 2026-05-14 | Added Hermes AI orchestration service, five domain worker services (accounts, ar, ap, treasury, expense), and Grafana monitoring service to Appendix 20 docker-compose.yml. Fixed Ubuntu OS version to 24.04 LTS. Fixed Ollama model names (hermes3, llama3.1, nomic-embed-text). Added Hermes port 8001 to port allocation table. |
| 1.0.0 | 2026-05-11 | Initial runbook — complete Docker Compose stack, Traefik config, Supabase/Redis/Ollama setup, CI/CD pipeline, backup/recovery, disaster recovery, operational procedures, security hardening, troubleshooting guide |
