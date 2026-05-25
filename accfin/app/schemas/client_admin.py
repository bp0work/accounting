"""Schemas for Client Admin API."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class TenantProfileResponse(BaseModel):
    tenant_id: UUID
    legal_name: str
    trading_name: str | None = None
    uen: str | None = None
    gst_registration_number: str | None = None
    registered_address: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None


class TenantProfileUpdate(BaseModel):
    legal_name: str | None = None
    trading_name: str | None = None
    uen: str | None = None
    gst_registration_number: str | None = None
    registered_address: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None


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


class MailConfigurationResponse(BaseModel):
    id: UUID
    email_address: str
    display_name: str | None
    role: str | None
    mailbox_mode: str
    escalation_manager_email: str | None
    is_active: bool
    username_masked: str
    server_host: str

    model_config = {"from_attributes": True}


class MailConfigurationUpdate(BaseModel):
    display_name: str | None = None
    escalation_manager_email: str | None = None


class AdminUserResponse(BaseModel):
    id: UUID
    role_label: str
    role_name: str
    display_name: str
    email: str
    username: str


class AdminUserUpdate(BaseModel):
    email: str | None = None
    display_name: str | None = None


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
    name: str
    filename: str
    file_size: int
    content_type: str
    uploaded_at: datetime
    download_url: str | None = None

    model_config = {"from_attributes": True}


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
    gl_cutoff_date: date
    trial_balance_reviewer: str
    trial_balance_approved_at: datetime | None
    status: str

    model_config = {"from_attributes": True}


class AccountingCalendarSettings(BaseModel):
    gl_posting_cutoff_working_days: int = 3
    trial_balance_reviewer: str = "finfa.mmlogistix@bp0.work"


class DashboardCheckItem(BaseModel):
    section: str
    label: str
    complete: bool
    href: str


class DashboardResponse(BaseModel):
    checks: list[DashboardCheckItem]
    complete_count: int
    total_count: int
