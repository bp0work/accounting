"""AP Worker handlers — AP Process document 7-step validation sequence.

Implements the complete AP workflow: parsing → dedup → vendor → payment terms →
contract/sender → COA → journal routing.  Each failed step escalates to ACC with
Approve / Reject / Escalate buttons and full case details including original
attachment.  Manager approvals set override flags in workflow_metadata so the
re-queued case skips the resolved step on the next pass.
"""

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
from app.models.counterparty_master import CounterpartyAccount
from app.models.mail import Email
from app.policies.engine import PolicyEngine
from app.repositories.case import CaseRepository
from app.repositories.ledger import LedgerRepository
from app.repositories.purchase_order import PurchaseOrderRepository
from app.schemas.hermes import (
    CheckDuplicateRequest,
    ExtractInvoiceRequest,
    RecentCase,
    ValidatePOMatchRequest,
)
from app.services.approval_service import ApprovalService
from app.services.binding_authority_service import BindingAuthorityService, apply_binding_sla
from app.services.email_context import build_extraction_context
from app.services.executive_mail_service import ExecutiveMailService
from workers.ap.extraction import (
    compute_ap_invoice_risk_flags,
    evaluate_extraction_path,
    has_critical_missing,
    resolve_expense_account_code,
)
from workers.common.ap_validation import (
    check_duplicate_by_fields,
    extract_sender_validation,
    get_payment_term,
    lookup_vendor,
    payment_terms_match,
)
from workers.common.binding_authority_escalation import route_binding_authority_escalation
from workers.common.gl_period_check import ensure_gl_period_allows_posting
from workers.common.missing_fields_escalation import invoice_extracted_fields
from workers.common.policy_escalation import (
    route_po_mismatch_escalation,
    route_po_not_found_escalation,
)
from workers.common.processing_failure import route_processing_failure

logger = logging.getLogger(__name__)

AP_CASE_TYPES = frozenset({"ap_invoice", "ap_po_validation", "ap_payment_proposal"})

# Reason codes for each AP validation step — keyed in escalation.reason_code so the
# escalation service can set the correct override flag on manager approval.
_REASON_PARSING    = "AP_PARSING_INCOMPLETE"
_REASON_DUPLICATE  = "AP_DUPLICATE_FOUND"
_REASON_VENDOR_INACTIVE  = "AP_VENDOR_INACTIVE"
_REASON_VENDOR_NOT_FOUND = "AP_VENDOR_NOT_FOUND"
_REASON_PAYMENT_TERMS    = "AP_PAYMENT_TERMS_MISMATCH"
_REASON_CONTRACT         = "AP_CONTRACT_MISSING"
_REASON_SENDER_VALIDATION = "AP_SENDER_NOT_VALIDATED"
_REASON_COA_NOT_FOUND    = "AP_COA_NOT_FOUND"

# Mapping from reason code → workflow_metadata key set on approve
AP_OVERRIDE_KEYS: dict[str, str] = {
    _REASON_PARSING:           "override_parsing",
    _REASON_DUPLICATE:         "override_duplicate",
    _REASON_VENDOR_INACTIVE:   "override_vendor_inactive",
    _REASON_PAYMENT_TERMS:     "override_payment_terms",
    _REASON_CONTRACT:          "override_contract",
    _REASON_SENDER_VALIDATION: "override_sender_validation",
    _REASON_COA_NOT_FOUND:     "override_coa_not_found",
}


