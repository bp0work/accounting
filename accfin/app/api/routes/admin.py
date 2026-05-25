"""Client Admin API — tenant configuration (`admin.mmlogistix.bp0.work`)."""

from __future__ import annotations

import csv
import io
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session
from app.core.dependencies import require_client_admin
from app.core.exceptions import AppHTTPException
from app.models.accounting_period import AccountingPeriod
from app.models.agreements import DirectorExpenseAgreement, RentalAgreement
from app.models.expense import ExpensePolicy
from app.models.ledger import CoaAccount
from app.models.mail import MailGatewayConfig
from app.models.regulatory import RegulatoryDocument
from app.models.tenant import Tenant
from app.models.tenant_profile import TenantProfile
from app.models.travel import TravelRequest
from app.models.user import User
from app.models.rbac import Role
from app.schemas.auth import TokenData
from app.schemas.client_admin import (
    AccountingCalendarSettings,
    AccountingPeriodResponse,
    AdminUserResponse,
    AdminUserUpdate,
    CoaAccountCreate,
    CoaAccountResponse,
    CoaAccountUpdate,
    DashboardCheckItem,
    DashboardResponse,
    DirectorExpenseAgreementCreate,
    DirectorExpenseAgreementResponse,
    ExpensePolicyLimitsResponse,
    ExpensePolicyLimitsUpdate,
    MailConfigurationResponse,
    MailConfigurationUpdate,
    RegulatoryDocumentResponse,
    RentalAgreementCreate,
    RentalAgreementResponse,
    TenantProfileResponse,
    TenantProfileUpdate,
    TravelRequestAdminResponse,
    TravelRequestStatusUpdate,
)
from app.services.accounting_calendar import (
    add_working_days,
    ensure_period,
    gl_cutoff_working_days,
    month_end,
    utcnow,
)

router = APIRouter(tags=["Client Admin"])

TENANT_MMLOGISTIX = UUID("00000000-0000-0000-0000-000000000200")
ROLE_ADMIN_USERS = ("general_manager", "cfo", "finance_manager", "accounts_clerk")

POLICY_KEYS = {
    "meal_limit_per_day": "meal_daily_limit",
    "transport_limit_per_trip": "transport_trip_limit",
    "accommodation_limit_per_night": "accommodation_nightly_limit",
    "per_diem_rate": "per_diem_rate",
    "entertainment_limit_per_occasion": "entertainment_occasion_limit",
}


async def _tenant_id(user: TokenData, session: AsyncSession) -> UUID:
    result = await session.execute(select(User.tenant_id).where(User.id == user.user_id))
    tid = result.scalar_one_or_none()
    return tid or TENANT_MMLOGISTIX


def _mask_username(username: str) -> str:
    if len(username) <= 2:
        return "***"
    return username[:2] + "***"


# --- Dashboard ---


