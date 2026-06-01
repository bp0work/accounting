"""Expense claim reversal workflow — ACC raises, CFO approves."""

from __future__ import annotations

from calendar import month_name
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.core.accounting_errors import PeriodClosedError
from app.core.database import get_session_factory
from app.core.exceptions import AppHTTPException
from app.models.case import Case
from app.models.executive_mail import PendingOutboundEmail
from app.models.ledger import JournalEntry, JournalEntryLine
from app.models.mail import MailGatewayConfig
from app.models.user import User
from app.repositories.case import CaseRepository
from app.repositories.ledger import LedgerRepository
from app.schemas.auth import TokenData
from app.schemas.case_reversal import (
    ApproveReversalResponse,
    RaiseReversalResponse,
    RejectReversalResponse,
)
from app.schemas.executive_mail import FinanceActivityLogCreate
from app.services.accounting_calendar import assert_period_allows_posting, find_period_for_date
from app.services.finance_activity_log_service import FinanceActivityLogService
from app.services.timeline_actor import timeline_actor_label_for_user
from fastapi import status

POSTED_ORIGINAL_STATUSES = frozenset({"posted", "case_closed", "journal_posted"})
BLOCKING_REVERSAL_STATUSES = frozenset({"pending_reversal_approval", "reversed"})


def _meta_dict(case: Case) -> dict:
    raw = case.workflow_metadata or {}
    return raw if isinstance(raw, dict) else {}


def _period_month_label(posting_date: date) -> str:
    return f"{month_name[posting_date.month]} {posting_date.year}"


async def _load_posted_journal(session: AsyncSession, case_id: UUID) -> JournalEntry | None:
    result = await session.execute(
        select(JournalEntry)
        .where(JournalEntry.case_id == case_id, JournalEntry.status == "posted")
        .order_by(JournalEntry.posted_at.desc().nullslast(), JournalEntry.created_at.desc())
        .limit(1)
        .options(selectinload(JournalEntry.lines))
    )
    return result.scalar_one_or_none()


async def _load_draft_journal(session: AsyncSession, case_id: UUID) -> JournalEntry | None:
    result = await session.execute(
        select(JournalEntry)
        .where(JournalEntry.case_id == case_id, JournalEntry.status == "draft")
        .order_by(JournalEntry.created_at.desc())
        .limit(1)
        .options(selectinload(JournalEntry.lines))
    )
    return result.scalar_one_or_none()


def _mirror_lines(entry: JournalEntry) -> list[dict]:
    lines: list[dict] = []
    for line in sorted(entry.lines, key=lambda ln: ln.line_number):
        lines.append(
            {
                "line_number": line.line_number,
                "account_id": str(line.account_id),
                "debit": str(line.credit),
                "credit": str(line.debit),
                "description": line.description,
            }
        )
    return lines


async def _default_mailbox_id(session: AsyncSession) -> UUID | None:
    result = await session.execute(select(MailGatewayConfig.id).limit(1))
    return result.scalar_one_or_none()


async def _emails_for_role(session: AsyncSession, role_name: str) -> list[str]:
    from app.models.rbac import Role

    result = await session.execute(
        select(User.email)
        .join(Role, User.role_id == Role.id)
        .where(Role.name == role_name, User.status == "active")
    )
    return [row[0] for row in result.all() if row[0]]


async def _queue_notification_email(
    session: AsyncSession,
    *,
    case_id: UUID,
    to_addresses: list[str],
    subject: str,
    body_plain: str,
    message_type: str,
    metadata: dict | None = None,
) -> None:
    if not to_addresses:
        return
    mailbox_id = await _default_mailbox_id(session)
    if mailbox_id is None:
        return
    outbound = PendingOutboundEmail(
        case_id=case_id,
        mailbox_id=mailbox_id,
        to_addresses=to_addresses,
        cc_addresses=[],
        subject=subject[:998],
        body_plain=body_plain,
        message_type=message_type,
        status="approved",
        metadata_=metadata or {},
    )
    session.add(outbound)
    await session.flush()


def _require_accounts_manager(user: TokenData) -> None:
    if user.role != "accounts_manager":
        raise AppHTTPException(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "Only Accounts Manager may raise an expense reversal",
        )


