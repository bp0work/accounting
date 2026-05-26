"""Phase 13 UAT automation — UAT-012 through UAT-015 (`12` §11.3).

Run after `alembic upgrade head` (migrations 055–058):

    pytest tests/integration/test_phase13_uat.py -v -m integration
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security.password import hash_password
from app.models.case import Case, Counterparty
from app.models.counterparty_master import CounterpartyAccount, PaymentTerm, TenantTaxCode
from app.models.ledger import CoaAccount
from app.models.user import User
from app.models.workflow import WorkflowDefinition, WorkflowInstance
from app.schemas.hermes import (
    CheckDuplicateRequest,
    CheckDuplicateResponse,
    ExtractInvoiceRequest,
    ExtractInvoiceResponse,
    ExtractedInvoice,
)
from tests.conftest import TEST_PASSWORD
from workers.ar.handlers import ARWorkerService

ROLE_CLIENT_ADMIN = uuid.UUID("00000000-0000-0000-0000-000000000008")


@pytest.fixture
async def client_admin_headers(async_client: AsyncClient, db_session) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    user = User(
        id=uuid4(),
        username=f"ca_{suffix}",
        display_name="Client Admin UAT",
        email=f"ca_{suffix}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=ROLE_CLIENT_ADMIN,
        status="active",
        two_factor_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    response = await async_client.post(
        "/api/auth/login",
        json={"username": user.username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
async def test_uat_012_subaccounts_and_duplicate(
    async_client: AsyncClient,
    client_admin_headers: dict[str, str],
    db_session,
) -> None:
    """UAT-012: create parent, subaccount, duplicate code rejected."""
    cp_resp = await async_client.post(
        "/api/counterparties",
        headers=client_admin_headers,
        json={"name": f"ACME UAT {uuid4().hex[:6]}", "type": "supplier", "code": f"ACME-{uuid4().hex[:4]}"},
    )
    assert cp_resp.status_code == 201, cp_resp.text
    cp_id = cp_resp.json()["id"]

    terms = await async_client.get("/api/payment-terms", headers=client_admin_headers)
    assert terms.status_code == 200
    net30 = next((t for t in terms.json() if t["code"] == "NET30"), None)
    assert net30 is not None, "Migration 056 should seed NET30"

    sa_resp = await async_client.post(
        "/api/counterparty-accounts",
        headers=client_admin_headers,
        json={
            "counterparty_id": cp_id,
            "account_code": "ACME-SG",
            "display_name": "ACME Singapore",
            "payment_term_id": net30["id"],
        },
    )
    assert sa_resp.status_code == 201, sa_resp.text
    assert sa_resp.json()["payment_term_code"] == "NET30"

    dup_resp = await async_client.post(
        "/api/counterparty-accounts",
        headers=client_admin_headers,
        json={
            "counterparty_id": cp_id,
            "account_code": "ACME-SG",
            "display_name": "Duplicate",
        },
    )
    assert dup_resp.status_code == 409


@pytest.mark.integration
async def test_uat_013_due_date_from_payment_terms(db_session) -> None:
    """UAT-013: due_date = invoice_date + 30 when terms mapped, no explicit due on doc."""
    cp = Counterparty(name=f"Supplier {uuid4().hex[:6]}", type="supplier")
    db_session.add(cp)
    await db_session.flush()

    term = (
        await db_session.execute(select(PaymentTerm).where(PaymentTerm.code == "NET30"))
    ).scalar_one()

    sub = CounterpartyAccount(
        counterparty_id=cp.id,
        account_code="SITE-01",
        display_name="Main site",
        payment_term_id=term.id,
    )
    db_session.add(sub)
    await db_session.flush()

    from app.services.counterparty_intake import apply_intake_to_case

    case = Case(
        case_number=f"CAS-UAT13-{uuid4().hex[:6]}",
        type="ap_invoice",
        status="classified",
        subject="UAT-013",
        counterparty_id=cp.id,
        counterparty_name=cp.name,
        stp_eligible=False,
        confidence_score=Decimal("0.9"),
    )
    db_session.add(case)
    await db_session.flush()

    inv = ExtractedInvoice(
        invoice_number="INV-UAT13",
        invoice_date=date(2026, 5, 1),
        due_date=None,
        payment_terms="Net 30",
        total_amount="1000.00",
        tax_amount="90.00",
        currency="SGD",
    )
    resolution = await apply_intake_to_case(
        db_session,
        case=case,
        inv=inv,
        tax_direction="input",
        confidence=0.9,
        document_type="ap_invoice",
    )
    assert resolution.due_date == date(2026, 5, 31)
    assert resolution.due_date_source == "payment_terms"
    assert resolution.payment_term_code == "NET30"
    await db_session.commit()


@pytest.mark.integration
async def test_uat_014_gst_uses_tenant_tax_codes(db_session) -> None:
    """UAT-014: journal path resolves GL from tenant_tax_codes."""
    out_code = f"GSTOUT-{uuid4().hex[:4]}"
    in_code = f"GSTIN-{uuid4().hex[:4]}"
    db_session.add(
        CoaAccount(account_code=out_code, account_name="Output GST", account_type="liability")
    )
    db_session.add(
        CoaAccount(account_code=in_code, account_name="Input GST", account_type="asset")
    )
    db_session.add(
        TenantTaxCode(
            code="GST9",
            description="Standard 9%",
            rate=Decimal("0.09"),
            direction="both",
            output_gl_account_code=out_code,
            input_gl_account_code=in_code,
        )
    )
    await db_session.flush()

    from app.services.counterparty_intake import resolve_tax_gl

    code, source, gl = await resolve_tax_gl(
        db_session,
        direction="output",
        tax_code_hint="GST9",
        tax_amount=Decimal("9.00"),
    )
    assert code == "GST9"
    assert source == "extracted"
    assert gl == out_code


class _UAT15Hermes:
    async def extract_invoice(self, request: ExtractInvoiceRequest) -> ExtractInvoiceResponse:
        return ExtractInvoiceResponse(
            confidence_score=0.95,
            output=ExtractedInvoice(
                invoice_number="INV-E2E",
                invoice_date=date(2026, 5, 10),
                due_date=None,
                payment_terms="NET30",
                total_amount="1090.00",
                tax_amount="90.00",
                tax_code="GST9",
                currency="SGD",
                customer_name=request.customer_hint,
            ),
        )

    async def check_duplicate(self, request: CheckDuplicateRequest) -> CheckDuplicateResponse:
        from agents.hermes.extract import check_duplicate_stub

        return check_duplicate_stub(request)


@pytest.mark.integration
async def test_uat_015_e2e_ar_intake_with_subaccount_and_tax(db_session) -> None:
    """UAT-015: subaccount + terms + tax_resolution on AR invoice path."""
    out_gl = f"2100UAT-{uuid4().hex[:3]}"
    db_session.add(
        CoaAccount(account_code=out_gl, account_name="GST Payable", account_type="liability")
    )
    db_session.add(CoaAccount(account_code="1300", account_name="AR", account_type="asset"))
    db_session.add(CoaAccount(account_code="4100", account_name="Revenue", account_type="revenue"))
    db_session.add(
        TenantTaxCode(
            code="GST9",
            description="9%",
            rate=Decimal("0.09"),
            direction="output",
            output_gl_account_code=out_gl,
        )
    )

    cp = Counterparty(name=f"Customer {uuid4().hex[:6]}", type="customer")
    db_session.add(cp)
    await db_session.flush()

    term = (
        await db_session.execute(select(PaymentTerm).where(PaymentTerm.code == "NET30"))
    ).scalar_one()
    db_session.add(
        CounterpartyAccount(
            counterparty_id=cp.id,
            account_code="CUST-01",
            display_name="Bill-to 01",
            payment_term_id=term.id,
        )
    )
    await db_session.flush()

    case = Case(
        case_number=f"CAS-UAT15-{uuid4().hex[:6]}",
        type="ar_invoice",
        status="classified",
        subject="UAT-015 E2E",
        counterparty_id=cp.id,
        counterparty_name=cp.name,
        stp_eligible=True,
        confidence_score=Decimal("0.95"),
    )
    db_session.add(case)
    definition = WorkflowDefinition(
        name=f"wf_uat15_{uuid4().hex[:6]}",
        version=1,
        case_type="ar_invoice",
    )
    db_session.add(definition)
    await db_session.flush()
    db_session.add(
        WorkflowInstance(case_id=case.id, definition_id=definition.id, current_state="classified")
    )
    await db_session.commit()

    worker = ARWorkerService(db_session, hermes=_UAT15Hermes())
    result = await worker.handle_ar_invoice(
        {"case_id": str(case.id), "case_type": "ar_invoice", "stp_eligible": True}
    )
    assert result["status"] in ("posted", "pending_approval", "manual_review")

    await db_session.refresh(case)
    wm = case.workflow_metadata or {}
    assert wm.get("tax_resolution", {}).get("gl_account_code") == out_gl
    assert wm.get("extraction_output", {}).get("payment_term_code") == "NET30"
    assert case.counterparty_account_id is not None
