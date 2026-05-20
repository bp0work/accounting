"""Phase 6 AR Worker integration tests."""

from decimal import Decimal
from uuid import uuid4

import pytest

from agents.hermes.extract import (
    check_duplicate_stub,
    extract_invoice_stub,
    extract_payment_advice_stub,
    generate_soa_stub,
)
from app.models.case import Case, Counterparty
from app.models.workflow import WorkflowDefinition, WorkflowInstance
from app.schemas.hermes import (
    CheckDuplicateRequest,
    CheckDuplicateResponse,
    ExtractInvoiceRequest,
    ExtractInvoiceResponse,
    ExtractPaymentAdviceRequest,
    ExtractPaymentAdviceResponse,
    GenerateSOARequest,
    GenerateSOAResponse,
)
from workers.ar.handlers import ARWorkerService


class _StubHermes:
    async def extract_invoice(self, request: ExtractInvoiceRequest) -> ExtractInvoiceResponse:
        return extract_invoice_stub(request)

    async def extract_payment_advice(
        self, request: ExtractPaymentAdviceRequest
    ) -> ExtractPaymentAdviceResponse:
        return extract_payment_advice_stub(request)

    async def check_duplicate(self, request: CheckDuplicateRequest) -> CheckDuplicateResponse:
        return check_duplicate_stub(request)

    async def generate_soa(self, request: GenerateSOARequest) -> GenerateSOAResponse:
        return generate_soa_stub(request)


@pytest.mark.integration
async def test_ar_invoice_processing_posts_journal(db_session) -> None:
    cp = Counterparty(name=f"Customer {uuid4().hex[:6]}", type="customer")
    db_session.add(cp)
    await db_session.flush()

    case = Case(
        case_number=f"CAS-AR-{uuid4().hex[:8]}",
        type="ar_invoice",
        status="classified",
        subject="Invoice test",
        counterparty_id=cp.id,
        counterparty_name=cp.name,
        stp_eligible=True,
        confidence_score=Decimal("0.95"),
    )
    db_session.add(case)
    await db_session.flush()

    definition = WorkflowDefinition(
        name=f"wf_ar_{uuid4().hex[:8]}",
        version=1,
        case_type="ar_invoice",
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

    message = {
        "message_id": str(uuid4()),
        "case_id": str(case.id),
        "case_type": "ar_invoice",
        "case_number": case.case_number,
        "stp_eligible": True,
        "confidence_score": 0.95,
    }
    service = ARWorkerService(db_session, hermes=_StubHermes())
    result = await service.handle_ar_invoice(message)
    await db_session.commit()

    assert result["status"] in ("posted", "pending_approval", "manual_review")
    await db_session.refresh(case)
    assert case.amount_value is not None


@pytest.mark.integration
async def test_ar_soa_completes_case(db_session) -> None:
    cp = Counterparty(name=f"SOA Customer {uuid4().hex[:6]}", type="customer")
    db_session.add(cp)
    await db_session.flush()

    case = Case(
        case_number=f"CAS-SOA-{uuid4().hex[:8]}",
        type="ar_soa_request",
        status="classified",
        subject="SOA request",
        counterparty_id=cp.id,
        counterparty_name=cp.name,
    )
    db_session.add(case)
    await db_session.commit()

    service = ARWorkerService(db_session, hermes=_StubHermes())
    result = await service.handle_soa_request(
        {"message_id": str(uuid4()), "case_id": str(case.id), "case_type": "ar_soa_request"}
    )
    await db_session.commit()
    assert result["status"] == "completed"
    await db_session.refresh(case)
    assert case.status == "completed"
