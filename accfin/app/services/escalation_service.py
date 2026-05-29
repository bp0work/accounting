"""Manager escalation respond — `05` §8.8a."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from app.core.exceptions import AppHTTPException
from app.core.mail_action_token import (
    hash_token,
    issue_escalation_token,
    verify_escalation_token,
)
from app.models.executive_mail import CaseEscalation
from app.repositories.case import CaseRepository
from app.repositories.executive_mail import CaseEscalationRepository
from app.schemas.executive_mail import EscalationRespondContext, EscalationRespondResult
from app.policies.binding_authority import BINDING_AUTHORITY_REASON_PREFIX
from app.services.binding_authority_service import (
    BindingAuthorityService,
    binding_reason_code,
)
from app.services.executive_mail_service import ExecutiveMailService

# Mirrors AP_OVERRIDE_KEYS in workers.ap.handlers — kept here to avoid circular import
_AP_STEP_OVERRIDE_KEYS: dict[str, str] = {
    "AP_PARSING_INCOMPLETE":    "override_parsing",
    "AP_DUPLICATE_FOUND":       "override_duplicate",
    "AP_VENDOR_INACTIVE":       "override_vendor_inactive",
    "AP_PAYMENT_TERMS_MISMATCH": "override_payment_terms",
    "AP_CONTRACT_MISSING":      "override_contract",
    "AP_SENDER_NOT_VALIDATED":  "override_sender_validation",
    "AP_COA_NOT_FOUND":         "override_coa_not_found",
}
_REASON_VENDOR_NOT_FOUND = "AP_VENDOR_NOT_FOUND"
_REASON_CURRENCY_CONVERSION = "AP_CURRENCY_CONVERSION_REQUIRED"

_EXCHANGE_RATE_COMMENT_PATTERNS = (
    re.compile(r"1\s+[A-Z]{3}\s*=\s*([\d.]+)\s*SGD", re.I),
    re.compile(r"[A-Z]{3}/SGD\s+([\d.]+)", re.I),
    re.compile(r"exchange\s+rate\s*:?\s*([\d.]+)", re.I),
    re.compile(r"conversion\s+rate\s*:?\s*([\d.]+)", re.I),
    re.compile(r"([\d.]+)"),
)


def _parse_exchange_rate_from_comment(comment: str | None) -> str | None:
    text = (comment or "").strip()
    if not text:
        return None
    for pattern in _EXCHANGE_RATE_COMMENT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            rate = Decimal(match.group(1))
            if rate > 0:
                return str(rate)
        except (InvalidOperation, ValueError, IndexError):
            continue
    return None
_VENDOR_NOT_FOUND_REJECTION = (
    "Your document cannot be processed as {vendor_name} is not set up in our system. "
    "Please contact accounts to register the vendor."
)
_SENDER_VALIDATION_RESUBMIT_TEMPLATE = (
    "Please resubmit your document quoting Case ID {case_number} and include "
    "'validated dd/mm/yyyy' in your email (e.g. 'validated 28/05/2026') "
    "to confirm you have reviewed and approved this document."
)


class EscalationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CaseEscalationRepository(session)
        self._cases = CaseRepository(session)
        self._executive_mail = ExecutiveMailService(session)

    async def get_case_number(self, case_id: UUID) -> str | None:
        case = await self._cases.get(case_id)
        return case.case_number if case else None

    def _validate_token(self, wire_token: str, escalation_id: UUID) -> str:
        try:
            verify_escalation_token(wire_token, escalation_id=escalation_id)
        except ValueError as exc:
            code = str(exc)
            raise AppHTTPException(400, code, "Invalid or expired escalation token") from exc
        return hash_token(wire_token)

    async def _pending_for_case(self, case_id: UUID) -> CaseEscalation | None:
        result = await self._session.execute(
            select(CaseEscalation)
            .where(CaseEscalation.case_id == case_id, CaseEscalation.status == "pending")
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def respond_for_case(
        self,
        case_id: UUID,
        *,
        action: str,
        comment: str | None,
        responder_email: str,
    ) -> EscalationRespondResult:
        """Authenticated Finance UI respond — uses stored wire token from escalation context."""
        case = await self._cases.get(case_id)
        if case is None:
            raise AppHTTPException(status.HTTP_404_NOT_FOUND, "CASE_NOT_FOUND", "Case not found")
        if case.status not in ("manual_review", "on_hold"):
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "CASE_NOT_AWAITING_REVIEW",
                "Case is not in manual review or on hold",
            )

        row = await self._pending_for_case(case_id)
        if row is None:
            raise AppHTTPException(
                status.HTTP_404_NOT_FOUND,
                "NO_PENDING_ESCALATION",
                "No pending escalation for this case",
            )

        notification = (row.context or {}).get("notification") or {}
        wire = notification.get("wire_token")
        if not wire:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "ESCALATION_TOKEN_MISSING",
                "Escalation is missing an action token; use the email link or contact support",
            )

        return await self.respond(
            row.id,
            action=action,
            wire_token=str(wire),
            comment=comment,
            responder_email=responder_email,
        )

    async def get_respond_context(
        self,
        escalation_id: UUID,
        *,
        action: str,
        wire_token: str,
    ) -> EscalationRespondContext:
        if action not in ("approve", "reject", "escalate", "request_info"):
            raise AppHTTPException(
                422,
                "INVALID_ESCALATION_ACTION",
                "action must be approve, reject, escalate, or request_info",
            )

        token_hash = self._validate_token(wire_token, escalation_id)
        row = await self._repo.get(escalation_id)
        if row is None:
            raise AppHTTPException(404, "ESCALATION_NOT_FOUND", "Escalation not found")
        if row.response_token_hash != token_hash:
            raise AppHTTPException(400, "INVALID_ESCALATION_TOKEN", "Token does not match escalation")

        if str(row.reason_code or "") == _REASON_VENDOR_NOT_FOUND and action != "reject":
            raise AppHTTPException(
                422,
                "VENDOR_NOT_FOUND_REJECT_ONLY",
                "Vendor not set up — only Reject is available from this email. "
                "Use Retry in Finance UI after registering the vendor.",
            )

        case = await self._cases.get(row.case_id)
        case_number = case.case_number if case else str(row.case_id)

        if row.status != "pending":
            return EscalationRespondContext(
                escalation_id=row.id,
                case_id=row.case_id,
                case_number=case_number,
                action=action,
                status=row.status,
                already_responded=True,
                result=EscalationRespondResult(
                    escalation_id=row.id,
                    case_id=row.case_id,
                    action=action,
                    status=row.status,
                    responded_at=row.responded_at or datetime.now(UTC),
                    manager_comment=row.manager_comment,
                    message="Already responded (idempotent)",
                ),
            )

        return EscalationRespondContext(
            escalation_id=row.id,
            case_id=row.case_id,
            case_number=case_number,
            action=action,
            status=row.status,
            already_responded=False,
        )

    async def respond(
        self,
        escalation_id: UUID,
        *,
        action: str,
        wire_token: str,
        comment: str | None = None,
        responder_email: str | None = None,
    ) -> EscalationRespondResult:
        if action not in ("approve", "reject", "escalate", "request_info"):
            raise AppHTTPException(
                422,
                "INVALID_ESCALATION_ACTION",
                "action must be approve, reject, escalate, or request_info",
            )

        token_hash = self._validate_token(wire_token, escalation_id)
        row = await self._repo.get(escalation_id)
        if row is None:
            raise AppHTTPException(404, "ESCALATION_NOT_FOUND", "Escalation not found")
        if row.response_token_hash != token_hash:
            raise AppHTTPException(400, "INVALID_ESCALATION_TOKEN", "Token does not match escalation")

        if str(row.reason_code or "") == _REASON_VENDOR_NOT_FOUND and action != "reject":
            raise AppHTTPException(
                422,
                "VENDOR_NOT_FOUND_REJECT_ONLY",
                "Vendor not set up — only Reject is available from this email. "
                "Use Retry in Finance UI after registering the vendor.",
            )

        if row.status != "pending":
            if row.status in ("approved", "rejected", "escalated"):
                return EscalationRespondResult(
                    escalation_id=row.id,
                    case_id=row.case_id,
                    action=action,
                    status=row.status,
                    responded_at=row.responded_at or datetime.now(UTC),
                    manager_comment=row.manager_comment,
                    message="Already responded (idempotent)",
                )
            raise AppHTTPException(409, "ESCALATION_ALREADY_RESPONDED", "Escalation is not pending")

        trimmed_comment = (comment or "").strip() or None
        now = datetime.now(UTC)
        responder = responder_email or row.target_email
        child_id: UUID | None = None
        target_email: str | None = None
        message: str | None = None

        if action == "approve":
            reason_code_pre = row.reason_code or ""
            if str(reason_code_pre) == _REASON_VENDOR_NOT_FOUND:
                raise AppHTTPException(
                    422,
                    "VENDOR_NOT_FOUND_NO_APPROVE",
                    "Vendor not set up — use Reject to notify the sender, or Retry in Finance UI "
                    "after registering the vendor. Approve is not available for this escalation.",
                )
            row.status = "approved"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = trimmed_comment
            case = await self._cases.get(row.case_id)
            if case:
                reason_code = row.reason_code or (case.workflow_metadata or {}).get(
                    "reason_code", ""
                )
                if str(reason_code).startswith(BINDING_AUTHORITY_REASON_PREFIX):
                    binding = BindingAuthorityService(self._session)
                    await binding.complete_approval(
                        case,
                        actor_name=responder,
                        manager_comment=trimmed_comment,
                    )
                    row.status = "approved"
                    meta = dict(case.workflow_metadata or {})
                    meta["escalation_pending"] = False
                    case.workflow_metadata = meta
                    message = "Approved. Journal entry posted and submitter notified."
                else:
                    ap_override_key = _AP_STEP_OVERRIDE_KEYS.get(str(reason_code))
                    if str(reason_code) == _REASON_CURRENCY_CONVERSION:
                        rate = _parse_exchange_rate_from_comment(trimmed_comment)
                        if rate:
                            meta = dict(case.workflow_metadata or {})
                            extracted = dict(meta.get("extracted_fields") or {})
                            extracted["exchange_rate"] = rate
                            meta["extracted_fields"] = extracted
                            meta["resume_from_step"] = "2F"
                            case.workflow_metadata = meta
                    period_closed = reason_code == "PERIOD_CLOSED"
                    await self._executive_mail.resume_after_manager_approve(
                        case=case,
                        escalation=row,
                        actor_name=responder,
                        override_po_check=not period_closed,
                        override_gl_period=period_closed,
                        gl_period_override_reason=trimmed_comment
                        or "Manager approved GL period override",
                        gl_period_posted_by=responder,
                        ap_step_override_key=ap_override_key,
                    )
                    message = "Approved. Case requeued for processing and submitter notified."

        elif action == "reject":
            row.status = "rejected"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = trimmed_comment
            case = await self._cases.get(row.case_id)
            if case:
                reason_code = row.reason_code or ""
                if str(reason_code).startswith(BINDING_AUTHORITY_REASON_PREFIX):
                    binding = BindingAuthorityService(self._session)
                    await binding.reject_case(
                        case,
                        actor_name=responder,
                        reason=trimmed_comment or row.summary,
                    )
                    message = "Rejected. Submitter has been notified."
                else:
                    is_ap_step = str(reason_code) in _AP_STEP_OVERRIDE_KEYS
                    is_vendor_not_found = str(reason_code) == _REASON_VENDOR_NOT_FOUND
                    case.status = (
                        "case_rejected"
                        if is_ap_step or is_vendor_not_found
                        else "rejected"
                    )
                    meta = dict(case.workflow_metadata or {})
                    meta["manager_decision"] = "rejected"
                    meta["escalation_pending"] = False
                    if trimmed_comment:
                        meta["manager_comment"] = trimmed_comment
                    case.workflow_metadata = meta

                    email = await self._resolve_email(row, case)
                    error_reason = (row.context or {}).get("error_reason") or row.summary
                    if is_vendor_not_found:
                        ctx = row.context or {}
                        extracted = ctx.get("extracted_fields") or {}
                        vendor_name = (
                            meta.get("vendor_name")
                            or extracted.get("vendor_name")
                            or case.counterparty_name
                            or "the vendor"
                        )
                        error_reason = _VENDOR_NOT_FOUND_REJECTION.format(
                            vendor_name=str(vendor_name)
                        )
                    elif reason_code == "AP_SENDER_NOT_VALIDATED":
                        error_reason = _SENDER_VALIDATION_RESUBMIT_TEMPLATE.format(
                            case_number=case.case_number
                        )
                    if email is not None:
                        await self._executive_mail.queue_submitter_rejection(
                            case=case,
                            email=email,
                            reason=error_reason,
                            manager_comment=trimmed_comment,
                        )

                    await self._executive_mail.log_step(
                        action="manager_rejected",
                        summary=f"[{case.case_number}] Manager rejected escalation",
                        actor_type="manager",
                        actor_name=responder,
                        mailbox_id=row.originating_mailbox_id,
                        case_id=case.id,
                        email_id=email.id if email else None,
                        metadata={
                            "escalation_id": str(row.id),
                            "manager_comment": trimmed_comment,
                        },
                    )
                    message = "Rejected. Submitter has been notified."

        elif action == "escalate":
            case = await self._cases.get(row.case_id)
            reason_code = row.reason_code or ""
            if case and str(reason_code).startswith(BINDING_AUTHORITY_REASON_PREFIX):
                binding = BindingAuthorityService(self._session)
                await binding.escalate_tier2_to_cfo(
                    case, actor_name=responder, comment=trimmed_comment
                )
                row.status = "escalated"
                row.responded_at = now
                row.responded_by_email = responder
                row.manager_comment = trimmed_comment
                child_id = uuid4()
                wire, child_token_hash, expires = issue_escalation_token(
                    escalation_id=child_id,
                    case_id=row.case_id,
                )
                target_email = binding.target_email_for_tier(3)
                target_mailbox = await self._repo.get_mailbox_by_email(target_email)
                child = CaseEscalation(
                    id=child_id,
                    case_id=row.case_id,
                    email_id=row.email_id,
                    originating_mailbox_id=row.originating_mailbox_id,
                    target_mailbox_id=target_mailbox.id if target_mailbox else None,
                    target_email=target_email,
                    parent_escalation_id=row.id,
                    status="pending",
                    reason_code=binding_reason_code(3),
                    summary=row.summary,
                    context=dict(row.context or {}),
                    response_token_hash=child_token_hash,
                    token_expires_at=expires,
                )
                await self._repo.create(child)
                await self._executive_mail.dispatch_child_escalation(
                    case=case,
                    child=child,
                    parent=row,
                    wire_token=wire,
                    manager_comment=trimmed_comment,
                    responder_email=responder,
                )
                message = f"Escalated to {target_email}. A new email has been sent."
                await self._session.commit()
                return EscalationRespondResult(
                    escalation_id=row.id,
                    case_id=row.case_id,
                    action=action,
                    status=row.status,
                    child_escalation_id=child_id,
                    target_email=target_email,
                    responded_at=row.responded_at or now,
                    manager_comment=trimmed_comment,
                    message=message,
                )

            manager_mailbox = await self._repo.get_mailbox_by_email(row.target_email)
            if manager_mailbox is None or not manager_mailbox.escalation_manager_email:
                raise AppHTTPException(
                    422,
                    "ESCALATION_TIER_EXHAUSTED",
                    "No further escalation tier configured",
                )
            row.status = "escalated"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = trimmed_comment

            target_email = manager_mailbox.escalation_manager_email
            target_mailbox = await self._repo.get_mailbox_by_email(target_email)
            child_id = uuid4()
            wire, child_token_hash, expires = issue_escalation_token(
                escalation_id=child_id,
                case_id=row.case_id,
            )
            child = CaseEscalation(
                id=child_id,
                case_id=row.case_id,
                email_id=row.email_id,
                originating_mailbox_id=row.originating_mailbox_id,
                target_mailbox_id=target_mailbox.id if target_mailbox else None,
                target_email=target_email,
                parent_escalation_id=row.id,
                status="pending",
                summary=row.summary,
                context=dict(row.context or {}),
                response_token_hash=child_token_hash,
                token_expires_at=expires,
            )
            await self._repo.create(child)
            case = await self._cases.get(row.case_id)
            if case:
                await self._executive_mail.dispatch_child_escalation(
                    case=case,
                    child=child,
                    parent=row,
                    wire_token=wire,
                    manager_comment=trimmed_comment,
                    responder_email=responder,
                )
                message = f"Escalated to {target_email}. A new email has been sent."

        elif action == "request_info":
            row.status = "approved"
            row.responded_at = now
            row.responded_by_email = responder
            row.manager_comment = trimmed_comment
            case = await self._cases.get(row.case_id)
            if case:
                meta = dict(case.workflow_metadata or {})
                meta["manager_decision"] = "request_info"
                meta["clarification_pending"] = True
                meta["escalation_pending"] = False
                if trimmed_comment:
                    meta["manager_comment"] = trimmed_comment
                case.workflow_metadata = meta
                case.status = "on_hold"

                email = await self._resolve_email(row, case)
                missing_fields = (row.context or {}).get("missing_fields") or []
                if email is not None:
                    await self._executive_mail.queue_clarification_request(
                        case=case,
                        email=email,
                        missing_fields=missing_fields,
                        manager_comment=trimmed_comment,
                    )

                await self._executive_mail.log_step(
                    action="manager_request_info",
                    summary=f"[{case.case_number}] Manager requested more information from client",
                    actor_type="manager",
                    actor_name=responder,
                    mailbox_id=row.originating_mailbox_id,
                    case_id=case.id,
                    email_id=email.id if email else None,
                    metadata={
                        "escalation_id": str(row.id),
                        "missing_fields": missing_fields,
                        "manager_comment": trimmed_comment,
                    },
                )
                message = "Request for more information sent to the client."

        await self._session.commit()
        return EscalationRespondResult(
            escalation_id=row.id,
            case_id=row.case_id,
            action=action,
            status=row.status,
            child_escalation_id=child_id,
            target_email=target_email,
            responded_at=row.responded_at or now,
            manager_comment=trimmed_comment,
            message=message,
        )

    async def _resolve_email(self, row: CaseEscalation, case):
        if row.email_id:
            return await self._cases.get_email(row.email_id)
        if case.email_id:
            return await self._cases.get_email(case.email_id)
        return None
