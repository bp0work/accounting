"""Parsing confirmation persistence — `0.15.07-confirm-parsing-persistence`."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.case import Case
from app.models.mail import Email
from app.models.user import User
from app.repositories.case import CaseRepository
from app.schemas.auth import TokenData
from app.schemas.parsing_confirmation import ConfirmParsingRequest, ParsingConfirmationFields
from app.services.parsing_confirmation_service import (
    CONFIRM_PARSING_PERSISTED_KEYS,
    _merge_confirmed_workflow_metadata,
    _verify_confirmed_metadata_persisted,
    execute_confirm_parsing,
)
from workers.common.parsing_confirmation import CONFIRM_PARSING_RESUME_STEP
from workers.expense.handlers import ExpenseWorkerService


class _SessionFactoryCtx:
    def __init__(self, session) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _patch_get_session_factory(session):
    def get_session_factory():
        def factory():
            return _SessionFactoryCtx(session)

        return factory

    return get_session_factory


def _full_confirm_request(**overrides) -> ConfirmParsingRequest:
    gl_id = uuid4()
    fields = ParsingConfirmationFields(
        document_type="receipt",
        document_number="RCPT-1001",
        document_date="2026-05-01",
        vendor_name="Coffee Shop",
        total_amount="42.50",
        tax_amount="3.50",
        currency="SGD",
        business_purpose="Client meeting",
        gl_account_id=gl_id,
        sender_validated=True,
        document_validated=True,
        **overrides,
    )
    return ConfirmParsingRequest(extracted_fields=fields)


@pytest.mark.asyncio
async def test_confirm_parsing_persists_all_fields() -> None:
    user_id = uuid4()
    case = Case(
        id=uuid4(),
        case_number=f"CAS-PC-{uuid4().hex[:6]}",
        type="expense_claim",
        status="pending_confirmation",
        subject="Expense receipt",
        workflow_metadata={
            "extracted_fields": {"vendor_name": "Stale Vendor"},
            "pending_parsing_confirmation": True,
            "extraction_confidence": 0.55,
            "unrelated_key": "keep-me",
        },
    )
    session = AsyncMock()
    session.get = AsyncMock(
        return_value=User(
            id=user_id,
            username="acc_mgr",
            display_name="Accounts Manager",
            email="acc@mmlogistix.bp0.work",
            password_hash="x",
            role_id=uuid4(),
            status="active",
        )
    )
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()

    mock_cases = MagicMock(spec=CaseRepository)
    mock_cases.get = AsyncMock(return_value=case)
    mock_cases.add_timeline = AsyncMock()

    user = TokenData(
        user_id=user_id,
        role="accounts_manager",
        permissions=["cases:write"],
    )
    body = _full_confirm_request()

    with (
        patch(
            "app.services.parsing_confirmation_service.get_session_factory",
            _patch_get_session_factory(session),
        ),
        patch(
            "app.services.parsing_confirmation_service.CaseRepository",
            return_value=mock_cases,
        ),
        patch(
            "app.services.parsing_confirmation_service.enqueue_accounts",
            AsyncMock(return_value="msg-1"),
        ) as enqueue_mock,
    ):
        await execute_confirm_parsing(case.id, user=user, body=body)

    meta = case.workflow_metadata or {}
    stored = meta.get("extracted_fields") or {}

    assert meta.get("unrelated_key") == "keep-me"
    assert stored["vendor_name"] == "Coffee Shop"
    assert stored["document_number"] == "RCPT-1001"
    assert stored["document_date"] == "2026-05-01"
    assert stored["total_amount"] == "42.50"
    assert stored["tax_amount"] == "3.50"
    assert stored["currency"] == "SGD"
    assert stored["business_purpose"] == "Client meeting"
    assert stored["document_type"] == "receipt"
    assert stored["document_validated"] == "true"
    assert stored["gl_account_id"] == str(body.extracted_fields.gl_account_id)

    for key in CONFIRM_PARSING_PERSISTED_KEYS:
        expected = stored.get(key)
        if expected is not None and str(expected).strip():
            assert str(stored.get(key)) == str(expected)

    enqueue_mock.assert_awaited_once()
    enqueue_kwargs = enqueue_mock.await_args.kwargs
    assert enqueue_kwargs["parsing_confirmed"] is True
    assert enqueue_kwargs["confirmed_extracted_fields"]["vendor_name"] == "Coffee Shop"


@pytest.mark.asyncio
async def test_confirm_parsing_sets_resume_step() -> None:
    user_id = uuid4()
    case = Case(
        id=uuid4(),
        case_number=f"CAS-PC-{uuid4().hex[:6]}",
        type="expense_claim",
        status="pending_confirmation",
        subject="Expense receipt",
        workflow_metadata={"extracted_fields": {}, "pending_parsing_confirmation": True},
    )
    session = AsyncMock()
    session.get = AsyncMock(
        return_value=User(
            id=user_id,
            username="acc_mgr",
            display_name="Accounts Manager",
            email="acc@mmlogistix.bp0.work",
            password_hash="x",
            role_id=uuid4(),
            status="active",
        )
    )
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()

    mock_cases = MagicMock(spec=CaseRepository)
    mock_cases.get = AsyncMock(return_value=case)
    mock_cases.add_timeline = AsyncMock()

    user = TokenData(
        user_id=user_id,
        role="accounts_manager",
        permissions=["cases:write"],
    )

    with (
        patch(
            "app.services.parsing_confirmation_service.get_session_factory",
            _patch_get_session_factory(session),
        ),
        patch(
            "app.services.parsing_confirmation_service.CaseRepository",
            return_value=mock_cases,
        ),
        patch(
            "app.services.parsing_confirmation_service.enqueue_accounts",
            AsyncMock(return_value="msg-2"),
        ),
    ):
        await execute_confirm_parsing(
            case.id,
            user=user,
            body=_full_confirm_request(),
        )

    meta = case.workflow_metadata or {}
    assert meta.get("parsing_confirmed") is True
    assert meta.get("resume_from_step") == CONFIRM_PARSING_RESUME_STEP
    assert meta.get("pending_parsing_confirmation") is None
    assert case.status == "classified"


def test_merge_confirmed_workflow_metadata_preserves_unrelated_keys() -> None:
    user_id = uuid4()
    meta, normalized = _merge_confirmed_workflow_metadata(
        {
            "extracted_fields": {"vendor_name": "Old"},
            "pending_parsing_confirmation": True,
            "custom_flag": True,
        },
        {
            "document_type": "receipt",
            "vendor_name": "New Vendor",
            "total_amount": "10.00",
            "currency": "SGD",
            "document_date": "2026-05-01",
            "document_validated": True,
        },
        user_id=user_id,
        confirmed_at=MagicMock(isoformat=lambda: "2026-06-03T00:00:00+00:00"),
    )
    assert meta["custom_flag"] is True
    assert meta["parsing_confirmed"] is True
    assert meta["resume_from_step"] == CONFIRM_PARSING_RESUME_STEP
    assert normalized["vendor_name"] == "New Vendor"
    _verify_confirmed_metadata_persisted(meta, normalized)


@pytest.mark.asyncio
async def test_worker_resumes_from_confirmed_parsing_without_reextraction() -> None:
    case_id = uuid4()
    email_id = uuid4()
    gl_id = uuid4()
    confirmed = {
        "document_type": "receipt",
        "document_number": "RCPT-2002",
        "document_date": "2026-05-02",
        "vendor_name": "Confirmed Vendor",
        "total_amount": "99.00",
        "tax_amount": "7.20",
        "currency": "SGD",
        "business_purpose": "Team lunch",
        "gl_account_id": str(gl_id),
        "document_validated": "true",
        "sender_validated": "true",
    }
    case = Case(
        id=case_id,
        case_number="EXP-PC-007",
        type="expense_claim",
        status="classified",
        subject="Expense",
        email_id=email_id,
        confidence_score=0.91,
        workflow_metadata={
            "extracted_fields": confirmed,
            "parsing_confirmed": True,
            "resume_from_step": CONFIRM_PARSING_RESUME_STEP,
            "extraction_confidence": 0.91,
        },
    )
    email = Email(
        id=email_id,
        mailbox_address="accexp.mmlogistix@bp0.work",
        from_address="staff@mmlogistix.bp0.work",
        subject="Receipt",
        body_text="Please reimburse",
    )

    extract_mock = AsyncMock(return_value=({"unexpected": "extract"}, 0.99))
    session = AsyncMock()
    service = ExpenseWorkerService(session=session, hermes=AsyncMock())

    with (
        patch.object(service, "_load_case", AsyncMock(return_value=case)),
        patch.object(service, "_email_for_case", AsyncMock(return_value=email)),
        patch.object(service, "_extract_from_email", extract_mock),
        patch.object(service, "_start_processing", AsyncMock()),
        patch.object(service, "_add_timeline", AsyncMock()),
        patch(
            "workers.expense.handlers.check_expense_duplicate",
            AsyncMock(return_value=(False, None)),
        ),
        patch(
            "workers.expense.handlers.lookup_staff_by_email",
            AsyncMock(return_value=(None, "not_found")),
        ),
        patch.object(service, "_escalate_step", AsyncMock(return_value={"status": "escalated"})),
    ):
        result = await service.process_accounts_message(
            {
                "case_type": "expense_claim",
                "case_id": str(case_id),
                "parsing_confirmed": True,
                "confirmed_extracted_fields": confirmed,
            }
        )

    extract_mock.assert_not_awaited()
    assert result["status"] == "escalated"
    stored = (case.workflow_metadata or {}).get("extracted_fields") or {}
    assert stored.get("vendor_name") == "Confirmed Vendor"
    assert stored.get("document_number") == "RCPT-2002"
