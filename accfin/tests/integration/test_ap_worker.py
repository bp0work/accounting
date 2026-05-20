"""Phase 7 AP Worker integration tests."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from agents.hermes.extract import (
    check_duplicate_stub,
    extract_invoice_stub,
    validate_po_match_stub,
)
from app.models.case import Case, Counterparty
from app.models.purchase_order import PurchaseOrder
from app.models.workflow import WorkflowDefinition, WorkflowInstance
from app.schemas.hermes import (
    CheckDuplicateRequest,
    CheckDuplicateResponse,
    ExtractInvoiceRequest,
    ExtractInvoiceResponse,
    ValidatePOMatchRequest,
    ValidatePOMatchResponse,
)
from workers.ap.handlers import APWorkerService


class _StubHermes:
    async def extract_invoice(self, request: ExtractInvoiceRequest) -> ExtractInvoiceResponse:
        return extract_invoice_stub(request)

    async def check_duplicate(self, request: CheckDuplicateRequest) -> CheckDuplicateResponse:
        return check_duplicate_stub(request)

    async def validate_po_match(
        self, request: ValidatePOMatchRequest
    ) -> ValidatePOMatchResponse:
        return validate_po_match_stub(request)


@pytest.mark.integration
async def test_ap_invoice_with_matching_po(db_session) -> None:
    cp = Counterparty(name=f"Supplier {uuid4().hex[:6]}", type="supplier")
    db_session.add(cp)
    await db_session.flush()

    po_number = f"PO-{uuid4().hex[:8].upper()}"
    po = PurchaseOrder(
        po_number=po_number,
        counterparty_id=cp.id,
        issue_date=date.today(),
        total_amount=Decimal("5000.0000"),
        currency="SGD",
        line_items=[{"account_code": "5500", "description": "Goods"}],
    )
    db_session.add(po)
    await db_session.flush()

    case = Case(
        case_number=f"CAS-AP-{uuid4().hex[:8]}",
        type="ap_invoice",
        status="classified",
        subject=f"Supplier invoice {po_number}",
        counterparty_id=cp.id,
        counterparty_name=cp.name,
        stp_eligible=True,
        confidence_score=Decimal("0.95"),
    )
    db_session.add(case)
    await db_session.flush()

    definition = WorkflowDefinition(
        name=f"wf_ap_{uuid4().hex[:8]}",
        version=1,
        case_type="ap_invoice",
    )
    db_session.add(definition)
    await db_session.flush()
    db_session.add(
        WorkflowInstance(
            case_id=case.id,
            definition_id=definition.id,
            current_state="classified",
        )
    )
    await db_session.commit()

    from app.models.mail import Email

    email = Email(
        message_id=f"msg-{uuid4().hex}@example.com",
        mailbox_address="accap.mmlogistix@bp0.work",
        from_address="supplier@example.com",
        to_addresses=["accap.mmlogistix@bp0.work"],
        cc_addresses=[],
        subject=case.subject,
        body_text=f"Invoice INV-AP-1 PO {po_number} Total: 5,000.00",
        status="classified",
        received_at=case.created_at,
    )
    db_session.add(email)
    await db_session.flush()
    case.email_id = email.id
    await db_session.commit()

    message = {
        "message_id": str(uuid4()),
        "case_id": str(case.id),
        "case_type": "ap_invoice",
        "case_number": case.case_number,
        "stp_eligible": True,
        "confidence_score": 0.95,
    }
    service = APWorkerService(db_session, hermes=_StubHermes())
    result = await service.handle_ap_invoice(message)
    await db_session.commit()

    assert result["status"] in ("posted", "pending_approval", "manual_review")
    await db_session.refresh(case)
    assert case.amount_value == Decimal("5000.00")


@pytest.mark.integration
async def test_po_validation_completes_on_match(db_session) -> None:
    cp = Counterparty(name=f"PO Supplier {uuid4().hex[:6]}", type="supplier")
    db_session.add(cp)
    await db_session.flush()

    po_number = f"PO-VAL-{uuid4().hex[:6].upper()}"
    db_session.add(
        PurchaseOrder(
            po_number=po_number,
            counterparty_id=cp.id,
            issue_date=date.today(),
            total_amount=Decimal("1200.0000"),
        )
    )
    await db_session.flush()

    case = Case(
        case_number=f"CAS-POV-{uuid4().hex[:8]}",
        type="ap_po_validation",
        status="classified",
        subject="PO validation",
        counterparty_id=cp.id,
        counterparty_name=cp.name,
    )
    db_session.add(case)
    await db_session.flush()

    from app.models.mail import Email

    email = Email(
        message_id=f"msg-{uuid4().hex}@example.com",
        mailbox_address="accap.mmlogistix@bp0.work",
        from_address="supplier@example.com",
        to_addresses=["accap.mmlogistix@bp0.work"],
        cc_addresses=[],
        subject="PO check",
        body_text=f"PO {po_number} Total: 1,200.00",
        status="classified",
        received_at=case.created_at,
    )
    db_session.add(email)
    await db_session.flush()
    case.email_id = email.id
    await db_session.commit()

    service = APWorkerService(db_session, hermes=_StubHermes())
    result = await service.handle_po_validation(
        {"message_id": str(uuid4()), "case_id": str(case.id), "case_type": "ap_po_validation"}
    )
    await db_session.commit()
    assert result["status"] == "completed"
    await db_session.refresh(case)
    assert case.status == "completed"


@pytest.mark.integration
async def test_payment_proposal_manual_review(db_session) -> None:
    case = Case(
        case_number=f"CAS-PAY-{uuid4().hex[:8]}",
        type="ap_payment_proposal",
        status="classified",
        subject="Payment proposal",
    )
    db_session.add(case)
    await db_session.commit()

    service = APWorkerService(db_session, hermes=_StubHermes())
    result = await service.handle_payment_proposal(
        {
            "message_id": str(uuid4()),
            "case_id": str(case.id),
            "case_type": "ap_payment_proposal",
        }
    )
    await db_session.commit()
    assert result["status"] == "manual_review"