async def _actor_email(session: AsyncSession, user: TokenData) -> str:
    db_user = await session.get(User, user.user_id)
    if db_user and db_user.email:
        return db_user.email
    return timeline_actor_label_for_user(user)


async def execute_raise_reversal(
    case_id: UUID,
    *,
    user: TokenData,
    reason: str | None = None,
) -> RaiseReversalResponse:
    _require_accounts_manager(user)
    factory = get_session_factory()

    async with factory() as session:
        cases = CaseRepository(session)
        ledger = LedgerRepository(session)
        original = await cases.get(case_id)
        if original is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Case not found")
        if original.type != "expense_claim":
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INVALID_CASE_TYPE",
                "Reversal is only supported for expense claims",
            )
        if original.status not in POSTED_ORIGINAL_STATUSES:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INVALID_CASE_STATUS",
                "Case must be posted before a reversal can be raised",
            )

        meta = _meta_dict(original)
        if meta.get("reversed_by"):
            raise AppHTTPException(
                status.HTTP_409_CONFLICT,
                "REVERSAL_EXISTS",
                "This case already has a completed reversal",
            )

        existing = await cases.find_reversal_child(
            original.id, statuses=tuple(BLOCKING_REVERSAL_STATUSES)
        )
        if existing is not None:
            raise AppHTTPException(
                status.HTTP_409_CONFLICT,
                "REVERSAL_PENDING",
                f"Reversal {existing.case_number} is already pending or completed",
            )

        posted_entry = await _load_posted_journal(session, original.id)
        if posted_entry is None:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "NO_POSTED_JOURNAL",
                "Posted journal entry not found for this case",
            )

        actor = await _actor_email(session, user)
        reversal_number = await cases.generate_case_number()
        mirrored = _mirror_lines(posted_entry)
        orig_extracted = meta.get("extracted_fields")
        source_doc = None
        if isinstance(orig_extracted, dict):
            raw_doc = orig_extracted.get("document_number")
            if raw_doc is not None:
                source_doc = str(raw_doc).strip() or None
        reversal_meta = {
            "reversal_of": original.case_number,
            "reversal_journal_lines": mirrored,
            "reversal_reason": (reason or "").strip() or None,
            "source_document_number": source_doc,
        }

        reversal = Case(
            case_number=reversal_number,
            type="expense_claim",
            status="pending_reversal_approval",
            priority=original.priority,
            subject=f"Reversal of {original.case_number}",
            description=original.description,
            counterparty_id=original.counterparty_id,
            counterparty_name=original.counterparty_name,
            amount_value=original.amount_value,
            amount_currency=original.amount_currency,
            parent_case_id=original.id,
            workflow_metadata=reversal_meta,
            classification_metadata={"source": "reversal"},
        )
        session.add(reversal)
        await session.flush()

        total = posted_entry.total_debit or Decimal("0")
        draft = await ledger.create_journal_entry(
            case_id=reversal.id,
            case_number=reversal.case_number,
            status="draft",
            entry_date=posted_entry.entry_date,
            description=f"Reversal of expense {original.case_number}",
            reference=f"REV-{original.case_number}",
            currency=posted_entry.currency or original.amount_currency or "SGD",
            total=total,
            posted=False,
            metadata={"reversal_of_case": original.case_number},
        )
        for line in sorted(posted_entry.lines, key=lambda ln: ln.line_number):
            await ledger.add_line(
                entry=draft,
                line_number=line.line_number,
                account_id=line.account_id,
                debit=line.credit,
                credit=line.debit,
                description=line.description,
            )

        await cases.add_timeline(
            case_id=original.id,
            event_type="reversal_raised",
            from_status=original.status,
            to_status=original.status,
            actor=actor,
            description=f"Reversal raised by ACC — {reversal.case_number}",
            metadata={"reversal_case_id": str(reversal.id)},
            actor_user_id=user.user_id,
        )
        await cases.add_timeline(
            case_id=reversal.id,
            event_type="reversal_raised",
            from_status=None,
            to_status="pending_reversal_approval",
            actor=actor,
            description="Reversal raised — pending CFO approval",
            metadata={"original_case_id": str(original.id)},
            actor_user_id=user.user_id,
        )

        vendor = original.counterparty_name or "—"
        amount = f"{original.amount_currency or 'SGD'} {original.amount_value or '—'}"
        cfo_subject = (
            f"[{reversal.case_number}] Reversal approval required — {original.case_number}"
        )
        body_lines = [
            f"Reversal case: {reversal.case_number}",
            f"Original case: {original.case_number}",
            f"Vendor: {vendor}",
            f"Amount: {amount}",
        ]
        if reason and reason.strip():
            body_lines.append(f"Reason: {reason.strip()}")
        body_lines.append("Approve or reject from the Finance UI case detail.")
        cfo_emails = await _emails_for_role(session, "cfo")
        await _queue_notification_email(
            session,
            case_id=reversal.id,
            to_addresses=cfo_emails,
            subject=cfo_subject,
            body_plain="\n\n".join(body_lines),
            message_type="reversal_approval",
            metadata={
                "reversal_case_number": reversal.case_number,
                "original_case_number": original.case_number,
            },
        )

        await session.commit()
        return RaiseReversalResponse(
            reversal_case_id=reversal.id,
            reversal_case_number=reversal.case_number,
        )


