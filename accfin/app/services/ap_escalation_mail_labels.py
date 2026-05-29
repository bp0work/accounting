"""AP manager escalation email — primary action button labels (URL still action=approve)."""

from __future__ import annotations

AP_ESCALATION_APPROVE_BUTTON_LABELS: dict[str, str] = {
    "AP_CONTRACT_MISSING": "Resubmit",
    "AP_VENDOR_INACTIVE": "Reactivate & Resubmit",
    "AP_PAYMENT_TERMS_MISMATCH": "Accept & Continue",
    "AP_SENDER_NOT_VALIDATED": "Accept & Continue",
    "AP_COA_NOT_FOUND": "Confirm Account & Continue",
    "AP_CURRENCY_CONVERSION_REQUIRED": "Apply Rate & Continue",
}


def ap_escalation_approve_button_label(reason_code: str | None) -> str:
    """Human label for the green escalation email button (behaviour unchanged)."""
    if not reason_code:
        return "Approve"
    return AP_ESCALATION_APPROVE_BUTTON_LABELS.get(str(reason_code), "Approve")
