# AI Finance Operations Platform — Specification Suite (`platform_dox`)

## Version 1.23

## Filename: README.md

## Date: 25 May 2026

---

This folder is the **authoritative specification workspace**. It contains numbered design documents (`00`–`21`), `env.example`, `21_openapi.yaml`, and maintenance scripts. It does **not** contain runnable application code, frontend apps, Alembic migrations, production secrets, or live infrastructure.

That separation is intentional. `03_Cursor_Development_Brief.md` §2 and `11_Deployment_Operations_Runbook.md` Appendix 20 describe the **target** runtime layout in the implementation monorepo — not files missing from this folder.

---

## What is in this folder

| Artifact | Purpose |
|----------|---------|
| `00_Project_Overview.md` … `20_Git_Workflow_and_Prompt_Management.md` | Business, architecture, API, schema, workers, deployment, security, UI behaviour |
| `Product_Overview.md` | Non-technical product summary — purpose, roles, agents, task flow, escalations, compliance |
| `21_openapi.yaml` | Machine-readable API contract (synced from `05` Appendix A) |
| `env.example` | Variable **names** and documented defaults — not production values |
| `scripts/sync_openapi_from_05.py` | Maintainer tool to sync `21` paths from `05` Appendix A |
| `scripts/validate_openapi_yaml.py` | Validate `21_openapi.yaml` (PyYAML + redocly); asserts **144** ops + `info.version` 1.0.14; `--rewrite` removes YAML anchors |
| `sample files from previous version/` | Read-only legacy prototype reference (pre-platform) |
| `cursor_master_development_prompt.md` | Cursor session **index** (v2.0 — modules in `cursor_prompt/`) |
| `cursor_prompt/M*.md` | Split development rules (read per task map in index) |
| `.cursor/rules/bp0work-agent-session.mdc` | Always-on session protocol when this folder is workspace root |

---

## What is outside this folder (expected)

