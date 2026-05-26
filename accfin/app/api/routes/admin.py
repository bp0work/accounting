"""Client Admin API — tenant configuration (`admin.mmlogistix.bp0.work`)."""

from __future__ import annotations

import csv
import io
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session
from app.core.config import get_settings
from app.core.dependencies import (
    require_client_admin,
    require_finance_setup_access,
    require_gl_posting_override,
    require_period_reopen,
)
from app.core.exceptions import AppHTTPException
from app.models.accounting_period import AccountingPeriod
from app.models.gl_cutoff_reminder import GlCutoffReminder
from app.models.agreements import DirectorExpenseAgreement, RentalAgreement
from app.models.counterparty_master import PaymentTerm, TenantTaxCode
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
from app.constants.client_admin import (
    BOOTSTRAP_PASSWORD_HASH,
    REGULATORY_CATALOG,
    ROLE_ADMIN_NAMES,
    ROLE_ORDER,
    ROLE_PROVISION,
    TRAVEL_EXPENSE_POLICY_KEY,
    TRAVEL_EXPENSE_POLICY_LABEL,
)
from app.schemas.client_admin import (
    AccountingCalendarSettings,
    AccountingPeriodCloseRequest,
    AccountingPeriodResponse,
    AccountingSettingsResponse,
    AccountingSettingsUpdate,
    GlCutoffReminderCreate,
    GlCutoffReminderResponse,
    GlCutoffReminderUpdate,
    GlPeriodOverridePostRequest,
    GlPeriodOverridePostResponse,
    AdminUserResponse,
    AdminUserUpdate,
    CoaAccountCreate,
    CoaAccountResponse,
    CoaAccountUpdate,
    CoaImportResponse,
    CoaStatusResponse,
    DashboardCheckItem,
    DashboardResponse,
    DirectorExpenseAgreementCreate,
    DirectorExpenseAgreementResponse,
    ExpensePolicyLimitsResponse,
    ExpensePolicyLimitsUpdate,
    MailConfigurationResponse,
    MailConfigurationUpdate,
    RegulatoryCatalogItemResponse,
    RegulatoryDocumentResponse,
    RentalAgreementCreate,
    RentalAgreementResponse,
    TenantProfileResponse,
    TenantProfileUpdate,
    TravelPolicyDocumentResponse,
    TravelRequestAdminResponse,
    TravelRequestStatusUpdate,
)
from app.services.gl_period_override_service import GlPeriodOverrideService
from app.services.gl_period_reopen_service import GlPeriodReopenService
from app.services.regulatory_storage import (
    TRAVEL_EXPENSE_POLICY_PATH,
    RegulatoryStorageService,
)
from app.repositories.system_settings import SystemSettingsRepository
from app.services.accounting_calendar import (
    accounting_fye_month,
    audit_frequency,
    ensure_period,
    gl_cutoff_working_days,
    trial_balance_frequency,
    utcnow,
)

router = APIRouter(tags=["Client Admin"])

TENANT_MMLOGISTIX = UUID("00000000-0000-0000-0000-000000000200")
ROLE_LABELS = dict(ROLE_ORDER)

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


def _nonempty(value: str | None) -> bool:
    return bool(value and str(value).strip())


async def _regulatory_by_key(session: AsyncSession, tid: UUID) -> dict[str, RegulatoryDocument]:
    result = await session.execute(
        select(RegulatoryDocument).where(
            RegulatoryDocument.tenant_id == tid,
            RegulatoryDocument.document_key.isnot(None),
        )
    )
    return {d.document_key: d for d in result.scalars().all() if d.document_key}


async def _has_expense_limits(session: AsyncSession) -> bool:
    for pname in POLICY_KEYS.values():
        p = await _policy_by_name(session, pname)
        if p and (p.daily_limit is not None or p.per_claim_limit is not None):
            return True
    return False


def _period_year_month_add(year: int, month: int, offset: int) -> tuple[int, int]:
    total = (year * 12 + (month - 1)) + offset
    return total // 12, (total % 12) + 1