class APWorkerService:
    def __init__(self, session: AsyncSession, hermes: HermesClient | None = None) -> None:
        self._session = session
        self._hermes = hermes or HermesClient()
        self._cases = CaseRepository(session)
        self._ledger = LedgerRepository(session)
        self._pos = PurchaseOrderRepository(session)
        self._approvals = ApprovalService(session)
        self._policy = PolicyEngine()

    async def process_accounts_message(self, message: dict) -> dict:
        case_type = message.get("case_type")
        if case_type == "ap_invoice":
            return await self.handle_ap_invoice(message)
        if case_type == "ap_po_validation":
            return await self.handle_po_validation(message)
        if case_type == "ap_payment_proposal":
            return await self.handle_payment_proposal(message)
        return {"status": "skipped", "reason": "unknown_ap_type", "case_type": case_type}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _load_case(self, case_id: UUID) -> Case | None:
        result = await self._session.execute(
            select(Case)
            .options(selectinload(Case.workflow_instance))
            .where(Case.id == case_id)
        )
        return result.scalar_one_or_none()

    async def _email_for_case(self, case: Case) -> Email | None:
        if not case.email_id:
            return None
        result = await self._session.execute(select(Email).where(Email.id == case.email_id))
        return result.scalar_one_or_none()

    async def _attachment_text(self, email_id: UUID | None) -> tuple[str, UUID | None, str]:
        if not email_id:
            return "", None, ""
        return await build_extraction_context(self._session, email_id, hermes=self._hermes)

    async def _start_processing(self, case: Case) -> None:
        from_status = case.status
        case.status = "processing"
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="processing_started",
            from_status=from_status,
            to_status="processing",
            actor="ap-worker",
            description="AP Worker began processing",
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
            from_status=from_status,
            to_status=to_status,
            actor="ap-worker",
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
        include_escalate: bool = True,
    ) -> dict:
        """Escalate current validation step to ACC, set case to manual_review."""
        svc = ExecutiveMailService(self._session)
        case.status = "manual_review"
        await self._session.flush()

        escalation = await svc.escalate_to_manager(
            case=case,
            email=email,
            reason_code=reason_code,
            summary=summary,
            error_detail=summary,
            actor_name="ap-worker",
            extracted_fields=extracted_fields,
            extraction_confidence=extraction_confidence,
            escalation_template="manager.escalation.request",
            include_escalate=include_escalate,
        )
        if escalation is None:
            await self._add_timeline(
                case,
                "exception_raised",
                from_status="processing",
                to_status="manual_review",
                description=summary,
                metadata={"reason_code": reason_code, "escalation": "skipped"},
            )
        else:
            await self._add_timeline(
                case,
                "exception_raised",
                from_status="processing",
                to_status="manual_review",
                description=f"Escalated to {escalation.target_email}: {summary}",
                metadata={
                    "reason_code": reason_code,
                    "escalation_id": str(escalation.id),
                    "target_email": escalation.target_email,
                },
            )
        await self._session.flush()
        return {
            "status": "manual_review",
            "reason": reason_code,
            "case_id": str(case.id),
            "escalation_id": str(escalation.id) if escalation else None,
        }

    async def _send_rejection_to_sender(
        self,
        case: Case,
        email: Email | None,
        *,
        reason: str,
        manager_comment: str | None = None,
    ) -> None:
        """Notify the original external sender after a rejected case."""
        if email is None:
            return
        svc = ExecutiveMailService(self._session)
        await svc.queue_submitter_rejection(
            case=case,
            email=email,
            reason=reason,
            manager_comment=manager_comment,
        )

    # ------------------------------------------------------------------
    # Main invoice handler — 7-step AP validation sequence
    # ------------------------------------------------------------------

    async def handle_ap_invoice(self, message: dict) -> dict:  # noqa: PLR0912, PLR0915
        case = await self._load_case(UUID(message["case_id"]))
        if case is None:
            return {"status": "skipped", "reason": "case_not_found"}

        email = await self._email_for_case(case)
        overrides: dict = (case.workflow_metadata or {}).get("ap_step_overrides", {})

        # ── Extract ────────────────────────────────────────────────────
        text, att_id, body = await self._attachment_text(case.email_id)
        try:
            extraction = await self._hermes.extract_invoice(
                ExtractInvoiceRequest(
                    case_id=case.id,
                    attachment_id=att_id or case.id,
                    extracted_text=text,
                    email_body=body,
                    document_role="ap",
                    supplier_hint=case.counterparty_name,
                    currency_hint=case.amount_currency or "SGD",
                )
            )
        except HermesError as exc:
            return await self._route_exception(case, email, exc.error_code, str(exc))

        inv = extraction.output
        if inv is None:
            await self._start_processing(case)
            return await self._route_exception(case, email, "EMPTY_EXTRACTION", "Empty extraction")

        confidence_f = float(extraction.confidence_score)

        # Sender validation runs on email text — not Hermes
        email_subject = email.subject if email else None
        email_body_text = email.body_text if email else None
        sender_val = extract_sender_validation(email_subject, email_body_text)

        # Merge sender_validated into extraction metadata
        extracted = invoice_extracted_fields(inv)
        extracted["document_type"] = getattr(inv, "document_type", None) or "invoice"

        # ── Step 1: Parsing validation ────────────────────────────────
        await self._start_processing(case)
        if not overrides.get("override_parsing"):
            missing = list(inv.missing_fields or [])
            has_critical = has_critical_missing("ap_invoice", missing)
            if has_critical or confidence_f < 0.70:
                missing_label = ", ".join(missing) if missing else "low extraction confidence"
                summary = (
                    f"Unable to parse all required details for {case.case_number}. "
                    f"Missing fields: {missing_label}. "
                    f"Please advise: a) provide missing details for reprocessing quoting "
                    f"Case ID {case.case_number}, or b) ask sender to resubmit quoting "
                    f"Case ID {case.case_number}."
                )
                _update_meta(case, {
                    "current_stage": "parsing",
                    "extraction_confidence": confidence_f,
                    "extracted_fields": extracted,
                    "missing_fields": missing,
                    "error_type": _REASON_PARSING,
                    "reason_code": _REASON_PARSING,
                })
                await self._add_timeline(
                    case, "parsing_failed",
                    from_status="processing", to_status="manual_review",
                    description=f"Parsing failed: {missing_label}",
                    metadata={"missing_fields": missing, "confidence": confidence_f},
                )
                return await self._escalate_step(
                    case, email,
                    reason_code=_REASON_PARSING,
                    summary=summary,
                    extracted_fields=extracted,
                    extraction_confidence=confidence_f,
                )

        await self._add_timeline(
            case, "parsing_completed",
            description=f"Parsing OK — confidence {confidence_f:.2f}",
            metadata={"confidence": confidence_f, "extracted_fields": extracted},
        )

        # ── Step 2: Duplicate check ───────────────────────────────────
        if not overrides.get("override_duplicate"):
            doc_number = (
                getattr(inv, "invoice_number", None)
                or getattr(inv, "document_number", None)
                or ""
            )
            total_amount_dec = Decimal(str(inv.total_amount or "0"))
            vendor_name_str = inv.vendor_name or case.counterparty_name or ""
            if doc_number and vendor_name_str:
                is_dup, dup_case_number = await check_duplicate_by_fields(
                    self._session,
                    vendor_name=vendor_name_str,
                    document_number=doc_number,
                    total_amount=total_amount_dec,
                    exclude_case_id=case.id,
                )
                if is_dup:
                    summary = (
                        f"Duplicate document detected for {case.case_number}. "
                        f"This document matches existing case {dup_case_number}. "
                        f"Please advise."
                    )
                    _update_meta(case, {
                        "error_type": _REASON_DUPLICATE,
                        "reason_code": _REASON_DUPLICATE,
                        "duplicate_of": dup_case_number,
                    })
                    await self._add_timeline(
                        case, "duplicate_checked",
                        from_status="processing", to_status="manual_review",
                        description=f"Duplicate found: {dup_case_number}",
                        metadata={"duplicate_of": dup_case_number},
                    )
                    return await self._escalate_step(
                        case, email,
                        reason_code=_REASON_DUPLICATE,
                        summary=summary,
                        extracted_fields=extracted,
                        extraction_confidence=confidence_f,
                        include_escalate=False,
                    )

        await self._add_timeline(case, "duplicate_checked", description="No duplicate found")

        # ── Step 3: Vendor subaccount ─────────────────────────────────
        vendor_name_str = inv.vendor_name or case.counterparty_name or ""
        uen = getattr(inv, "vendor_uen", None) or getattr(inv, "registration_number", None)
        counterparty, subaccount, vendor_status = await lookup_vendor(
            self._session, vendor_name_str, uen=uen
        )

        if vendor_status == "not_found":
            summary = (
                f"Vendor {vendor_name_str} has no subaccount in the system. "
                f"Vendor must be set up before this document can be processed. "
                f"Document will be rejected."
            )
            _update_meta(case, {
                "error_type": _REASON_VENDOR_NOT_FOUND,
                "reason_code": _REASON_VENDOR_NOT_FOUND,
            })
            await self._add_timeline(
                case, "vendor_not_found",
                from_status="processing", to_status="manual_review",
                description=summary,
            )
            result = await self._escalate_step(
                case, email,
                reason_code=_REASON_VENDOR_NOT_FOUND,
                summary=summary,
                extracted_fields=extracted,
                extraction_confidence=confidence_f,
                include_escalate=False,
            )
            # Reject-only path: notify sender immediately
            await self._send_rejection_to_sender(
                case, email,
                reason=(
                    f"Your document cannot be processed as {vendor_name_str} is not "
                    f"set up in our system. Please contact accounts to register the vendor."
                ),
            )
            case.status = "case_rejected"
            await self._session.flush()
            return result

        if vendor_status == "inactive" and not overrides.get("override_vendor_inactive"):
            summary = (
                f"Vendor {vendor_name_str} has an inactive subaccount. "
                f"Please advise: a) reactivate and proceed, or b) reject document."
            )
            _update_meta(case, {
                "error_type": _REASON_VENDOR_INACTIVE,
                "reason_code": _REASON_VENDOR_INACTIVE,
                "counterparty_id": str(counterparty.id) if counterparty else None,
            })
            await self._add_timeline(
                case, "vendor_inactive",
                from_status="processing", to_status="manual_review",
                description=summary,
            )
            return await self._escalate_step(
                case, email,
                reason_code=_REASON_VENDOR_INACTIVE,
                summary=summary,
                extracted_fields=extracted,
                extraction_confidence=confidence_f,
            )

        if vendor_status == "inactive" and overrides.get("override_vendor_inactive"):
            # Manager approved reactivation — reactivate subaccount now
            if subaccount is not None:
                subaccount.is_active = True
                await self._session.flush()
                logger.info(
                    "Reactivated subaccount %s for counterparty %s per manager override",
                    subaccount.id,
                    vendor_name_str,
                )

        # Attach vendor to case if not already
        if counterparty and not case.counterparty_id:
            case.counterparty_id = counterparty.id
            case.counterparty_name = counterparty.name
        if subaccount and not case.counterparty_account_id:
            case.counterparty_account_id = subaccount.id

        await self._add_timeline(
            case, "vendor_validated",
            description=f"Vendor {vendor_name_str} — status {vendor_status}",
        )

        # ── Step 4: Payment terms ─────────────────────────────────────
        if not overrides.get("override_payment_terms"):
            doc_terms = getattr(inv, "payment_terms", None) or extracted.get("payment_terms")
            subaccount_terms_code: str | None = None
            if subaccount and subaccount.payment_term_id:
                pt = await get_payment_term(self._session, subaccount.payment_term_id)
                subaccount_terms_code = pt.code if pt else None
            elif counterparty:
                subaccount_terms_code = counterparty.payment_terms

            if doc_terms and subaccount_terms_code:
                if not payment_terms_match(doc_terms, subaccount_terms_code):
                    summary = (
                        f"Payment terms on document ({doc_terms}) do not match "
                        f"subaccount terms ({subaccount_terms_code}) for {vendor_name_str}. "
                        f"Please advise: a) reject — incorrect terms, or "
                        f"b) accept with override reason."
                    )
                    _update_meta(case, {
                        "error_type": _REASON_PAYMENT_TERMS,
                        "reason_code": _REASON_PAYMENT_TERMS,
                        "doc_payment_terms": doc_terms,
                        "subaccount_payment_terms": subaccount_terms_code,
                    })
                    await self._add_timeline(
                        case, "payment_terms_mismatch",
                        from_status="processing", to_status="manual_review",
                        description=summary,
                    )
                    return await self._escalate_step(
                        case, email,
                        reason_code=_REASON_PAYMENT_TERMS,
                        summary=summary,
                        extracted_fields=extracted,
                        extraction_confidence=confidence_f,
                    )

        await self._add_timeline(case, "payment_terms_validated", description="Payment terms OK")

        # ── Step 5a: Contract validation ──────────────────────────────
        today = date.today()
        contract_valid = bool(
            counterparty
            and counterparty.has_contract
            and counterparty.contract_expiry_date
            and counterparty.contract_expiry_date >= today
        )

        if not contract_valid and not overrides.get("override_contract"):
            summary = (
                f"Vendor {vendor_name_str} subaccount has no valid contract "
                f"(or contract has expired). Please advise: "
                f"a) reject document, or b) accept with override reason."
            )
            _update_meta(case, {
                "error_type": _REASON_CONTRACT,
                "reason_code": _REASON_CONTRACT,
            })
            await self._add_timeline(
                case, "contract_missing",
                from_status="processing", to_status="manual_review",
                description=summary,
            )
            return await self._escalate_step(
                case, email,
                reason_code=_REASON_CONTRACT,
                summary=summary,
                extracted_fields=extracted,
                extraction_confidence=confidence_f,
            )

        # ── Step 5b: Sender validation ────────────────────────────────
        if not sender_val["sender_validated"] and not overrides.get("override_sender_validation"):
            failure_reason = sender_val.get("failure_reason") or (
                "Document not validated. Please include 'validated dd/mm/yyyy' in your email "
                "(e.g. 'validated 28/05/2026')"
            )
            summary = (
                f"Sender has not validated this document. "
                f"The email must include 'validated dd/mm/yyyy' with a date in the last 7 days. "
                f"Reason: {failure_reason}. "
                f"Please advise: a) reject and ask sender to resubmit with validation, "
                f"or b) accept with override."
            )
            _update_meta(case, {
                "error_type": _REASON_SENDER_VALIDATION,
                "reason_code": _REASON_SENDER_VALIDATION,
                "sender_validation_failure": failure_reason,
            })
            await self._add_timeline(
                case, "sender_not_validated",
                from_status="processing", to_status="manual_review",
                description=summary,
            )
            return await self._escalate_step(
                case, email,
                reason_code=_REASON_SENDER_VALIDATION,
                summary=summary,
                extracted_fields=extracted,
                extraction_confidence=confidence_f,
            )

        await self._add_timeline(
            case, "contract_validated",
            description=(
                f"Contract valid={contract_valid} "
                f"sender_validated={sender_val['sender_validated']}"
            ),
        )

        # Store sender_validated in extraction metadata
        meta_extraction = dict((case.workflow_metadata or {}).get("extraction", {}))
        meta_extraction["sender_validated"] = sender_val["sender_validated"]
        meta_extraction["validation_date"] = sender_val.get("validation_date")
        _update_meta(case, {"extraction": meta_extraction})

        # ── Step 6: COA mapping ───────────────────────────────────────
        coa_override_code: str | None = overrides.get("coa_account_code")
        po = None
        if inv.po_reference:
            po = await self._pos.get_by_po_number(inv.po_reference)

        expense_code = coa_override_code or resolve_expense_account_code(
            po.line_items if po else None
        )
        expense_account = await self._ledger.get_account_by_code(expense_code)

        if expense_account is None:
            summary = (
                f"Unable to identify the correct GL account for "
                f"{vendor_name_str} — {extracted.get('document_type', 'invoice')}. "
                f"Please advise which account to use."
            )
            _update_meta(case, {
                "error_type": _REASON_COA_NOT_FOUND,
                "reason_code": _REASON_COA_NOT_FOUND,
                "expense_code_attempted": expense_code,
            })
            await self._add_timeline(
                case, "coa_not_found",
                from_status="processing", to_status="manual_review",
                description=summary,
            )
            return await self._escalate_step(
                case, email,
                reason_code=_REASON_COA_NOT_FOUND,
                summary=summary,
                extracted_fields=extracted,
                extraction_confidence=confidence_f,
            )

        await self._add_timeline(
            case, "coa_mapped",
            description=f"Expense account {expense_code} resolved",
        )

        # ── Step 7: Document type routing + journal ───────────────────
        amount = Decimal(str(inv.total_amount or "0"))
        tax = Decimal(str(getattr(inv, "tax_amount", None) or "0"))
        document_type = (
            str(extracted.get("document_type", "invoice"))
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        # GL period check before posting
        posting_date = getattr(inv, "invoice_date", None) or date.today()
        period_block = await ensure_gl_period_allows_posting(
            self._session,
            case,
            message,
            posting_date=posting_date,
            email=email,
            actor_name="ap-worker",
        )
        if period_block:
            await self._session.flush()
            return period_block

        # Binding authority tier
        risk_flags = compute_ap_invoice_risk_flags(
            duplicate_score=0.0,
            amount=amount,
            po_not_found=False,
            po_mismatch=False,
            warnings=list(getattr(inv, "warnings", None) or []),
        )
        binding = BindingAuthorityService(self._session)
        tier, thresholds = await binding.evaluate_tier(
            amount=amount,
            confidence=confidence_f,
            risk_flags=risk_flags,
            case_type=case.type,
        )
        apply_binding_sla(case, tier, thresholds)

        is_credit_or_debit_note = document_type in ("credit_note", "debit_note")
        # Step 3a routing precedence:
        # credit/debit notes must always go through approval, regardless of amount.
        if is_credit_or_debit_note:
            tier = max(tier, 2)

        # Resolve trade creditors account
        creditors = await self._ledger.get_account_by_code("2000")
        gst_account = None
        gst_code = (
            getattr(inv, "tax_gl_account_code", None)
            or (case.workflow_metadata or {}).get("tax_gl_account_code")
            or "1190"
        )
        if tax > 0:
            gst_account = await self._ledger.get_account_by_code(gst_code)

        if not creditors:
            return await self._route_exception(
                case, email, "ACCOUNT_NOT_FOUND", "Trade creditors account (2000) not found"
            )

        case.amount_value = amount
        case.amount_currency = getattr(inv, "currency", None) or "SGD"
        case.risk_flags = risk_flags
        case.current_approval_tier = tier if tier >= 2 else None

        if not is_credit_or_debit_note and tier == 1:
            # Auto-post
            journal_id = await self._create_journal(
                case, inv, amount, tax,
                expense_account=expense_account,
                gst_account=gst_account,
                creditors=creditors,
                document_type=document_type,
                posted=True,
            )
            case.status = "journal_posted"
            case.completed_at = datetime.now(UTC)
            _update_meta(case, {
                "current_stage": "completed",
                "extraction_confidence": confidence_f,
                "extracted_fields": extracted,
                "expense_account_code": expense_code,
                "policy_tier": tier,
            })
            await self._add_timeline(
                case, "journal_posted",
                from_status="processing", to_status="journal_posted",
                description=f"Tier 1 auto-post — {case.amount_currency} {amount:,.2f}",
                metadata={"journal_entry_id": journal_id, "tier": tier},
            )
            # Immediately close the case
            case.status = "case_closed"
            await self._add_timeline(
                case, "case_closed",
                from_status="journal_posted", to_status="case_closed",
                description="Case closed after Tier 1 auto-post",
            )
            await self._session.flush()
            return {
                "status": "case_closed",
                "case_id": str(case.id),
                "journal_entry_id": journal_id,
                "tier": tier,
            }

        # Tier 2 / Tier 3 — create draft journal, request approval
        journal_id = await self._create_journal(
            case, inv, amount, tax,
            expense_account=expense_account,
            gst_account=gst_account,
            creditors=creditors,
            document_type=document_type,
            posted=False,
        )
        case.status = "journal_entry_created"
        _update_meta(case, {
            "current_stage": "journal_created",
            "extraction_confidence": confidence_f,
            "extracted_fields": extracted,
            "expense_account_code": expense_code,
            "policy_tier": tier,
            "journal_entry_id": journal_id,
        })
        await self._add_timeline(
            case, "journal_entry_created",
            from_status="processing", to_status="journal_entry_created",
            description=f"Journal entry draft — {case.amount_currency} {amount:,.2f}",
            metadata={"journal_entry_id": journal_id, "tier": tier},
        )

        # Move to pending approval
        case.status = "journal_pending_approval"
        await self._add_timeline(
            case, "journal_pending_approval",
            from_status="journal_entry_created", to_status="journal_pending_approval",
            description=f"Pending Tier {tier} approval",
        )
        await self._session.flush()

        # Create approval record + escalation email
        await self._approvals.request_approval(
            case_id=case.id, tier=tier, amount_value=amount,
            amount_currency=getattr(inv, "currency", None) or "SGD",
        )
        currency = getattr(inv, "currency", None) or "SGD"

        if is_credit_or_debit_note:
            doc_label = "Credit note" if document_type == "credit_note" else "Debit note"
            ba_summary = (
                f"{doc_label} received from {vendor_name_str} for "
                f"{currency} {amount:,.2f}. Please review and approve journal entry."
            )
        else:
            ba_summary = None  # standard binding-authority email

        await route_binding_authority_escalation(
            self._session,
            case,
            email=email,
            tier=tier,
            amount=amount,
            currency=currency,
            extracted_fields=extracted,
            extraction_confidence=confidence_f,
            actor_name="ap-worker",
        )

        return {
            "status": "journal_pending_approval",
            "case_id": str(case.id),
            "journal_entry_id": journal_id,
            "tier": tier,
        }

    # ------------------------------------------------------------------
    # Journal creation helper
    # ------------------------------------------------------------------

    async def _create_journal(
        self,
        case: Case,
        inv,
        amount: Decimal,
        tax: Decimal,
        *,
        expense_account,
        gst_account,
        creditors,
        document_type: str,
        posted: bool,
    ) -> str | None:
        net = amount - tax
        status = "posted" if posted else "draft"
        inv_number = (
            getattr(inv, "invoice_number", None)
            or getattr(inv, "document_number", None)
            or ""
        )
        inv_date = getattr(inv, "invoice_date", None) or date.today()
        currency = getattr(inv, "currency", None) or "SGD"
        description = f"AP {document_type.replace('_', ' ').title()} — {case.counterparty_name} {inv_number}"

        entry = await self._ledger.create_journal_entry(
            case_id=case.id,
            case_number=case.case_number,
            status=status,
            entry_date=inv_date,
            description=description,
            reference=inv_number,
            currency=currency,
            total=amount,
            posted=posted,
        )

        line_no = 1
        if document_type == "credit_note":
            # Debit trade creditors, Credit expense, Credit GST reversal
            await self._ledger.add_line(entry=entry, line_number=line_no,
                account_id=creditors.id, debit=amount, credit=Decimal("0"))
            line_no += 1
            if tax > 0 and gst_account:
                await self._ledger.add_line(entry=entry, line_number=line_no,
                    account_id=gst_account.id, debit=Decimal("0"), credit=tax)
                line_no += 1
            await self._ledger.add_line(entry=entry, line_number=line_no,
                account_id=expense_account.id, debit=Decimal("0"), credit=net)
        else:
            # Invoice or debit_note: Debit expense, Debit GST, Credit trade creditors
            await self._ledger.add_line(entry=entry, line_number=line_no,
                account_id=expense_account.id, debit=net, credit=Decimal("0"))
            line_no += 1
            if tax > 0 and gst_account:
                await self._ledger.add_line(entry=entry, line_number=line_no,
                    account_id=gst_account.id, debit=tax, credit=Decimal("0"))
                line_no += 1
            await self._ledger.add_line(entry=entry, line_number=line_no,
                account_id=creditors.id, debit=Decimal("0"), credit=amount)

        return str(entry.id)

    # ------------------------------------------------------------------
    # PO and payment proposal handlers (unchanged from previous)
    # ------------------------------------------------------------------

    async def handle_po_validation(self, message: dict) -> dict:
        """Mandatory PO validation — mismatch or missing PO routes to manual_review."""
        case = await self._load_case(UUID(message["case_id"]))
        if case is None:
            return {"status": "skipped", "reason": "case_not_found"}

        text, att_id, body = await self._attachment_text(case.email_id)
        try:
            extraction = await self._hermes.extract_invoice(
                ExtractInvoiceRequest(
                    case_id=case.id,
                    attachment_id=att_id or case.id,
                    extracted_text=text,
                    email_body=body,
                    document_role="ap",
                    supplier_hint=case.counterparty_name,
                    currency_hint=case.amount_currency or "SGD",
                )
            )
        except HermesError as exc:
            email = await self._email_for_case(case)
            return await self._route_exception(case, email, exc.error_code, str(exc))

        inv = extraction.output
        if inv is None or not getattr(inv, "po_reference", None):
            email = await self._email_for_case(case)
            return await self._route_exception(case, email, "PO_MISSING", "PO reference required")

        po = await self._pos.get_by_po_number(inv.po_reference)
        if po is None:
            await self._start_processing(case)
            case.status = "manual_review"
            case.risk_flags = ["po_not_found"]
            await self._add_timeline(
                case, "processing_completed",
                from_status="processing", to_status="manual_review",
                description="PO not found",
            )
            await self._session.flush()
            return {"status": "manual_review", "reason": "po_not_found", "case_id": str(case.id)}

        match = await self._hermes.validate_po_match(
            ValidatePOMatchRequest(
                case_id=case.id,
                extracted_invoice=inv,
                po_data=self._pos.to_po_data(po),
            )
        )
        match_status = match.output.match_status if match.output else "mismatch"
        await self._start_processing(case)
        if match_status == "exact":
            case.status = "completed"
            case.completed_at = datetime.now(UTC)
            final = "completed"
        else:
            case.status = "manual_review"
            case.risk_flags = ["po_amount_mismatch"]
            final = "manual_review"

        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "po_reference": inv.po_reference,
            "po_match_status": match_status,
        }
        await self._add_timeline(
            case, "processing_completed",
            from_status="processing", to_status=final,
            description=f"PO validation: {match_status}",
        )
        await self._session.flush()
        return {"status": final, "case_id": str(case.id), "po_match_status": match_status}

    async def handle_payment_proposal(self, message: dict) -> dict:
        """Payment proposals deferred — route to manual review per `17` §5.4."""
        case = await self._load_case(UUID(message["case_id"]))
        if case is None:
            return {"status": "skipped", "reason": "case_not_found"}
        await self._start_processing(case)
        case.status = "manual_review"
        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "payment_proposal": "stub_pending_implementation",
        }
        await self._add_timeline(
            case, "processing_completed",
            from_status="processing", to_status="manual_review",
            description="Payment proposal — deferred",
        )
        await self._session.flush()
        return {"status": "manual_review", "case_id": str(case.id), "reason": "payment_proposal_stub"}

    # ------------------------------------------------------------------
    # Error helpers
    # ------------------------------------------------------------------

    async def _route_exception(
        self, case: Case, email: Email | None, error_type: str, msg: str
    ) -> dict:
        detail = f"{error_type}: {msg}"
        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "error_code": error_type,
            "error_type": error_type,
            "error_message": msg,
        }
        from workers.common.processing_failure import route_processing_failure
        return await route_processing_failure(
            self._session,
            case,
            email=email,
            reason_code=error_type,
            summary=f"Worker processing error — {detail}",
            error_detail=detail,
            actor_name="ap-worker",
        )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _update_meta(case: Case, updates: dict) -> None:
    """Merge updates into case.workflow_metadata in-place."""
    meta = dict(case.workflow_metadata or {})
    meta.update(updates)
    case.workflow_metadata = meta


# Backwards-compatible alias used by missing_fields_escalation
def invoice_extracted_fields_from_inv(inv) -> dict[str, str | None]:
    return invoice_extracted_fields(inv)
