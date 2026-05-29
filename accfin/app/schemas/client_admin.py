"""Schemas for Client Admin API."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    legal_name: str
    trading_name: str | None = None
    uen: str | None = None
    gst_registration_number: str | None = None
    registered_address: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None
    email_signature_html: str | None = None
    email_signature_plain: str | None = None


class TenantProfileUpdate(BaseModel):
    legal_name: str | None = None
    trading_name: str | None = None
    uen: str | None = None
    gst_registration_number: str | None = None
    registered_address: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None
    email_signature_html: str | None = None
    email_signature_plain: str | None = None


class CoaAccountResponse(BaseModel):
    id: UUID
    account_code: str
    account_name: str
    account_type: str
    parent_id: UUID | None = None
    is_active: bool
    description: str | None = None

    model_config = {"from_attributes": True}


class CoaAccountCreate(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    parent_code: str | None = None
    description: str | None = None


class CoaAccountUpdate(BaseModel):
    account_name: str | None = None
    account_type: str | None = None
    is_active: bool | None = None
    description: str | None = None


class CoaImportResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    active_count: int


class MailConfigurationResponse(BaseModel):
    id: UUID
    email_address: str
    display_name: str | None
    role: str | None
    mailbox_mode: str
    escalation_manager_email: str | None
    is_active: bool
    require_parsing_confirmation: bool = False
    username_masked: str
    server_host: str

    model_config = {"from_attributes": True}


class MailConfigurationUpdate(BaseModel):
    display_name: str | None = None
    escalation_manager_email: str | None = None
    require_parsing_confirmation: bool | None = None


class AdminUserResponse(BaseModel):
    id: UUID | None = None
    role_label: str
    role_name: str
    display_name: str | None = None
    email: str | None = None
    username: str | None = None
    configured: bool = False


class AdminUserUpdate(BaseModel):
    email: str | None = None
    display_name: str | None = None


class BindingAuthorityThresholdsBody(BaseModel):
    tier_1_ceiling: float | None = None
    tier_2_ceiling: float | None = None
    tier_3_threshold: float | None = None
    stp_confidence_minimum: float | None = None
    tier_2_sla_hours: int | None = None
    tier_3_sla_hours: int | None = None


class BindingAuthorityDocumentResponse(BaseModel):
    document_key: str
    label: str
    thresholds: BindingAuthorityThresholdsBody


class BindingAuthorityResponse(BaseModel):
    ap_invoice: BindingAuthorityDocumentResponse
    ar_invoice: BindingAuthorityDocumentResponse
    expense_claim: BindingAuthorityDocumentResponse


class BindingAuthorityUpdate(BaseModel):
    ap_approval_thresholds: BindingAuthorityThresholdsBody | None = None
    ar_approval_thresholds: BindingAuthorityThresholdsBody | None = None
    expense_approval_thresholds: BindingAuthorityThresholdsBody | None = None


class ExpensePolicyLimitsResponse(BaseModel):
    meal_limit_per_day: Decimal | None = None
    transport_limit_per_trip: Decimal | None = None
    accommodation_limit_per_night: Decimal | None = None
    per_diem_rate: Decimal | None = None
    entertainment_limit_per_occasion: Decimal | None = None


class ExpensePolicyLimitsUpdate(BaseModel):
    meal_limit_per_day: Decimal | None = None
    transport_limit_per_trip: Decimal | None = None
    accommodation_limit_per_night: Decimal | None = None
    per_diem_rate: Decimal | None = None
    entertainment_limit_per_occasion: Decimal | None = None


class RegulatoryDocumentResponse(BaseModel):
    id: UUID
    document_key: str | None = None
    name: str
    filename: str
    file_size: int
    content_type: str
    uploaded_at: datetime
    download_url: str | None = None

    model_config = {"from_attributes": True}


class RegulatoryCatalogItemResponse(BaseModel):
    document_key: str
    label: str
    uploaded: bool
    id: UUID | None = None
    filename: str | None = None
    file_size: int | None = None
    uploaded_at: datetime | None = None
    download_url: str | None = None


class TravelPolicyDocumentResponse(BaseModel):
    uploaded: bool
    filename: str | None = None
    file_size: int | None = None
    uploaded_at: datetime | None = None
    download_url: str | None = None
    wasabi_path: str = "transactions/regulatory/travel-expense-policy.pdf"


class CoaStatusResponse(BaseModel):
    account_count: int
    empty: bool


class RentalAgreementResponse(BaseModel):
    id: UUID
    property_address: str
    monthly_rent_sgd: Decimal
    business_use_percent: Decimal
    effective_date: date
    expiry_date: date | None
    landlord_name: str | None
    landlord_contact: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class RentalAgreementCreate(BaseModel):
    property_address: str
    monthly_rent_sgd: Decimal
    business_use_percent: Decimal = Field(default=Decimal("100"))
    effective_date: date
    expiry_date: date | None = None
    landlord_name: str | None = None
    landlord_contact: str | None = None


class DirectorExpenseAgreementResponse(BaseModel):
    id: UUID
    director_name: str
    director_email: str
    authorised_expense_types: list[str]
    monthly_limit_sgd: Decimal | None
    effective_date: date
    expiry_date: date | None
    is_active: bool

    model_config = {"from_attributes": True}


class DirectorExpenseAgreementCreate(BaseModel):
    director_name: str
    director_email: str
    authorised_expense_types: list[str] = Field(default_factory=list)
    monthly_limit_sgd: Decimal | None = None
    effective_date: date
    expiry_date: date | None = None


class TravelRequestAdminResponse(BaseModel):
    id: UUID
    request_number: str
    traveller_name: str
    employee_email: str
    destination: str | None
    travel_from: date
    travel_to: date
    purpose: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TravelRequestStatusUpdate(BaseModel):
    status: str


class AccountingPeriodResponse(BaseModel):
    id: UUID
    period_year: int
    period_month: int
    period_type: str = "monthly"
    gl_cutoff_date: date
    trial_balance_reviewer: str
    trial_balance_approved_at: datetime | None
    status: str
    audit_metadata: dict | None = None

    model_config = {"from_attributes": True}


class AccountingPeriodCloseRequest(BaseModel):
    audit_adjustments_completed: bool | None = None
    year_end_adjustments_completed: bool | None = None
    auditor_name: str | None = None
    auditor_firm: str | None = None
    sign_off_date: date | None = None


class AccountingSettingsResponse(BaseModel):
    accounting_fye_month: int = 12
    trial_balance_frequency: str = "monthly"
    audit_frequency: str = "annual"
    gl_cutoff_working_days: int = 3
    accounting_start_date: date | None = None


class AccountingSettingsUpdate(BaseModel):
    accounting_fye_month: int | None = Field(default=None, ge=1, le=12)
    trial_balance_frequency: str | None = None
    audit_frequency: str | None = None
    gl_cutoff_working_days: int | None = Field(default=None, ge=1, le=30)
    accounting_start_date: date | None = None


class GlCutoffReminderResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    display_name: str | None = None
    notify_7_days: bool
    notify_3_days: bool
    notify_1_day: bool
    notify_on_date: bool
    is_active: bool

    model_config = {"from_attributes": True}


class GlCutoffReminderCreate(BaseModel):
    email: str
    display_name: str | None = None
    notify_7_days: bool = True
    notify_3_days: bool = True
    notify_1_day: bool = True
    notify_on_date: bool = True
    is_active: bool = True


class GlCutoffReminderUpdate(BaseModel):
    email: str | None = None
    display_name: str | None = None
    notify_7_days: bool | None = None
    notify_3_days: bool | None = None
    notify_1_day: bool | None = None
    notify_on_date: bool | None = None
    is_active: bool | None = None


class AccountingCalendarSettings(BaseModel):
    gl_posting_cutoff_working_days: int = 3
    trial_balance_reviewer: str = "finfa.mmlogistix@bp0.work"


class DashboardCheckItem(BaseModel):
    section: str
    label: str
    complete: bool
    href: str
    detail: str | None = None


class DashboardResponse(BaseModel):
    checks: list[DashboardCheckItem]
    complete_count: int
    total_count: int


class GlPeriodOverridePostRequest(BaseModel):
    case_id: UUID
    override_reason: str = Field(min_length=3, max_length=2000)


class GlPeriodOverridePostResponse(BaseModel):
    case_id: str
    period_id: str
    message_id: str
    status: str


class CounterpartyResponse(BaseModel):
    id: UUID
    name: str
    code: str | None = None
    type: str
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    is_recurring: bool = False
    has_contract: bool = False
    contract_reference: str | None = None
    contract_start_date: date | None = None
    contract_expiry_date: date | None = None
    supplier_owner: str | None = None
    contract_warning_days: int = 30

    model_config = {"from_attributes": True}


class CounterpartyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    type: str = Field(
        default="vendor",
        pattern="^(customer|vendor|supplier|employee|staff|bank|other)$",
    )
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    is_recurring: bool = False
    has_contract: bool = False
    contract_reference: str | None = Field(default=None, max_length=255)
    contract_start_date: date | None = None
    contract_expiry_date: date | None = None
    supplier_owner: str | None = None
    contract_warning_days: int = Field(default=30, ge=0)


class CounterpartyUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    type: str | None = Field(
        default=None,
        pattern="^(customer|vendor|supplier|employee|staff|bank|other)$",
    )
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    is_recurring: bool | None = None
    has_contract: bool | None = None
    contract_reference: str | None = Field(default=None, max_length=255)
    contract_start_date: date | None = None
    contract_expiry_date: date | None = None
    supplier_owner: str | None = None
    contract_warning_days: int | None = Field(default=None, ge=0)


class PaymentTermResponse(BaseModel):
    id: UUID
    code: str
    label: str
    due_days: int
    discount_percent: Decimal | None = None
    discount_if_paid_within_days: int | None = None
    minimum_invoice_amount: Decimal | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class PaymentTermCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    label: str = Field(min_length=1, max_length=100)
    due_days: int = Field(ge=0)
    discount_percent: Decimal | None = None
    discount_if_paid_within_days: int | None = Field(default=None, ge=0)
    minimum_invoice_amount: Decimal | None = None


class PaymentTermUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=100)
    due_days: int | None = Field(default=None, ge=0)
    discount_percent: Decimal | None = None
    discount_if_paid_within_days: int | None = Field(default=None, ge=0)
    minimum_invoice_amount: Decimal | None = None
    is_active: bool | None = None


class CounterpartyAccountResponse(BaseModel):
    id: UUID
    counterparty_id: UUID
    counterparty_name: str | None = None
    account_code: str
    display_name: str
    role: str
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    payment_term_id: UUID | None = None
    payment_term_code: str | None = None
    credit_limit_amount: Decimal | None = None
    credit_limit_currency: str | None = None
    counterparty_gst_reg: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class CounterpartyAccountCreate(BaseModel):
    counterparty_id: UUID
    account_code: str = Field(min_length=1, max_length=50)
    display_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="bill_to", max_length=30)
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    payment_term_id: UUID | None = None
    credit_limit_amount: Decimal | None = None
    credit_limit_currency: str | None = Field(default="SGD", max_length=3)
    counterparty_gst_reg: str | None = Field(default=None, max_length=20)


class CounterpartyAccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=30)
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    payment_term_id: UUID | None = None
    credit_limit_amount: Decimal | None = None
    credit_limit_currency: str | None = Field(default=None, max_length=3)
    counterparty_gst_reg: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class TenantTaxCodeResponse(BaseModel):
    id: UUID
    code: str
    description: str
    rate: Decimal
    direction: str
    output_gl_account_code: str | None = None
    input_gl_account_code: str | None = None
    is_active: bool
    effective_from: date | None = None

    model_config = {"from_attributes": True}


class TenantTaxCodeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    description: str = Field(min_length=1, max_length=200)
    rate: Decimal = Field(ge=0, le=1)
    direction: str = Field(pattern="^(output|input|both)$")
    output_gl_account_code: str | None = Field(default=None, max_length=20)
    input_gl_account_code: str | None = Field(default=None, max_length=20)
    effective_from: date | None = None


class TenantTaxCodeUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=200)
    rate: Decimal | None = Field(default=None, ge=0, le=1)
    direction: str | None = Field(default=None, pattern="^(output|input|both)$")
    output_gl_account_code: str | None = Field(default=None, max_length=20)
    input_gl_account_code: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None
    effective_from: date | None = None
