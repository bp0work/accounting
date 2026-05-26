# AI Finance Operations Platform

# Project Overview

## Version 2.64

## Filename: 00_Project_Overview.md

## Prepared For: mmlogistix

## Date: 25 May 2026

---

# Companion Documents

| Document | Filename |
|----------|----------|
| Project Overview | 00_Project_Overview.md |
| **Product Overview** | **Product_Overview.md** v1.1 *(non-technical — purpose, roles, agents, escalations, compliance; §11 implementation status)* |
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

## Table of Contents

1. [Purpose](#1-purpose)
2. [Scope](#2-scope)
3. [Architecture Summary](#3-architecture-summary)
4. [Document Map](#4-document-map)
5. [Delivery Roadmap](#5-delivery-roadmap)

---

## 1. Purpose

The **AI Finance Operations Platform** is an intelligent workflow automation system designed for **mmlogistix** to streamline finance operations through AI-powered email intake, automated transaction classification, intelligent routing, policy-enforced approvals, and tamper-evident audit logging.

### 1.1 Problem Statement

Finance operations currently rely on manual, repetitive processes:

- **Manual email processing** — Inbound financial emails (invoices, payment advices, statements) are read and triaged by hand
- **Manual document classification** — Staff must determine whether an email relates to AR, AP, treasury, or other functions
- **Disconnected approval workflows** — Approvals happen via email chains, spreadsheets, or verbal sign-offs with no systematic tracking
- **Inconsistent audit trails** — No unified log of who approved what, when, and why
- **Spreadsheet-driven controls** — Business rules live in undocumented spreadsheets rather than enforceable policies
- **Repetitive data entry** — Information is manually transcribed from emails into accounting systems

These manual processes create operational risks: delayed processing, duplicate postings, reconciliation delays, inconsistent accounting treatment, weak audit visibility, dependence on key personnel, and scalability limitations.

### 1.2 Solution Approach

The platform **augments** finance operations — it does not replace finance personnel. Core principles:

- **Human authority overrides AI output** — All AI decisions are recommendations, not final actions
- **Accounting treatment follows policy** — A configurable policy engine enforces consistency
- **All financial actions are auditable** — Immutable audit trails with tamper-evident hash chains
- **Segregation of duties is preserved** — GM/COO cannot approve financial postings
- **Exception handling is mandatory** — Low-confidence transactions always route to human review
- **Governance takes priority over automation speed** — Controls are never relaxed for convenience

### 1.3 Target Metrics


| Metric                         | Target             | Measurement Period |
| ------------------------------ | ------------------ | ------------------ |
| Classification accuracy        | >= 95%             | Post-UAT           |
| Extraction accuracy            | >= 90%             | Post-UAT           |
| Exception rate                 | < 10%              | Ongoing            |
| Reconciliation auto-match rate | >= 80%             | Post-Phase 8       |
| Approval SLA                   | < 4 business hours | Ongoing            |
| Platform uptime                | 99.5%              | Ongoing            |


### 1.4 Disaster Recovery Targets


| Target                         | Value      |
| ------------------------------ | ---------- |
| Recovery Point Objective (RPO) | <= 1 hour  |
| Recovery Time Objective (RTO)  | <= 4 hours |


---

## 2. Scope

### 2.1 Phase 1 — MVP (Included)


| Module                             | Functional Area                                                                                                     | Description |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ----------- |
| **Accounts Receivable**            | Invoice intake, credit/debit note handling, payment advice processing, SOA generation, reconciliation support       |             |
| **Accounts Payable**               | Supplier invoice processing, PO/GRN validation, payment proposal handling, supplier reconciliation                  |             |
| **Treasury / Bank Reconciliation** | Bank reconciliation, FX handling, cash matching, suspense account handling                                          |             |
| **Expense Management**             | Employee expense claims, travel policy validation, reimbursement workflows, duplicate claim detection               |             |
| **Finance Workflow Approvals**     | 3-tier approval system (STP / Assisted / Exception), escalation management, SLA monitoring                          |             |
| **Accounting Policy Framework**    | Version-controlled policies for revenue/expense recognition, GST, FX, payment allocation, reconciliation tolerances |             |
| **Audit Logging**                  | Tamper-evident hash chain, immutable audit trails, approval history, policy version tracking                        |             |
| **Workflow Orchestration**         | Email intake → AI classification → policy validation → routing → approval → posting → audit                         |             |
| **Executive Email Operations**     | Domain executives with IMAP listeners; managers (`acc`, `fin`, `cfo`, `ceo`) human-only; Approve/Reject/Escalate chain (`01` §3.2.3, §6.8) |             |


### 2.2 Post-MVP Phase 2 — Future Scope (Excluded from MVP)


| Module                             | Functional Area                                                                                       | Planned  |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------- | -------- |
| **Payroll**                        | Payroll journal support, statutory contribution handling, payroll reconciliation                      | Post-MVP |
| **Fixed Assets**                   | Capitalization assessment, depreciation management, disposal handling                                 | Post-MVP |
| **Financial Control & Compliance** | Policy compliance analytics, advanced exception monitoring, RAG knowledge base                        | Post-MVP |
| **Advanced Reporting**             | Custom dashboards, trend analysis, predictive analytics                                               | Post-MVP |


### 2.3 Approval & Risk Management

The platform implements a **3-tier approval system** based on AI confidence scores and risk factors:


| Tier       | Name                              | Confidence  | Approval Required      | Description                                                   |
| ---------- | --------------------------------- | ----------- | ---------------------- | ------------------------------------------------------------- |
| **Tier 1** | STP (Straight-Through Processing) | >= 0.90     | None                   | Auto-release for low-risk, well-understood transactions       |
| **Tier 2** | Assisted Processing               | 0.70 – 0.89 | Accounts team          | Medium-risk transactions with human review                    |
| **Tier 3** | Exception Workflow                | < 0.70      | CFO / Finance Director | High-risk or uncertain transactions requiring senior approval |


Additional risk factors that may elevate a transaction's tier: policy validation failures, duplicate risk, reconciliation mismatch, and historical anomalies.

### 2.4 Approval Authority Separation


| Role                         | Financial Approvals                                                                     | Operational Approvals                                              |
| ---------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| **CFO / Finance Director**   | Journal entries, accounting treatment, financial postings, write-offs, policy overrides | —                                                                  |
| **Finance Agent / Accounts** | Low/medium value transactions, routine AP/AR                                            | —                                                                  |
| **Financial Analyst**        | **NONE** — analysis, reporting, and month-end close only                                | —                                                                  |
| **GM / COO**                 | **NONE** — GM cannot approve financial postings                                         | Operational workflows, customer/vendor communications, escalations |


This segregation is enforced at **4 architectural layers**: database constraints, API authorization, workflow state machine guards, and policy engine rules. It cannot be bypassed for implementation simplicity.

### 2.5 Compliance Framework

The platform supports:

- **Singapore PDPA** — Personal data protection obligations (consent, purpose limitation, access/correction)
- **MAS TRM Guidelines** — Technology risk management where applicable
- **Financial audit retention** — 7-year audit log retention with tamper-evident hash chains
- **Client-defined data sovereignty** — Data stored in Singapore-region cloud infrastructure

### 2.6 Documentation workspace vs implementation repositories

**Local layout (bp0work 20260511):**

```text
bp0work 20260511/
├── platform_dox/    # This specification suite — Cursor reference; NOT pushed to GitHub
└── application/     # Runnable monorepo — git push ONLY this folder
```

The folder **`platform_dox/`** (this specification suite) is **documentation and contracts only**. It is normal — and required — that the following are **not** in `platform_dox/` and are **not** committed to GitHub from this folder:

| Expected outside `platform_dox` | Location |
|--------------------------------|----------|
| Backend (`app/`, workers, gateway, Alembic, compose) | **`application/accfin/`** (GitHub: [`accounting/accfin`](https://github.com/bp0work/accounting/tree/main/accfin); VPS: `/opt/bp0work/accounting/accfin`) |
| SvelteKit UIs | **`application/finance-ui/`**, `platform-admin-ui/`, `client-admin-ui/` |
| Hermes / Ollama containers | `application/accfin/docker-compose.yml` (`04`, `11` Appendix 20) |
| Production `.env`, API keys, Supabase service role | Host secrets only (`14`, `03` §17.4) — template in `platform_dox/env.example` |

**Git rule:** Push **`application/`** to the implementation remote. **Never push `platform_dox/`** to that repository.

Repository trees in §3.6 and `03` §2 describe the **target layout inside `application/`**, not the contents of `platform_dox/`. See **`README.md`** in this folder for the full in/out matrix.

`03` and `11` assume those implementation artifacts exist at deploy time; they are not gaps in the spec suite.

---

## 3. Architecture Summary

### 3.1 Technology Stack


| Layer                | Technology                       | Purpose                                 |
| -------------------- | -------------------------------- | --------------------------------------- |
| **Language**         | Python 3.12                      | Application runtime                     |
| **API Framework**    | FastAPI                          | RESTful API gateway                     |
| **AI Engine**        | Hermes 3 (via Ollama)            | On-device LLM inference                 |
| **Fallback AI**      | qwen2.5:7b / qwen2.5:0.5b        | Task-differentiated fallback (extraction / classification) — see `04` §8.4 |
| **Database**         | Supabase PostgreSQL              | Primary data store with RLS             |
| **Cache & Queue**    | Redis 7                          | Job queues, caching, event streaming    |
| **Reverse Proxy**    | Traefik v2.11                    | TLS termination, routing, rate limiting |
| **ORM**              | SQLAlchemy (async)               | Database abstraction                    |
| **Migrations**       | Alembic                          | Schema version control                  |
| **Monitoring**       | Prometheus + Grafana             | Metrics and observability               |
| **Containerization** | Docker + Docker Compose          | Deployment packaging                    |
| **Infrastructure**   | Hostinger VPS (Ubuntu 24.04 LTS) | Production hosting                      |


### 3.2 High-Level Architecture

```plaintext
Internet
    |
    v
[Traefik] — TLS 1.3 (Let's Encrypt), public hostnames only for UIs
    |
    +-- https://finance.mmlogistix.bp0.work  --> [finance-ui] Approval UI (mmlogistix finance team)
    |       \-- path routing (/auth, /mail, /approvals, ...) --> [FastAPI] (internal Docker only)
    +-- https://admin.bp0.work  --> [platform-admin-ui] (post-MVP, bp0.work staff)
    +-- https://admin.mmlogistix.bp0.work  --> [client-admin-ui] (post-MVP, mmlogistix admins)
    |
    v
[FastAPI] — http://fastapi:8000 on Docker network; no public API subdomain
    |
    v
[Workflow Orchestrator] — State machine, routing
    |
    v
[Policy Engine] — JSONB rule evaluation
    |
    v
[Redis Queue] — Job distribution, event streaming
    |--- intake_queue      (executive mailbox mail only → Accounts Worker service classifier; NOT acc inbox)
    |--- accounts_queue    (classified cases → Accounts/AR/AP Workers; routing by case_type)
    |--- retry_queue       (Redis Sorted Set — cases scheduled for retry)
    |--- dead_letter_queue (cases that exceeded max retries — admin only)
    |
    Note: AR, AP, and Accounts Workers all consume from accounts_queue and route
    internally by case_type. Treasury Worker is triggered via POST /reconciliation/start
    or scheduler — not queue-driven. See 17_Worker_Specifications.md §2.1.
    |
    v
[Worker Services]
    |--- Accounts Worker  (email classification, routing, case creation)
    |--- AR Worker        (invoice extraction, payment advice, SOA)
    |--- AP Worker        (supplier invoice handling, PO validation)
    |--- Treasury Worker  (reconciliation, FX, cash matching — API/scheduler triggered)
    |--- Expense Worker   (expense claims, policy validation, reimbursement — Phase 11)
    |
    v
[Supabase PostgreSQL] — 40 tables (Phases 1–10; **43** including Phase 11 expense + email SOP — see `06` §7.4–§7.6, §14, `19` §3), RLS, audit triggers
    |--- Business Data (cases, transactions, entities)
    |--- Configuration (policies, rules, chart of accounts)
    |--- Audit (immutable audit log with hash chain)
    |--- Identity (users, roles, permissions)
```

### 3.3 AI Processing Pipeline

```plaintext
Inbound Email
    |
    v
[Mail Gateway] — IMAP poll on executive_agent mailboxes only (accar, accap, … — not acc/fin/cfo/ceo)
    |--- Duplicate detection (Message-ID, content hash, attachment hash)
    |--- Attachment extraction → Supabase Storage
    |--- intake_queue → Accounts Worker service (Phase 5; see 17 §2.1.1)
    |
    v
[AI Classification] — Hermes 3 via Ollama (Accounts Worker consumes intake_queue)
    |--- Document type detection (invoice, payment advice, statement, etc.)
    |--- Entity extraction (amounts, dates, counterparty, references)
    |--- Confidence scoring (0.00 – 1.00)
    |--- Chain-of-thought reasoning (when enabled)
    |
    v
[Routing Decision — Stage 1: Classification Gate (INBOUND → CLASSIFIED)]
    |--- Confidence >= 0.70  →  CLASSIFIED (queued for domain worker processing)
    |--- Confidence < 0.70   →  MANUAL_REVIEW (no queue push — human must classify)
    |
    | Note: The STP / Assisted / Exception split is a NET EFFECT of two stages,
    | not a single branch. Stage 2 occurs inside the domain worker (below).
    |
    v
[Domain Worker Processing — Stage 2: STP Gate (PROCESSING → APPROVED / PENDING_APPROVAL)]
    |--- Confidence >= 0.90 + policy pass + no risk flags  →  STP (auto-release, Tier 1)
    |--- Confidence 0.70-0.89 OR policy flags              →  Assisted (Tier 2 approval)
    |--- Policy violation OR high-risk flags               →  Exception (Tier 3 / senior approval)
    |
    | Authoritative logic: 08_Workflow_State_Machine.md §3.2 (transitions) and §7 (STP eligibility)
    |
    v
[Policy Engine] — JSONB rule evaluation
    |--- 15 condition operators, 8 action types
    |--- 10 default policies (AP/AR approval, GST, FX, reconciliation)
    |--- Restrictiveness ranking (1-8 scale)
    |
    v
[Approval Workflow] — Table-driven state machine
    |--- 11 case statuses, 30 transitions (exact count)
    |--- Guard predicates, entry/exit actions
    |--- SLA monitoring with escalation
    |
    v
[Posting / Communication]
    |--- Journal entry generation
    |--- Counterparty communication (email/SOA)
    |--- GL account posting
    |
    v
[Audit Logging] — Immutable, tamper-evident
    |--- SHA-256 sequential hash chain
    |--- 7-year retention
    |--- Event-driven (35 event types via CloudEvents)
```

### 3.4 Event Architecture

The platform uses **CloudEvents 1.0** for event interoperability with Redis Pub/Sub and Redis Streams:

- **35 event types** covering the full workflow lifecycle
- **Real-time UI updates** via Server-Sent Events (SSE)
- **Event replay capability** for debugging and auditing
- **Idempotent consumers** with deduplication (24h TTL)

### 3.5 Security Architecture


| Layer                     | Control                           | Implementation                                         |
| ------------------------- | --------------------------------- | ------------------------------------------------------ |
| **Authentication**        | Argon2id + JWT + TOTP 2FA         | 15-min access tokens, 7-day refresh tokens             |
| **Authorization**         | RBAC with **9** roles (incl. `financial_analyst`); **28** permission codes at Phase 2 seed (`06` §19.2); **31** after Phase 11 migration `043` adds `expenses:read`, `expenses:write`, `expenses:approve` (`13` §5.6); two-tier system admins per `13` §5.9 | Permission-based API guards                            |
| **Encryption at rest**    | AES-256                           | Database volumes, attachments, PII fields              |
| **Encryption in transit** | TLS 1.3                           | All network communication                              |
| **Audit integrity**       | SHA-256 hash chain                | Sequential, tamper-evident                             |
| **Segregation of duties** | 4-layer enforcement               | DB constraints, API auth, state machine, policy engine |
| **Secrets management**    | Quarterly rotation                | Automated rotation scripts                             |


### 3.6 Repository Structure

> **Not in `platform_dox/`:** The tree below is **`accounting/accfin/`** inside monorepo `bp0work/accounting` (deploy `/opt/bp0work/accounting/accfin`). UIs are sibling dirs `finance-ui/`, `platform-admin-ui/`, `client-admin-ui/` (`README.md`, §2.6).

```plaintext
accfin/                    # Under bp0work/accounting — backend (not platform_dox/)
|
|--- app/                    # FastAPI application
|      |--- api/             # Route handlers (18 functional areas)
|      |--- core/            # Configuration, dependencies
|      |--- models/          # SQLAlchemy ORM models (40 tables Phases 1–10; 43 with Phase 11 + SOP)
|      |--- schemas/         # Pydantic request/response models
|      |--- services/        # Business logic layer
|      |--- security/        # Auth, encryption, audit
|      |--- events/          # Event bus, producers, consumers
|      |--- policies/        # Policy engine, condition evaluator
|      |--- state_machine/   # Workflow state machine
|      |--- utils/           # Helpers, validators
|
|--- agents/                 # Hermes AI coordination layer
|      |--- classification/  # Document type classification
|      |--- extraction/      # Entity extraction prompts
|      |--- validation/      # Output guardrails
|      |--- prompts/         # System prompt templates
|
|--- workers/                # Background job processors
|      |--- accounts/        # Accounts Worker
|      |--- ar/              # AR Worker
|      |--- ap/              # AP Worker
|      |--- treasury/        # Treasury Worker
|      |--- expense/         # Expense Worker (Phase 11)
|
|--- gateway/                # Email intake gateway
|      |--- imap/            # IMAP client (inbound mail — only supported transport)
|      |--- parser/          # Email normalization, attachment handling
|
|--- orchestrator/           # Workflow orchestration
|      |--- engine/          # State machine engine
|      |--- router/          # Case routing logic
|      |--- scheduler/       # Cron jobs, SLA monitoring
|
|--- prompts/                # AI prompt templates (versioned)
|--- policies/               # Policy definitions
|      |--- accounting/      # Revenue, expense, GST policies
|      |--- approval/        # Approval threshold policies
|      |--- tax/             # Tax handling rules
|      |--- reconciliation/  # Reconciliation tolerance policies
|
|--- migrations/             # Alembic database migrations
|      |--- versions/        # Migration scripts per phase
|
|--- tests/                  # Test suite
|      |--- unit/            # ~60% — pure functions, models, guards, evaluators
|      |--- contract/        # ~20% — API contract tests (schemathesis + httpx); run as dedicated CI job
|      |--- integration/     # ~15% — DB, Redis, Ollama, auth service interactions
|      |--- e2e/             # ~5% — full workflow simulation
|      |--- uat/             # Manual UAT scenarios (`12` §11), outside automated pyramid
|      |--- fixtures/        # Test data factories
|      |--- golden/          # Golden test sets for AI
|
|--- docs/                   # Documentation
|      |--- 00_Project_Overview.md
|      |--- 01_Business_Requirement_Document.md
|      |--- 02_Technical_Architecture.md
|      |--- 03_Cursor_Development_Brief.md
|      |--- 04_Hermes_Integration_Spec.md
|      |--- 05_API_Specification.md
|      |--- 06_Database_Schema_Design.md
|      |--- 07_AI_Runtime_Sequence_Diagrams.md
|      |--- 08_Workflow_State_Machine.md
|      |--- 09_Event_Model_Specification.md
|      |--- 10_Policy_Engine_Specification.md
|      |--- 11_Deployment_Operations_Runbook.md
|      |--- 12_Testing_and_UAT_Strategy.md
|      |--- 13_Security_and_Compliance_Specification.md
|      |--- 14_Environment_and_Configuration_Reference.md
|      |--- 15_Approval_UI_Specification.md
|      |--- 16_Migration_and_ORM_Specification.md
|      |--- 17_Worker_Specifications.md
|      |--- 18_Notification_Service_Specification.md
|      |--- 19_Expense_Worker_Specification.md
|      |--- 20_Git_Workflow_and_Prompt_Management.md
|      |--- 21_openapi.yaml
|      # Multi-service stack — see 11_Deployment_Operations_Runbook.md Appendix 20
|--- Dockerfile
|--- pyproject.toml
|--- alembic.ini
|--- README.md
```

---

## 4. Document Map

### 4.1 Document Suite

The complete specification suite comprises **22 documents** organized by function. Each document is independently consumable by Cursor for code generation while maintaining cross-document consistency.

#### Foundation Documents (Upstream Reference)


| #   | Document                              | Purpose                                                                              | Status |
| --- | ------------------------------------- | ------------------------------------------------------------------------------------ | ------ |
| —   | `01_Business_Requirement_Document.md` | Business requirements, scope definition, approval framework, compliance requirements | Input  |
| —   | `02_Technical_Architecture.md`        | Technology stack, high-level architecture, infrastructure requirements               | Input  |
| —   | `03_Cursor_Development_Brief.md`      | §2.1 implementation file map (`0.14.8` planned); repository structure, phases, coding rules | Input  |


#### Specification Documents (Engineering Reference)

> **Note on numbering:** Documents `01`, `02`, and `03` appear in the Foundation table above and are not repeated here. The `#` column below starts at `00` (the master index) then jumps to `05`–`21` (the engineering specs and contract). There are no missing documents — `04` (`04_Hermes_Integration_Spec.md`) is listed in the Companion Documents table at the top of every file but is an engineering spec consumed during worker and AI implementation phases. The suite contains exactly 22 documents total.

| #      | Document                                        | Lines                                                                                                                                               | Contents       | Downstream Dependencies |
| ------ | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- | ----------------------- |
| **00** | `00_Project_Overview.md`                        | **v2.48** — master index, scope summary, architecture at-a-glance, document map, delivery roadmap                                                    | —              |                         |
| **04** | `04_Hermes_Integration_Spec.md`                 | Hermes client (`HermesClient` 120s default), HTTP API contract, Ollama wire format, retry/circuit breaker (`04` v2.9) | 02, 07, 17     |                         |
| **05** | `05_API_Specification.md`                       | COA §4.16d.3; finance setup APIs §4.16d.4/8/11–13 (`05` v1.3.23, shipped `0.14.8`) | 06, 08, 10     |                         |
| **06** | `06_Database_Schema_Design.md`                  | §4.1a–c subaccounts, payment terms, tax codes (`06` v2.10.7); migrations `055`–`058` planned | 05, 08, 09, 13, 15 |                     |
| **07** | `07_AI_Runtime_Sequence_Diagrams.md`            | 13 sequence areas incl. §13 manager email Escalate (same case, not Approval SLA); email intake → STP → exception → Phase 11 expense | 05, 06, 08, 10, 17 |                         |
| **08** | `08_Workflow_State_Machine.md`                  | 11 case statuses, 30 transitions (exact), guard predicates, `CaseStateMachine` Python class, `CaseService`, FastAPI routes, pytest tests                   | 05, 06, 09, 10 |                         |
| **09** | `09_Event_Model_Specification.md`               | CloudEvents 1.0 envelope, 35 event types, Redis Pub/Sub + Streams architecture, SSE endpoint, `EventBus` + `EventProducer` Python classes           | 06, 08, 11     |                         |
| **10** | `10_Policy_Engine_Specification.md`             | Condition language (15 operators), action language (8 types), 10 default policies, `ConditionEvaluator` + `PolicyEngine` Python classes             | 05, 06, 08     |                         |
| **11** | `11_Deployment_Operations_Runbook.md`           | **v2.52:** §4.5k binding authority (`0.14.9`); §4.5j finance-ui setup; §4.5i `0.14.8` | 09, 14         |                         |
| **12** | `12_Testing_and_UAT_Strategy.md`                | Testing pyramid per §1.1: ~60% unit, ~20% API contract, ~15% integration, ~5% E2E; UAT manual on top; golden AI sets, **11** UAT scenarios (UAT-010/011 email SOP, `12` v1.6.4), Phase 11 §16, factories | 05, 06, 08, 10 |                         |
| **13** | `13_Security_and_Compliance_Specification.md`   | **v2.0:** Singapore statute citations (Companies Act §199, IRAS GST, MAS TRM 2021); PDPA 2020, Cybersecurity Act 2018; §4.5 TRM alignment, §4.6 IRAS GST; Argon2id + JWT + TOTP, segregation, tamper-evident audit | 06, 14         |                         |
| **14** | `14_Environment_and_Configuration_Reference.md` | Env vars, hosts (`14` v2.32); Client Admin `admin.mmlogistix.bp0.work`; deploy **`0.14.6-email-signature`**          | 05, 06, 11, 13 |                         |
| **15** | `15_Approval_UI_Specification.md`               | §8.22–§8.24 finance setup UI (counterparty, agreements, calendar); §8.13 Client Admin nav (`15` v2.30) | 05, 06, 08, 09, 13 |                       |
| **16** | `16_Migration_and_ORM_Specification.md`         | Phase 2 worked examples; Phase 13 migrations `055`–`058` (`16` v2.6, shipped `0.14.8`) | 06             |                         |
| **17** | `17_Worker_Specifications.md`                   | Executive mail SMTP §10.3.1 (`17` v2.35, `0.14.6` signatures); GL gate §2.1.3; Expense Worker in `19`. | 06, 07 |          |
| **18** | `18_Notification_Service_Specification.md`      | SMTP outbound + tenant signature §10.2 (`18` v1.5.0, shipped `0.14.6`); `NotificationDispatcher` consumer still pending §1.1 | 05, 06, 09, 15 |        |
| **19** | `19_Expense_Worker_Specification.md`            | Phase 11 implementation contract for the Expense Worker: `expense_claims`, `expense_line_items`, `expense_policies` DDL, worker handler, policy validation, risk flags, Alembic migrations (039b + 040–044), ORM models, seed data, testing requirements | 06, 07, 10, 17 |        |
| **20** | `20_Git_Workflow_and_Prompt_Management.md`      | Authoritative Git workflow policy (branch naming, commit conventions, PR rules, merge approval, release tagging, semantic versioning, rollback) and prompt management standard (file naming, versioning, rollback, testing, storage, auditability). Extends `04` §7. | 04             |        |
| **21** | `21_openapi.yaml`                               | Machine-readable OpenAPI 3.1 contract (**v1.0.12**) — **127** operations; de-anchored YAML for CI; mail escalation JSON schema; `POST /internal/jobs/finance-daily-log`. Lockstep with `05` Appendix A. | 05             |        |


### 4.2 Cross-Document Consistency Matrix

To maintain consistency across the specification suite, the following conventions are enforced:


| Convention                | Applied Across         | Example                                                                                                           |
| ------------------------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Confidence thresholds** | BRD §9, 07, 08, 10, 14 | STP >= 0.90, Assisted 0.70–0.89, Exception < 0.70. Note: STP eligibility requires confidence >= 0.90 **plus** policy pass (counterparty recurring, no risk flags, amount below threshold) — not confidence alone. See `08` §5.1 guard `stp_eligible` and `10` for the full condition. |
| **Case status** (lifecycle) | 05, 06, 07, 08        | `inbound`, `classified`, `processing`, `pending_approval`, `approved`, `posted`, `completed`, `rejected`, `exception`, `manual_review`, `on_hold` (`06` §4.2 enum; `08` §2.1). Journal/workflow use separate enums (e.g. journal `draft` / `posted`). |
| **Event `type` (CloudEvents)** | 07, 08, 09, 11, 13 | Short names in `09_Event_Model_Specification.md` §2–4 and §4.1 inventory, e.g. `case.created`, `case.classified`, `approval.requested`, `approval.approved`, `journal.posted`. SSE uses the same names (see `09` §15.2). |
| **Policy actions**        | 06, 08, 10             | `require_approval`, `auto_release`, `escalate`, `flag_review`, `block`                                            |
| **Approval tiers**        | BRD §8, 05, 08, 10     | Tier 1 (auto), Tier 2 (accounts), Tier 3 (CFO)                                                                    |
| **Organizational hierarchy** | BRD §3, 17 §10 | CEO → CFO → Manager Accounts (`acc`) / Manager Finance (`fin`) → executives; escalation to CFO → CEO; authoritative diagram `01` §3.1 |
| **Role `name` (RBAC)**    | BRD §3.2.4, 05, 06, 08, 13 | Seeded system roles in `06` §19.1: `platform_admin`, `client_admin`, `cfo`, `finance_manager`, `finance_officer`, `accounts_clerk`, `auditor`, `general_manager`, `financial_analyst`. Two-tier administration: Platform Admin manages Client Admin identity and SMTP sender; Client Admin manages tenant mailboxes, COA import, and tenant settings (`13` §5.9). BRD “CFO / Finance Director” ↔ Tier 3 slug **`cfo`**. The `general_manager` role has no `approvals:approve` or `journal-entries:write` (BRD GM/COO segregation — `13` §5.7). |
| **Database table names**  | 05, 06, 08, 09, 10, 13 | `cases`, `case_timeline`, `policies`, `policy_rules`, `audit_logs`, `users`, `roles` (note: there is no `case_events` table — state history lives in `case_timeline` §4.3 and event bus uses `audit_logs`) |
| **Email SOP persistence** | 06 §7.4–§7.6, 16 §10, 17 §10 | Manager escalations: `case_escalations` (`046`). Client clarification queue: `pending_outbound_emails`. Digest: `finance_activity_log` (`045`). Not `cases.workflow_metadata` alone. |
| **Mail intake boundary** | 17 §2.1.1, `06` §19.7 | Gateway IMAP poll: `executive_agent` only. `intake_queue` → Accounts Worker **service** (Phase 5). `acc`/`fin`/`cfo`/`ceo` = `manager_human`, no poller. |
| **Environment variables** | 11, 13, 14             | `FINANCE_`* prefix, `__` nested delimiter                                                                         |
| **API path prefix**       | 05, 12                 | `/api/v1/`                                                                                                        |


---

## 5. Delivery Roadmap

### 5.1 Development Phases

The platform is delivered in **11 sequential phases**, each building on the previous. Each phase has defined deliverables, database migrations, and acceptance criteria. Phases 1–11 are all **MVP scope**; post-MVP modules (Payroll, Fixed Assets, Advanced Reporting, etc.) are listed in §5.3.


| Phase  | Name                                           | Duration | Deliverables                                                                                         | DB Migrations (Alembic `.py` files — see `06` §18.4 and `16` §10)                                                                                                            | Key Specs          |
| ------ | ---------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| **1**  | Infrastructure Setup                           | 1 week   | Docker Compose stack, Traefik, PostgreSQL, Redis, Ollama, monitoring baseline                        | No DB migrations — infrastructure only                                                                                                                                        | 11, 14             |
| **2**  | Authentication & RBAC                          | 1 week   | Two-tier system admins, RBAC (9 roles incl. `financial_analyst`; 28 permissions at seed, 31 after Phase 11 `043`), Argon2id + JWT + TOTP | `001`–`005`, `006_seed_roles_and_permissions.py`, `006b_create_password_history_table.py`, `006c_seed_system_admin_users.py` | 05, 06, 13         |
| **3**  | Mail Gateway                                   | 1 week   | **IMAP** (`bp0.work:993`) on **`executive_agent` mailboxes only**; normalize, dedup, attachments → `intake_queue` | `007`–`009` | 05, 06, 07, 14 §7, 17 §2.1.1–§2.1.2 |
| **4**  | Workflow Orchestrator + Policy Engine Scaffold | 2 weeks  | State machine engine, policy engine core (15 operators, 8 actions), routing logic                    | `010_create_counterparty_table.py` → `024_create_approval_configuration_table.py` (15 migrations — see `06` §18.4)                                                            | 05, 06, 08, 09, 10 |
| **5**  | Accounts Worker                                | 1 week   | **Service** consuming `intake_queue` (from Phase 3 Gateway on executive mailboxes): classify, case creation — **not** IMAP on `acc.mmlogistix` | `025_seed_default_policies.py`, `026_create_queue_messages_table.py`                                                                                                          | 05, 06, 07, 10, 17 §2.1.1, §3 |
| **6**  | AR Worker                                      | 1 week   | Invoice extraction, payment advice processing, SOA workflows, customer reconciliation                | `026b_create_purchase_orders_table.py` (Phase 7 AP prerequisite — see `06` §13a and `16` §10)                                                                                | 05, 06, 07, 10, 17 |
| **7**  | AP Worker                                      | 1 week   | Supplier invoice handling, PO validation, 3-way matching, payment proposals                          | No additional tables — uses `purchase_orders` created in Phase 6 migration `026b`                                                                                            | 05, 06, 07, 10, 17 |
| **8**  | Treasury & Reconciliation                      | 2 weeks  | Bank reconciliation, FX handling, cash matching, suspense account management                         | `027_create_coa_accounts_table.py` → `033_create_reconciliation_matches_table.py` (7 migrations — see `06` §18.4)                                                             | 05, 06, 07, 10, 17 |
| **9**  | Approval UI                                    | 1 week   | Approval dashboard, case detail view, action buttons, audit trail viewer, notification preferences   | `034_create_notification_templates_table.py`, `035_create_user_notification_preferences_table.py`, `036_seed_notification_templates.py`                                        | 05, 06, 08, 09, 15, 18 |
| **10** | Monitoring & Audit                             | 1 week   | Prometheus metrics, Grafana dashboards, tamper-evident audit hash chain, incident response playbooks | `037_create_audit_logs_table.py`, `038_create_system_settings_table.py`, `039_add_audit_log_partitioning.py`                                                                  | 05, 06, 09, 11, 13 |
| **11** | Expense Management *(MVP)* | 1 week | Employee expense claim intake, receipt OCR/AI extraction, travel policy validation, policy rule checking, reimbursement workflows, duplicate claim detection, expense approval workflow (Tier 1–3), GL posting | New expense tables (see `06` for schema additions) | 05, 06, 07, 10, 17, 19 |

> **Migration format note:** All migrations are Alembic `.py` files with `upgrade()` and `downgrade()` functions. The `.sql` labels previously shown in this table were logical scope identifiers, not literal filenames. See `06_Database_Schema_Design.md` §17.1 (naming) and **§18.4** (authoritative phase-ordered file list), plus `16_Migration_and_ORM_Specification.md` §10, for filenames, Phase 2 worked examples, and `alembic.ini` / `env.py` configuration.

> **Before production go-live (mandatory):** Read `11_Deployment_Operations_Runbook.md` **Appendix 20 §20.0** (pre-production gates: business sign-offs, Phases 1–11 acceptance, Expense Worker stub OBS-3, IMAP-only mail). Cross-ref `01` Document Governance five-item checklist.

> **Phase 11 implementation contract:** `19_Expense_Worker_Specification.md` is part of the MVP document suite. Read it before beginning Phase 11 development. It defines the full Expense Worker trigger, DB writes, events, error paths, and the complete DDL for `expense_claims`, `expense_line_items`, and `expense_policies` (Alembic migrations `039b` + `040`–`044` — six files in total: `039b_add_expense_claim_case_type.py` extends the `case_type` ENUM between Phase 10 and Phase 11, followed by five expense table migrations `040`–`044`). Remove the startup warning comment from the `worker-expense` service in `docker-compose.yml` (see `11_Deployment_Operations_Runbook.md` Appendix 20) once Phase 11 development begins. Expense Management is **MVP scope** — **Phase 11 implementation must replace the stub before production.** Phase 11 acceptance criteria must be satisfied before the platform is considered production-ready.


**Total MVP timeline: 14 weeks (Phases 1–11)**

### 5.2 Phase Dependency Graph

```plaintext
Phase 1  (Infrastructure)
    |
    v
Development Phase 2  (Auth & RBAC)
    |
    v
Phase 3  (Mail Gateway)
    |
    v
Phase 4  (Orchestrator + Policy Engine)  <---------┐
    |                                                |
    |--- Phase 5  (Accounts Worker)                  |
    |       |                                        |
    |       v                                        |
    |--- Phase 6  (AR Worker)                        |
    |       |                                        |
    |       v                                        |
    |--- Phase 7  (AP Worker)                        |
    |       |                                        |
    |       v                                        |
    |--- Phase 8  (Treasury & Reconciliation)        |
    |                                                |
    v                                                |
Phase 9  (Approval UI)                              |
    |                                                |
    v                                                |
Phase 10 (Monitoring & Audit)  --------------------┘
    |
    v
Phase 11 (Expense Management)
```

### 5.3 Future Phases (Post-MVP)

The following modules are **excluded from MVP** and deferred to Post-MVP Phase 2 or later. No worker, API section, or database migration for these modules exists in the current specification suite.


| Phase | Name                           | Description                                                                              | Dependencies |
| ----- | ------------------------------ | ---------------------------------------------------------------------------------------- | ------------ |
| **A** | Payroll                        | Payroll journal support, CPF/statutory handling, payroll reconciliation                  | Phase 11     |
| **B** | Fixed Assets                   | Capitalization assessment, depreciation management, disposal handling                    | Phase 11     |
| **C** | Advanced Policy Automation     | RAG knowledge base, ML-based policy recommendations, predictive analytics                | Phase 11     |
| **D** | Multi-Entity Support           | Intercompany transactions, consolidated reporting, entity-level permissions              | Phase A–C    |
| **E** | Banking Integrations & Tax     | Direct bank feed integrations, tax automation, advanced reconciliation                   | Phase D      |
| **F** | Predictive Finance AI          | Cashflow forecasting, anomaly detection, AI-driven budget recommendations                | Phase D      |


> **Scope clarity:** Expense Management — employee expense claims, the approval workflow, reimbursement processing, receipt OCR/AI extraction, and policy rule checking — is **MVP scope** (Phase 11). Only the modules in the table above are post-MVP.


### 5.4 Risk Register


| Risk                      | Impact                | Mitigation                                                           | Owner      | Phase Addressed |
| ------------------------- | --------------------- | -------------------------------------------------------------------- | ---------- | --------------- |
| AI extraction failure     | Incorrect postings    | Human approvals (Tier 2/3), guardrails, output validation            | Finance    | 4, 6-8          |
| Duplicate invoice posting | Financial loss        | Duplicate detection (Message-ID + hash), database unique constraints | Accounts   | 3, 5-8          |
| Email spoofing            | Fraud                 | SPF/DKIM/DMARC validation, allowed-sender domain restrictions        | IT         | 3               |
| AI model outage           | Workflow interruption | Fallback models (qwen2.5:7b, qwen2.5:0.5b), manual intake API, dead letter queue | IT         | 1, 4            |
| Compliance breach         | Legal exposure        | PDPA data handling, 7-year audit retention, segregation of duties    | Compliance | 2, 10           |
| Prompt injection          | Unauthorized actions  | Output guardrails, input sanitization, no direct SQL from AI         | IT         | 4               |
| Segregation bypass        | Governance failure    | 4-layer enforcement (DB + API + state machine + policy engine)       | Compliance | 2, 4            |


### 5.5 Definition of Done

Each phase is considered complete when:

1. **Code**: All endpoints implemented per API specification with type hints and docstrings
2. **Database**: Migrations applied successfully, seed data loaded, RLS policies active
3. **Tests**: Unit tests > 80% coverage, integration tests passing, golden test sets validated
4. **Documentation**: README updated, API docs generated (OpenAPI), sequence diagrams verified
5. **Security**: No hardcoded secrets, RBAC enforced on all endpoints, audit logging active
6. **Deployment**: Docker Compose stack deploys cleanly, health checks passing, monitoring active
7. **Review**: Code review completed, Cursor rules compliance verified

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.65 | 2026-05-26 | **`0.14.9-binding-authority` shipped.** `10` §7 tiers in workers; `11` §4.5k; `05` v1.3.24; `15` v2.31; `16` v2.7 — migration `060`, Client Admin thresholds, finance role approval queues. |
| 2.66 | 2026-05-27 | **`0.14.10-counterparty-fixes` shipped.** Reactivate inactive subaccounts on `/counterparty-accounts`; add vendor contract fields + expiry warning badge and Client Admin dashboard warning. Migration `061`; config version bumped to `0.14.10`. |
| 2.64 | 2026-05-20 | **Finance UI setup screens.** `15` v2.30, `05` v1.3.23, `11` v2.51 — counterparty/agreements/calendar on finance.mmlogistix; Client Admin travel tab removed (`e73c869`). |
| 2.63 | 2026-05-20 | **Subaccount edit UI.** `15` v2.29, `05` v1.3.22, `11` v2.50 — inline Edit/Save for payment terms + credit on Subaccounts tab (`9b0662e`). |
| 2.62 | 2026-05-20 | **Credit limit UI.** `15` v2.28, `05` v1.3.21, `11` v2.49 — subaccount credit limit in Client Admin (not payment-terms catalog). |
| 2.61 | 2026-05-20 | **`0.14.8` shipped.** §4.1: `05` v1.3.20 (**144** ops), `21` v1.0.14, `11` v2.48, `12` v1.7.0, `15` v2.27, `16` v2.6 — counterparty subaccounts live (`b1095c1`–`9350495`). |
| 2.60 | 2026-05-20 | **Counterparty accounts (`0.14.8`, planned).** §4.1: `05` v1.3.18, `06` v2.10.7, `15` v2.26, `17` v2.37 — subaccounts, payment terms, GST intake. Superseded by v2.61 (shipped). |
| 2.59 | 2026-05-20 | **COA UI build fix (`8d6bf6e`).** §4.1: `11` v2.46, `15` v2.25 — Svelte 5 event syntax on `/chart-of-accounts`. |
| 2.58 | 2026-05-20 | **Tenant COA (`0.14.7-coa-tenant-import`).** §4.1: `05` v1.3.17, `06` v2.10.6, `11` v2.45, `15` v2.24, `17` v2.36. Commits `5a2b441`, `7502b3e`. |
| 2.57 | 2026-05-20 | **Email signatures (`0.14.6`).** §4.1: `05` v1.3.16, `11` v2.44, `15` v2.23, `17` v2.35, `18` v1.5.0, `14` v2.32. |
| 2.56 | 2026-05-20 | **GL period reopen (`0.14.5`).** §4.1: `05` v1.3.15, `06` v2.10.4, `11` v2.43, `15` v2.22, `17` v2.34, `14` v2.31. |
| 2.55 | 2026-05-25 | **Ops docs consolidated in `11`.** §20.0.1 checklist + §20.2 version history; `accfin/docs/*` pointers only. |
| 2.54 | 2026-05-25 | **Client Admin + GL calendar (`0.14.4`).** §4.1: `05` v1.3.14, `06` v2.10.3, `11` v2.41, `15` v2.21, `17` v2.33. |
| 2.53 | 2026-05-24 | **Production incident doc sync.** `11` v2.33 (Supabase vs compose `db`, §19.4a SMTP escalation gap). `17` v2.19 (§10.3.1 shipped vs pending outbound). `Product_Overview` v1.1 §11 implementation status. `18` v1.4.8 §1.1. `14` v2.28 §7b.1. |
| 2.52 | 2026-05-20 | **Security compliance framework (Singapore).** `13` v2.0: statute/edition citations in §1.1; statutory retention minima vs 7-year platform policy (§4.1); MAS TRM 2021 alignment (§4.5); IRAS GST e-Tax Guide (§4.6). |
| 2.51 | 2026-05-20 | **Wasabi attachment archive on intake.** Deploy `0.13.8-wasabi-attachment-archive`: `WasabiArchiveService` uploads to `transactions/{case_number}/`; `FINANCE_WASABI__*` settings in `config.py`; trigger on case–email link (`17` v2.18, `14` v2.27, `11` v2.32). |
| 2.50 | 2026-05-20 | **Worker idle CPU fix.** Deploy `0.13.7-worker-blpop-idle-fix`: `QueueConsumer` BLPOP block 5s (`workers/base.py`). `17` v2.17. |
| 2.49 | 2026-05-20 | **Finance UI security 2FA.** Deploy `0.13.6-finance-security-2fa`: `/settings/security` (setup/verify/disable), mandatory-2FA banner for `cfo`/`finance_manager`; retry button fix. finance-ui `0.13.3-security-2fa` (`15` v2.16). |
| 2.48 | 2026-05-20 | **Ollama CLI healthcheck.** Deploy `0.13.5-ollama-healthcheck-cli`: compose `ollama list` (no curl/wget in image); supersedes `0.13.4`. `11` v2.29. |
| 2.47 | 2026-05-20 | **Ollama healthcheck fix (superseded).** Deploy `0.13.4-ollama-healthcheck-wget`: compose `wget --spider` — wget unavailable in image. |
| 2.46 | 2026-05-20 | **Case retry + Hermes timeout.** Deploy `0.13.3-case-retry-hermes-timeout`: Hermes client default timeout 120s (slow Ollama CPU); `POST /cases/{id}/retry` requeues `exception`/`manual_review` to `accounts_queue`; finance-ui Retry button on case detail (`05` v1.3.13, `15` v2.15, `17` v2.15, `11` v2.27, `14` v2.24). |
| 2.45 | 2026-05-20 | **Case visibility dashboard.** Deploy `0.13.2-case-visibility`: timeline audit trail, error reason on detail/list, Message-ID-only dedupe; finance-ui `0.13.0-case-dashboard`. |
| 2.44 | 2026-05-20 | **Mail text sanitization (urgent).** Deploy `0.13.1-mail-text-sanitize`: `sanitize_text()` on all parsed mail fields at ingest (`body_text`, `body_html`, `subject`, `extracted_text`, etc.) — fixes PostgreSQL NUL/UTF-8 errors blocking intake (`17` v2.14, `11` v2.26). |
| 2.43 | 2026-05-20 | **Executive mail SOP implementation.** Deploy `0.13.0-executive-mail-sop`: manager-first failure escalation, sender ack with `[CAS-…]`, failure notify on manager reject only, `finance_activity_log` at each step (`11` v2.25, `14` v2.22, `17` v2.13). |
| 2.42 | 2026-05-20 | **PDF attachment text fix.** Deploy `0.12.9-mail-pdf-sanitize`: strip NUL bytes from PDF `extracted_text` before PostgreSQL insert (`17` v2.12). |
| 2.41 | 2026-05-20 | **Finance UI token refresh.** Deploy `0.12.8-finance-token-refresh`; finance-ui `0.12.5-finance-token-refresh` — silent `POST /auth/refresh` within 2 min of JWT expiry (`15` v2.14). |
| 2.40 | 2026-05-20 | **Ollama extraction MVP.** Deploy `0.12.7-ollama-extraction`: Hermes `/extract/invoice`, `/extract/expense-claim`, `/extract/document-text` via `qwen2.5:7b`; mailbox-first classify (`accar`/`accap`/`accexp`). `04` v2.8, `11` v2.23, `14` v2.20, `17` v2.11. |
| 2.39 | 2026-05-20 | **Mail Gateway IMAP poller.** Deploy `0.12.6-gateway-imap-poller`: compose poll enabled + async session fix (`gateway/imap/poller.py`). `11` v2.22, `14` v2.19, `17` v2.10. |
| 2.38 | 2026-05-22 | **Deploy doc sync.** `accfin/docs/DEPLOYMENT_VERSION_HISTORY.md`; current `0.12.4-client-auth` (`11` v2.20, `14` v2.17). |
| 2.37 | 2026-05-20 | **Approval UI branding.** Product name **mmlogistix Finance** (`15` v2.11); finance-ui `0.12.2-mmlogistix-branding`; API deploy `0.12.3-mmlogistix-branding`. |
| 2.33a | 2026-05-19 | **Production Traefik.** HTTPS on VPS; `traefik:v2.11`; network label `accfin_frontend` (`11` v2.6a). |
| 2.36 | 2026-05-20 | **Traefik UI root.** Deploy `0.12.2-traefik-ui-root`; `/` → finance-ui; API-only prefixes in `api-routes.yml` (`11` v2.19, `14` v2.16). |
| 2.35 | 2026-05-20 | **Traefik routing fix.** Production deploy `0.12.1-traefik-routes`; `api-routes.yml` single-line rule (`11` v2.18, `14` v2.15). |
| 2.34 | 2026-05-20 | **Final public URL structure.** §3.2: `finance.mmlogistix.bp0.work` (Approval UI + edge API paths); `admin.bp0.work` / `admin.mmlogistix.bp0.work` (post-MVP); FastAPI internal only (`14` v2.14, `05` v1.3.12). |
| 2.33 | 2026-05-19 | **§2.6 local layout.** Sibling `application/` for implementation; `platform_dox/` spec-only — do not push to GitHub. Cross-ref `README` v1.5, `cursor_master_development_prompt` v1.8. |
| 2.32 | 2026-05-19 | **Doc-suite hygiene (audit fixes).** Companion tables: `21_openapi.yaml` added to all specs; doc `20` no longer lists itself. §4.1 row **00** shows this document version (`v2.32`). `21_openapi.yaml` de-anchored for CI (`scripts/validate_openapi_yaml.py`). |
| 2.31 | 2026-05-19 | **Executive mail + daily log (doc-suite sync).** Transaction number `[{case_number}]` on case-linked email Subjects (`06` v2.10.1, `17` v2.8, `18` v1.4.6, `01` v5.3). Daily 9pm SGT digest: RFC 4180 CSV `finance_daily_{date}.csv` to CFO + Wasabi `logs/` (`06` v2.10.2, `05` v1.3.11, `17` v2.9, `18` v1.4.7, `01` v5.4, `12` v1.6.7–1.6.8). |
| 2.30 | 2026-05-19 | **Doc-suite alignment (repo + mail).** Monorepo `bp0work/accounting` (`accfin/` + three UI dirs); IMAP-only mail (Graph removed); `platform_dox` vs implementation (`README.md`, §2.6). Header synced to v2.30. |
| 2.29 | 2026-05-19 | **Monorepo.** `bp0work/accounting` with `accfin/`, `finance-ui/`, `platform-admin-ui/`, `client-admin-ui/` (§2.6, §3.6). |
| 2.28 | 2026-05-19 | **Backend repo.** `bp0work/accounting` (was `accfin`); deploy `/opt/bp0work/accounting`. |
| 2.27 | 2026-05-19 | **§2.6 Documentation vs implementation.** Clarifies `platform_dox` is specs-only; `accounting` + three UI repos + secrets live elsewhere. `README.md` added. §3.6 note on target monorepo. |
| 2.26 | 2026-05-19 | **Mail transport.** Removed Microsoft Graph / `gateway/graph/` from repo tree and Phase 3 row; IMAP-only (`14` §7, `17` §2.1.2). |
| 2.25 | 2026-05-19 | **Go-live gates + mail MVP.** §5.1 → `11` Appendix 20 §20.0; Phase 3 **IMAP-only** (Graph post-MVP). `gateway/graph/` noted post-MVP. |
| 2.24 | 2026-05-19 | **API contract depth.** `05` v1.3.9 §8.8a escalation token/idempotency; §19 internal daily log; `07` §13 Escalate flow; **127** operations. |
| 2.23 | 2026-05-19 | **Cross-ref audit.** §3.5/§5.1: RBAC **9** roles, **28** permissions (seed), **31** after Phase 11 (`13` §5.6). §5.1 migration refs → `06` §18.4. §4.2: `financial_analyst` in role list. |
| 2.22 | 2026-05-19 | **OpenAPI contract sync.** `21_openapi.yaml` v1.0.10 aligned with `05` Appendix A (**126** operations); OBS-4 adds OpenAPI as fourth sync target. Counts: `05` v1.3.8, `12`/`20` contract-test target updated. |
| 2.21 | 2026-05-19 | **Mail intake vs `acc` mailbox.** §3.2/§5.1: Gateway polls `executive_agent` only; Phase 5 Accounts Worker = `intake_queue` consumer, not `acc` inbox (`17` §2.1.1, §10.2.1). |
| 2.20 | 2026-05-19 | **Executive email SOP — doc-suite alignment.** Schema closure: `06` v2.9.8–2.9.9 (`case_escalations`, `pending_outbound_emails`, `rejection_reason_code`, Appendix B.5–B.7); migrations `045`–`046` (`16` §10). Clarification SOP: client reply with full email thread; manager pre-approval when toggle ON; reject → Hermes re-extract (`01` v5.1, `17` v2.2, `15` v2.7, `05` v1.3.6, `18` v1.4.5, `04` §16.6). UAT-011 (`12` v1.6.4). Counts: **43** tables, **117** endpoints; `21_openapi.yaml` v1.0.9. §4.2 email SOP persistence row. |
| 2.19 | 2026-05-19 | **UAT-011 + OpenAPI SOP.** `12` §11.3 UAT-011 (clarification thread, manager reject/re-parse); `21_openapi.yaml` v1.0.9 (`/mail/escalations/.../respond`, `/mail/outbound/.../respond`). |
| 2.18 | 2026-05-19 | **Audit corrections (doc-suite audit).** Issue 1: Updated table counts in §3.2 architecture diagram (37→38 Phases 1–10; 40→41 all phases) and §3.6 ORM models comment (37→38; 40→41) to match `06` §20 v2.9.6 which added `tenants`, `tenant_profiles`, and `finance_activity_log`. Issue 3: Added `20_Git_Workflow_and_Prompt_Management.md` and `21_openapi.yaml` to Companion Documents table, §3.6 docs/ directory listing, §4.1 document count (20→22), numbering note, and Specification Documents table (new rows 20 and 21). Updated `06` description in §4.1 (37→38 tables). |
| 2.17 | 2026-05-19 | **Organizational hierarchy (`01` §3).** CEO → CFO → Manager Accounts (AR, AP, Expense, Payroll) and Manager Finance (Treasury, Fixed Assets, Financial Reporting/Control). Role authority §3.2.2; escalation §3.2.3. Mailbox/seed alignment in `06` §19.7. |
| 2.16 | 2026-05-19 | **Executive email operations SOP.** Business rules `01` §6.8: executives process against COA + T&E policy only; escalate to Finance Manager → CEO; one IMAP listener per executive; manager mailboxes human-only; finance activity log + daily 9pm SGT digest; ack external mail; Approve/Reject escalation emails; Client Admin outbound approval toggle (`15` §8.14). Technical: `17` §10, `06` §7.3–7.4, migration `045`, `18` §7.7, `11` §17.5, UAT-010 in `12`. |
| 2.15 | 2026-05-19 | **Financial Analyst role.** Nine RBAC roles (`financial_analyst`): expense/cost/revenue analysis, financial statements, month-end close (`15` §8.3); mailbox `finfa.mmlogistix@bp0.work`. Permissions `reports:read`, `month-end:read`, `month-end:write`; no `approvals:approve`. `06` §19.1–§19.3, `13` §5.6. |
| 2.14 | 2026-05-19 | **Client Admin expense policy and API count.** §4.1: `05` endpoint count 108→115. Production API host `api.bp0.work` (superseded by v2.34). |
| 2.13 | 2026-05-19 | **Two-tier administration and three frontends.** Platform Admin UI (`system@bp0.work`) — dynamic tenant list, Client Admin email updates only. Client Admin UI (`system.mmlogistix@bp0.work`) — role mailbox addresses/From names, COA, logo, company details (SOA), email signature. Approval UI unchanged for finance users. Updated §3.5 Authorization (8 roles, 25 permissions, 28 after Phase 11); §4.2 role names; Phase 2 migrations `006b`–`006d`. Authoritative detail: `13` §5.9, `15` §8.11–8.16, `06` §13.2a–b, `05` §4.16a–b. |
| 2.10 | 2026-05-17 | Fix: Updated §4.1 doc-19 description from "migrations (040–044)" to "migrations (039b + 040–044)" to reflect the correct six-file Phase 11 sequence. Updated §5.1 Phase 11 implementation contract note from "040–044" to "`039b` + `040`–`044`" with an inline explanation that `039b_add_expense_claim_case_type.py` extends the `case_type` ENUM between Phase 10 and Phase 11 proper, and that `040`–`044` are the five expense table migrations. Aligns with `06` §14.2 and `16` §10 (both already correct). Parallel fix applied in `03` (Phase 11 read-order note) and `19` §11 (the authoritative source, also corrected in this pass). |
| 2.9 | 2026-05-17 | Consistency fix: Corrected stale "Llama 3.1" fallback model references — updated §3.1 Technology Stack "Fallback AI" row to `qwen2.5:7b / qwen2.5:0.5b` (task-differentiated) and §5.4 Risk Register "AI model outage" mitigation to match. Authoritative fallback chain is `hermes3` → `qwen2.5:7b` (extraction/reconciliation) or `qwen2.5:0.5b` (classification), defined in `04_Hermes_Integration_Spec.md` §8.4 and confirmed in `11_Deployment_Operations_Runbook.md` §8.2. `env.example` was already correct (`qwen2.5:7b`); only `00` and `14` referenced the stale Llama 3.1 name. |
| 2.8 | 2026-05-17 | Fix (H-2 from audit): Replaced non-existent table name `case_events` with `case_timeline` in §4.2 Cross-Document Consistency Matrix "Database table names" row. Added explanatory note that there is no `case_events` table — state history lives in `case_timeline` (§4.3) and the event bus uses `audit_logs`. Fix (M-6 from audit): Added STP eligibility clarification to §4.2 "Confidence thresholds" row — STP requires confidence >= 0.90 *plus* policy pass (counterparty recurring, no risk flags, amount below threshold), not confidence alone; points to `08` §5.1 and `10` for authoritative guard. Fix (H-1 from audit): Updated §3.5 Security Architecture "Authorization" row to note that Phase 11 migration `043` adds `expenses:read`, `expenses:write`, and `expenses:approve`, raising the permission count from 22 to 25 post-Phase 11. |
| 2.7 | 2026-05-16 | Fix (Issue 3 from audit): Corrected stale `## Date:` header — was `15 May 2026`, updated to `16 May 2026` to match the latest version history entry (v2.6, dated 2026-05-16). Same class of stale-header bug previously fixed in `01` v4.3, `02` v5.5, and `00` v2.3. |
| 2.6 | 2026-05-16 | Scope consistency fix: Updated §5.1 roadmap from "10 sequential phases" to "11 sequential phases" with explicit MVP declaration for all Phases 1–11. Updated Phase 11 row to label it "MVP" and expanded its deliverables to include receipt OCR/AI extraction, policy rule checking, and expense approval workflow. Updated total MVP timeline from 13 → 14 weeks. Updated §5.3 Future Phases: expanded post-MVP table from 3 rows (Payroll, Advanced Policy, Multi-Entity) to 6 rows adding Fixed Assets, Banking Integrations/Tax, and Predictive Finance AI; added scope clarity note distinguishing Expense Management (MVP) from post-MVP modules. Updated §4.1 doc 17 description to remove stale "Expense Worker contract is deferred" language. Updated Phase 11 implementation contract note to remove gating language and restate Expense as MVP scope. |
| 2.5 | 2026-05-16 | Fix (Issue 1 from audit-3): Updated `app/api/` comment in §3.6 repo structure from `17 functional areas` → `18 functional areas`; updated §4.1 document map row for `05` from `17 functional areas` → `18 functional areas`. Both now reflect `05` v1.0.3 which added §18 Expense Claims (Phase 11) as the eighteenth functional section. Fix (Issue 3 from audit-3): Removed stale `workers/email/` sub-directory entry from §3.6 repo structure. The Mail Gateway is a top-level `gateway/` service (already correctly shown below it); the `workers/email/` entry was a remnant of an earlier layout and conflicted with `03` §2 and `17` §2, which are the authoritative boundary references. |
| 2.4 | 2026-05-15 | Fix (INC-1 from audit): Corrected `05_API_Specification.md` endpoint count in §4.1 from "104" to "108" — the authoritative count is the Appendix A row total in `05` v1.0.5. Updated `07` description in §4.1 from "11 Mermaid sequence diagrams" to "12" to reflect the Phase 11 expense claim sequence (§12) added in `07` v1.2. Fix (INC-2 from audit): Added `026b_create_purchase_orders_table.py` to Phase 6 (AR Worker) DB Migrations column in §5.1 roadmap table, and updated Phase 7 (AP Worker) row to reference `026b` as the prerequisite — consistent with `16` §10 and `06` §13a corrections in the same audit pass. |
| 2.3 | 2026-05-15 | Fix (Issue 3 from audit-2): Corrected stale `## Date:` header — was `11 May 2026`, updated to `15 May 2026` to match the latest version history entry (v2.2, dated 2026-05-15). Same pattern as `01` v4.3 and `02` v5.4 header-date fixes. |
| 2.2 | 2026-05-15 | Fix (Issue 1 from audit): Replaced misleading single-block "Routing Decision" in §3.3 AI Processing Pipeline diagram with a two-stage representation. Stage 1 is the classification gate at INBOUND (confidence >= 0.70 → CLASSIFIED, < 0.70 → MANUAL_REVIEW). Stage 2 is the STP/Assisted/Exception gate inside the domain worker during PROCESSING (>= 0.90 + policy pass → STP auto-release; 0.70–0.89 or flags → Assisted Tier 2; policy violation / high risk → Exception Tier 3). Added cross-reference to `08` §3.2 and §7 as authoritative source. The prior diagram conflated two distinct decision points, which could mislead a developer into implementing a three-way branch at classification time. |
| 2.1 | 2026-05-15 | Fix (Issue 6 from audit): Replaced "30+ transitions" with "30 transitions (exact)" in §4.1 description row for `08` and §3.3 AI Processing Pipeline diagram. Exact count verified by enumerating §3.2.1 (18 transitions) + §3.2.2 (12 transitions) in `08_Workflow_State_Machine.md`. |
| 2.0 | 2026-05-15 | Fix (Issue 5 from audit): Corrected stale `36 tables` → `37 tables` in §4.1 Specification Documents table, row for `06` (the count was correct in §3.2 and §3.6 since v1.9, but §4.1 had not been updated). Updated §4.1 description rows for `12` (9 UAT scenarios, Phase 11 §16) and `15` (Phase 11 expense claim UI §8.6–8.7) to reflect the medium-issue corrections applied in the same audit pass. |
| 1.9 | 2026-05-15 | Fix (Issue 3): Corrected stale table counts in §3.2 architecture diagram (`36 tables` → `37 tables`, `39 including Phase 11` → `40 including Phase 11`) and §3.6 repository structure ORM models comment (`36 tables` → `37 tables`, `39 with Phase 11` → `40 with Phase 11`). These were missed when `06` was updated to v1.6.0 (which added `purchase_orders` as table 37). `02` §11 had been correctly updated; `00` was not. |
| 1.8 | 2026-05-14 | Fix (Issue 1): Corrected stale section-number citations in §4.2 Cross-Document Consistency Matrix — `06` §18.1 → §19.1 and `06` §18.3 → §19.3 (Seed Data section was renumbered from §18 to §19 when §14 expense placeholder was inserted in v1.4.0 of `06`). Fix (Issue 2): Corrected table name `audit_log` → `audit_logs` in §4.2 Database table names example row. |
| 1.7 | 2026-05-14 | Fix: Added missing `19_Expense_Worker_Specification.md` row to Companion Documents table at top of document. Body references in §3.6 and §4.1 were already correct; companion table had not been updated. |
| 1.6 | 2026-05-14 | Fix 1: Corrected §4.1 numbering note — updated range `05–18` → `05–19` and document count `19` → `20`. Fix 2: Added `19_Expense_Worker_Specification.md` to `docs/` directory listing in §3.6. Fix 3: Added `expense/` subdirectory to `workers/` listing in §3.6. Fix 4: Updated three `36 tables` references in §3.2, §3.6, and §4.1 to note 36 (Phases 1–10) + 3 expense tables (Phase 11) = 39 total. |
| 1.5 | 2026-05-14 | Added `19_Expense_Worker_Specification.md` to Companion Documents table, §4.1 Specification Documents table, and §5.1 Phase 11 roadmap note. Updated document suite count 19→20. Replaced ⚠️ Phase 11 blocking note with implementation-ready note. |
| 1.4 | 2026-05-14 | Fix 5 (Issue 1): Added ⚠️ Phase 11 pre-condition note after roadmap table warning developers that `19_Expense_Worker_Specification.md` does not exist, listing three actions required before Phase 11 begins. Fix 6 (Issue 2): Added clarifying note above Specification Documents table explaining the numbering gap (01–03 in Foundation table, 04 absent from spec table); added `04` as an explicit row so all 19 documents are enumerated in one place. |
| 1.3 | 2026-05-14 | Fix 1: Corrected stale "6-service" docker-compose comment in §3.6 to reference `11` Appendix 20. Fix 2: Corrected queue diagram in §3.2 — replaced separate AR/AP/Treasury/Expense queue entries with accurate single `accounts_queue` topology matching `17_Worker_Specifications.md` §2.1; added Treasury trigger note. |
| 1.2 | 2026-05-14 | Updated document map: endpoint count 93→104 in `05`; corrected `11` description to reflect full service list (Hermes, workers, Grafana); updated `17` description to note Expense Worker contract deferred to Phase 11 spec. |
| 1.1 | 2026-05-11 | Added delivery roadmap, risk register, definition of done, cross-document consistency matrix |
| 1.0 | 2026-05-11 | Initial project overview |
