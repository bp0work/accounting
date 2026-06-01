"""Expense Hermes extraction — vendor hints prompt prefix."""

from unittest.mock import AsyncMock, patch

import pytest

from agents.hermes.expense_extract import extract_expense_claim_llm
from app.schemas.hermes import ExtractExpenseClaimRequest


@pytest.mark.asyncio
async def test_extract_expense_claim_prepends_vendor_hints() -> None:
    request = ExtractExpenseClaimRequest(
        email_id="e1",
        email_body="Receipt from ACRA",
        vendor_hints="For vendor ACRA, note the following field locations on the document:\n- document_date is labelled 'Date'\n\n",
    )
    captured: dict = {}

    async def fake_generate_json(*, prompt: str, model: str) -> dict:
        captured["prompt"] = prompt
        return {
            "confidence_score": 0.9,
            "currency": "SGD",
            "total_amount": "10.00",
            "line_items": [],
        }

    with patch(
        "agents.hermes.expense_extract.generate_json",
        new=AsyncMock(side_effect=fake_generate_json),
    ):
        await extract_expense_claim_llm(request)

    assert captured["prompt"].startswith("For vendor ACRA")
    assert "You are an expense claim extractor" in captured["prompt"]
