"""Counterparty subaccount, payment terms, and GST resolution at intake — `17` §3.2.1–§3.2.3."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.case import Case
from app.models.counterparty_master import CounterpartyAccount, PaymentTerm, TenantTaxCode
from app.models.ledger import CoaAccount
from app.schemas.hermes import ExtractedInvoice


@dataclass
class IntakeResolution:
    counterparty_account_id: UUID | None
    counterparty_account_code: str | None
    payment_term_code: str | None
    due_date: date | None
    due_date_source: str | None
    tax_code: str | None
    tax_source: str | None
    tax_gl_account_code: str | None
    tax_direction: str
    warnings: list[str]


def _normalize_term_code(payment_terms: str | None) -> str | None:
    if not payment_terms:
        return None
    raw = payment_terms.strip().upper()
    if re.match(r"^NET\d+$", raw):
        return raw
    m = re.search(r"NET\s*(\d+)", raw, re.I)
    if m:
        return f"NET{m.group(1)}"
    m = re.search(r"(\d+)\s*DAYS?", raw, re.I)
    if m:
        return f"NET{m.group(1)}"
    if raw in ("COD", "C.O.D.", "CASH ON DELIVERY"):
        return "COD"
    return None


async def resolve_subaccount(
    session: AsyncSession,
    *,
    counterparty_id: UUID | None,
    account_code_hint: str | None = None,
    contact_email: str | None = None,
) -> CounterpartyAccount | None:
    if not counterparty_id:
        return None
    if account_code_hint:
        result = await session.execute(
            select(CounterpartyAccount)
            .options(selectinload(CounterpartyAccount.payment_term))
            .where(
                CounterpartyAccount.counterparty_id == counterparty_id,
                CounterpartyAccount.account_code.ilike(account_code_hint.strip()),
                CounterpartyAccount.is_active.is_(True),
            )
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            return row
    if contact_email:
        result = await session.execute(
            select(CounterpartyAccount)
            .options(selectinload(CounterpartyAccount.payment_term))
            .where(
                CounterpartyAccount.counterparty_id == counterparty_id,
                CounterpartyAccount.contact_email.ilike(contact_email.strip()),
                CounterpartyAccount.is_active.is_(True),
            )
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            return row
    result = await session.execute(
        select(CounterpartyAccount)
        .options(selectinload(CounterpartyAccount.payment_term))
        .where(
            CounterpartyAccount.counterparty_id == counterparty_id,
            CounterpartyAccount.is_active.is_(True),
        )
    )
    active = list(result.scalars().all())
    if len(active) == 1:
        return active[0]
    return None


async def resolve_payment_term(
    session: AsyncSession,
    *,
    payment_terms_text: str | None,
    subaccount: CounterpartyAccount | None,
) -> PaymentTerm | None:
    code = _normalize_term_code(payment_terms_text)
    if code:
        result = await session.execute(
            select(PaymentTerm).where(
                PaymentTerm.code == code,
                PaymentTerm.is_active.is_(True),
            )
        )
        term = result.scalar_one_or_none()
        if term:
            return term
    if subaccount and subaccount.payment_term_id:
        if subaccount.payment_term:
            return subaccount.payment_term
        return await session.get(PaymentTerm, subaccount.payment_term_id)
    result = await session.execute(
        select(PaymentTerm).where(PaymentTerm.code == "NET30", PaymentTerm.is_active.is_(True))
    )
    return result.scalar_one_or_none()


def compute_due_date(
    *,
    document_date: date | None,
    extracted_due: date | None,
    term: PaymentTerm | None,
    document_total: Decimal,
) -> tuple[date | None, str | None, list[str]]:
    warnings: list[str] = []
    if extracted_due:
        return extracted_due, "extracted", warnings
    if not document_date:
        return None, None, warnings
    if term is None:
        return None, None, warnings
    if term.minimum_invoice_amount is not None and document_total < term.minimum_invoice_amount:
        warnings.append("payment_term_not_applied")
        return None, "payment_terms", warnings
    return document_date + timedelta(days=term.due_days), "payment_terms", warnings


async def resolve_tax_gl(
    session: AsyncSession,
    *,
    direction: str,
    tax_code_hint: str | None,
    tax_amount: Decimal,
) -> tuple[str | None, str | None, str | None]:
    """Returns (tax_code, tax_source, gl_account_code). Falls back to legacy codes when unmapped."""
    if tax_amount <= 0:
        return tax_code_hint, None, None

    code = (tax_code_hint or "").strip().upper() or None
    if code:
        result = await session.execute(
            select(TenantTaxCode).where(
                TenantTaxCode.code.ilike(code),
                TenantTaxCode.is_active.is_(True),
            )
        )
        row = result.scalar_one_or_none()
        if row:
            gl = row.output_gl_account_code if direction == "output" else row.input_gl_account_code
            if direction == "both":
                gl = row.output_gl_account_code or row.input_gl_account_code
            if gl:
                return row.code, "extracted", gl

    default_code = "GST9"
    result = await session.execute(
        select(TenantTaxCode).where(
            TenantTaxCode.code == default_code,
            TenantTaxCode.is_active.is_(True),
        )
    )
    row = result.scalar_one_or_none()
    if row:
        gl = row.output_gl_account_code if direction == "output" else row.input_gl_account_code
        if gl:
            return row.code, "tenant_default", gl

    legacy = "2100" if direction == "output" else "1190"
    return code or default_code, "legacy_hardcoded", legacy


async def _coa_exists(session: AsyncSession, account_code: str) -> bool:
    n = await session.scalar(
        select(func.count())
        .select_from(CoaAccount)
        .where(CoaAccount.account_code == account_code, CoaAccount.is_active.is_(True))
    )
    return bool(n)


async def resolve_invoice_intake(
    session: AsyncSession,
    *,
    case: Case,
    inv: ExtractedInvoice,
    tax_direction: str,
    account_code_hint: str | None = None,
) -> IntakeResolution:
    amount = Decimal(inv.total_amount or "0")
    sub = await resolve_subaccount(
        session,
        counterparty_id=case.counterparty_id,
        account_code_hint=account_code_hint,
    )
    term = await resolve_payment_term(
        session,
        payment_terms_text=inv.payment_terms,
        subaccount=sub,
    )
    due, due_source, term_warnings = compute_due_date(
        document_date=inv.document_date,
        extracted_due=inv.due_date,
        term=term,
        document_total=amount,
    )
    tax_code, tax_source, tax_gl = await resolve_tax_gl(
        session,
        direction=tax_direction,
        tax_code_hint=getattr(inv, "tax_code", None),
        tax_amount=Decimal(inv.tax_amount or "0"),
    )
    warnings = list(term_warnings)
    if tax_gl and not await _coa_exists(session, tax_gl):
        warnings.append(f"tax_gl_not_in_coa:{tax_gl}")
        tax_gl = "2100" if tax_direction == "output" else "1190"
        tax_source = "legacy_hardcoded"

    return IntakeResolution(
        counterparty_account_id=sub.id if sub else None,
        counterparty_account_code=sub.account_code if sub else None,
        payment_term_code=term.code if term else None,
        due_date=due,
        due_date_source=due_source,
        tax_code=tax_code,
        tax_source=tax_source,
        tax_gl_account_code=tax_gl,
        tax_direction=tax_direction,
        warnings=warnings,
    )


def build_extraction_output(
    *,
    case: Case,
    inv: ExtractedInvoice,
    resolution: IntakeResolution,
    document_type: str,
    confidence: float,
) -> dict:
    return {
        "document_type": document_type,
        "document_number": inv.document_number,
        "document_date": str(inv.document_date) if inv.document_date else None,
        "due_date": str(resolution.due_date) if resolution.due_date else None,
        "amount_value": str(inv.total_amount or "0"),
        "amount_currency": inv.currency,
        "tax_amount": inv.tax_amount,
        "tax_code": resolution.tax_code,
        "counterparty_name": case.counterparty_name,
        "counterparty_ref": str(case.counterparty_id) if case.counterparty_id else None,
        "counterparty_account_ref": (
            str(resolution.counterparty_account_id) if resolution.counterparty_account_id else None
        ),
        "payment_term_code": resolution.payment_term_code,
        "due_date_source": resolution.due_date_source,
        "tax_source": resolution.tax_source,
        "line_items": [],
        "document_completeness": 1.0 - (len(inv.missing_fields) * 0.1),
        "confidence_score": confidence,
        "extraction_model": "hermes-extractor",
        "extracted_at": None,
    }


async def apply_intake_to_case(
    session: AsyncSession,
    *,
    case: Case,
    inv: ExtractedInvoice,
    tax_direction: str,
    confidence: float,
    document_type: str,
    account_code_hint: str | None = None,
) -> IntakeResolution:
    from datetime import UTC, datetime, time

    resolution = await resolve_invoice_intake(
        session,
        case=case,
        inv=inv,
        tax_direction=tax_direction,
        account_code_hint=account_code_hint,
    )
    case.counterparty_account_id = resolution.counterparty_account_id
    if resolution.due_date:
        case.due_date = datetime.combine(resolution.due_date, time.min, tzinfo=UTC)
    extraction_output = build_extraction_output(
        case=case,
        inv=inv,
        resolution=resolution,
        document_type=document_type,
        confidence=confidence,
    )
    wm = dict(case.workflow_metadata or {})
    wm["extraction_output"] = extraction_output
    wm["tax_resolution"] = {
        "tax_code": resolution.tax_code,
        "tax_source": resolution.tax_source,
        "gl_account_code": resolution.tax_gl_account_code,
        "tax_amount": inv.tax_amount,
    }
    if resolution.warnings:
        wm["intake_warnings"] = resolution.warnings
    if resolution.counterparty_account_code:
        wm["counterparty_account_code"] = resolution.counterparty_account_code
    case.workflow_metadata = wm
    return resolution


async def has_open_balance_for_subaccount(session: AsyncSession, account_id: UUID) -> bool:
    terminal = ("completed", "rejected")
    n = await session.scalar(
        select(func.count())
        .select_from(Case)
        .where(
            Case.counterparty_account_id == account_id,
            Case.status.notin_(terminal),
        )
    )
    return bool(n and n > 0)
