"""Rule-based extraction stubs for AR/AP — MVP until Ollama prompts ship."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from app.schemas.hermes import (
    CheckDuplicateOutput,
    CheckDuplicateRequest,
    CheckDuplicateResponse,
    ExtractInvoiceRequest,
    ExtractInvoiceResponse,
    ExtractPaymentAdviceRequest,
    ExtractPaymentAdviceResponse,
    ExtractedInvoice,
    ExtractedPaymentAdvice,
    GenerateSOARequest,
    GenerateSOAResponse,
    GenerateSOAOutput,
    InvoiceAllocation,
    PODifference,
    ValidatePOMatchOutput,
    ValidatePOMatchRequest,
    ValidatePOMatchResponse,
)


def _parse_amount(text: str) -> str | None:
    match = re.search(r"(?:total|amount)[:\s]*\$?\s*([\d,]+\.?\d*)", text, re.I)
    if match:
        return match.group(1).replace(",", "")
    match = re.search(r"\$\s*([\d,]+\.?\d*)", text)
    return match.group(1).replace(",", "") if match else None


def _parse_document_number(text: str) -> str | None:
    patterns = [
        r"(?:invoice|inv)[\s#:.-]*([A-Z0-9-]+)",
        r"(?:receipt(?:\s+no\.?|\s+number)?)[\s#:.-]*([A-Z0-9-]+)",
        r"(?:reference(?:\s+no\.?)?|ref(?:\s+no\.?)?)[\s#:.-]*([A-Z0-9-]+)",
        r"(?:ARN|document(?:\s+no\.?)?)[\s#:.-]*([A-Z0-9-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return None


def _parse_po_reference(text: str) -> str | None:
    match = re.search(r"(?:PO|purchase\s+order)[\s#:.-]*([A-Z0-9-]+)", text, re.I)
    return match.group(1) if match else None


def extract_invoice_stub(request: ExtractInvoiceRequest) -> ExtractInvoiceResponse:
    text = request.extracted_text or ""
    document_number = _parse_document_number(text)
    po_reference = _parse_po_reference(text)
    total = _parse_amount(text)
    missing = []
    if not document_number:
        missing.append("document_number")
    if not total:
        missing.append("total_amount")
    today = date.today()
    is_paid_receipt = bool(
        re.search(r"\b(receipt|paid|payment\s+confirmed|payment\s+received)\b", text, re.I)
    )
    extracted = ExtractedInvoice(
        document_number=document_number,
        document_date=today,
        due_date=today if is_paid_receipt else None,
        vendor_name=request.supplier_hint,
        po_reference=po_reference,
        total_amount=total,
        tax_amount="0.00",
        currency=request.currency_hint,
        missing_fields=missing,
        warnings=[],
    )
    confidence = 0.92 if not missing else 0.65
    return ExtractInvoiceResponse(
        confidence_score=confidence,
        output=extracted,
    )


def extract_payment_advice_stub(
    request: ExtractPaymentAdviceRequest,
) -> ExtractPaymentAdviceResponse:
    text = request.extracted_text or ""
    amount = _parse_amount(text)
    inv = _parse_document_number(text)
    allocations: list[InvoiceAllocation] = []
    if inv and amount:
        allocations.append(
            InvoiceAllocation(document_number=inv, amount_applied=amount, discount_taken="0.00")
        )
    missing = []
    if not amount:
        missing.append("payment_amount")
    extracted = ExtractedPaymentAdvice(
        payer_name=request.customer_hint,
        payment_date=date.today(),
        payment_amount=amount,
        currency=request.currency_hint,
        bank_reference=None,
        allocations=allocations,
        unallocated_amount="0.00" if allocations else (amount or "0.00"),
        missing_fields=missing,
    )
    confidence = 0.90 if not missing else 0.60
    return ExtractPaymentAdviceResponse(confidence_score=confidence, output=extracted)


def check_duplicate_stub(request: CheckDuplicateRequest) -> CheckDuplicateResponse:
    inv_num = request.extracted_invoice.document_number
    total = request.extracted_invoice.total_amount
    for recent in request.recent_cases:
        if recent.document_number and inv_num and recent.document_number == inv_num:
            if recent.total_amount and total and recent.total_amount == total:
                return CheckDuplicateResponse(
                    output=CheckDuplicateOutput(
                        is_duplicate=True,
                        similarity_score=0.95,
                        matched_case_id=recent.case_id,
                    )
                )
    return CheckDuplicateResponse(
        output=CheckDuplicateOutput(is_duplicate=False, similarity_score=0.0)
    )


def generate_soa_stub(request: GenerateSOARequest) -> GenerateSOAResponse:
    total = Decimal("0")
    lines = [f"Statement of Account — {request.counterparty_name}"]
    as_of = request.as_of_date or date.today()
    lines.append(f"As of: {as_of.isoformat()}")
    for item in request.open_invoices:
        amt = Decimal(item.amount or "0")
        total += amt
        lines.append(f"  {item.case_number} / {item.document_number}: {item.currency} {amt}")
    lines.append(f"Total outstanding: SGD {total}")
    return GenerateSOAResponse(
        output=GenerateSOAOutput(
            soa_text="\n".join(lines),
            total_outstanding=str(total),
            open_invoice_count=len(request.open_invoices),
        )
    )


def validate_po_match_stub(request: ValidatePOMatchRequest) -> ValidatePOMatchResponse:
    """Rule-based PO match — compares invoice total to PO total_amount."""
    inv = request.extracted_invoice
    po = request.po_data
    differences: list[PODifference] = []
    inv_total = Decimal(inv.total_amount or "0")
    po_total = Decimal(str(po.get("total_amount", "0")))
    tolerance = Decimal("0.01")
    partial_pct = Decimal("0.05")

    if abs(inv_total - po_total) > tolerance:
        differences.append(
            PODifference(
                field="total_amount",
                invoice_value=str(inv_total),
                po_value=str(po_total),
            )
        )
    po_currency = po.get("currency", "SGD")
    currency_mismatch = bool(
        inv.currency and po_currency and inv.currency != po_currency
    )
    if currency_mismatch:
        differences.append(
            PODifference(
                field="currency",
                invoice_value=inv.currency,
                po_value=str(po_currency),
            )
        )

    if not differences:
        return ValidatePOMatchResponse(
            output=ValidatePOMatchOutput(
                match_status="exact",
                recommendation="Proceed with AP posting",
            ),
        )

    if currency_mismatch:
        return ValidatePOMatchResponse(
            confidence_score=0.70,
            output=ValidatePOMatchOutput(
                match_status="mismatch",
                differences=differences,
                recommendation="Route to manual review for PO variance",
            ),
        )

    if po_total > 0 and abs(inv_total - po_total) / po_total <= partial_pct:
        return ValidatePOMatchResponse(
            confidence_score=0.85,
            output=ValidatePOMatchOutput(
                match_status="partial",
                differences=differences,
                recommendation="Approve — amount variance within 5% tolerance",
            ),
        )

    return ValidatePOMatchResponse(
        confidence_score=0.70,
        output=ValidatePOMatchOutput(
            match_status="mismatch",
            differences=differences,
            recommendation="Route to manual review for PO variance",
        ),
    )
