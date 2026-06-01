"""Unit tests — sync_pending_escalation_metadata."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.case import Case
from app.models.executive_mail import CaseEscalation
from app.services.executive_mail_service import ExecutiveMailService


@pytest.mark.asyncio
async def test_sync_repairs_false_pending_flag_when_db_escalation_open() -> None:
    case_id = uuid.uuid4()
    esc_id = uuid.uuid4()
    case = Case(
        case_number="CAS-SYNC-1",
        type="expense_claim",
        status="on_hold",
        subject="test",
        workflow_metadata={
            "escalation_id": str(esc_id),
            "escalation_pending": False,
            "reason_code": "EXP_PARSING_INCOMPLETE",
        },
    )
    pending = CaseEscalation(
        id=esc_id,
        case_id=case_id,
        originating_mailbox_id=uuid.uuid4(),
        target_email="mgr@example.com",
        status="pending",
        reason_code="EXP_PARSING_INCOMPLETE",
        summary="Parsing incomplete",
    )

    session = AsyncMock()
    svc = ExecutiveMailService(session)
    svc._pending_escalation = AsyncMock(return_value=pending)

    changed = await svc.sync_pending_escalation_metadata(case)

    assert changed is True
    assert case.workflow_metadata["escalation_pending"] is True
    assert case.workflow_metadata["escalation_id"] == str(esc_id)


@pytest.mark.asyncio
async def test_sync_clears_stale_pending_flag_when_no_db_row() -> None:
    case = Case(
        case_number="CAS-SYNC-2",
        type="ap_invoice",
        status="on_hold",
        subject="test",
        workflow_metadata={
            "escalation_id": str(uuid.uuid4()),
            "escalation_pending": True,
        },
    )
    session = AsyncMock()
    svc = ExecutiveMailService(session)
    svc._pending_escalation = AsyncMock(return_value=None)

    changed = await svc.sync_pending_escalation_metadata(case)

    assert changed is True
    assert case.workflow_metadata["escalation_pending"] is False
