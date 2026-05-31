"""Empty expense extraction pauses for parsing confirmation — `0.14.48`."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.case import Case
from app.models.mail import Email
from workers.expense.handlers import ExpenseWorkerService


@pytest.mark.asyncio
async def test_empty_extraction_pauses_for_parsing_confirmation() -> None:
    case_id = uuid4()
    email_id = uuid4()
    case = Case(
        id=case_id,
        case_number="EXP-003",
        type="expense_claim",
        status="classified",
        email_id=email_id,
    )
    email = Email(
        id=email_id,
        mailbox_address="accexp.mmlogistix@bp0.work",
        from_address="staff@mmlogistix.bp0.work",
        subject="Receipt",
        body_text="Please reimburse",
    )
    session = MagicMock()
    session.flush = AsyncMock()
    service = ExpenseWorkerService(session=session, hermes=MagicMock())

    pause_result = {
        "status": "pending_confirmation",
        "case_id": str(case_id),
        "reason": "parsing_confirmation_required",
    }

    with (
        patch.object(service, "_load_case", AsyncMock(return_value=case)),
        patch.object(service, "_email_for_case", AsyncMock(return_value=email)),
        patch.object(service, "_extract_from_email", AsyncMock(return_value=(None, 0.0))),
        patch.object(service, "_route_failure", AsyncMock()) as route_failure_mock,
        patch(
            "workers.expense.handlers.pause_for_parsing_confirmation",
            AsyncMock(return_value=pause_result),
        ) as pause_mock,
    ):
        result = await service.process_accounts_message(
            {"case_type": "expense_claim", "case_id": str(case_id)}
        )

    assert result["status"] == "pending_confirmation"
    assert result["status"] != "manual_review"
    route_failure_mock.assert_not_called()
    pause_mock.assert_awaited_once()
    call_kwargs = pause_mock.await_args.kwargs
    assert call_kwargs["extraction_confidence"] == 0.0
    assert call_kwargs["actor_name"] == "expense-worker"
    assert isinstance(call_kwargs["extracted_fields"], dict)