@router.get("/admin/dashboard", response_model=DashboardResponse)
async def admin_dashboard(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardResponse:
    tid = await _tenant_id(user, session)
    profile = await session.get(TenantProfile, tid)
    coa_count = await session.scalar(select(func.count()).select_from(CoaAccount).where(CoaAccount.is_active.is_(True)))
    mailbox_count = await session.scalar(
        select(func.count()).select_from(MailGatewayConfig).where(MailGatewayConfig.is_active.is_(True))
    )
    key_users = await session.scalar(
        select(func.count())
        .select_from(User)
        .join(Role, User.role_id == Role.id)
        .where(Role.name.in_(ROLE_ADMIN_USERS), User.status == "active")
    )
    policy_count = await session.scalar(
        select(func.count()).select_from(ExpensePolicy).where(ExpensePolicy.is_active.is_(True))
    )
    period_count = await session.scalar(
        select(func.count()).select_from(AccountingPeriod).where(AccountingPeriod.tenant_id == tid)
    )
    checks = [
        DashboardCheckItem(section="company", label="Company profile", complete=profile is not None and bool(profile.legal_name), href="/company"),
        DashboardCheckItem(section="coa", label="Chart of accounts", complete=(coa_count or 0) > 0, href="/chart-of-accounts"),
        DashboardCheckItem(section="mailboxes", label="Mailboxes configured", complete=(mailbox_count or 0) >= 9, href="/mailboxes"),
        DashboardCheckItem(section="users", label="Key role emails", complete=(key_users or 0) >= 3, href="/users"),
        DashboardCheckItem(section="policies", label="Expense policies", complete=(policy_count or 0) > 0, href="/policies"),
        DashboardCheckItem(section="calendar", label="Accounting periods", complete=(period_count or 0) > 0, href="/accounting-calendar"),
    ]
    complete = sum(1 for c in checks if c.complete)
    return DashboardResponse(checks=checks, complete_count=complete, total_count=len(checks))


# --- Tenants / company profile ---


@router.get("/tenants/{tenant_id}/profile", response_model=TenantProfileResponse)
async def get_tenant_profile(
    tenant_id: UUID,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TenantProfileResponse:
    row = await session.get(TenantProfile, tenant_id)
    if row is None:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Tenant not found")
        return TenantProfileResponse(tenant_id=tenant_id, legal_name=tenant.display_name)
    return TenantProfileResponse.model_validate(row)


@router.patch("/tenants/{tenant_id}/profile", response_model=TenantProfileResponse)
async def patch_tenant_profile(
    tenant_id: UUID,
    body: TenantProfileUpdate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TenantProfileResponse:
    row = await session.get(TenantProfile, tenant_id)
    if row is None:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Tenant not found")
        row = TenantProfile(tenant_id=tenant_id, legal_name=body.legal_name or tenant.display_name)
        session.add(row)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    await session.commit()
    await session.refresh(row)
    return TenantProfileResponse.model_validate(row)


# --- COA ---


@router.get("/coa", response_model=list[CoaAccountResponse])
async def list_coa(
    q: str | None = Query(None),
    active_only: bool = Query(True),
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[CoaAccountResponse]:
    stmt = select(CoaAccount).order_by(CoaAccount.account_code)
    if active_only:
        stmt = stmt.where(CoaAccount.is_active.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            CoaAccount.account_code.ilike(like) | CoaAccount.account_name.ilike(like)
        )
    result = await session.execute(stmt)
    return [CoaAccountResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/coa", response_model=CoaAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_coa(
    body: CoaAccountCreate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> CoaAccountResponse:
    parent_id = None
    if body.parent_code:
        pres = await session.execute(
            select(CoaAccount).where(CoaAccount.account_code == body.parent_code)
        )
        parent = pres.scalar_one_or_none()
        if parent is None:
            raise AppHTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_PARENT", "Parent account not found")
        parent_id = parent.id
    row = CoaAccount(
        account_code=body.account_code,
        account_name=body.account_name,
        account_type=body.account_type,
        parent_id=parent_id,
        description=body.description,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return CoaAccountResponse.model_validate(row)


@router.patch("/coa/{account_id}", response_model=CoaAccountResponse)
async def patch_coa(
    account_id: UUID,
    body: CoaAccountUpdate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> CoaAccountResponse:
    row = await session.get(CoaAccount, account_id)
    if row is None:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Account not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await session.commit()
    await session.refresh(row)
    return CoaAccountResponse.model_validate(row)


@router.post("/coa/import")
async def import_coa_csv(
    file: UploadFile = File(...),
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    required = {"account_code", "account_name", "account_type"}
    if not required.issubset({h.strip() for h in (reader.fieldnames or [])}):
        raise AppHTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_CSV", f"CSV must include {required}")
    created = 0
    for row in reader:
        code = (row.get("account_code") or "").strip()
        if not code:
            continue
        existing = await session.execute(select(CoaAccount).where(CoaAccount.account_code == code))
        if existing.scalar_one_or_none():
            continue
        parent_id = None
        pc = (row.get("parent_code") or "").strip()
        if pc:
            pres = await session.execute(select(CoaAccount).where(CoaAccount.account_code == pc))
            p = pres.scalar_one_or_none()
            if p:
                parent_id = p.id
        session.add(
            CoaAccount(
                account_code=code,
                account_name=(row.get("account_name") or "").strip(),
                account_type=(row.get("account_type") or "expense").strip(),
                parent_id=parent_id,
            )
        )
        created += 1
    await session.commit()
    return {"imported": created}


# --- Mail configuration ---


@router.get("/mail/configuration", response_model=list[MailConfigurationResponse])
async def list_mail_configuration(
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[MailConfigurationResponse]:
    result = await session.execute(
        select(MailGatewayConfig).order_by(MailGatewayConfig.email_address)
    )
    out = []
    for m in result.scalars().all():
        out.append(
            MailConfigurationResponse(
                id=m.id,
                email_address=m.email_address,
                display_name=m.display_name,
                role=m.role,
                mailbox_mode=m.mailbox_mode,
                escalation_manager_email=m.escalation_manager_email,
                is_active=m.is_active,
                username_masked=_mask_username(m.username),
                server_host=m.server_host,
            )
        )
    return out


@router.patch("/mail/configuration/{mailbox_id}", response_model=MailConfigurationResponse)
async def patch_mail_configuration(
    mailbox_id: UUID,
    body: MailConfigurationUpdate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> MailConfigurationResponse:
    m = await session.get(MailGatewayConfig, mailbox_id)
    if m is None:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Mailbox not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    await session.commit()
    await session.refresh(m)
    return MailConfigurationResponse(
        id=m.id,
        email_address=m.email_address,
        display_name=m.display_name,
        role=m.role,
        mailbox_mode=m.mailbox_mode,
        escalation_manager_email=m.escalation_manager_email,
        is_active=m.is_active,
        username_masked=_mask_username(m.username),
        server_host=m.server_host,
    )


# --- Users (role emails) ---


@router.get("/users", response_model=list[AdminUserResponse])
async def list_admin_users(
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[AdminUserResponse]:
    labels = {
        "general_manager": "CEO / Managing Director",
        "cfo": "CFO / Finance Director",
        "finance_manager": "Finance Manager",
        "accounts_clerk": "Accounts Manager",
    }
    result = await session.execute(
        select(User, Role)
        .join(Role, User.role_id == Role.id)
        .where(Role.name.in_(ROLE_ADMIN_USERS))
        .order_by(Role.name)
    )
    return [
        AdminUserResponse(
            id=u.id,
            role_label=labels.get(r.name, r.name),
            role_name=r.name,
            display_name=u.display_name,
            email=u.email,
            username=u.username,
        )
        for u, r in result.all()
    ]


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def patch_admin_user(
    user_id: UUID,
    body: AdminUserUpdate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> AdminUserResponse:
    result = await session.execute(
        select(User, Role).join(Role, User.role_id == Role.id).where(User.id == user_id)
    )
    row = result.one_or_none()
    if row is None:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "User not found")
    u, r = row
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(u, k, v)
    await session.commit()
    labels = {"general_manager": "CEO / Managing Director", "cfo": "CFO / Finance Director"}
    return AdminUserResponse(
        id=u.id,
        role_label=labels.get(r.name, r.name),
        role_name=r.name,
        display_name=u.display_name,
        email=u.email,
        username=u.username,
    )


# --- Expense policy limits (named policies) ---


async def _policy_by_name(session: AsyncSession, name: str) -> ExpensePolicy | None:
    res = await session.execute(select(ExpensePolicy).where(ExpensePolicy.name == name))
    return res.scalar_one_or_none()


@router.get("/expense-policies/limits", response_model=ExpensePolicyLimitsResponse)
async def get_expense_limits(
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> ExpensePolicyLimitsResponse:
    out = {}
    for field, pname in POLICY_KEYS.items():
        p = await _policy_by_name(session, pname)
        if p:
            out[field] = p.daily_limit or p.per_claim_limit
    return ExpensePolicyLimitsResponse(**out)


@router.patch("/expense-policies/limits", response_model=ExpensePolicyLimitsResponse)
async def patch_expense_limits(
    body: ExpensePolicyLimitsUpdate,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> ExpensePolicyLimitsResponse:
    for field, pname in POLICY_KEYS.items():
        val = getattr(body, field, None)
        if val is None:
            continue
        p = await _policy_by_name(session, pname)
        if p is None:
            p = ExpensePolicy(
                name=pname,
                display_name=pname.replace("_", " ").title(),
                daily_limit=val,
                effective_from=date.today(),
                created_by=user.user_id,
            )
            session.add(p)
        else:
            p.daily_limit = val
    await session.commit()
    return await get_expense_limits(_user=user, session=session)


# --- Travel requests ---


@router.get("/travel-requests", response_model=list[TravelRequestAdminResponse])
async def list_travel_requests(
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[TravelRequestAdminResponse]:
    result = await session.execute(
        select(TravelRequest, User.display_name)
        .join(User, TravelRequest.employee_id == User.id)
        .order_by(TravelRequest.created_at.desc())
    )
    return [
        TravelRequestAdminResponse(
            id=t.id,
            request_number=t.request_number,
            traveller_name=name or t.employee_email,
            employee_email=t.employee_email,
            destination=t.destination,
            travel_from=t.travel_from,
            travel_to=t.travel_to,
            purpose=t.purpose,
            status=t.status,
            created_at=t.created_at,
        )
        for t, name in result.all()
    ]


@router.patch("/travel-requests/{request_id}", response_model=TravelRequestAdminResponse)
async def patch_travel_request(
    request_id: UUID,
    body: TravelRequestStatusUpdate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TravelRequestAdminResponse:
    if body.status not in ("approved", "rejected", "submitted", "cancelled"):
        raise AppHTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_STATUS", "Invalid status")
    t = await session.get(TravelRequest, request_id)
    if t is None:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Travel request not found")
    t.status = body.status
    await session.commit()
    u = await session.get(User, t.employee_id)
    return TravelRequestAdminResponse(
        id=t.id,
        request_number=t.request_number,
        traveller_name=u.display_name if u else t.employee_email,
        employee_email=t.employee_email,
        destination=t.destination,
        travel_from=t.travel_from,
        travel_to=t.travel_to,
        purpose=t.purpose,
        status=t.status,
        created_at=t.created_at,
    )


# --- Agreements ---


@router.get("/agreements/rental", response_model=list[RentalAgreementResponse])
async def list_rental_agreements(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[RentalAgreementResponse]:
    tid = await _tenant_id(user, session)
    result = await session.execute(
        select(RentalAgreement).where(RentalAgreement.tenant_id == tid).order_by(RentalAgreement.effective_date.desc())
    )
    return [RentalAgreementResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/agreements/rental", response_model=RentalAgreementResponse, status_code=status.HTTP_201_CREATED)
async def create_rental_agreement(
    body: RentalAgreementCreate,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> RentalAgreementResponse:
    tid = await _tenant_id(user, session)
    row = RentalAgreement(tenant_id=tid, **body.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return RentalAgreementResponse.model_validate(row)


@router.get("/agreements/director-expense", response_model=list[DirectorExpenseAgreementResponse])
async def list_director_agreements(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[DirectorExpenseAgreementResponse]:
    tid = await _tenant_id(user, session)
    result = await session.execute(
        select(DirectorExpenseAgreement)
        .where(DirectorExpenseAgreement.tenant_id == tid)
        .order_by(DirectorExpenseAgreement.effective_date.desc())
    )
    return [DirectorExpenseAgreementResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/agreements/director-expense", response_model=DirectorExpenseAgreementResponse, status_code=status.HTTP_201_CREATED)
async def create_director_agreement(
    body: DirectorExpenseAgreementCreate,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> DirectorExpenseAgreementResponse:
    tid = await _tenant_id(user, session)
    row = DirectorExpenseAgreement(tenant_id=tid, **body.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return DirectorExpenseAgreementResponse.model_validate(row)


# --- Regulatory documents (metadata; upload stores path) ---


@router.get("/regulatory-documents", response_model=list[RegulatoryDocumentResponse])
async def list_regulatory_documents(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[RegulatoryDocumentResponse]:
    tid = await _tenant_id(user, session)
    result = await session.execute(
        select(RegulatoryDocument).where(RegulatoryDocument.tenant_id == tid).order_by(RegulatoryDocument.uploaded_at.desc())
    )
    return [
        RegulatoryDocumentResponse(
            id=d.id,
            name=d.name,
            filename=d.filename,
            file_size=d.file_size,
            content_type=d.content_type,
            uploaded_at=d.uploaded_at,
            download_url=f"/api/regulatory-documents/{d.id}/download",
        )
        for d in result.scalars().all()
    ]


@router.post("/regulatory-documents", response_model=RegulatoryDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_regulatory_document(
    name: str = Query(...),
    file: UploadFile = File(...),
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> RegulatoryDocumentResponse:
    tid = await _tenant_id(user, session)
    data = await file.read()
    filename = file.filename or "document.pdf"
    wasabi_path = f"transactions/regulatory/{filename}"
    row = RegulatoryDocument(
        tenant_id=tid,
        name=name,
        filename=filename,
        wasabi_path=wasabi_path,
        file_size=len(data),
        content_type=file.content_type or "application/pdf",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return RegulatoryDocumentResponse(
        id=row.id,
        name=row.name,
        filename=row.filename,
        file_size=row.file_size,
        content_type=row.content_type,
        uploaded_at=row.uploaded_at,
        download_url=f"/api/regulatory-documents/{row.id}/download",
    )


# --- Accounting periods ---


@router.get("/accounting-periods", response_model=list[AccountingPeriodResponse])
async def list_accounting_periods(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[AccountingPeriodResponse]:
    tid = await _tenant_id(user, session)
    result = await session.execute(
        select(AccountingPeriod)
        .where(AccountingPeriod.tenant_id == tid)
        .order_by(AccountingPeriod.period_year.desc(), AccountingPeriod.period_month.desc())
    )
    return [AccountingPeriodResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/accounting-periods/settings", response_model=AccountingCalendarSettings)
async def get_calendar_settings(
    session: AsyncSession = Depends(get_db_session),
    _user: TokenData = Depends(require_client_admin()),
) -> AccountingCalendarSettings:
    days = await gl_cutoff_working_days(session)
    return AccountingCalendarSettings(gl_posting_cutoff_working_days=days)


@router.post("/accounting-periods/generate", response_model=list[AccountingPeriodResponse])
async def generate_accounting_periods(
    months: int = Query(12, ge=1, le=24),
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[AccountingPeriodResponse]:
    tid = await _tenant_id(user, session)
    today = date.today()
    y, m = today.year, today.month
    reviewer = "finfa.mmlogistix@bp0.work"
    created = []
    for _ in range(months):
        p = await ensure_period(session, tenant_id=tid, year=y, month=m, trial_balance_reviewer=reviewer)
        created.append(p)
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    await session.commit()
    return [AccountingPeriodResponse.model_validate(p) for p in created]


@router.post("/accounting-periods/{period_id}/approve-trial-balance", response_model=AccountingPeriodResponse)
async def approve_trial_balance(
    period_id: UUID,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> AccountingPeriodResponse:
    if user.role not in ("financial_analyst", "client_admin"):
        raise AppHTTPException(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "finfa role required")
    period = await session.get(AccountingPeriod, period_id)
    if period is None:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Period not found")
    period.trial_balance_approved_at = utcnow()
    period.trial_balance_approved_by = user.user_id
    period.status = "review"
    await session.commit()
    await session.refresh(period)
    return AccountingPeriodResponse.model_validate(period)


@router.post("/accounting-periods/{period_id}/close", response_model=AccountingPeriodResponse)
async def close_accounting_period(
    period_id: UUID,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> AccountingPeriodResponse:
    if user.role not in ("finance_manager", "client_admin"):
        raise AppHTTPException(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Finance Manager role required")
    period = await session.get(AccountingPeriod, period_id)
    if period is None:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Period not found")
    if period.trial_balance_approved_at is None:
        raise AppHTTPException(status.HTTP_409_CONFLICT, "TB_NOT_APPROVED", "Trial balance must be approved first")
    period.gl_closed_at = utcnow()
    period.gl_closed_by = user.user_id
    period.status = "closed"
    await session.commit()
    await session.refresh(period)
    return AccountingPeriodResponse.model_validate(period)
