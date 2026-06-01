"""Case re-extract with vendor hints — in-place metadata update."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import AppHTTPException
from app.models.case import Case
from app.schemas.auth import TokenData
from app.schemas.hermes import (
    ExtractExpenseClaimOutput,
    ExtractedExpenseLineItem,
    ExtractInvoiceResponse,
    ExtractedInvoice,
)
from app.services.case_re_extract import execute_case_re_extract


@pytest.mark.asyncio
async def test_re_extract_expense_updates_metadata_in_place() -> None:
    case_id = uuid4()
    case = Case(
        id=case_id,
        case_number="EXP-REX-1",
        type="expense_claim",
        status="pending_confirmation",
        email_id=uuid4(),
        counterparty_name="ACRA",
        workflow_metadata={
            "extracted_fields": {"vendor_name": "ACRA", "currency": "SGD"},
            "extraction_confidence": 0.5,
        },
    )
    expense_out = ExtractExpenseClaimOutput(
        confidence_score=0.92,
        currency="SGD",
        purpose="Filing fee",
        line_items=[
            ExtractedExpenseLineItem(
                line_number=1,
                expense_date=date(2026, 5, 1),
                category="government_fees",
                merchant="ACRA",
                amount_claimed="50.00",
            )
        ],
    )

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_cases = MagicMock()
    mock_cases.get = AsyncMock(return_value=case)
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.case_re_extract.get_session_factory", return_value=mock_factory),
        patch("app.services.case_re_extract.CaseRepository", return_value=mock_cases),
        patch("app.services.case_re_extract._email_for_case", new=AsyncMock(return_value=None)),
        patch(
            "app.services.case_re_extract._re_extract_expense",
            new=AsyncMock(
                return_value=(
                    {
                        "vendor_name": "ACRA",
                        "total_amount": "50.00",
                        "currency": "SGD",
                        "document_date": "2026-05-01",
                        "sender_validated": "false",
                    },
                    0.92,
                )
            ),
        ),
    ):
        user = TokenData(user_id=uuid4(), role="accounts_manager", permissions=["cases:write"])
        result = await execute_case_re_extract(case_id, user=user)

    assert result.status == "pending_confirmation"
    assert result.extracted_fields["total_amount"] == "50.00"
    assert result.extraction_confidence == pytest.approx(0.92)
    meta = case.workflow_metadata or {}
    assert meta["extracted_fields"]["total_amount"] == "50.00"
    assert meta["extraction_confidence"] == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_re_extract_rejects_wrong_status() -> None:
    case_id = uuid4()
    case = Case(
        id=case_id,
        case_number="EXP-REX-2",
        type="expense_claim",
        status="processing",
    )
    mock_session = MagicMock()
    mock_cases = MagicMock()
    mock_cases.get = AsyncMock(return_value=case)
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.case_re_extract.get_session_factory", return_value=mock_factory),
        patch("app.services.case_re_extract.CaseRepository", return_value=mock_cases),
    ):
        user = TokenData(user_id=uuid4(), role="accounts_manager", permissions=["cases:write"])
        with pytest.raises(AppHTTPException) as exc:
            await execute_case_re_extract(case_id, user=user)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_re_extract_invoice_uses_hermes() -> None:
    case_id = uuid4()
    email_id = uuid4()
    case = Case(
        id=case_id,
        case_number="AP-REX-1",
        type="ap_invoice",
        status="pending_confirmation",
        email_id=email_id,
        counterparty_name="Supplier Co",
        workflow_metadata={"extracted_fields": {"vendor_name": "Supplier Co"}},
    )
    inv = ExtractedInvoice(
        vendor_name="Supplier Co",
        total_amount="100.00",
        currency="SGD",
        document_date=date(2026, 5, 2),
    )
    hermes = MagicMock()
    hermes.extract_invoice = AsyncMock(
        return_value=ExtractInvoiceResponse(
            success=True,
            confidence_score=0.88,
            output=inv,
        )
    )

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_cases = MagicMock()
    mock_cases.get = AsyncMock(return_value=case)
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    email = MagicMock()
    email.subject = "Invoice"
    email.body_text = "body"

    with (
        patch("app.services.case_re_extract.get_session_factory", return_value=mock_factory),
        patch("app.services.case_re_extract.CaseRepository", return_value=mock_cases),
        patch("app.services.case_re_extract.HermesClient", return_value=hermes),
        patch("app.services.case_re_extract._email_for_case", new=AsyncMock(return_value=email)),
        patch(
            "app.services.case_re_extract.build_extraction_context",
            new=AsyncMock(return_value=("pdf text", email_id, "email body")),
        ),
    ):
        user = TokenData(user_id=uuid4(), role="accounts_manager", permissions=["cases:write"])
        result = await execute_case_re_extract(case_id, user=user)

    assert result.extracted_fields.get("total_amount") == "100.00"
    hermes.extract_invoice.assert_awaited_once()