async def _calendar_complete(session: AsyncSession, tid: UUID) -> tuple[bool, str]:
    today = date.today()
    y, m = today.year, today.month
    missing: list[str] = []
    for offset in range(13):
        py, pm = _period_year_month_add(y, m, offset)
        exists = await session.scalar(
            select(func.count())
            .select_from(AccountingPeriod)
            .where(
                AccountingPeriod.tenant_id == tid,
                AccountingPeriod.period_year == py,
                AccountingPeriod.period_month == pm,
            )
        )
        if not exists:
            missing.append(f"{py}-{pm:02d}")
    if not missing:
        return True, "Current month and next 12 months generated"
    return False, f"Missing periods: {', '.join(missing[:3])}{'…' if len(missing) > 3 else ''}"


# --- Dashboard ---


@router.get("/admin/dashboard", response_model=DashboardResponse)
async def admin_dashboard(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardResponse:
    tid = await _tenant_id(user, session)
    finance_ui = get_settings().edge_public_base_url
    profile = await session.get(TenantProfile, tid)
    coa_count = await session.scalar(
        select(func.count()).select_from(CoaAccount).where(CoaAccount.is_active.is_(True))
    )
    coa_n = coa_count or 0
    mailboxes = (
        await session.execute(
            select(MailGatewayConfig).where(MailGatewayConfig.is_active.is_(True))
        )
    ).scalars().all()
    mail_unconfigured = [m.email_address for m in mailboxes if not _nonempty(m.display_name)]
    users_by_role: dict[str, User] = {}
    user_rows = await session.execute(
        select(User, Role)
        .join(Role, User.role_id == Role.id)
        .where(Role.name.in_(ROLE_ADMIN_NAMES), User.status == "active")
    )
    for u, r in user_rows.all():
        users_by_role[r.name] = u
    missing_roles = [label for role, label in ROLE_ORDER if role not in users_by_role or not _nonempty(users_by_role[role].email)]
    reg_map = await _regulatory_by_key(session, tid)
    travel_doc = reg_map.get(TRAVEL_EXPENSE_POLICY_KEY)
    reg_missing = [label for key, label, _ in REGULATORY_CATALOG if key not in reg_map]
    company_fields_ok = profile is not None and all(
        _nonempty(getattr(profile, f, None))
        for f in ("legal_name", "uen", "registered_address", "contact_email")
    )
    signature_ok = profile is not None and (
        _nonempty(profile.email_signature_html) or _nonempty(profile.email_signature_plain)
    )
    limits_ok = await _has_expense_limits(session)
    cal_ok, cal_detail = await _calendar_complete(session, tid)
    reminder_count = await session.scalar(
        select(func.count())
        .select_from(GlCutoffReminder)
        .where(GlCutoffReminder.tenant_id == tid, GlCutoffReminder.is_active.is_(True))
    )
    reminders_ok = (reminder_count or 0) > 0
    terms_count = await session.scalar(
        select(func.count()).select_from(PaymentTerm).where(PaymentTerm.is_active.is_(True))
    )
    tax_count = await session.scalar(
        select(func.count()).select_from(TenantTaxCode).where(TenantTaxCode.is_active.is_(True))
    )
    terms_ok = (terms_count or 0) > 0
    tax_ok = (tax_count or 0) > 0

    checks = [
        DashboardCheckItem(
            section="company",
            label="Company profile",
            complete=company_fields_ok,
            href="/company",
            detail=None if company_fields_ok else "Legal name, UEN, address, and contact email required",
        ),
        DashboardCheckItem(
            section="signature",
            label="Email signature",
            complete=signature_ok,
            href="/company",
            detail=None if signature_ok else "HTML or plain-text signature not set",
        ),
        DashboardCheckItem(
            section="coa",
            label="Chart of accounts",
            complete=coa_n > 0,
            href="/chart-of-accounts",
            detail=f"{coa_n} active account(s)" if coa_n else "No accounts — import CSV",
        ),
        DashboardCheckItem(
            section="payment_terms",
            label="Payment terms",
            complete=terms_ok,
            href=f"{finance_ui}/counterparty-accounts",
            detail=f"{terms_count or 0} active term(s)" if terms_ok else "Configure payment terms catalog",
        ),
        DashboardCheckItem(
            section="tax_codes",
            label="GST / tax codes",
            complete=tax_ok,
            href=f"{finance_ui}/counterparty-accounts",
            detail=f"{tax_count or 0} active tax code(s)" if tax_ok else "Map tax codes to GL accounts",
        ),
        DashboardCheckItem(
            section="mailboxes",
            label="Mailboxes",
            complete=len(mail_unconfigured) == 0 and len(mailboxes) > 0,
            href="/mailboxes",
            detail="All mailboxes have display names"
            if not mail_unconfigured
            else f"Missing display name: {', '.join(mail_unconfigured[:2])}",
        ),
        DashboardCheckItem(
            section="users",
            label="Key role emails",
            complete=len(missing_roles) == 0,
            href="/users",
            detail="CEO, CFO, Finance Manager, Accounts Manager configured"
            if not missing_roles
            else f"Missing or incomplete: {', '.join(missing_roles)}",
        ),
        DashboardCheckItem(
            section="travel_policy",
            label="Travel & Entertainment policy (PDF)",
            complete=travel_doc is not None,
            href="/policies",
            detail=travel_doc.filename if travel_doc else "Upload policy PDF on Policies page",
        ),
        DashboardCheckItem(
            section="expense_limits",
            label="Expense limits",
            complete=limits_ok,
            href="/policies",
            detail=None if limits_ok else "Set at least one expense limit",
        ),
        DashboardCheckItem(
            section="regulatory",
            label="Regulatory documents",
            complete=len(reg_missing) == 0,
            href="/policies",
            detail="All five documents uploaded"
            if not reg_missing
            else f"Missing: {', '.join(reg_missing)}",
        ),
        DashboardCheckItem(
            section="calendar",
            label="Accounting calendar",
            complete=cal_ok,
            href=f"{finance_ui}/accounting-calendar",
            detail=cal_detail,
        ),
        DashboardCheckItem(
            section="gl_reminders",
            label="GL reminder recipients",
            complete=reminders_ok,
            href=f"{finance_ui}/accounting-calendar",
            detail=f"{reminder_count or 0} active recipient(s)"
            if reminders_ok
            else "Add at least one active reminder recipient",
        ),
    ]
    complete = sum(1 for c in checks if c.complete)
    return DashboardResponse(checks=checks, complete_count=complete, total_count=len(checks))


# --- Tenants / company profile ---


async def _require_tenant_access(
    user: TokenData, session: AsyncSession, tenant_id: UUID
) -> UUID:
    tid = await _tenant_id(user, session)
    if tenant_id != tid:
        raise AppHTTPException(
            status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Tenant profile access denied"
        )
    return tid


async def _load_tenant_profile(
    session: AsyncSession, tenant_id: UUID
) -> TenantProfileResponse:
    row = await session.get(TenantProfile, tenant_id)
    if row is None:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Tenant not found")
        return TenantProfileResponse(tenant_id=tenant_id, legal_name=tenant.display_name)
    return TenantProfileResponse.model_validate(row)


async def _save_tenant_profile(
    session: AsyncSession, tenant_id: UUID, body: TenantProfileUpdate
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


@router.get("/admin/company-profile", response_model=TenantProfileResponse)
async def get_company_profile(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TenantProfileResponse:
    """Company profile for the authenticated client-admin user's tenant."""
    tid = await _tenant_id(user, session)
    return await _load_tenant_profile(session, tid)


@router.patch("/admin/company-profile", response_model=TenantProfileResponse)
async def patch_company_profile(
    body: TenantProfileUpdate,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TenantProfileResponse:
    tid = await _tenant_id(user, session)
    return await _save_tenant_profile(session, tid, body)


@router.get("/tenants/{tenant_id}/profile", response_model=TenantProfileResponse)
async def get_tenant_profile(
    tenant_id: UUID,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TenantProfileResponse:
    await _require_tenant_access(user, session, tenant_id)
    return await _load_tenant_profile(session, tenant_id)


@router.patch("/tenants/{tenant_id}/profile", response_model=TenantProfileResponse)
async def patch_tenant_profile(
    tenant_id: UUID,
    body: TenantProfileUpdate,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TenantProfileResponse:
    await _require_tenant_access(user, session, tenant_id)
    return await _save_tenant_profile(session, tenant_id, body)


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


@router.get("/coa/status", response_model=CoaStatusResponse)
async def coa_status(
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> CoaStatusResponse:
    count = await session.scalar(
        select(func.count()).select_from(CoaAccount).where(CoaAccount.is_active.is_(True))
    )
    n = count or 0
    return CoaStatusResponse(account_count=n, empty=n == 0)


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


_VALID_COA_TYPES = frozenset({"asset", "liability", "equity", "revenue", "expense"})


async def _resolve_parent_id(session: AsyncSession, parent_code: str) -> UUID | None:
    if not parent_code:
        return None
    pres = await session.execute(select(CoaAccount).where(CoaAccount.account_code == parent_code))
    parent = pres.scalar_one_or_none()
    return parent.id if parent else None


@router.post("/coa/import", response_model=CoaImportResponse)
async def import_coa_csv(
    file: UploadFile = File(...),
    replace_all: bool = Query(
        False,
        description="Deactivate all existing accounts, then load CSV (tenant chart replaces demo seed)",
    ),
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> CoaImportResponse:
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    required = {"account_code", "account_name", "account_type"}
    if not required.issubset({(h or "").strip() for h in (reader.fieldnames or [])}):
        raise AppHTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_CSV", f"CSV must include {required}")

    if replace_all:
        await session.execute(update(CoaAccount).values(is_active=False))

    created = updated = skipped = 0
    rows = list(reader)
    if not rows:
        raise AppHTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_CSV", "CSV has no data rows")

    for row in rows:
        code = (row.get("account_code") or "").strip()
        if not code:
            skipped += 1
            continue
        name = (row.get("account_name") or "").strip()
        if not name:
            skipped += 1
            continue
        acct_type = (row.get("account_type") or "expense").strip().lower()
        if acct_type not in _VALID_COA_TYPES:
            skipped += 1
            continue

        parent_id = await _resolve_parent_id(session, (row.get("parent_code") or "").strip())
        existing = (
            await session.execute(select(CoaAccount).where(CoaAccount.account_code == code))
        ).scalar_one_or_none()

        if existing:
            existing.account_name = name
            existing.account_type = acct_type
            existing.parent_id = parent_id
            existing.is_active = True
            updated += 1
        else:
            session.add(
                CoaAccount(
                    account_code=code,
                    account_name=name,
                    account_type=acct_type,
                    parent_id=parent_id,
                    is_active=True,
                )
            )
            created += 1

    await session.commit()

    active_count = await session.scalar(
        select(func.count()).select_from(CoaAccount).where(CoaAccount.is_active.is_(True))
    )
    return CoaImportResponse(
        created=created,
        updated=updated,
        skipped=skipped,
        active_count=active_count or 0,
    )


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
    result = await session.execute(
        select(User, Role)
        .join(Role, User.role_id == Role.id)
        .where(Role.name.in_(ROLE_ADMIN_NAMES), User.status == "active")
    )
    by_role = {r.name: u for u, r in result.all()}
    out: list[AdminUserResponse] = []
    for role_name, role_label in ROLE_ORDER:
        u = by_role.get(role_name)
        if u:
            out.append(
                AdminUserResponse(
                    id=u.id,
                    role_label=role_label,
                    role_name=role_name,
                    display_name=u.display_name,
                    email=u.email,
                    username=u.username,
                    configured=_nonempty(u.email),
                )
            )
        else:
            out.append(
                AdminUserResponse(
                    role_label=role_label,
                    role_name=role_name,
                    configured=False,
                )
            )
    return out


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
    return AdminUserResponse(
        id=u.id,
        role_label=ROLE_LABELS.get(r.name, r.name),
        role_name=r.name,
        display_name=u.display_name,
        email=u.email,
        username=u.username,
        configured=_nonempty(u.email),
    )


def _admin_user_response(u: User, role_name: str) -> AdminUserResponse:
    return AdminUserResponse(
        id=u.id,
        role_label=ROLE_LABELS.get(role_name, role_name),
        role_name=role_name,
        display_name=u.display_name,
        email=u.email,
        username=u.username,
        configured=_nonempty(u.email),
    )


@router.put("/users/by-role/{role_name}", response_model=AdminUserResponse)
async def upsert_admin_user_by_role(
    role_name: str,
    body: AdminUserUpdate,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> AdminUserResponse:
    if role_name not in ROLE_ADMIN_NAMES:
        raise AppHTTPException(
            status.HTTP_404_NOT_FOUND, "NOT_FOUND", f"Unknown role: {role_name}"
        )
    email = (body.email or "").strip()
    display_name = (body.display_name or "").strip()
    if not email or not display_name:
        raise AppHTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "display_name and email are required",
        )
    tid = await _tenant_id(user, session)
    role_row = await session.execute(select(Role).where(Role.name == role_name))
    role = role_row.scalar_one_or_none()
    if role is None:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Role not found")

    existing = await session.execute(
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(Role.name == role_name, User.status == "active")
    )
    u = existing.scalar_one_or_none()
    if u is None:
        username, user_id_str = ROLE_PROVISION[role_name]
        u = await session.get(User, UUID(user_id_str))
        if u is None:
            u = User(
                id=UUID(user_id_str),
                username=username,
                display_name=display_name,
                email=email,
                password_hash=BOOTSTRAP_PASSWORD_HASH,
                role_id=role.id,
                tenant_id=tid,
                status="active",
                two_factor_enabled=False,
            )
            session.add(u)
        else:
            u.display_name = display_name
            u.email = email
            u.role_id = role.id
            u.tenant_id = tid
            u.status = "active"
    else:
        u.display_name = display_name
        u.email = email
        if u.tenant_id is None:
            u.tenant_id = tid

    await session.commit()
    await session.refresh(u)
    return _admin_user_response(u, role_name)


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


def _travel_policy_response(doc: RegulatoryDocument | None) -> TravelPolicyDocumentResponse:
    if doc is None:
        return TravelPolicyDocumentResponse(uploaded=False)
    return TravelPolicyDocumentResponse(
        uploaded=True,
        filename=doc.filename,
        file_size=doc.file_size,
        uploaded_at=doc.uploaded_at,
        download_url=f"/api/expense-policies/document/download",
    )


@router.get("/expense-policies/document", response_model=TravelPolicyDocumentResponse)
async def get_travel_policy_document(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TravelPolicyDocumentResponse:
    tid = await _tenant_id(user, session)
    reg_map = await _regulatory_by_key(session, tid)
    return _travel_policy_response(reg_map.get(TRAVEL_EXPENSE_POLICY_KEY))


@router.post("/expense-policies/document", response_model=TravelPolicyDocumentResponse)
async def upload_travel_policy_document(
    file: UploadFile = File(...),
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TravelPolicyDocumentResponse:
    tid = await _tenant_id(user, session)
    data = await file.read()
    if not data:
        raise AppHTTPException(status.HTTP_400_BAD_REQUEST, "EMPTY_FILE", "PDF file is required")
    filename = file.filename or "travel-expense-policy.pdf"
    storage = RegulatoryStorageService()
    await storage.upload_bytes(
        key=TRAVEL_EXPENSE_POLICY_PATH,
        body=data,
        content_type=file.content_type or "application/pdf",
    )
    doc = await _upsert_regulatory_document(
        session,
        tenant_id=tid,
        document_key=TRAVEL_EXPENSE_POLICY_KEY,
        label=TRAVEL_EXPENSE_POLICY_LABEL,
        wasabi_path=TRAVEL_EXPENSE_POLICY_PATH,
        filename=filename,
        data=data,
        content_type=file.content_type or "application/pdf",
    )
    await session.commit()
    await session.refresh(doc)
    return _travel_policy_response(doc)


@router.get("/expense-policies/document/download")
async def download_travel_policy_document(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    tid = await _tenant_id(user, session)
    reg_map = await _regulatory_by_key(session, tid)
    doc = reg_map.get(TRAVEL_EXPENSE_POLICY_KEY)
    if doc is None:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Policy document not uploaded")
    storage = RegulatoryStorageService()
    return await storage.download_response(key=doc.wasabi_path, filename=doc.filename)


# --- Travel requests (API retained; UI uses email workflow) ---


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
    user: TokenData = Depends(require_finance_setup_access()),
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
    user: TokenData = Depends(require_finance_setup_access()),
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
    user: TokenData = Depends(require_finance_setup_access()),
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
    user: TokenData = Depends(require_finance_setup_access()),
    session: AsyncSession = Depends(get_db_session),
) -> DirectorExpenseAgreementResponse:
    tid = await _tenant_id(user, session)
    row = DirectorExpenseAgreement(tenant_id=tid, **body.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return DirectorExpenseAgreementResponse.model_validate(row)


# --- Regulatory documents ---


async def _upsert_regulatory_document(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    document_key: str,
    label: str,
    wasabi_path: str,
    filename: str,
    data: bytes,
    content_type: str,
) -> RegulatoryDocument:
    result = await session.execute(
        select(RegulatoryDocument).where(
            RegulatoryDocument.tenant_id == tenant_id,
            RegulatoryDocument.document_key == document_key,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = RegulatoryDocument(
            tenant_id=tenant_id,
            document_key=document_key,
            name=label,
            filename=filename,
            wasabi_path=wasabi_path,
            file_size=len(data),
            content_type=content_type,
        )
        session.add(row)
    else:
        row.name = label
        row.filename = filename
        row.wasabi_path = wasabi_path
        row.file_size = len(data)
        row.content_type = content_type
        row.uploaded_at = utcnow()
    await session.flush()
    return row


@router.get("/regulatory-documents/catalog", response_model=list[RegulatoryCatalogItemResponse])
async def regulatory_catalog(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[RegulatoryCatalogItemResponse]:
    tid = await _tenant_id(user, session)
    reg_map = await _regulatory_by_key(session, tid)
    out: list[RegulatoryCatalogItemResponse] = []
    for key, label, _path in REGULATORY_CATALOG:
        doc = reg_map.get(key)
        if doc:
            out.append(
                RegulatoryCatalogItemResponse(
                    document_key=key,
                    label=label,
                    uploaded=True,
                    id=doc.id,
                    filename=doc.filename,
                    file_size=doc.file_size,
                    uploaded_at=doc.uploaded_at,
                    download_url=f"/api/regulatory-documents/{doc.id}/download",
                )
            )
        else:
            out.append(RegulatoryCatalogItemResponse(document_key=key, label=label, uploaded=False))
    return out


@router.get("/regulatory-documents", response_model=list[RegulatoryDocumentResponse])
async def list_regulatory_documents(
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[RegulatoryDocumentResponse]:
    tid = await _tenant_id(user, session)
    result = await session.execute(
        select(RegulatoryDocument)
        .where(RegulatoryDocument.tenant_id == tid)
        .order_by(RegulatoryDocument.uploaded_at.desc())
    )
    return [
        RegulatoryDocumentResponse(
            id=d.id,
            document_key=d.document_key,
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
    document_key: str = Query(...),
    file: UploadFile = File(...),
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> RegulatoryDocumentResponse:
    catalog = {k: (label, path) for k, label, path in REGULATORY_CATALOG}
    if document_key not in catalog:
        raise AppHTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_KEY", "Unknown regulatory document key")
    label, wasabi_path = catalog[document_key]
    tid = await _tenant_id(user, session)
    data = await file.read()
    if not data:
        raise AppHTTPException(status.HTTP_400_BAD_REQUEST, "EMPTY_FILE", "PDF file is required")
    filename = file.filename or wasabi_path.rsplit("/", 1)[-1]
    storage = RegulatoryStorageService()
    await storage.upload_bytes(
        key=wasabi_path,
        body=data,
        content_type=file.content_type or "application/pdf",
    )
    row = await _upsert_regulatory_document(
        session,
        tenant_id=tid,
        document_key=document_key,
        label=label,
        wasabi_path=wasabi_path,
        filename=filename,
        data=data,
        content_type=file.content_type or "application/pdf",
    )
    await session.commit()
    await session.refresh(row)
    return RegulatoryDocumentResponse(
        id=row.id,
        document_key=row.document_key,
        name=row.name,
        filename=row.filename,
        file_size=row.file_size,
        content_type=row.content_type,
        uploaded_at=row.uploaded_at,
        download_url=f"/api/regulatory-documents/{row.id}/download",
    )


@router.get("/regulatory-documents/{document_id}/download")
async def download_regulatory_document(
    document_id: UUID,
    user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    tid = await _tenant_id(user, session)
    doc = await session.get(RegulatoryDocument, document_id)
    if doc is None or doc.tenant_id != tid:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Document not found")
    storage = RegulatoryStorageService()
    return await storage.download_response(key=doc.wasabi_path, filename=doc.filename)


# --- Accounting settings & GL cutoff reminders ---


@router.get("/admin/accounting-settings", response_model=AccountingSettingsResponse)
async def get_accounting_settings(
    session: AsyncSession = Depends(get_db_session),
    _user: TokenData = Depends(require_finance_setup_access()),
) -> AccountingSettingsResponse:
    return AccountingSettingsResponse(
        accounting_fye_month=await accounting_fye_month(session),
        trial_balance_frequency=await trial_balance_frequency(session),
        audit_frequency=await audit_frequency(session),
        gl_cutoff_working_days=await gl_cutoff_working_days(session),
    )


@router.patch("/admin/accounting-settings", response_model=AccountingSettingsResponse)
async def patch_accounting_settings(
    body: AccountingSettingsUpdate,
    session: AsyncSession = Depends(get_db_session),
    _user: TokenData = Depends(require_finance_setup_access()),
) -> AccountingSettingsResponse:
    repo = SystemSettingsRepository(session)
    entries: dict[str, tuple[str, str, str]] = {}
    if body.accounting_fye_month is not None:
        entries["accounting_fye_month"] = (str(body.accounting_fye_month), "integer", "accounting")
    if body.trial_balance_frequency is not None:
        if body.trial_balance_frequency not in ("monthly", "weekly"):
            raise AppHTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_VALUE", "trial_balance_frequency")
        entries["trial_balance_frequency"] = (body.trial_balance_frequency, "string", "accounting")
    if body.audit_frequency is not None:
        if body.audit_frequency not in ("annual", "semi_annual", "quarterly"):
            raise AppHTTPException(status.HTTP_400_BAD_REQUEST, "INVALID_VALUE", "audit_frequency")
        entries["audit_frequency"] = (body.audit_frequency, "string", "accounting")
    if body.gl_cutoff_working_days is not None:
        entries["gl_cutoff_working_days"] = (str(body.gl_cutoff_working_days), "integer", "accounting")
        entries["gl_posting_cutoff_working_days"] = (
            str(body.gl_cutoff_working_days),
            "integer",
            "accounting",
        )
    if entries:
        await repo.set_many(entries)
    return AccountingSettingsResponse(
        accounting_fye_month=await accounting_fye_month(session),
        trial_balance_frequency=await trial_balance_frequency(session),
        audit_frequency=await audit_frequency(session),
        gl_cutoff_working_days=await gl_cutoff_working_days(session),
    )


@router.get("/admin/gl-cutoff-reminders", response_model=list[GlCutoffReminderResponse])
async def list_gl_cutoff_reminders(
    user: TokenData = Depends(require_finance_setup_access()),
    session: AsyncSession = Depends(get_db_session),
) -> list[GlCutoffReminderResponse]:
    tid = await _tenant_id(user, session)
    result = await session.execute(
        select(GlCutoffReminder)
        .where(GlCutoffReminder.tenant_id == tid)
        .order_by(GlCutoffReminder.email)
    )
    return [GlCutoffReminderResponse.model_validate(r) for r in result.scalars().all()]


@router.post(
    "/admin/gl-cutoff-reminders",
    response_model=GlCutoffReminderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_gl_cutoff_reminder(
    body: GlCutoffReminderCreate,
    user: TokenData = Depends(require_finance_setup_access()),
    session: AsyncSession = Depends(get_db_session),
) -> GlCutoffReminderResponse:
    tid = await _tenant_id(user, session)
    row = GlCutoffReminder(tenant_id=tid, **body.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return GlCutoffReminderResponse.model_validate(row)


@router.patch("/admin/gl-cutoff-reminders/{reminder_id}", response_model=GlCutoffReminderResponse)
async def patch_gl_cutoff_reminder(
    reminder_id: UUID,
    body: GlCutoffReminderUpdate,
    user: TokenData = Depends(require_finance_setup_access()),
    session: AsyncSession = Depends(get_db_session),
) -> GlCutoffReminderResponse:
    tid = await _tenant_id(user, session)
    row = await session.get(GlCutoffReminder, reminder_id)
    if row is None or row.tenant_id != tid:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Reminder not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await session.commit()
    await session.refresh(row)
    return GlCutoffReminderResponse.model_validate(row)


@router.delete("/admin/gl-cutoff-reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_gl_cutoff_reminder(
    reminder_id: UUID,
    user: TokenData = Depends(require_finance_setup_access()),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    tid = await _tenant_id(user, session)
    row = await session.get(GlCutoffReminder, reminder_id)
    if row is None or row.tenant_id != tid:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Reminder not found")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/accounting-periods", response_model=list[AccountingPeriodResponse])
async def list_accounting_periods(
    user: TokenData = Depends(require_finance_setup_access()),
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
    months: int = Query(13, ge=1, le=24),
    user: TokenData = Depends(require_finance_setup_access()),
    session: AsyncSession = Depends(get_db_session),
) -> list[AccountingPeriodResponse]:
    """Create periods for the current month and the next ``months - 1`` months (default 13)."""
    tid = await _tenant_id(user, session)
    today = date.today()
    y, m = today.year, today.month
    reviewer = "finfa.mmlogistix@bp0.work"
    fye = await accounting_fye_month(session)
    freq = await audit_frequency(session)
    days = await gl_cutoff_working_days(session)
    created = []
    for offset in range(months):
        py, pm = _period_year_month_add(y, m, offset)
        p = await ensure_period(
            session,
            tenant_id=tid,
            year=py,
            month=pm,
            trial_balance_reviewer=reviewer,
            fye_month=fye,
            audit_freq=freq,
            cutoff_days=days,
        )
        created.append(p)
    await session.commit()
    return [AccountingPeriodResponse.model_validate(p) for p in created]


@router.post(
    "/accounting-periods/{period_id}/override-post",
    response_model=GlPeriodOverridePostResponse,
)
async def override_post_closed_period(
    period_id: UUID,
    body: GlPeriodOverridePostRequest,
    user: TokenData = Depends(require_gl_posting_override()),
    session: AsyncSession = Depends(get_db_session),
) -> GlPeriodOverridePostResponse:
    result = await GlPeriodOverrideService(session).override_and_requeue(
        period_id=period_id,
        case_id=body.case_id,
        override_reason=body.override_reason,
        user=user,
    )
    return GlPeriodOverridePostResponse(**result)


@router.post("/accounting-periods/{period_id}/approve-trial-balance", response_model=AccountingPeriodResponse)
async def approve_trial_balance(
    period_id: UUID,
    user: TokenData = Depends(require_finance_setup_access()),
    session: AsyncSession = Depends(get_db_session),
) -> AccountingPeriodResponse:
    if user.role not in ("financial_analyst", "client_admin", "finance_manager", "cfo"):
        raise AppHTTPException(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Finance role required")
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
    body: AccountingPeriodCloseRequest | None = None,
    user: TokenData = Depends(require_finance_setup_access()),
    session: AsyncSession = Depends(get_db_session),
) -> AccountingPeriodResponse:
    if user.role not in ("finance_manager", "client_admin", "cfo"):
        raise AppHTTPException(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Finance Manager role required")
    period = await session.get(AccountingPeriod, period_id)
    if period is None:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Period not found")
    if period.trial_balance_approved_at is None:
        raise AppHTTPException(status.HTTP_409_CONFLICT, "TB_NOT_APPROVED", "Trial balance must be approved first")
    req = body or AccountingPeriodCloseRequest()
    meta = dict(period.audit_metadata or {})
    if period.period_type == "audit":
        if not req.audit_adjustments_completed:
            raise AppHTTPException(
                status.HTTP_409_CONFLICT,
                "AUDIT_NOT_COMPLETE",
                "Audit adjustments must be completed before GL close",
            )
        meta["audit_adjustments_completed"] = True
    if period.period_type == "year_end":
        if not req.year_end_adjustments_completed:
            raise AppHTTPException(
                status.HTTP_409_CONFLICT,
                "YEAR_END_NOT_COMPLETE",
                "Year-end adjustments must be completed before GL close",
            )
        meta["year_end_adjustments_completed"] = True
    if req.auditor_name:
        meta["auditor_name"] = req.auditor_name
    if req.auditor_firm:
        meta["auditor_firm"] = req.auditor_firm
    if req.sign_off_date:
        meta["sign_off_date"] = req.sign_off_date.isoformat()
    period.audit_metadata = meta or period.audit_metadata
    period.gl_closed_at = utcnow()
    period.gl_closed_by = user.user_id
    period.status = "closed"
    await session.commit()
    await session.refresh(period)
    return AccountingPeriodResponse.model_validate(period)


@router.post("/accounting-periods/{period_id}/reopen", response_model=AccountingPeriodResponse)
async def reopen_accounting_period(
    period_id: UUID,
    user: TokenData = Depends(require_period_reopen()),
    session: AsyncSession = Depends(get_db_session),
) -> AccountingPeriodResponse:
    tid = await _tenant_id(user, session)
    existing = await session.get(AccountingPeriod, period_id)
    if existing is None or existing.tenant_id != tid:
        raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Period not found")
    period = await GlPeriodReopenService(session).reopen(period_id=period_id, user=user)
    return AccountingPeriodResponse.model_validate(period)
