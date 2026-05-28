"""Expense Worker handlers — `19` §4."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.hermes import HermesClient, HermesError
from app.models.case import Case
from app.models.expense import ExpenseClaim, ExpenseLineItem
from app.models.mail import Email, EmailAttachment
from app.models.user import User
from app.repositories.case import CaseRepository
from app.repositories.expense import ExpenseRepository
from app.repositories.ledger import LedgerRepository
from app.repositories.travel import TravelRequestRepository
from app.schemas.hermes import ExtractExpenseClaimRequest
from app.services.approval_service import ApprovalService
from app.services.email_context import ensure_attachment_texts
from app.services.executive_mail_service import ExecutiveMailService
from app.services.expense_policy_evaluator import evaluate_expense_claim
from app.services.binding_authority_service import BindingAuthorityService, apply_binding_sla
from workers.common.binding_authority_escalation import route_binding_authority_escalation
from workers.common.gl_period_check import ensure_gl_period_allows_posting
from workers.common.policy_escalation import route_travel_request_escalation
from workers.common.parsing_confirmation import (
    expense_claim_to_confirmation_fields,
    pause_for_parsing_confirmation,
    requires_parsing_confirmation,
)
from workers.common.processing_failure import route_processing_failure
from workers.common.travel_detection import claim_requires_travel_request

logger = logging.getLogger(__name__)

EXPENSE_CASE_TYPES = frozenset({"expense_claim"})
DEFAULT_EXPENSE_ACCOUNT = "5500"
DEFAULT_PAYABLE_ACCOUNT = "2000"


class ExpenseWorkerService:
    def __init__(self, session: AsyncSession, hermes: HermesClient | None = None) -> None:
        self._session = session
        self._hermes = hermes or HermesClient()
        self._cases = CaseRepository(session)
        self._expense = ExpenseRepository(session)
        self._travel = TravelRequestRepository(session)
        self._ledger = LedgerRepository(session)
        self._approvals = ApprovalService(session)
        self._executive_mail = ExecutiveMailService(session)

    async def process_accounts_message(self, message: dict) -> dict:
        if message.get("case_type") != "expense_claim":
            return {"status": "skipped", "reason": "not_expense_claim"}
        case_id = UUID(message["case_id"])
        case = await self._load_case(case_id)
        if case is None:
            return {"status": "skipped", "reason": "case_not_found"}
        if case.status in ("posted", "completed", "pending_approval"):
            return {"status": "skipped", "reason": "terminal_state", "case_status": case.status}

        email = None
        if case.email_id:
            result = await self._session.execute(
                select(Email).where(Email.id == case.email_id)
            )
            email = result.scalar_one_or_none()

        if message.get("parsing_confirmed"):
            claim = await self._expense.get_claim_by_case(case.id)
            if claim is None:
                return {"status": "skipped", "reason": "no_claim_data"}
        else:
            claim = await self._expense.get_claim_by_case(case.id)
            if claim is None:
                claim = await self._bootstrap_from_email(case)
                if claim is None:
                    return {"status": "manual_review", "case_id": str(case.id), "reason": "no_claim_data"}

        case.status = "processing"
        claim.status = "processing"
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="processing_started",
            from_status="classified",
            to_status="processing",
            actor="expense-worker",
            description="Expense Worker began claim processing",
        )

        await self._resolve_gl_accounts(claim)
        policies = await self._expense.list_active_policies()
        confidence = float(claim.extraction_confidence or 0.85)
        evaluation = evaluate_expense_claim(
            line_items=claim.line_items,
            total_claimed=claim.total_claimed,
            confidence=confidence,
            policies=policies,
            submission_date=claim.submission_date,
            claim_period_to=claim.claim_period_to,
        )
        claim.policy_violations = evaluation.violations
        claim.risk_flags = evaluation.risk_flags
        claim.approval_tier = evaluation.tier
        claim.stp_eligible = evaluation.stp_eligible

        case.amount_value = claim.total_claimed
        case.amount_currency = claim.currency
        case.risk_flags = evaluation.risk_flags
        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "worker": "expense-worker",
            "policy_tier": evaluation.tier,
            "stp": evaluation.stp_eligible,
            "line_item_count": len(claim.line_items),
        }

        if confidence < 0.70 or not claim.line_items:
            return await self._finish_manual_review(case, claim, "INCOMPLETE_EXTRACTION")

        if not message.get("parsing_confirmed"):
            await self._cases.add_timeline(
                case_id=case.id,
                event_type="parsing_completed",
                from_status="processing",
                to_status="processing",
                actor="expense-worker",
                description=f"Expense extraction OK — confidence {confidence:.2f}",
                metadata={"confidence": confidence},
            )
            if await requires_parsing_confirmation(self._session, case, email):
                return await pause_for_parsing_confirmation(
                    self._session,
                    case=case,
                    email=email,
                    extracted_fields=expense_claim_to_confirmation_fields(claim),
                    extraction_confidence=confidence,
                    actor_name="expense-worker",
                )

        if claim_requires_travel_request(claim.line_items):
            travel = await self._travel.find_approved_for_period(
                employee_id=claim.claimant_id,
                period_from=claim.claim_period_from,
                period_to=claim.claim_period_to,
            )
            if travel is None:
                travel_validation = {
                    "requires_travel_request": True,
                    "travel_request_found": False,
                    "claim_period_from": str(claim.claim_period_from),
                    "claim_period_to": str(claim.claim_period_to),
                }
                claim_summary = {
                    "claimant_name": claim.claimant_name,
                    "total_claimed": str(claim.total_claimed),
                    "currency": claim.currency,
                    "purpose": claim.purpose,
                }
                email = None
                if case.email_id:
                    result = await self._session.execute(
                        select(Email).where(Email.id == case.email_id)
                    )
                    email = result.scalar_one_or_none()
                return await route_travel_request_escalation(
                    self._session,
                    case,
                    email=email,
                    claim_summary=claim_summary,
                    extraction_confidence=confidence,
                    actor_name="expense-worker",
                    travel_validation=travel_validation,
                )
            case.workflow_metadata = {
                **(case.workflow_metadata or {}),
                "travel_request_validation": {
                    "requires_travel_request": True,
                    "travel_request_found": True,
                    "travel_request_number": travel.request_number,
                },
            }

        posting_date = claim.claim_period_to or claim.claim_period_from or date.today()
        email = None
        if case.email_id:
            result = await self._session.execute(
                select(Email).where(Email.id == case.email_id)
            )
            email = result.scalar_one_or_none()
        period_block = await ensure_gl_period_allows_posting(
            self._session,
            case,
            message,
            posting_date=posting_date,
            email=email,
            actor_name="expense-worker",
            expense=True,
        )
        if period_block:
            claim.status = "manual_review"
            await self._cases.add_timeline(
                case_id=case.id,
                event_type="processing_completed",
                from_status="processing",
                to_status="on_hold",
                actor="expense-worker",
                description="Blocked by closed GL period",
            )
            await self._session.flush()
            return period_block

        entry_id = await self._create_reimbursement_journal(
            case, claim, posted=claim.stp_eligible
        )
        if entry_id is None:
            return await self._finish_manual_review(case, claim, "ACCOUNT_NOT_FOUND")

        claim.journal_entry_id = entry_id
        if claim.stp_eligible:
            claim.status = "posted"
            claim.total_approved = claim.total_claimed
            case.status = "posted"
            case.completed_at = datetime.now(UTC)
        else:
            claim.status = "pending_approval"
            case.status = "pending_approval"
            case.current_approval_tier = evaluation.tier
            await self._approvals.request_approval(
                case_id=case.id,
                tier=tier,
                amount_value=claim.total_claimed,
                amount_currency=claim.currency,
                comments=f"Expense claim {claim.case_number}",
            )
            if tier >= 2:
                claim_summary = {
                    "claimant_name": claim.claimant_name,
                    "total_claimed": str(claim.total_claimed),
                    "currency": claim.currency,
                    "purpose": claim.purpose,
                }
                await route_binding_authority_escalation(
                    self._session,
                    case,
                    email=email,
                    tier=tier,
                    amount=claim.total_claimed,
                    currency=claim.currency or "SGD",
                    extracted_fields=claim_summary,
                    extraction_confidence=confidence,
                    actor_name="expense-worker",
                )

        await self._cases.add_timeline(
            case_id=case.id,
            event_type="processing_completed",
            from_status="processing",
            to_status=case.status,
            actor="expense-worker",
            description=f"Expense claim processed — {len(claim.line_items)} line(s), SGD {claim.total_claimed}",
            metadata={
                "stp": evaluation.stp_eligible,
                "approval_tier": evaluation.tier,
                "journal_entry_id": str(entry_id),
            },
        )
        await self._session.flush()
        return {
            "status": case.status,
            "case_id": str(case.id),
            "expense_claim_id": str(claim.id),
            "stp": evaluation.stp_eligible,
        }

    async def _load_case(self, case_id: UUID) -> Case | None:
        result = await self._session.execute(
            select(Case).options(selectinload(Case.workflow_instance)).where(Case.id == case_id)
        )
        return result.scalar_one_or_none()

    async def _bootstrap_from_email(self, case: Case) -> ExpenseClaim | None:
        email = await self._cases.get_email(case.email_id) if case.email_id else None
        body = ""
        attachments: list[dict] = []
        if email:
            body = email.body_text or email.body_preview or ""
            await ensure_attachment_texts(self._session, email.id, hermes=self._hermes)
            result = await self._session.execute(
                select(EmailAttachment).where(EmailAttachment.email_id == email.id).limit(5)
            )
            for att in result.scalars().all():
                attachments.append(
                    {
                        "attachment_id": str(att.id),
                        "filename": att.filename,
                        "extracted_text": att.extracted_text or "",
                    }
                )

        claimant = await self._resolve_claimant(case, email)
        if claimant is None:
            case.status = "manual_review"
            return None

        try:
            extraction = await self._hermes.extract_expense_claim(
                ExtractExpenseClaimRequest(
                    email_id=str(case.email_id or case.id),
                    email_body=body,
                    attachments=attachments,
                    claimant_hint=claimant.display_name,
                    department_hint=claimant.department,
                    expense_categories=[
                        "meals",
                        "transport",
                        "accommodation",
                        "entertainment",
                        "office_supplies",
                        "other",
                    ],
                )
            )
        except HermesError:
            return None

        if not extraction.line_items:
            return None

        period_from = extraction.claim_period_from or date.today()
        period_to = extraction.claim_period_to or period_from
        claim = ExpenseClaim(
            case_id=case.id,
            case_number=case.case_number,
            claimant_id=claimant.id,
            claimant_name=claimant.display_name,
            submission_date=date.today(),
            claim_period_from=period_from,
            claim_period_to=period_to,
            purpose=extraction.purpose,
            department=claimant.department,
            currency=extraction.currency or "SGD",
            total_claimed=Decimal("0"),
            status="processing",
            submitted_via="email",
            extraction_confidence=Decimal(str(extraction.confidence_score)),
            workflow_metadata={"missing_fields": extraction.missing_fields},
        )
        total = Decimal("0")
        for idx, item in enumerate(extraction.line_items, start=1):
            amount = Decimal(item.amount_claimed or "0")
            total += amount
            claim.line_items.append(
                ExpenseLineItem(
                    line_number=idx,
                    expense_date=item.expense_date or period_from,
                    category=item.category or "other",
                    description=item.description or "Expense",
                    merchant=item.merchant,
                    currency=item.currency or claim.currency,
                    amount_claimed=amount,
                    amount_sgd=amount,
                )
            )
        claim.total_claimed = total
        await self._expense.add_claim(claim)
        return claim

    async def _resolve_claimant(self, case: Case, email: Email | None) -> User | None:
        if email and email.from_address:
            result = await self._session.execute(
                select(User).where(User.email == email.from_address, User.status == "active").limit(1)
            )
            user = result.scalar_one_or_none()
            if user:
                return user
        return None

    async def _resolve_gl_accounts(self, claim: ExpenseClaim) -> None:
        expense_acct = await self._ledger.get_account_by_code(DEFAULT_EXPENSE_ACCOUNT)
        for item in claim.line_items:
            if expense_acct:
                item.gl_account_id = expense_acct.id
            if item.currency != "SGD" and not item.exchange_rate:
                claim.risk_flags = list(claim.risk_flags or []) + ["fx_missing_rate"]

    async def _create_reimbursement_journal(
        self, case: Case, claim: ExpenseClaim, *, posted: bool
    ) -> UUID | None:
        expense = await self._ledger.get_account_by_code(DEFAULT_EXPENSE_ACCOUNT)
        payable = await self._ledger.get_account_by_code(DEFAULT_PAYABLE_ACCOUNT)
        if not expense or not payable:
            return None
        total = claim.total_claimed
        entry = await self._ledger.create_journal_entry(
            case_id=case.id,
            case_number=case.case_number,
            status="posted" if posted else "draft",
            entry_date=claim.claim_period_to,
            description=f"Expense reimbursement — {claim.claimant_name}",
            reference=claim.case_number,
            currency=claim.currency,
            total=total,
            posted=posted,
        )
        await self._ledger.add_line(
            entry=entry,
            line_number=1,
            account_id=expense.id,
            debit=total,
            credit=Decimal("0"),
            description="Employee expense",
        )
        await self._ledger.add_line(
            entry=entry,
            line_number=2,
            account_id=payable.id,
            debit=Decimal("0"),
            credit=total,
            description="Employee payable",
        )
        return entry.id

    async def _finish_manual_review(
        self, case: Case, claim: ExpenseClaim, error_type: str
    ) -> dict:
        claim.status = "manual_review"
        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "error_type": error_type,
        }
        email = None
        if case.email_id:
            result = await self._session.execute(
                select(Email).where(Email.id == case.email_id)
            )
            email = result.scalar_one_or_none()
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="processing_completed",
            from_status="processing",
            to_status="on_hold",
            actor="expense-worker",
            description=f"Escalated to manager: {error_type}",
        )
        return await route_processing_failure(
            self._session,
            case,
            email=email,
            reason_code=error_type,
            summary="Expense claim requires manager review",
            error_detail=error_type,
            actor_name="expense-worker",
        )