Implementation lives in the sibling folder **`application/`** on your machine — a **single Git monorepo** pushed to [bp0work](https://github.com/bp0work) (e.g. `accounting`). Clone or open `application/`; do not clone specs into the same Git repo unless you deliberately maintain an optional `docs/` mirror (not required).

| Component | Path in monorepo | Browse on GitHub |
|-----------|------------------|------------------|
| **Backend** (FastAPI, workers, gateway, orchestrator, Alembic, `docker-compose.yml`) | `accfin/` | [accounting/accfin](https://github.com/bp0work/accounting/tree/main/accfin) |
| **Approval UI** (SvelteKit) | `finance-ui/` | [accounting/finance-ui](https://github.com/bp0work/accounting/tree/main/finance-ui) |
| **Platform Admin UI** (SvelteKit) | `platform-admin-ui/` | [accounting/platform-admin-ui](https://github.com/bp0work/accounting/tree/main/platform-admin-ui) |
| **Client Admin UI** (SvelteKit) | `client-admin-ui/` | [accounting/client-admin-ui](https://github.com/bp0work/accounting/tree/main/client-admin-ui) |

| Operations | Location |
|------------|----------|
| **Git clone URL** | `https://github.com/bp0work/accounting` |
| **VPS deploy root** | `/opt/bp0work/accounting` |
| **Compose / backend cwd** | `/opt/bp0work/accounting/accfin` |
| **Production `.env`** | `/opt/bp0work/accounting/accfin/.env` (or monorepo root per team convention — see `03` §17.2) |
| **Hermes + Ollama** | Docker services defined in `accfin/docker-compose.yml` (`04`, `11`) |

### Previous repo layout (superseded)

| Component | Former standalone repo |
|-----------|------------------------|
| Backend | `https://github.com/bp0work/accfin` |
| Approval UI | `https://github.com/bp0work/finance-ui` |
| Platform Admin | `https://github.com/bp0work/platform-admin-ui` |
| Client Admin | `https://github.com/bp0work/client-admin-ui` |

All four are now top-level directories in **`bp0work/accounting`**.

---

## How to use this suite

1. Start with `00_Project_Overview.md` and `03_Cursor_Development_Brief.md` §14 (reading order).
2. Implement in **`application/`** per phase (`accfin/`, `finance-ui/`, etc.) — `03` §6, `00` §5.1. Start with `cursor_master_development_prompt.md` (index) and read required `cursor_prompt/` modules in full.
3. Copy **`platform_dox/env.example`** → **`application/accfin/.env`** and fill secrets per `14` and `03` §17.
4. Run `docker compose` from **`application/accfin/`**, using `11` Appendix 20 as the target stack definition.
5. **Git:** commit and push from **`application/`** only — never push `platform_dox/` to GitHub.

**Production go-live:** `11_Deployment_Operations_Runbook.md` §20.0.1 (checklist) and §20.2 (deploy versions). Client Admin: `15` §8.13; Finance setup UI: `15` §8.22–§8.24. Do not recreate `accfin/docs/` copies of these specs in the Git repo.

---

## Legacy prototype (reference only)

The pre-platform systemd app (`/opt/mmlogistix/accounting-agent`) and scripts under `sample files from previous version/` are **not** the target architecture. Use them only as behavioural reference when building `accfin/` (`03` §16).

---

## Maintainer note

When adding a numbered spec file, update the **Companion Documents** table in every file in the suite (`03` §15).

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.24 | 2026-05-26 | **`0.14.9-binding-authority` shipped.** Binding authority tiers in workers; Client Admin `/binding-authority`; finance approval queues. `11` §4.5k; `05` v1.3.24; `10` §7; `15` v2.31; `16` v2.7. |
| 1.23 | 2026-05-20 | **Finance UI setup screens.** Counterparty, agreements, accounting calendar moved to `finance.mmlogistix`; Client Admin drops Travel tab. `15` v2.30; `05` v1.3.23; `11` v2.51 §4.5j (`e73c869`). |
| 1.22 | 2026-05-20 | **Subaccount edit UI.** `15` v2.29 §8.22; `05` v1.3.22 §4.16d.4; `11` v2.50 §4.5i. Inline Edit/Save for payment terms + credit (`9b0662e`). |
| 1.21 | 2026-05-20 | **Credit limit UI.** `15` v2.28 §8.22; `05` v1.3.21 §4.16d.4; `11` v2.49. Client Admin subaccount form + table. |
| 1.20 | 2026-05-20 | **`0.14.8` shipped.** **144** API ops (`05` v1.3.20, `21` v1.0.14); contract checker in `validate_openapi_yaml.py`. Deploy §4.5i; UAT `uat_phase13.sh`. |
| 1.19 | 2026-05-20 | **Counterparty accounts (`0.14.8`, planned).** Design: `05`, `06`, `15`, `17`. **Implementation:** `03` §2.1, `16` §10 (`055`–`058`), `11` §4.5i. |
| 1.18 | 2026-05-20 | **COA Docker build fix (`8d6bf6e`).** `11` v2.46, `15` v2.25, `00` v2.59 — Svelte 5 `onclick`/`onchange` on COA page; §4.5h troubleshooting. |
| 1.17 | 2026-05-20 | **Tenant COA (`0.14.7-coa-tenant-import`).** `05` v1.3.17, `06` v2.10.6, `11` v2.45, `15` v2.24, `17` v2.36, `00` v2.58. Migration `054`; upsert import + Client Admin search UX. |
| 1.16 | 2026-05-20 | **Email signatures (`0.14.6`).** `05` v1.3.16, `06` v2.10.5, `11` v2.44, `15` v2.23, `17` v2.35, `18` v1.5.0, `14` v2.32, `00` v2.57. |
| 1.15 | 2026-05-20 | **GL period reopen (`0.14.5`).** `05` v1.3.15, `06` v2.10.4, `11` v2.43, `15` v2.22, `17` v2.34, `14` v2.31, `00` v2.56. |
| 1.14 | 2026-05-25 | **Ops docs in suite.** `11` §20.0.1 production checklist + §20.2 deploy history; removed duplicate `accfin/docs/*.md` from Git repo. |
| 1.13 | 2026-05-25 | **Client Admin + GL calendar (`0.14.4`).** `05` v1.3.14, `06` v2.10.3, `11` v2.41, `15` v2.21, `17` v2.33, `00` v2.54. |
| 1.12 | 2026-05-24 | **Production incident doc sync.** `Product_Overview` v1.1 §11; `11` v2.33 (Supabase vs compose `db`, §19.4a); `17` v2.19 (SMTP gap §10.3.1); `18` v1.4.8; `14` v2.28; `00` v2.53. |
| 1.11 | 2026-05-20 | **Product Overview.** New `Product_Overview.md` — purpose, functions, users/agents, task flow, escalations, compliance summary for non-technical readers. |
| 1.10 | 2026-05-20 | **Wasabi attachment archive.** Deploy `0.13.8-wasabi-attachment-archive`; `17` v2.18, `14` v2.27, `11` v2.32. |
| 1.9 | 2026-05-20 | **Worker idle BLPOP.** Deploy `0.13.7-worker-blpop-idle-fix`; `17` v2.17. |
| 1.8 | 2026-05-20 | **Finance UI 2FA.** Deploy `0.13.6-finance-security-2fa`; finance-ui `0.13.3-security-2fa`; `15` v2.16. |
| 1.7 | 2026-05-20 | **Deploy sync.** Current production target `0.13.5-ollama-healthcheck-cli`; suite versions in `00` §4.1 document map updated. |
| 1.6 | 2026-05-19 | **Cursor prompt split.** `cursor_master` v2.0 = index; rules in `cursor_prompt/`; `.cursor/rules/bp0work-agent-session.mdc`. Monolith v1.14 archived. |
| 1.5 | 2026-05-19 | **Local layout.** Sibling `application/` for code; `platform_dox/` spec-only — **do not push to GitHub**. How-to-use and §2.6 cross-refs. |
| 1.4 | 2026-05-19 | **Doc-suite hygiene.** Companion tables list `21_openapi.yaml` everywhere; doc `20` excludes self. `validate_openapi_yaml.py` for anchor-free OpenAPI CI. See `00` v2.32, `03` §15. |
| 1.3 | 2026-05-19 | **Mail + daily log conventions.** Transaction number `[CAS-…]` required in case-linked email Subjects (`06` §7.5, `18` §7.2.1). Daily finance digest: CSV `finance_daily_{date}.csv` emailed and archived to Wasabi `logs/` (`06` §7.4.1, `05` §19.1). |
| 1.2 | 2026-05-19 | **Wasabi `bp0workacc`.** Long-term storage: `logs/`, `backups/`, `transactions/{case_number}/` — see `06` §7.5. |
| 1.1 | 2026-05-19 | **Monorepo layout.** Implementation under `bp0work/accounting` with `accfin/`, `finance-ui/`, `platform-admin-ui/`, `client-admin-ui/`; superseded five-repo table retained for reference. |
| 1.0 | 2026-05-19 | Initial README: `platform_dox` vs implementation split; clone/deploy paths; reading order. |
