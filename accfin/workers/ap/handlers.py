"""AP Worker handlers — `17` §5."""

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
from app.models.mail import Email, EmailAttachment
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
from app.services.email_context import build_extraction_context
from workers.ap.extraction import (
    compute_ap_invoice_risk_flags,
    evaluate_extraction_path,
    has_critical_missing,
    resolve_expense_account_code,
)
from workers.common.missing_fields_escalation import (
    invoice_extracted_fields,
    route_missing_fields_to_manager,
)
from workers.common.processing_failure import route_processing_failure

logger = logging.getLogger(__name__)

AP_CASE_TYPES = frozenset({"ap_invoice", "ap_po_validation", "ap_payment_proposal"})


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

    async def handle_ap_invoice(self, message: dict) -> dict:
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
            return await self._route_exception(case, exc.error_code, str(exc))

        inv = extraction.output
        if inv is None:
            return await self._route_manual(case, "Empty extraction")

        po_mismatch = False
        po_not_found = False
        po = None
        if inv.po_reference:
            po = await self._pos.get_by_po_number(inv.po_reference)
            if po is None:
                po_not_found = True
            else:
                match = await self._hermes.validate_po_match(
                    ValidatePOMatchRequest(
                        case_id=case.id,
                        extracted_invoice=inv,
                        po_data=self._pos.to_po_data(po),
                    )
                )
                status = match.output.match_status if match.output else "mismatch"
                po_mismatch = status in ("mismatch", "partial")

        recent = await self._recent_invoices(case.counterparty_id)
        dup = await self._hermes.check_duplicate(
            CheckDuplicateRequest(case_id=case.id, extracted_invoice=inv, recent_cases=recent)
        )
        dup_score = dup.output.similarity_score if dup.output else 0.0

        amount = Decimal(inv.total_amount or "0")
        risk_flags = compute_ap_invoice_risk_flags(
            duplicate_score=dup_score,
            amount=amount,
            po_not_found=po_not_found,
            po_mismatch=po_mismatch,
            warnings=inv.warnings,
        )
        policy_action = self._policy.combine_results(
            [
                self._policy.evaluate_policy(
                    {"rules": [], "default_action": {"type": "require_approval", "tier": 2}},
                    {"case": {"amount_value": float(amount), "type": case.type}},
                )
            ]
        )
        tier = int(policy_action.get("tier", 2))
        stp = message.get("stp_eligible", False) and policy_action.get("type") == "auto_release"
        final_status = evaluate_extraction_path(
            case_type="ap_invoice",
            confidence=float(extraction.confidence_score),
            missing_fields=inv.missing_fields,
            stp_eligible=stp,
            risk_flags=risk_flags,
        )

        expense_code = resolve_expense_account_code(po.line_items if po else None)

        await self._start_processing(case)
        journal_id = None
        if final_status == "posted":
            journal_id = await self._post_ap_invoice_journal(
                case, inv, amount, expense_code=expense_code, posted=True
            )
            case.status = "posted"
            case.completed_at = datetime.now(UTC)
        elif final_status == "pending_approval":
            journal_id = await self._post_ap_invoice_journal(
                case, inv, amount, expense_code=expense_code, posted=False
            )
            case.status = "pending_approval"
        else:
            case.status = "manual_review"

        case.amount_value = amount
        case.amount_currency = inv.currency
        case.risk_flags = risk_flags
        case.current_approval_tier = tier if final_status == "pending_approval" else None
        extracted = invoice_extracted_fields(inv)
        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "current_stage": "processing",
            "extraction_confidence": extraction.confidence_score,
            "policy_tier": tier,
            "po_reference": inv.po_reference,
            "expense_account_code": expense_code,
            "missing_fields": inv.missing_fields,
            "extracted_fields": extracted,
            "error_type": "INCOMPLETE_EXTRACTION" if final_status == "manual_review" else None,
        }
        # Remove null error_type when not manual review
        if case.workflow_metadata.get("error_type") is None:
            case.workflow_metadata.pop("error_type", None)
        await self._timeline_completed(case, "ap_invoice", inv.invoice_number, final_status, journal_id)
        await self._session.flush()

        if final_status == "pending_approval":
            await self._approvals.request_approval(
                case_id=case.id, tier=tier, amount_value=amount, amount_currency=inv.currency
            )

        if final_status == "manual_review":
            email = await self._email_for_case(case)
            escalation_result = await route_missing_fields_to_manager(
                self._session,
                case,
                email=email,
                missing_fields=list(inv.missing_fields or []),
                extraction_confidence=float(extraction.confidence_score),
                extracted_fields=extracted,
                actor_name="ap-worker",
            )
            return {
                "status": escalation_result.get("status", final_status),
                "case_id": str(case.id),
                "journal_entry_id": journal_id,
                "missing_fields": inv.missing_fields,
                **{
                    k: v
                    for k, v in escalation_result.items()
                    if k not in ("status", "case_id")
                },
            }

        return {"status": final_status, "case_id": str(case.id), "journal_entry_id": journal_id}

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
            return await self._route_exception(case, exc.error_code, str(exc))

        inv = extraction.output
        if inv is None or not inv.po_reference:
            return await self._route_manual(case, "PO reference required")

        po = await self._pos.get_by_po_number(inv.po_reference)
        if po is None:
            await self._start_processing(case)
            case.status = "manual_review"
            case.risk_flags = ["po_not_found"]
            await self._timeline_completed(
                case, "ap_po_validation", inv.po_reference, "manual_review", None
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
        if match_status == "match":
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
        await self._timeline_completed(case, "ap_po_validation", inv.po_reference, final, None)
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
        await self._timeline_completed(case, "ap_payment_proposal", None, "manual_review", None)
        await self._session.flush()
        return {"status": "manual_review", "case_id": str(case.id), "reason": "payment_proposal_stub"}

    async def _recent_invoices(self, counterparty_id: UUID | None) -> list[RecentCase]:
        if not counterparty_id:
            return []
        result = await self._session.execute(
            select(Case)
            .where(
                Case.counterparty_id == counterparty_id,
                Case.type == "ap_invoice",
            )
            .order_by(Case.created_at.desc())
            .limit(20)
        )
        rows = []
        for c in result.scalars().all():
            meta = c.classification_metadata or {}
            rows.append(
                RecentCase(
                    case_id=c.id,
                    case_number=c.case_number,
                    invoice_number=meta.get("invoice_number")
                    or (c.workflow_metadata or {}).get("invoice_number"),
                    total_amount=str(c.amount_value) if c.amount_value else None,
                )
            )
        return rows

    async def _post_ap_invoice_journal(
        self,
        case: Case,
        inv,
        amount: Decimal,
        *,
        expense_code: str,
        posted: bool,
    ) -> str | None:
        expense = await self._ledger.get_account_by_code(expense_code)
        gst_in = await self._ledger.get_account_by_code("1190")
        creditors = await self._ledger.get_account_by_code("2000")
        if not expense or not creditors:
            case.status = "manual_review"
            case.workflow_metadata = {
                **(case.workflow_metadata or {}),
                "error_type": "ACCOUNT_NOT_FOUND",
            }
            return None

        tax = Decimal(inv.tax_amount or "0")
        net = amount - tax
        status = "posted" if posted else "draft"
        entry = await self._ledger.create_journal_entry(
            case_id=case.id,
            case_number=case.case_number,
            status=status,
            entry_date=inv.invoice_date or date.today(),
            description=f"AP Invoice — {case.counterparty_name} {inv.invoice_number}",
            reference=inv.invoice_number,
            currency=inv.currency,
            total=amount,
            posted=posted,
        )
        line_no = 1
        await self._ledger.add_line(
            entry=entry,
            line_number=line_no,
            account_id=expense.id,
            debit=net,
            credit=Decimal("0"),
        )
        line_no += 1
        if tax > 0 and gst_in:
            await self._ledger.add_line(
                entry=entry,
                line_number=line_no,
                account_id=gst_in.id,
                debit=tax,
                credit=Decimal("0"),
            )
            line_no += 1
        await self._ledger.add_line(
            entry=entry,
            line_number=line_no,
            account_id=creditors.id,
            debit=Decimal("0"),
            credit=amount,
        )
        return str(entry.id)

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

    async def _timeline_completed(
        self, case: Case, kind: str, ref: str | None, final: str, journal_id: str | None
    ) -> None:
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="processing_completed",
            from_status="processing",
            to_status=final,
            actor="ap-worker",
            description=f"AP {kind} processed — {final}",
            metadata={"reference": ref, "journal_entry_id": journal_id},
        )

    async def _route_manual(self, case: Case, reason: str) -> dict:
        email = await self._email_for_case(case)
        return await route_processing_failure(
            self._session,
            case,
            email=email,
            reason_code="manual_review",
            summary="Processing requires manager review",
            error_detail=reason,
            actor_name="ap-worker",
        )

    async def _route_exception(self, case: Case, error_type: str, msg: str) -> dict:
        email = await self._email_for_case(case)
        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "error_type": error_type,
            "error_message": msg,
        }
        return await route_processing_failure(
            self._session,
            case,
            email=email,
            reason_code=error_type,
            summary="Worker processing error",
            error_detail=msg,
            actor_name="ap-worker",
        )