async def execute_approve_reversal(
    case_id: UUID,
    *,
    user: TokenData,
    comment: str | None = None,
    gl_period_override_reason: str | None = None,
) -> ApproveReversalResponse:
    factory = get_session_factory()

    async with factory() as session:
        cases = CaseRepository(session)
        activity = FinanceActivityLogService(session)
        reversal = await cases.get(case_id)
        if reversal is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Case not found")
        if reversal.status != "pending_reversal_approval":
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INVALID_CASE_STATUS",
                "Case is not awaiting reversal approval",
            )
        if reversal.parent_case_id is None:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "NOT_A_REVERSAL_CASE",
                "Case is not a reversal",
            )

        original = await cases.get(reversal.parent_case_id)
        if original is None:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "ORIGINAL_NOT_FOUND",
                "Original case not found",
            )

        draft = await _load_draft_journal(session, reversal.id)
        if draft is None:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "NO_DRAFT_JOURNAL",
                "Draft reversal journal entry not found",
            )

        posted_original = await _load_posted_journal(session, original.id)
        entry_date = (
            posted_original.entry_date if posted_original else draft.entry_date
        )
        period = await find_period_for_date(session, entry_date)
        period_closed = period is not None and period.status == "closed"
        override_reason = (gl_period_override_reason or "").strip()

        if period_closed and not override_reason:
            label = _period_month_label(entry_date)
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "PERIOD_CLOSED_OVERRIDE_REQUIRED",
                f"Period [{label}] is closed — provide an override reason to post the reversal",
            )

        actor = await _actor_email(session, user)
        try:
            await assert_period_allows_posting(
                session,
                entry_date,
                override=period_closed,
                override_reason=override_reason if period_closed else None,
                posted_by=actor if period_closed else None,
                case_id=reversal.id,
                case_number=reversal.case_number,
            )
        except PeriodClosedError as exc:
            label = _period_month_label(exc.posting_date)
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "PERIOD_CLOSED_OVERRIDE_REQUIRED",
                f"Period [{label}] is closed — provide an override reason to post the reversal",
            ) from exc

        draft.status = "posted"
        draft.posted_at = datetime.now(UTC)
        draft.posting_date = entry_date
        db_user = await session.get(User, user.user_id)
        if db_user:
            draft.posted_by = db_user.id

        reversal.status = "reversed"
        reversal.completed_at = datetime.now(UTC)
        rev_meta = _meta_dict(reversal)
        if period_closed:
            rev_meta["gl_period_override"] = True
            rev_meta["gl_period_override_reason"] = override_reason
            rev_meta["gl_period_posted_by"] = actor
            if period:
                rev_meta["gl_period_id"] = str(period.id)
            await activity.log(
                FinanceActivityLogCreate(
                    actor_type="manager",
                    actor_name=actor,
                    action="reversal_gl_period_override",
                    summary=(
                        f"[{reversal.case_number}] Reversal posted to closed period "
                        f"({override_reason})"
                    ),
                    case_id=reversal.id,
                    metadata={
                        "original_case_number": original.case_number,
                        "override_reason": override_reason,
                    },
                )
            )
        if comment and comment.strip():
            rev_meta["reversal_approval_comment"] = comment.strip()
        reversal.workflow_metadata = rev_meta

        orig_meta = _meta_dict(original)
        orig_meta["reversed_by"] = reversal.case_number
        original.workflow_metadata = orig_meta

        await cases.add_timeline(
            case_id=reversal.id,
            event_type="reversal_approved",
            from_status="pending_reversal_approval",
            to_status="reversed",
            actor=actor,
            description="Reversal approved and posted to GL",
            metadata={"journal_entry_id": str(draft.id)},
            actor_user_id=user.user_id,
        )
        await cases.add_timeline(
            case_id=original.id,
            event_type="reversal_approved",
            from_status=original.status,
            to_status=original.status,
            actor=actor,
            description=f"Reversal {reversal.case_number} approved and posted",
            metadata={"reversal_case_number": reversal.case_number},
            actor_user_id=user.user_id,
        )

        acc_emails = await _emails_for_role(session, "accounts_manager")
        await _queue_notification_email(
            session,
            case_id=reversal.id,
            to_addresses=acc_emails,
            subject=f"[{reversal.case_number}] Reversal approved and posted",
            body_plain=(
                f"Reversal {reversal.case_number} for original case {original.case_number} "
                "has been approved and posted to the GL."
            ),
            message_type="reversal_approved",
        )

        await session.commit()
        return ApproveReversalResponse(status="reversed", journal_entry_id=draft.id)


