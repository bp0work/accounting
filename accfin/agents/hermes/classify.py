"""Email classification — mailbox-first routing, optional subject hints — `17` §2.1.1."""

from __future__ import annotations

import re

from app.schemas.hermes import ClassifyEmailRequest, ClassifyEmailOutput, ClassifyEmailResponse

# Local-part hints in executive mailbox addresses (unambiguous intake routes).
MAILBOX_CASE_TYPES: dict[str, tuple[str, float]] = {
    "accap": ("ap_invoice", 0.96),
    "accar": ("ar_invoice", 0.96),
    "accexp": ("expense_claim", 0.96),
    "fintreasury": ("treasury_reconciliation", 0.92),
    "finfa": ("treasury_suspense", 0.90),
}

UNAMBIGUOUS_MAILBOX_PREFIXES = frozenset({"accap", "accar", "accexp"})

_SUBJECT_RULES: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"\binvoice\b", re.I), "ap_invoice", 0.92),
    (re.compile(r"\bpayment\s+advice\b", re.I), "ar_payment_advice", 0.90),
    (re.compile(r"\bcredit\s+note\b", re.I), "ar_credit_note", 0.88),
    (re.compile(r"\bexpense\b|\breceipt\b|\breimburs", re.I), "expense_claim", 0.88),
    (re.compile(r"\bpurchase\s+order\b|\bPO\b", re.I), "ap_po_validation", 0.85),
    (re.compile(r"\breconcil", re.I), "treasury_reconciliation", 0.87),
    (re.compile(r"\bFX\b|foreign\s+exchange", re.I), "treasury_fx", 0.86),
]


def _mailbox_prefix(mailbox: str) -> str | None:
    local = (mailbox or "").split("@")[0].lower()
    for prefix in MAILBOX_CASE_TYPES:
        if prefix in local:
            return prefix
    return None


def classify_email_stub(request: ClassifyEmailRequest) -> ClassifyEmailResponse:
    mailbox = (request.mailbox or "").lower()
    prefix = _mailbox_prefix(mailbox)

    case_type = "general_inquiry"
    confidence = 0.72
    reasoning = "Default general inquiry — no strong mailbox or subject signal."

    if prefix and prefix in MAILBOX_CASE_TYPES:
        case_type, confidence = MAILBOX_CASE_TYPES[prefix]
        reasoning = f"Executive mailbox '{prefix}' is the primary case-type signal."

    # Subject/body heuristics apply only when mailbox is ambiguous.
    if prefix not in UNAMBIGUOUS_MAILBOX_PREFIXES:
        text = f"{request.subject} {request.body_preview}"
        for pattern, ctype, conf in _SUBJECT_RULES:
            if pattern.search(text):
                case_type = ctype
                confidence = max(confidence, conf)
                reasoning = f"Subject/body matched {ctype} (mailbox not unambiguous)."
                break

    if request.valid_case_types and case_type not in request.valid_case_types:
        case_type = "general_inquiry"
        confidence = min(confidence, 0.65)
        reasoning = "Resolved type not in valid_case_types; routed to general_inquiry."

    counterparty_match = None
    text = f"{request.subject} {request.body_preview}"
    if request.known_counterparties:
        for cp in request.known_counterparties:
            if cp.name.lower() in text.lower():
                counterparty_match = cp.name
                if prefix not in UNAMBIGUOUS_MAILBOX_PREFIXES:
                    confidence = min(0.98, confidence + 0.05)
                break

    stp = confidence >= 0.90 and counterparty_match is not None and prefix in UNAMBIGUOUS_MAILBOX_PREFIXES
    return ClassifyEmailResponse(
        success=True,
        confidence_score=round(confidence, 2),
        model_used="mailbox-routing-v1",
        prompt_version="email_classify-v1",
        output=ClassifyEmailOutput(
            case_type=case_type,
            stp_eligible=stp,
            counterparty_match=counterparty_match,
            reasoning=reasoning,
        ),
    )
