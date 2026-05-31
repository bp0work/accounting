"""Hermes API schemas — `04` §6."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class AttachmentInput(BaseModel):
    attachment_id: UUID
    filename: str
    mime_type: str
    extracted_text: str | None = None
    page_count: int | None = None


class CounterpartyHint(BaseModel):
    name: str
    code: str | None = None
    type: str | None = None
    is_recurring: bool = False


class ClassifyEmailRequest(BaseModel):
    case_id: UUID | None = None
    email_id: UUID
    subject: str
    body_preview: str = ""
    from_address: str
    mailbox: str | None = None
    attachments: list[AttachmentInput] = Field(default_factory=list)
    known_counterparties: list[CounterpartyHint] = Field(default_factory=list)
    valid_case_types: list[str] = Field(default_factory=list)


class ClassifyEmailOutput(BaseModel):
    case_type: str
    stp_eligible: bool = False
    counterparty_match: str | None = None
    reasoning: str = ""


class ClassifyEmailResponse(BaseModel):
    success: bool = True
    confidence_score: float = 0.0
    model_used: str = "hermes-stub"
    prompt_version: str = "email_classify-v1"
    processing_time_ms: int = 0
    output: ClassifyEmailOutput | None = None
    error_code: str | None = None
    error_message: str | None = None


class ExtractInvoiceRequest(BaseModel):
    case_id: UUID
    attachment_id: UUID | None = None
    mime_type: str = "application/pdf"
    extracted_text: str = ""
    email_body: str = ""
    document_role: str = "ap"  # "ar" customer invoice | "ap" supplier invoice
    supplier_hint: str | None = None
    customer_hint: str | None = None
    currency_hint: str = "SGD"
    tenant_id: UUID | None = None
    vendor_name_for_hints: str | None = None


class InvoiceLineItem(BaseModel):
    description: str = ""
    quantity: str | None = None
    unit_price: str | None = None
    amount: str | None = None


class ExtractedInvoice(BaseModel):
    document_number: str | None = None
    document_date: date | None = None
    due_date: date | None = None
    vendor_name: str | None = None
    customer_name: str | None = None
    po_reference: str | None = None
    subtotal: str | None = None
    total_amount: str | None = None
    tax_amount: str | None = None
    tax_code: str | None = None
    currency: str = "SGD"
    exchange_rate: str | None = None
    sgd_amount: str | None = None
    payment_terms: str | None = None
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidatePOMatchRequest(BaseModel):
    case_id: UUID
    extracted_invoice: ExtractedInvoice
    po_data: dict


class PODifference(BaseModel):
    field: str
    invoice_value: str
    po_value: str


class ValidatePOMatchOutput(BaseModel):
    match_status: str
    differences: list[PODifference] = Field(default_factory=list)
    recommendation: str = ""


class ValidatePOMatchResponse(BaseModel):
    success: bool = True
    confidence_score: float = 1.0
    output: ValidatePOMatchOutput | None = None


class ExtractInvoiceResponse(BaseModel):
    success: bool = True
    confidence_score: float = 0.0
    model_used: str = "hermes-stub"
    prompt_version: str = "ar_invoice_extract-v1"
    output: ExtractedInvoice | None = None


class InvoiceAllocation(BaseModel):
    document_number: str
    amount_applied: str
    discount_taken: str = "0.00"


class ExtractPaymentAdviceRequest(BaseModel):
    case_id: UUID
    extracted_text: str = ""
    customer_hint: str | None = None
    currency_hint: str = "SGD"


class ExtractedPaymentAdvice(BaseModel):
    payer_name: str | None = None
    payment_date: date | None = None
    payment_amount: str | None = None
    currency: str = "SGD"
    bank_reference: str | None = None
    allocations: list[InvoiceAllocation] = Field(default_factory=list)
    unallocated_amount: str = "0.00"
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExtractPaymentAdviceResponse(BaseModel):
    success: bool = True
    confidence_score: float = 0.0
    model_used: str = "hermes-stub"
    prompt_version: str = "ar_payment_advice-v1"
    output: ExtractedPaymentAdvice | None = None


class RecentCase(BaseModel):
    case_id: UUID
    case_number: str
    document_number: str | None = None
    total_amount: str | None = None
    created_at: str | None = None


class CheckDuplicateRequest(BaseModel):
    case_id: UUID
    extracted_invoice: ExtractedInvoice
    recent_cases: list[RecentCase] = Field(default_factory=list)


class CheckDuplicateOutput(BaseModel):
    is_duplicate: bool = False
    similarity_score: float = 0.0
    matched_case_id: UUID | None = None


class CheckDuplicateResponse(BaseModel):
    success: bool = True
    output: CheckDuplicateOutput | None = None


class OpenInvoiceItem(BaseModel):
    case_number: str
    document_number: str | None = None
    amount: str | None = None
    currency: str = "SGD"


class GenerateSOARequest(BaseModel):
    case_id: UUID
    counterparty_name: str
    open_invoices: list[OpenInvoiceItem] = Field(default_factory=list)
    as_of_date: date | None = None


class GenerateSOAOutput(BaseModel):
    soa_text: str
    total_outstanding: str
    open_invoice_count: int


class GenerateSOAResponse(BaseModel):
    success: bool = True
    output: GenerateSOAOutput | None = None


class ReconciliationBankItem(BaseModel):
    id: UUID
    transaction_date: date
    description: str | None = None
    reference: str | None = None
    amount: str
    currency: str = "SGD"


class ReconciliationLedgerItem(BaseModel):
    id: UUID
    transaction_date: date
    description: str | None = None
    reference: str | None = None
    amount: str
    currency: str = "SGD"


class SuggestMatchesRequest(BaseModel):
    reconciliation_id: UUID
    unmatched_bank_items: list[ReconciliationBankItem] = Field(default_factory=list)
    unmatched_ledger_items: list[ReconciliationLedgerItem] = Field(default_factory=list)
    tolerance_days: int = 3
    tolerance_amount_pct: float = 0.01


class MatchSuggestion(BaseModel):
    bank_item_id: UUID
    ledger_item_id: UUID
    confidence: float
    match_reason: str


class SuggestMatchesOutput(BaseModel):
    suggestions: list[MatchSuggestion] = Field(default_factory=list)
    unresolvable_bank_items: list[UUID] = Field(default_factory=list)
    unresolvable_ledger_items: list[UUID] = Field(default_factory=list)


class SuggestMatchesResponse(BaseModel):
    success: bool = True
    output: SuggestMatchesOutput | None = None


class ExtractExpenseClaimRequest(BaseModel):
    email_id: str
    email_body: str = ""
    attachments: list[dict] = Field(default_factory=list)
    claimant_hint: str | None = None
    department_hint: str | None = None
    expense_categories: list[str] = Field(default_factory=list)


class ExtractedExpenseLineItem(BaseModel):
    line_number: int
    expense_date: date | None = None
    category: str | None = None
    description: str = ""
    merchant: str | None = None
    currency: str = "SGD"
    amount_claimed: str = "0"
    exchange_rate: str | None = None
    confidence: float = 0.0


class ExtractExpenseClaimOutput(BaseModel):
    confidence_score: float = 0.0
    claim_period_from: date | None = None
    claim_period_to: date | None = None
    purpose: str | None = None
    currency: str = "SGD"
    line_items: list[ExtractedExpenseLineItem] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExtractExpenseClaimResponse(BaseModel):
    success: bool = True
    confidence_score: float = 0.0
    model_used: str = "qwen2.5:7b"
    prompt_version: str = "expense_claim_extract-v1"
    output: ExtractExpenseClaimOutput | None = None
    error_message: str | None = None


class DocumentTextRequest(BaseModel):
    filename: str = ""
    mime_type: str
    content_base64: str


class DocumentTextResponse(BaseModel):
    success: bool = True
    extracted_text: str = ""
    model_used: str = ""
    error_message: str | None = None
