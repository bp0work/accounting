"""Unit tests for executive mail SOP — `17` §10."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.executive_mail_service import ExecutiveMailService, INTERNAL_DOMAIN


def test_is_external_sender():
    assert ExecutiveMailService.is_external_sender("vendor@example.com") is True
    assert ExecutiveMailService.is_external_sender("accar.mmlogistix@bp0.work") is False
    assert ExecutiveMailService.is_external_sender("") is False


def test_escalation_action_urls(monkeypatch):
    monkeypatch.setenv("FINANCE_PUBLIC__APP_HOST", "finance.example.test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    session = MagicMock()
    svc = ExecutiveMailService(session)
    esc_id = uuid.uuid4()
    urls = svc.escalation_action_urls(esc_id, "wire-token")
    assert urls["approve_url"].startswith("https://finance.example.test/mail/escalations/")
    assert "action=approve" in urls["approve_url"]
    assert "action=reject" in urls["reject_url"]
    assert "action=escalate" in urls["escalate_url"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_queue_acknowledgement_skips_internal_sender():
    session = AsyncMock()
    svc = ExecutiveMailService(session)
    case = MagicMock()
    case.id = uuid.uuid4()
    case.case_number = "CAS-20260520-0001"
    email = MagicMock()
    email.from_address = f"accar.mmlogistix{INTERNAL_DOMAIN}"
    result = await svc.queue_acknowledgement(case=case, email=email)
    assert result is None
