"""Expense Worker handlers — Expense Process document 7-step validation (`0.14.45`)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.hermes import HermesClient, HermesError
from app.models.case import Case, Counterparty
from app.models.expense import ExpenseClaim, ExpenseLineItem
from app.models.mail import Email, EmailAttachment
from app.repositories.case import CaseRepository
from app.repositories.expense import ExpenseRepository
from app.repositories.ledger import LedgerRepository
from app.schemas.hermes import ExtractExpenseClaimRequest
from app.services.approval_service import ApprovalService
from app.services.binding_authority_service import BindingAuthorityService, apply_binding_sla
from app.services.email_context import ensure_attachment_texts
from app.services.executive_mail_service import ExecutiveMailService
from workers.common.ap_validation import extract_sender_validation
from workers.common.binding_authority_escalation import route_binding_authority_escalation
from workers.common.expense_validation import (
    check_expense_duplicate,
    check_expense_policy,
    expense_account_code_for_category,
    expense_extraction_to_fields,
    expense_parsing_missing,
    lookup_staff_by_email,
    normalize_expense_category,
    parse_document_date,
    receipt_validity_issues,
    resolve_expense_sgd_amount,
)
from workers.common.gl_period_check import ensure_gl_period_allows_posting
from workers.common.parsing_confirmation import (
    expense_fields_to_confirmation,
    pause_for_parsing_confirmation,
    requires_parsing_confirmation,
)
from workers.common.processing_failure import route_processing_failure

logger = logging.getLogger(__name__)

EXPENSE_CASE_TYPES = frozenset({"expense_claim"})
STAFF_PAYABLE_ACCOUNT_CODE = "2110"
GST_INPUT_ACCOUNT_CODE = "1190"

_REASON_PARSING = "EXP_PARSING_INCOMPLETE"
_REASON_DUPLICATE = "EXP_DUPLICATE"
_REASON_SUBMITTER_NOT_FOUND = "EXP_SUBMITTER_NOT_FOUND"
_REASON_SUBMITTER_INACTIVE = "EXP_SUBMITTER_INACTIVE"
_REASON_POLICY = "EXP_POLICY_EXCEEDED"
_REASON_RECEIPT = "EXP_RECEIPT_INVALID"
_REASON_CURRENCY = "EXP_CURRENCY_CONVERSION_REQUIRED"
_REASON_COA = "EXP_COA_NOT_FOUND"

EXP_OVERRIDE_KEYS: dict[str, str] = {
    _REASON_PARSING: "override_parsing",
    _REASON_DUPLICATE: "override_duplicate",
    _REASON_SUBMITTER_INACTIVE: "override_submitter",
    _REASON_POLICY: "override_policy",
    _REASON_RECEIPT: "override_receipt",
    _REASON_COA: "override_coa",
}

_RESUME_STEP_ORDER: tuple[str, ...] = ("2A", "2B", "2C", "2D", "2E", "2F", "2G")
REASON_TO_RESUME_STEP: dict[str, str] = {
    _REASON_PARSING: "2A",
    _REASON_DUPLICATE: "2B",
    _REASON_SUBMITTER_NOT_FOUND: "2C",
    _REASON_SUBMITTER_INACTIVE: "2C",
    _REASON_POLICY: "2D",
    _REASON_RECEIPT: "2E",
    _REASON_CURRENCY: "2F",
    _REASON_COA: "2G",
}


def _update_meta(case: Case, updates: dict) -> None:
    meta = dict(case.workflow_metadata or {})
    meta.update(updates)
    case.workflow_metadata = meta


def _resume_step_reached(resume_from: str | None, step_id: str) -> bool:
    if resume_from is None:
        return True
    return _RESUME_STEP_ORDER.index(step_id) >= _RESUME_STEP_ORDER.index(resume_from)


def _pop_resume_from_step(case: Case) -> str | None:
    meta = dict(case.workflow_metadata or {})
    step = meta.pop("resume_from_step", None)
    if step is not None:
        case.workflow_metadata = meta
    return str(step) if step else None


class ExpenseWorkerService:
    def __init__(self, session: AsyncSession, hermes: HermesClient | None = None) -> None:
        self._session = session
        self._hermes = hermes or HermesClient()
        self._cases = CaseRepository(session)
        self._expense = ExpenseRepository(session)
        self._ledger = LedgerRepository(session)
        self._approvals = ApprovalService(session)

    async def process_accounts_message(self, message: dict) -> dict:
        if message.get("case_type") != "expense_claim":
            return {"status": "skipped", "reason": "not_expense_claim"}

        case_id = UUID(message["case_id"])
        case = await self._load_case(case_id)
        if case is None:
            return {"status": "skipped", "reason": "case_not_found"}
        if case.status in ("posted", "completed", "case_closed", "case_rejected"):
            return {"status": "skipped", "reason": "terminal_state", "case_status": case.status}

        email = await self._email_for_case(case)
        resume_from = _pop_resume_from_step(case)
        meta = case.workflow_metadata or {}
        overrides: dict = meta.get("exp_step_overrides") or {}

        if resume_from:
            await self._add_timeline(
                case,
                "processing_resumed",
                description=f"Resuming expense validation from step {resume_from}",
                metadata={"resume_from_step": resume_from},
            )

        use_stored = bool(message.get("parsing_confirmed") or resume_from)

        if use_stored:
            extracted = dict(meta.get("extracted_fields") or {})
            confidence_f = float(meta.get("extraction_confidence") or case.confidence_score or 0)
            await self._start_processing(case)
        else:
            extracted, confidence_f = await self._extract_from_email(case, email)
            if extracted is None:
                extracted = {}
                confidence_f = 0.0
                return await pause_for_parsing_confirmation(
                    self._session,
                    case=case,
                    email=email,
                    extracted_fields=expense_fields_to_confirmation(extracted),
                    extraction_confidence=confidence_f,
                    actor_name="expense-worker",
                )

        sender_val = extract_sender_validation(
            email.subject if email else None,
            email.body_text if email else None,
        )
        if extracted.get("sender_validated") is None:
            extracted["sender_validated"] = (
                "true" if sender_val.get("sender_validated") else "false"
            )

        # ── Step 2A: Parsing ─────────────────────────────────────────
        if _resume_step_reached(resume_from, "2A") and not overrides.get("override_parsing"):
            if resume_from is None and not use_stored:
                if await requires_parsing_confirmation(self._session, case, email):
                    return await pause_for_parsing_confirmation(
                        self._session,
                        case=case,
                        email=email,
                        extracted_fields=expense_fields_to_confirmation(extracted),
                        extraction_confidence=confidence_f,
                        actor_name="expense-worker",
                    )

            missing = expense_parsing_missing(extracted)
            if missing or confidence_f < 0.70:
                missing_label = ", ".join(missing) if missing else "low extraction confidence"
                summary = (
                    f"Unable to parse all required expense details for {case.case_number}. "
                    f"Missing: {missing_label}. "
                    f"Please advise: a) provide missing details quoting Case ID {case.case_number}, "
                    f"or b) ask submitter to resubmit quoting Case ID {case.case_number}."
                )
                _update_meta(
                    case,
                    {
                        "extracted_fields": extracted,
                        "extraction_confidence": confidence_f,
                        "missing_fields": missing,
                        "reason_code": _REASON_PARSING,
                    },
                )
                await self._add_timeline(
                    case,
                    "parsing_failed",
                    description=f"Parsing failed: {missing_label}",
                    metadata={"missing_fields": missing},
                )
                return await self._escalate_step(
                    case,
                    email,
                    reason_code=_REASON_PARSING,
                    summary=summary,
                    extracted_fields=extracted,
                    extraction_confidence=confidence_f,
                    missing_fields=missing,
                )

        if _resume_step_reached(resume_from, "2A"):
            await self._add_timeline(
                case,
                "parsing_completed",
                description=f"Expense parsing OK — confidence {confidence_f:.2f}",
            )

        _update_meta(case, {"extracted_fields": extracted, "extraction_confidence": confidence_f})

        staff: Counterparty | None = None
        staff_raw = (case.workflow_metadata or {}).get("staff_counterparty_id")
        if staff_raw:
            try:
                staff = await self._session.get(Counterparty, UUID(str(staff_raw)))
            except (TypeError, ValueError):
                staff = None

        # ── Step 2B: Duplicate ─────────────────────────────────────────
        if _resume_step_reached(resume_from, "2B") and not overrides.get("override_duplicate"):
            merchant = str(extracted.get("merchant_name") or "")
            doc_num = extracted.get("document_number")
            doc_date = parse_document_date(extracted)
            try:
                total_dec = Decimal(str(extracted.get("total_amount") or "0"))
            except Exception:
                total_dec = None
            if merchant:
                is_dup, dup_num = await check_expense_duplicate(
                    self._session,
                    merchant_name=merchant,
                    document_number=str(doc_num) if doc_num else None,
                    total_amount=total_dec,
                    document_date=doc_date,
                    exclude_case_id=case.id,
                )
                if is_dup:
                    summary = (
                        f"Duplicate expense detected for {case.case_number}. "
                        f"Matches case {dup_num}. Please advise."
                    )
                    return await self._escalate_step(
                        case,
                        email,
                        reason_code=_REASON_DUPLICATE,
                        summary=summary,
                        extracted_fields=extracted,
                    )

        if _resume_step_reached(resume_from, "2B"):
            await self._add_timeline(case, "duplicate_checked", description="No duplicate found")

        # ── Step 2C: Submitter (staff counterparty) ────────────────────
        if _resume_step_reached(resume_from, "2C"):
            sender_email = (email.from_address if email else "") or ""
            staff, staff_status = await lookup_staff_by_email(self._session, sender_email)
            if staff_status == "not_found":
                summary = (
                    f"Submitter {sender_email} is not registered as staff. Staff must be added "
                    "as a counterparty (type: Staff) with contact email before expense claims "
                    "can be processed."
                )
                return await self._escalate_step(
                    case,
                    email,
                    reason_code=_REASON_SUBMITTER_NOT_FOUND,
                    summary=summary,
                    extracted_fields=extracted,
                    include_escalate=False,
                )
            if staff_status == "inactive":
                summary = (
                    f"Staff member {staff.name if staff else sender_email} is inactive. "
                    "Please advise: a) reactivate and proceed, or b) reject."
                )
                return await self._escalate_step(
                    case,
                    email,
                    reason_code=_REASON_SUBMITTER_INACTIVE,
                    summary=summary,
                    extracted_fields=extracted,
                )
            if staff is not None:
                _update_meta(case, {"staff_counterparty_id": str(staff.id)})
                case.counterparty_id = staff.id
                case.counterparty_name = staff.name
                await self._add_timeline(
                    case,
                    "submitter_verified",
                    description=f"Submitter verified: {staff.name}",
                    metadata={"staff_counterparty_id": str(staff.id)},
                )

        # ── Step 2D: Policy ────────────────────────────────────────────
        if _resume_step_reached(resume_from, "2D") and not overrides.get("override_policy"):
            policies = await self._expense.list_active_policies()
            within, category, limit = check_expense_policy(
                extracted=extracted,
                policies=policies,
                submission_date=date.today(),
            )
            if not within:
                try:
                    amount = Decimal(str(extracted.get("sgd_amount") or extracted.get("total_amount") or "0"))
                except Exception:
                    amount = Decimal("0")
                limit_str = f"{limit:,.2f}" if limit else "policy"
                summary = (
                    f"Expense of {amount:,.2f} SGD for {category} exceeds policy limit of "
                    f"{limit_str} SGD. Please advise: a) reject, or b) accept with override reason."
                )
                return await self._escalate_step(
                    case,
                    email,
                    reason_code=_REASON_POLICY,
                    summary=summary,
                    extracted_fields=extracted,
                )

        if _resume_step_reached(resume_from, "2D"):
            await self._add_timeline(case, "policy_checked", description="Expense policy checked")

        # ── Step 2E: Receipt validity ──────────────────────────────────
        if _resume_step_reached(resume_from, "2E") and not overrides.get("override_receipt"):
            issues = receipt_validity_issues(extracted)
            if issues:
                summary = (
                    "Receipt is invalid or older than 90 days. Please advise: a) reject and ask "
                    f"submitter to resubmit with valid receipt quoting Case ID {case.case_number}, "
                    "or b) accept with override reason."
                )
                return await self._escalate_step(
                    case,
                    email,
                    reason_code=_REASON_RECEIPT,
                    summary=summary,
                    extracted_fields=extracted,
                )

        if _resume_step_reached(resume_from, "2E"):
            await self._add_timeline(case, "receipt_validated", description="Receipt validated")

        # ── Step 2F: Currency ──────────────────────────────────────────
        if _resume_step_reached(resume_from, "2F"):
            sgd_amount, extracted, needs_fx = resolve_expense_sgd_amount(extracted)
            if needs_fx:
                currency = str(extracted.get("currency") or "foreign")
                summary = (
                    f"Receipt is in {currency}. Please provide the exchange rate "
                    f"(1 {currency} = ? SGD)."
                )
                return await self._escalate_step(
                    case,
                    email,
                    reason_code=_REASON_CURRENCY,
                    summary=summary,
                    extracted_fields=extracted,
                )
            extracted["sgd_amount"] = str(sgd_amount)
            _update_meta(case, {"extracted_fields": extracted})
            await self._add_timeline(
                case,
                "currency_converted",
                description=f"SGD amount {sgd_amount:,.2f}",
            )

        # ── Step 2G: COA mapping ───────────────────────────────────────
        expense_account = await self._resolve_expense_account(extracted)

        if _resume_step_reached(resume_from, "2G") and not overrides.get("override_coa"):
            if expense_account is None:
                category = normalize_expense_category(extracted.get("expense_category"))
                summary = (
                    f"Could not map expense category {category} to a GL account. "
                    "Please configure the chart of accounts."
                )
                return await self._escalate_step(
                    case,
                    email,
                    reason_code=_REASON_COA,
                    summary=summary,
                    extracted_fields=extracted,
                )

        await self._add_timeline(
            case,
            "coa_mapped",
            description=f"Expense account {expense_account.account_code if expense_account else 'unknown'}",
            metadata={"expense_account_code": expense_account.account_code if expense_account else None},
        )

        claim = await self._ensure_claim(case, extracted, staff)
        sgd_amount = Decimal(str(extracted.get("sgd_amount") or extracted.get("total_amount") or "0"))
        try:
            gst = Decimal(str(extracted.get("gst_amount") or "0"))
        except Exception:
            gst = Decimal("0")

        case.amount_value = sgd_amount
        case.amount_currency = "SGD"

        posting_date = parse_document_date(extracted) or date.today()
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
            await self._session.flush()
            return period_block

        # ── Step 3: Journal + binding authority ────────────────────────
        binding = BindingAuthorityService(self._session)
        tier, thresholds = await binding.evaluate_tier(
            amount=sgd_amount,
            confidence=confidence_f,
            risk_flags=[],
            case_type=case.type,
        )
        apply_binding_sla(case, tier, thresholds)
        case.current_approval_tier = tier if tier >= 2 else None

        staff_id = (case.workflow_metadata or {}).get("staff_counterparty_id")
        payable_code = STAFF_PAYABLE_ACCOUNT_CODE
        if staff and staff.extra_metadata.get("payable_gl_code"):
            payable_code = str(staff.extra_metadata["payable_gl_code"])
        payable_account = await self._ledger.get_account_by_code(payable_code)
        gst_account = await self._ledger.get_account_by_code(GST_INPUT_ACCOUNT_CODE) if gst > 0 else None

        if payable_account is None:
            return await self._route_failure(case, email, "ACCOUNT_NOT_FOUND", "Staff payable account missing")

        auto_post = tier <= 1
        journal_id = await self._create_expense_journal(
            case,
            claim,
            sgd_amount,
            gst,
            expense_account=expense_account,
            gst_account=gst_account,
            payable_account=payable_account,
            posted=auto_post,
            posting_date=posting_date,
        )
        if journal_id is None:
            return await self._escalate_step(
                case,
                email,
                reason_code=_REASON_COA,
                summary="Journal entry could not be created",
                extracted_fields=extracted,
            )

        claim.journal_entry_id = journal_id
        _update_meta(case, {"journal_entry_id": str(journal_id), "policy_tier": tier})

        if auto_post:
            claim.status = "posted"
            claim.total_approved = sgd_amount
            case.status = "case_closed"
            case.completed_at = datetime.now(UTC)
            await self._add_timeline(
                case,
                "journal_posted",
                to_status="case_closed",
                description="Tier 1 auto-posted expense journal",
                metadata={"journal_entry_id": str(journal_id)},
            )
        else:
            claim.status = "pending_approval"
            case.status = "journal_pending_approval"
            await self._add_timeline(
                case,
                "journal_entry_created",
                to_status="journal_pending_approval",
                description=f"Draft journal — Tier {tier} approval required",
                metadata={"journal_entry_id": str(journal_id), "tier": tier},
            )
            await self._approvals.request_approval(
                case_id=case.id,
                tier=tier,
                amount_value=sgd_amount,
                amount_currency="SGD",
                comments=f"Expense claim {claim.case_number}",
            )
            await route_binding_authority_escalation(
                self._session,
                case,
                email=email,
                tier=tier,
                amount=sgd_amount,
                currency="SGD",
                extracted_fields=extracted,
                extraction_confidence=confidence_f,
                actor_name="expense-worker",
            )

        await self._session.flush()
        return {
            "status": case.status,
            "case_id": str(case.id),
            "journal_entry_id": str(journal_id),
            "tier": tier,
        }

    async def _extract_from_email(
        self, case: Case, email: Email | None
    ) -> tuple[dict | None, float]:
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
        try:
            extraction = await self._hermes.extract_expense_claim(
                ExtractExpenseClaimRequest(
                    email_id=str(case.email_id or case.id),
                    email_body=body,
                    attachments=attachments,
                    expense_categories=list(
                        {
                            "meals",
                            "travel",
                            "accommodation",
                            "entertainment",
                            "office_supplies",
                            "government_fees",
                            "other",
                        }
                    ),
                )
            )
        except HermesError:
            return None, 0.0
        if not extraction.line_items:
            return None, float(extraction.confidence_score or 0)
        out = extraction
        flat = {
            "document_type": "receipt",
            "document_date": str(out.line_items[0].expense_date or out.claim_period_to or ""),
            "document_number": None,
            "merchant_name": out.line_items[0].merchant,
            "total_amount": str(out.line_items[0].amount_claimed),
            "currency": out.currency,
            "expense_category": out.line_items[0].category,
            "business_purpose": out.purpose,
            "gst_amount": None,
        }
        total = sum(Decimal(li.amount_claimed or "0") for li in out.line_items)
        flat["total_amount"] = str(total)
        sender_val = extract_sender_validation(
            email.subject if email else None,
            email.body_text if email else None,
        )
        fields = expense_extraction_to_fields(flat, sender_val=sender_val)
        return fields, float(extraction.confidence_score or 0.85)

    async def _ensure_claim(
        self,
        case: Case,
        extracted: dict,
        staff: Counterparty | None,
    ) -> ExpenseClaim:
        claim = await self._expense.get_claim_by_case(case.id)
        if claim is None:
            claim = ExpenseClaim(
                case_id=case.id,
                case_number=case.case_number,
                claimant_id=case.assigned_to,
                claimant_name=staff.name if staff else case.counterparty_name or "Staff",
                submission_date=date.today(),
                claim_period_from=parse_document_date(extracted) or date.today(),
                claim_period_to=parse_document_date(extracted) or date.today(),
                purpose=extracted.get("business_purpose"),
                currency=str(extracted.get("currency") or "SGD"),
                total_claimed=Decimal(str(extracted.get("total_amount") or "0")),
                status="processing",
                submitted_via="email",
            )
            await self._expense.add_claim(claim)
        claim.total_claimed = Decimal(str(extracted.get("sgd_amount") or extracted.get("total_amount") or "0"))
        claim.currency = "SGD"
        if not claim.line_items:
            gl_uuid = self._parse_gl_account_id(extracted.get("gl_account_id"))
            claim.line_items.append(
                ExpenseLineItem(
                    line_number=1,
                    expense_date=parse_document_date(extracted) or date.today(),
                    category=normalize_expense_category(extracted.get("expense_category")),
                    description=str(extracted.get("business_purpose") or "Expense"),
                    merchant=extracted.get("merchant_name"),
                    currency="SGD",
                    amount_claimed=claim.total_claimed,
                    amount_sgd=claim.total_claimed,
                    gl_account_id=gl_uuid,
                )
            )
        return claim

    async def _resolve_expense_account(self, extracted: dict):
        gl_uuid = self._parse_gl_account_id(extracted.get("gl_account_id"))
        if gl_uuid is not None:
            account = await self._ledger.get_account_by_id(gl_uuid)
            if account is not None:
                return account
        category = normalize_expense_category(extracted.get("expense_category"))
        expense_code = expense_account_code_for_category(category)
        account = await self._ledger.get_account_by_code(expense_code)
        if account is None:
            account = await self._ledger.get_account_by_code("5500")
        return account

    @staticmethod
    def _parse_gl_account_id(raw: object | None) -> UUID | None:
        if raw is None or str(raw).strip() == "":
            return None
        try:
            return UUID(str(raw).strip())
        except (TypeError, ValueError):
            return None

    async def _create_expense_journal(
        self,
        case: Case,
        claim: ExpenseClaim,
        amount: Decimal,
        gst: Decimal,
        *,
        expense_account,
        gst_account,
        payable_account,
        posted: bool,
        posting_date: date,
    ) -> UUID | None:
        if expense_account is None or payable_account is None:
            return None
        net = amount - gst if gst < amount else amount
        status = "posted" if posted else "draft"
        entry = await self._ledger.create_journal_entry(
            case_id=case.id,
            case_number=case.case_number,
            status=status,
            entry_date=posting_date,
            description=f"Expense claim — {claim.claimant_name}",
            reference=claim.case_number,
            currency="SGD",
            total=amount,
            posted=posted,
        )
        line_no = 1
        await self._ledger.add_line(
            entry=entry,
            line_number=line_no,
            account_id=expense_account.id,
            debit=net,
            credit=Decimal("0"),
            description="Employee expense",
        )
        line_no += 1
        if gst > 0 and gst_account:
            await self._ledger.add_line(
                entry=entry,
                line_number=line_no,
                account_id=gst_account.id,
                debit=gst,
                credit=Decimal("0"),
                description="GST input tax",
            )
            line_no += 1
        await self._ledger.add_line(
            entry=entry,
            line_number=line_no,
            account_id=payable_account.id,
            debit=Decimal("0"),
            credit=amount,
            description="Due to staff",
        )
        return entry.id

    async def _load_case(self, case_id: UUID) -> Case | None:
        result = await self._session.execute(
            select(Case).options(selectinload(Case.workflow_instance)).where(Case.id == case_id)
        )
        return result.scalar_one_or_none()

    async def _email_for_case(self, case: Case) -> Email | None:
        if not case.email_id:
            return None
        result = await self._session.execute(select(Email).where(Email.id == case.email_id))
        return result.scalar_one_or_none()

    async def _start_processing(self, case: Case) -> None:
        from_status = case.status
        case.status = "processing"
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="processing_started",
            from_status=from_status,
            to_status="processing",
            actor="expense-worker",
            description="Expense Worker began claim processing",
        )

    async def _add_timeline(
        self,
        case: Case,
        event_type: str,
        *,
        from_status: str | None = None,
        to_status: str | None = None,
        description: str = "",
        metadata: dict | None = None,
    ) -> None:
        await self._cases.add_timeline(
            case_id=case.id,
            event_type=event_type,
            from_status=from_status or case.status,
            to_status=to_status,
            actor="expense-worker",
            description=description,
            metadata=metadata or {},
        )

    async def _escalate_step(
        self,
        case: Case,
        email: Email | None,
        *,
        reason_code: str,
        summary: str,
        extracted_fields: dict | None = None,
        extraction_confidence: float | None = None,
        missing_fields: list[str] | None = None,
        include_escalate: bool = True,
    ) -> dict:
        resume_step = REASON_TO_RESUME_STEP.get(reason_code)
        updates: dict = {"reason_code": reason_code, "error_type": reason_code}
        if resume_step:
            updates["resume_from_step"] = resume_step
        if extracted_fields is not None:
            updates["extracted_fields"] = extracted_fields
        if extraction_confidence is not None:
            updates["extraction_confidence"] = extraction_confidence
        _update_meta(case, updates)

        case.status = "manual_review"
        await self._session.flush()

        svc = ExecutiveMailService(self._session)
        escalation = await svc.escalate_to_manager(
            case=case,
            email=email,
            reason_code=reason_code,
            summary=summary,
            error_detail=summary,
            actor_name="expense-worker",
            missing_fields=missing_fields,
            extracted_fields=extracted_fields,
            extraction_confidence=extraction_confidence,
            include_escalate=include_escalate,
        )
        await self._add_timeline(
            case,
            "exception_raised",
            to_status="manual_review",
            description=summary,
            metadata={"reason_code": reason_code},
        )
        await self._session.flush()
        return {
            "status": "manual_review",
            "reason": reason_code,
            "case_id": str(case.id),
            "escalation_id": str(escalation.id) if escalation else None,
        }

    async def _route_failure(
        self, case: Case, email: Email | None, error_type: str, summary: str
    ) -> dict:
        case.status = "manual_review"
        _update_meta(case, {"error_type": error_type, "reason_code": error_type})
        return await route_processing_failure(
            self._session,
            case,
            email=email,
            reason_code=error_type,
            summary=summary,
            error_detail=error_type,
            actor_name="expense-worker",
        )
