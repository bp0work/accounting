"""Rule-based email classifier (MVP stub) — replace with LLM when Ollama prompt is ready."""

from __future__ import annotations

import re

from app.schemas.hermes import ClassifyEmailRequest, ClassifyEmailOutput, ClassifyEmailResponse

_SUBJECT_RULES: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\binvoice\b", re.I), "ap_invoice", 0.92),
    (re.compile(r"\bpayment\s+advice\b", re.I), "ar_payment_advice", 0.90),
    (re.compile(r"\bcredit\s+note\b", re.I), "ar_credit_note", 0.88),
    (re.compile(r"\bpurchase\s+order\b|\bPO\b", re.I), "ap_po_validation", 0.85),
    (re.compile(r"\breconcil", re.I), "treasury_reconciliation", 0.87),
    (re.compile(r"\bFX\b|foreign\s+exchange", re.I), "treasury_fx", 0.86),
]


def classify_email_stub(request: ClassifyEmailRequest) -> ClassifyEmailResponse:
    mailbox = (request.mailbox or "").lower()
    case_type = "general_inquiry"
    confidence = 0.72

    for hint, ctype in [
        ("accap", "ap_invoice"),
        ("accar", "ar_invoice"),
        ("accexp", "general_inquiry"),
        ("fintreasury", "treasury_reconciliation"),
        ("finfa", "treasury_suspense"),
    ]:
        if hint in mailbox:
            case_type = ctype
            confidence = 0.88
            break

    text = f"{request.subject} {request.body_preview}"
    for pattern, ctype, conf in _SUBJECT_RULES:
        if pattern.search(text):
            case_type = ctype
            confidence = max(confidence, conf)
            break

    if request.valid_case_types and case_type not in request.valid_case_types:
        case_type = "general_inquiry"
        confidence = min(confidence, 0.65)

    counterparty_match = None
    if request.known_counterparties:
        for cp in request.known_counterparties:
            if cp.name.lower() in text.lower():
                counterparty_match = cp.name
                confidence = min(0.98, confidence + 0.05)
                break

    stp = confidence >= 0.90 and counterparty_match is not None
    return ClassifyEmailResponse(
        success=True,
        confidence_score=round(confidence, 2),
        model_used="hermes-stub-rules",
        prompt_version="email_classify-v1",
        output=ClassifyEmailOutput(
            case_type=case_type,
            stp_eligible=stp,
            counterparty_match=counterparty_match,
            reasoning=f"Classified as {case_type} from mailbox/subject heuristics.",
        ),
    )