async def execute_reject_reversal(
    case_id: UUID,
    *,
    user: TokenData,
    comment: str,
) -> RejectReversalResponse:
    reason = (comment or "").strip()
    if not reason:
        raise AppHTTPException(
            status.HTTP_400_BAD_REQUEST, "INVALID_COMMENT", "comment is required"
        )

    factory = get_session_factory()

    async with factory() as session:
        cases = CaseRepository(session)
        reversal = await cases.get(case_id)
        if reversal is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Case not found")
        if reversal.status != "pending_reversal_approval":
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INVALID_CASE_STATUS",
                "Case is not awaiting reversal approval",
            )
        if reversal.parent_case_id is None:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "NOT_A_REVERSAL_CASE",
                "Case is not a reversal",
            )

        original = await cases.get(reversal.parent_case_id)
        draft = await _load_draft_journal(session, reversal.id)
        if draft is not None:
            draft.status = "reversed"
            void_meta = dict(draft.extra_metadata or {})
            void_meta.update({"voided": True, "void_reason": reason})
            draft.extra_metadata = void_meta
            flag_modified(draft, "extra_metadata")

        actor = await _actor_email(session, user)
        reversal.status = "reversal_rejected"
        rev_meta = _meta_dict(reversal)
        rev_meta["reversal_rejection_comment"] = reason
        reversal.workflow_metadata = rev_meta

        await cases.add_timeline(
            case_id=reversal.id,
            event_type="reversal_rejected",
            from_status="pending_reversal_approval",
            to_status="reversal_rejected",
            actor=actor,
            description=f"Reversal rejected — {reason}",
            actor_user_id=user.user_id,
        )
        if original is not None:
            await cases.add_timeline(
                case_id=original.id,
                event_type="reversal_rejected",
                from_status=original.status,
                to_status=original.status,
                actor=actor,
                description=f"Reversal rejected — {reason}",
                metadata={"reversal_case_number": reversal.case_number},
                actor_user_id=user.user_id,
            )

        acc_emails = await _emails_for_role(session, "accounts_manager")
        orig_no = original.case_number if original else "—"
        await _queue_notification_email(
            session,
            case_id=reversal.id,
            to_addresses=acc_emails,
            subject=f"[{reversal.case_number}] Reversal rejected",
            body_plain=(
                f"Reversal {reversal.case_number} for original case {orig_no} was rejected.\n\n"
                f"Reason: {reason}"
            ),
            message_type="reversal_rejected",
        )

        await session.commit()
        return RejectReversalResponse(status="reversal_rejected")


async def reversal_gl_period_context(
    session: AsyncSession, case: Case
) -> tuple[str | None, bool]:
    """GL period label and whether override is required (closed period)."""
    if case.status != "pending_reversal_approval":
        return None, False
    draft = await _load_draft_journal(session, case.id)
    if draft is None:
        return None, False
    label = _period_month_label(draft.entry_date)
    period = await find_period_for_date(session, draft.entry_date)
    closed = period is not None and period.status == "closed"
    if closed:
        return f"{label} [CLOSED — override required]", True
    return label, False
