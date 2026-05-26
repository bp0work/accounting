#!/usr/bin/env bash
# Phase 13 UAT runner — run on VPS (or anywhere Docker + Postgres are up).
# Maps to platform_dox UAT-012–UAT-015 (automated subset + manual UI checklist).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Alembic upgrade (055–058)"
docker compose run --rm fastapi alembic upgrade head

echo "==> Unit tests (intake helpers)"
docker compose run --rm fastapi pytest tests/unit/test_counterparty_intake.py -v

echo "==> Integration UAT (API + workers)"
docker compose run --rm fastapi pytest tests/integration/test_phase13_uat.py -v -m integration

echo ""
echo "==> Manual Client Admin checks (UAT-012–015)"
echo "  1. Open https://admin.mmlogistix.bp0.work/counterparty-accounts"
echo "  2. Payment terms tab: confirm COD, NET7, NET30, NET60 (seed 056)"
echo "  3. Subaccounts tab: create supplier + subaccount with NET30"
echo "  4. Tax codes tab: map GST9 → your COA output/input GL codes"
echo "  5. Dashboard: Payment terms + GST checklist items green"
echo "  6. Send test AP invoice (Net 30, no due date) → verify due_date on case"
echo "  7. Send test AR invoice with tax → verify tax_resolution in case metadata"
echo ""
echo "All automated steps passed. Complete manual rows in UAT spreadsheet before commit."
