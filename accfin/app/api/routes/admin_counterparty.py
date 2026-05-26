"""Client Admin — counterparty master, subaccounts, payment terms, tax codes (`05` §4.16d.4)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.core.dependencies import require_client_admin
from app.core.exceptions import AppHTTPException
from app.models.case import Counterparty
from app.models.counterparty_master import CounterpartyAccount, PaymentTerm, TenantTaxCode
from app.models.ledger import CoaAccount
from app.schemas.auth import TokenData
from app.schemas.client_admin import (
    CounterpartyAccountCreate,
    CounterpartyAccountResponse,
    CounterpartyAccountUpdate,
    CounterpartyCreate,
    CounterpartyResponse,
    CounterpartyUpdate,
    PaymentTermCreate,
    PaymentTermResponse,
    PaymentTermUpdate,
    TenantTaxCodeCreate,
    TenantTaxCodeResponse,
    TenantTaxCodeUpdate,
)
from app.services.counterparty_intake import has_open_balance_for_subaccount

router = APIRouter(tags=["Client Admin"])


def _account_response(row: CounterpartyAccount, cp_name: str | None = None) -> CounterpartyAccountResponse:
    term_code = row.payment_term.code if row.payment_term else None
    return CounterpartyAccountResponse(
        id=row.id,
        counterparty_id=row.counterparty_id,
        counterparty_name=cp_name,
        account_code=row.account_code,
        display_name=row.display_name,
        role=row.role,
        contact_email=row.contact_email,
        contact_phone=row.contact_phone,
        address=row.address,
        payment_term_id=row.payment_term_id,
        payment_term_code=term_code,
        credit_limit_amount=row.credit_limit_amount,
        credit_limit_currency=row.credit_limit_currency,
        counterparty_gst_reg=row.counterparty_gst_reg,
        is_active=row.is_active,
    )


async def _validate_tax_gl(session: AsyncSession, code: str | None) -> None:
    if not code:
        return
    exists = await session.scalar(
        select(func.count())
        .select_from(CoaAccount)
        .where(CoaAccount.account_code == code, CoaAccount.is_active.is_(True))
    )
    if not exists:
        raise AppHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="COA_ACCOUNT_NOT_FOUND",
            message=f"GL account code '{code}' not found in active chart of accounts",
        )


def _validate_tax_direction(
    direction: str,
    output_gl: str | None,
    input_gl: str | None,
) -> None:
    if direction == "output" and not output_gl:
        raise AppHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message="output_gl_account_code required for output direction",
        )
    if direction == "input" and not input_gl:
        raise AppHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message="input_gl_account_code required for input direction",
        )
    if direction == "both" and not (output_gl or input_gl):
        raise AppHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message="At least one GL account code required for both direction",
        )


# --- Counterparties ---


@router.get("/counterparties", response_model=list[CounterpartyResponse])
async def list_counterparties(
    type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[CounterpartyResponse]:
    stmt = select(Counterparty).order_by(Counterparty.name)
    if type:
        stmt = stmt.where(Counterparty.type == type)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Counterparty.name.ilike(like), Counterparty.code.ilike(like))
        )
    result = await session.execute(stmt.limit(200))
    return [CounterpartyResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/counterparties", response_model=CounterpartyResponse, status_code=status.HTTP_201_CREATED)
async def create_counterparty(
    body: CounterpartyCreate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> CounterpartyResponse:
    if body.code:
        dup = await session.scalar(
            select(func.count()).select_from(Counterparty).where(Counterparty.code == body.code)
        )
        if dup:
            raise AppHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="DUPLICATE_COUNTERPARTY_CODE",
                message="Counterparty code already exists",
            )
    row = Counterparty(**body.model_dump())
    session.add(row)
    await session.flush()
    return CounterpartyResponse.model_validate(row)


@router.patch("/counterparties/{counterparty_id}", response_model=CounterpartyResponse)
async def patch_counterparty(
    counterparty_id: UUID,
    body: CounterpartyUpdate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> CounterpartyResponse:
    row = await session.get(Counterparty, counterparty_id)
    if row is None:
        raise AppHTTPException(status_code=404, code="NOT_FOUND", message="Counterparty not found")
    data = body.model_dump(exclude_unset=True)
    if "code" in data and data["code"]:
        dup = await session.scalar(
            select(func.count())
            .select_from(Counterparty)
            .where(Counterparty.code == data["code"], Counterparty.id != counterparty_id)
        )
        if dup:
            raise AppHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="DUPLICATE_COUNTERPARTY_CODE",
                message="Counterparty code already exists",
            )
    for k, v in data.items():
        setattr(row, k, v)
    await session.flush()
    return CounterpartyResponse.model_validate(row)


# --- Counterparty accounts ---


@router.get("/counterparty-accounts", response_model=list[CounterpartyAccountResponse])
async def list_counterparty_accounts(
    counterparty_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[CounterpartyAccountResponse]:
    stmt = (
        select(CounterpartyAccount, Counterparty.name)
        .join(Counterparty, Counterparty.id == CounterpartyAccount.counterparty_id)
        .options(selectinload(CounterpartyAccount.payment_term))
        .order_by(Counterparty.name, CounterpartyAccount.account_code)
    )
    if counterparty_id:
        stmt = stmt.where(CounterpartyAccount.counterparty_id == counterparty_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                CounterpartyAccount.account_code.ilike(like),
                CounterpartyAccount.display_name.ilike(like),
                Counterparty.name.ilike(like),
            )
        )
    rows = []
    for acct, cp_name in (await session.execute(stmt.limit(500))).all():
        rows.append(_account_response(acct, cp_name))
    return rows


@router.post(
    "/counterparty-accounts",
    response_model=CounterpartyAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_counterparty_account(
    body: CounterpartyAccountCreate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> CounterpartyAccountResponse:
    cp = await session.get(Counterparty, body.counterparty_id)
    if cp is None:
        raise AppHTTPException(status_code=404, code="NOT_FOUND", message="Counterparty not found")
    dup = await session.scalar(
        select(func.count())
        .select_from(CounterpartyAccount)
        .where(
            CounterpartyAccount.counterparty_id == body.counterparty_id,
            CounterpartyAccount.account_code == body.account_code,
        )
    )
    if dup:
        raise AppHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_SUBACCOUNT_CODE",
            message="Account code already exists for this counterparty",
        )
    if body.payment_term_id:
        term = await session.get(PaymentTerm, body.payment_term_id)
        if term is None:
            raise AppHTTPException(status_code=404, code="NOT_FOUND", message="Payment term not found")
    row = CounterpartyAccount(**body.model_dump())
    session.add(row)
    await session.flush()
    await session.refresh(row, ["payment_term"])
    return _account_response(row, cp.name)


@router.patch("/counterparty-accounts/{account_id}", response_model=CounterpartyAccountResponse)
async def patch_counterparty_account(
    account_id: UUID,
    body: CounterpartyAccountUpdate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> CounterpartyAccountResponse:
    row = await session.get(
        CounterpartyAccount,
        account_id,
        options=[selectinload(CounterpartyAccount.payment_term)],
    )
    if row is None:
        raise AppHTTPException(status_code=404, code="NOT_FOUND", message="Subaccount not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("is_active") is False:
        if await has_open_balance_for_subaccount(session, account_id):
            raise AppHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="SUBACCOUNT_HAS_OPEN_BALANCE",
                message="Cannot deactivate subaccount with open cases",
            )
    if "payment_term_id" in data and data["payment_term_id"]:
        term = await session.get(PaymentTerm, data["payment_term_id"])
        if term is None:
            raise AppHTTPException(status_code=404, code="NOT_FOUND", message="Payment term not found")
    for k, v in data.items():
        setattr(row, k, v)
    await session.flush()
    cp = await session.get(Counterparty, row.counterparty_id)
    return _account_response(row, cp.name if cp else None)


# --- Payment terms ---


@router.get("/payment-terms", response_model=list[PaymentTermResponse])
async def list_payment_terms(
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[PaymentTermResponse]:
    result = await session.execute(select(PaymentTerm).order_by(PaymentTerm.due_days, PaymentTerm.code))
    return [PaymentTermResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/payment-terms", response_model=PaymentTermResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_term(
    body: PaymentTermCreate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> PaymentTermResponse:
    dup = await session.scalar(
        select(func.count()).select_from(PaymentTerm).where(PaymentTerm.code == body.code.upper())
    )
    if dup:
        raise AppHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_PAYMENT_TERM",
            message="Payment term code already exists",
        )
    row = PaymentTerm(**{**body.model_dump(), "code": body.code.upper()})
    session.add(row)
    await session.flush()
    return PaymentTermResponse.model_validate(row)


@router.patch("/payment-terms/{term_id}", response_model=PaymentTermResponse)
async def patch_payment_term(
    term_id: UUID,
    body: PaymentTermUpdate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> PaymentTermResponse:
    row = await session.get(PaymentTerm, term_id)
    if row is None:
        raise AppHTTPException(status_code=404, code="NOT_FOUND", message="Payment term not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await session.flush()
    return PaymentTermResponse.model_validate(row)


# --- Tenant tax codes ---


@router.get("/tenant/tax-codes", response_model=list[TenantTaxCodeResponse])
async def list_tax_codes(
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> list[TenantTaxCodeResponse]:
    result = await session.execute(select(TenantTaxCode).order_by(TenantTaxCode.code))
    return [TenantTaxCodeResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/tenant/tax-codes", response_model=TenantTaxCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_tax_code(
    body: TenantTaxCodeCreate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TenantTaxCodeResponse:
    code = body.code.upper()
    dup = await session.scalar(
        select(func.count()).select_from(TenantTaxCode).where(TenantTaxCode.code == code)
    )
    if dup:
        raise AppHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_TAX_CODE",
            message="Tax code already exists",
        )
    _validate_tax_direction(body.direction, body.output_gl_account_code, body.input_gl_account_code)
    if body.output_gl_account_code:
        await _validate_tax_gl(session, body.output_gl_account_code)
    if body.input_gl_account_code:
        await _validate_tax_gl(session, body.input_gl_account_code)
    row = TenantTaxCode(**{**body.model_dump(), "code": code})
    session.add(row)
    await session.flush()
    return TenantTaxCodeResponse.model_validate(row)


@router.patch("/tenant/tax-codes/{tax_id}", response_model=TenantTaxCodeResponse)
async def patch_tax_code(
    tax_id: UUID,
    body: TenantTaxCodeUpdate,
    _user: TokenData = Depends(require_client_admin()),
    session: AsyncSession = Depends(get_db_session),
) -> TenantTaxCodeResponse:
    row = await session.get(TenantTaxCode, tax_id)
    if row is None:
        raise AppHTTPException(status_code=404, code="NOT_FOUND", message="Tax code not found")
    data = body.model_dump(exclude_unset=True)
    direction = data.get("direction", row.direction)
    output_gl = data.get("output_gl_account_code", row.output_gl_account_code)
    input_gl = data.get("input_gl_account_code", row.input_gl_account_code)
    _validate_tax_direction(direction, output_gl, input_gl)
    if output_gl:
        await _validate_tax_gl(session, output_gl)
    if input_gl:
        await _validate_tax_gl(session, input_gl)
    for k, v in data.items():
        setattr(row, k, v)
    await session.flush()
    return TenantTaxCodeResponse.model_validate(row)
