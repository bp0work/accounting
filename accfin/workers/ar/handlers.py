"""AR Worker handlers — `17` §4."""

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
from app.schemas.hermes import (
    CheckDuplicateRequest,
    ExtractInvoiceRequest,
    ExtractPaymentAdviceRequest,
    GenerateSOARequest,
    OpenInvoiceItem,
    RecentCase,
)
from app.services.approval_service import ApprovalService
from app.services.email_context import build_extraction_context
from app.services.counterparty_intake import apply_intake_to_case
from app.services.executive_mail_service import ExecutiveMailService
from workers.ar.extraction import (
    compute_invoice_risk_flags,
    compute_payment_risk_flags,
    evaluate_extraction_path,
    has_critical_missing,
)
from app.services.binding_authority_service import BindingAuthorityService, apply_binding_sla
from workers.common.binding_authority_escalation import route_binding_authority_escalation
from workers.common.gl_period_check import ensure_gl_period_allows_posting
from workers.common.parsing_confirmation import (
    extracted_fields_to_invoice,
    invoice_to_confirmation_fields,
    pause_for_parsing_confirmation,
    requires_parsing_confirmation,
)
from workers.common.processing_failure import route_processing_failure

logger = logging.getLogger(__name__)

AR_CASE_TYPES = frozenset(
    {"ar_invoice", "ar_payment_advice", "ar_credit_note", "ar_soa_request"}
)


class ARWorkerService:
    def __init__(self, session: AsyncSession, hermes: HermesClient | None = None) -> None:
        self._session = session
        self._hermes = hermes or HermesClient()
        self._cases = CaseRepository(session)
        self._ledger = LedgerRepository(session)
        self._approvals = ApprovalService(session)
        self._policy = PolicyEngine()
        self._executive_mail = ExecutiveMailService(session)

    async def process_accounts_message(self, message: dict) -> dict:
        case_type = message.get("case_type")
        if case_type == "ar_invoice":
            return await self.handle_ar_invoice(message)
        if case_type == "ar_payment_advice":
            return await self.handle_payment_advice(message)
        if case_type == "ar_credit_note":
            return await self.handle_credit_note(message)
        if case_type == "ar_soa_request":
            return await self.handle_soa_request(message)
        return {"status": "skipped", "reason": "unknown_ar_type", "case_type": case_type}

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

    async def _mailbox_id_for_case(self, case: Case) -> UUID | None:
        email = await self._email_for_case(case)
        if email is None:
            return None
        mailbox = await self._executive_mail.get_mailbox_for_address(email.mailbox_address)
        return mailbox.id if mailbox else None

    async def _attachment_text(self, email_id: UUID | None) -> tuple[str, UUID | None, str]:
        if not email_id:
            return "", None, ""
        text, att_id, body = await build_extraction_context(
            self._session, email_id, hermes=self._hermes
        )
        return text, att_id, body

    async def handle_ar_invoice(self, message: dict) -> dict:
        case = await self._load_case(UUID(message["case_id"]))
        if case is None:
            return {"status": "skipped", "reason": "case_not_found"}

        email = await self._email_for_case(case)

        if message.get("parsing_confirmed"):
            meta = case.workflow_metadata or {}
            extracted = dict(meta.get("extracted_fields") or {})
            inv = extracted_fields_to_invoice(extracted)
            confidence_f = float(
                meta.get("extraction_confidence") or case.confidence_score or 0
            )
        else:
            text, att_id, body = await self._attachment_text(case.email_id)
            try:
                extraction = await self._hermes.extract_invoice(
                    ExtractInvoiceRequest(
                        case_id=case.id,
                        attachment_id=att_id or case.id,
                        extracted_text=text,
                        email_body=body,
                        document_role="ar",
                        customer_hint=case.counterparty_name,
                        supplier_hint=case.counterparty_name,
                        currency_hint=case.amount_currency or "SGD",
                    )
                )
            except HermesError as exc:
                return await self._route_exception(case, exc.error_code, str(exc))

            inv = extraction.output
            if inv is None:
                return await self._route_manual(case, "Empty extraction")

            confidence_f = float(extraction.confidence_score)
            if not (
                has_critical_missing("ar_invoice", inv.missing_fields)
                or confidence_f < 0.70
            ):
                await self._cases.add_timeline(
                    case_id=case.id,
                    event_type="parsing_completed",
                    from_status=case.status,
                    to_status=case.status,
                    actor="ar-worker",
                    description=f"Parsing OK — confidence {confidence_f:.2f}",
                    metadata={"confidence": confidence_f},
                )
                if await requires_parsing_confirmation(self._session, case, email):
                    doc_type = (
                        "credit_note"
                        if case.type == "ar_credit_note"
                        else "invoice"
                    )
                    confirm_fields = invoice_to_confirmation_fields(
                        inv, document_type=doc_type
                    )
                    return await pause_for_parsing_confirmation(
                        self._session,
                        case=case,
                        email=email,
                        extracted_fields=confirm_fields,
                        extraction_confidence=confidence_f,
                        actor_name="ar-worker",
                    )

        resolution = await apply_intake_to_case(
            self._session,
            case=case,
            inv=inv,
            tax_direction="output",
            confidence=confidence_f,
            document_type="ar_invoice",
        )
        if resolution.warnings:
            inv.warnings = list(inv.warnings or []) + resolution.warnings

        recent = await self._recent_invoices(case.counterparty_id)
        dup = await self._hermes.check_duplicate(
            CheckDuplicateRequest(case_id=case.id, extracted_invoice=inv, recent_cases=recent)
        )
        dup_score = dup.output.similarity_score if dup.output else 0.0

        amount = Decimal(inv.total_amount or "0")
        risk_flags = compute_invoice_risk_flags(
            duplicate_score=dup_score,
            amount=amount,
            warnings=inv.warnings,
        )
        binding = BindingAuthorityService(self._session)
        tier, thresholds = await binding.evaluate_tier(
            amount=amount,
            confidence=confidence_f,
            risk_flags=risk_flags,
            case_type=case.type,
        )
        apply_binding_sla(case, tier, thresholds)
        mailbox_id = await self._mailbox_id_for_case(case)
        await self._executive_mail.log_policy_check(
            case=case,
            mailbox_id=mailbox_id,
            passed=True,
            policy_action={"type": "binding_authority", "tier": tier},
            actor_name="ar-worker",
        )
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="status_change",
            from_status=case.status,
            to_status=case.status,
            actor="ar-worker",
            description=f"Binding authority tier {tier}",
            metadata={"policy_tier": tier},
        )
        if has_critical_missing("ar_invoice", inv.missing_fields) or confidence_f < 0.70:
            final_status = "manual_review"
        elif tier == 1 and confidence_f >= thresholds.stp_confidence_minimum and not risk_flags:
            final_status = "posted"
        elif tier >= 2:
            final_status = "pending_approval"
        else:
            final_status = evaluate_extraction_path(
                case_type="ar_invoice",
                confidence=confidence_f,
                missing_fields=inv.missing_fields,
                stp_eligible=False,
                risk_flags=risk_flags,
            )

        posting_date = inv.document_date or date.today()
        if email is None:
            email = await self._email_for_case(case)
        period_block = await ensure_gl_period_allows_posting(
            self._session,
            case,
            message,
            posting_date=posting_date,
            email=email,
            actor_name="ar-worker",
        )
        if period_block:
            await self._start_processing(case)
            await self._timeline_completed(case, "ar_invoice", inv.document_number, "manual_review", None)
            await self._session.flush()
            return period_block

        await self._start_processing(case)
        journal_id = None
        if final_status == "posted":
            journal_id = await self._post_ar_invoice_journal(
                case, inv, amount, posted=True, tax_gl_code=resolution.tax_gl_account_code
            )
            case.status = "posted"
            case.completed_at = datetime.now(UTC)
        elif final_status == "pending_approval":
            journal_id = await self._post_ar_invoice_journal(
                case, inv, amount, posted=False, tax_gl_code=resolution.tax_gl_account_code
            )
            case.status = "pending_approval"
        else:
            case.status = "manual_review"

        case.amount_value = amount
        case.amount_currency = inv.currency
        case.risk_flags = risk_flags
        case.current_approval_tier = tier if final_status == "pending_approval" else None
        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "current_stage": "processing",
            "extraction_confidence": confidence_f,
            "policy_tier": tier,
            "stp": final_status == "posted",
            "missing_fields": inv.missing_fields,
            "document_number": inv.document_number,
            "document_date": str(inv.document_date) if inv.document_date else None,
            "vendor": case.counterparty_name,
            "total_amount": str(amount),
            "currency": inv.currency,
        }
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="status_change",
            from_status="processing",
            to_status="processing",
            actor="ar-worker",
            description="Invoice extraction completed",
            metadata={
                "document_number": inv.document_number,
                "total_amount": str(amount),
                "currency": inv.currency,
                "vendor": case.counterparty_name,
                "confidence": confidence_f,
                "missing_fields": inv.missing_fields,
            },
        )
        await self._timeline_completed(case, "ar_invoice", inv.document_number, final_status, journal_id)
        if journal_id and final_status == "posted":
            await self._cases.add_timeline(
                case_id=case.id,
                event_type="journal_linked",
                from_status=final_status,
                to_status=final_status,
                actor="ar-worker",
                description=f"Journal posted — AR debit 1300, revenue credit 4100, amount {amount} {inv.currency}",
                metadata={
                    "journal_entry_id": journal_id,
                    "debit_account": "1300",
                    "credit_account": "4100",
                    "amount": str(amount),
                    "currency": inv.currency,
                },
            )
            await self._executive_mail.log_journal_posted(
                case=case,
                mailbox_id=mailbox_id,
                journal_entry_id=UUID(journal_id),
                debits=[{"account": "1300", "amount": str(amount)}],
                credits=[
                    {"account": "4100", "amount": str(amount - Decimal(inv.tax_amount or "0"))},
                ],
                actor_name="ar-worker",
            )
        await self._session.flush()

        if final_status == "pending_approval":
            await self._approvals.request_approval(
                case_id=case.id, tier=tier, amount_value=amount, amount_currency=inv.currency
            )
            if tier >= 2:
                extracted = {
                    "document_number": inv.document_number,
                    "total_amount": str(amount),
                    "currency": inv.currency,
                    "vendor_name": case.counterparty_name,
                }
                await route_binding_authority_escalation(
                    self._session,
                    case,
                    email=email,
                    tier=tier,
                    amount=amount,
                    currency=inv.currency or "SGD",
                    extracted_fields=extracted,
                    extraction_confidence=confidence_f,
                    actor_name="ar-worker",
                )

        return {"status": final_status, "case_id": str(case.id), "journal_entry_id": journal_id}

    async def handle_credit_note(self, message: dict) -> dict:
        """Credit notes use same extraction path as invoices with reversed GL in a later phase."""
        return await self.handle_ar_invoice(message)

    async def handle_payment_advice(self, message: dict) -> dict:
        case = await self._load_case(UUID(message["case_id"]))
        if case is None:
            return {"status": "skipped", "reason": "case_not_found"}

        text, _, _ = await self._attachment_text(case.email_id)
        try:
            extraction = await self._hermes.extract_payment_advice(
                ExtractPaymentAdviceRequest(
                    case_id=case.id,
                    extracted_text=text,
                    customer_hint=case.counterparty_name,
                )
            )
        except HermesError as exc:
            return await self._route_exception(case, exc.error_code, str(exc))

        pa = extraction.output
        if pa is None:
            return await self._route_manual(case, "Empty payment advice extraction")

        amount = Decimal(pa.payment_amount or "0")
        unallocated = Decimal(pa.unallocated_amount or "0")
        invoice_not_found = not pa.allocations
        risk_flags = compute_payment_risk_flags(
            unallocated=unallocated, invoice_not_found=invoice_not_found
        )

        missing = pa.missing_fields
        if has_critical_missing("ar_payment_advice", missing) or not pa.payment_amount:
            await self._start_processing(case)
            case.status = "manual_review"
            await self._timeline_completed(case, "ar_payment_advice", pa.bank_reference, "manual_review", None)
            await self._session.flush()
            return {"status": "manual_review", "case_id": str(case.id)}

        await self._start_processing(case)
        tier = 1 if not risk_flags and unallocated <= Decimal("1.00") else 2
        if tier == 1 and float(extraction.confidence_score) >= 0.90:
            await self._post_payment_journal(case, amount, posted=True)
            case.status = "completed"
            case.completed_at = datetime.now(UTC)
            final = "completed"
        else:
            case.status = "pending_approval"
            await self._post_payment_journal(case, amount, posted=False)
            await self._approvals.request_approval(
                case_id=case.id, tier=tier, amount_value=amount, amount_currency=pa.currency
            )
            final = "pending_approval"

        case.amount_value = amount
        case.risk_flags = risk_flags
        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "payment_ref": pa.bank_reference,
            "unallocated_amount": str(unallocated),
            "extraction_confidence": confidence_f,
        }
        await self._timeline_completed(case, "ar_payment_advice", pa.bank_reference, final, None)
        await self._session.flush()
        return {"status": final, "case_id": str(case.id)}

    async def handle_soa_request(self, message: dict) -> dict:
        case = await self._load_case(UUID(message["case_id"]))
        if case is None:
            return {"status": "skipped", "reason": "case_not_found"}

        open_cases = await self._session.execute(
            select(Case).where(
                Case.type == "ar_invoice",
                Case.counterparty_id == case.counterparty_id,
                Case.status.notin_(["completed", "rejected"]),
            )
        )
        items = [
            OpenInvoiceItem(
                case_number=c.case_number,
                document_number=(c.classification_metadata or {}).get("document_number")
                or (c.workflow_metadata or {}).get("document_number"),
                amount=str(c.amount_value) if c.amount_value else None,
                currency=c.amount_currency or "SGD",
            )
            for c in open_cases.scalars().all()
        ]

        soa = await self._hermes.generate_soa(
            GenerateSOARequest(
                case_id=case.id,
                counterparty_name=case.counterparty_name or "Customer",
                open_invoices=items,
                as_of_date=date.today(),
            )
        )
        output = soa.output
        await self._start_processing(case)
        case.status = "completed"
        case.completed_at = datetime.now(UTC)
        case.workflow_metadata = {
            **(case.workflow_metadata or {}),
            "soa_generated_at": datetime.now(UTC).isoformat(),
            "open_invoice_count": output.open_invoice_count if output else 0,
            "total_outstanding": output.total_outstanding if output else "0",
        }
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="processing_completed",
            from_status="processing",
            to_status="completed",
            actor="ar-worker",
            description="SOA generated",
            metadata={"soa_preview": (output.soa_text[:200] if output else "")},
        )
        await self._session.flush()
        return {"status": "completed", "case_id": str(case.id)}

    async def _recent_invoices(self, counterparty_id: UUID | None) -> list[RecentCase]:
        if not counterparty_id:
            return []
        result = await self._session.execute(
            select(Case)
            .where(
                Case.counterparty_id == counterparty_id,
                Case.type == "ar_invoice",
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
                    document_number=meta.get("document_number")
                    or (c.workflow_metadata or {}).get("document_number"),
                    total_amount=str(c.amount_value) if c.amount_value else None,
                )
            )
        return rows

    async def _post_ar_invoice_journal(
        self, case: Case, inv, amount: Decimal, *, posted: bool, tax_gl_code: str | None = None
    ) -> str:
        ar = await self._ledger.get_account_by_code("1300")
        rev = await self._ledger.get_account_by_code("4100")
        gst_code = tax_gl_code or "2100"
        gst = await self._ledger.get_account_by_code(gst_code)
        if not ar or not rev:
            case.status = "manual_review"
            case.workflow_metadata = {**(case.workflow_metadata or {}), "error_type": "ACCOUNT_NOT_FOUND"}
            return None

        tax = Decimal(inv.tax_amount or "0")
        net = amount - tax
        status = "posted" if posted else "draft"
        entry = await self._ledger.create_journal_entry(
            case_id=case.id,
            case_number=case.case_number,
            status=status,
            entry_date=inv.document_date or date.today(),
            description=f"AR Invoice — {case.counterparty_name} {inv.document_number}",
            reference=inv.document_number,
            currency=inv.currency,
            total=amount,
            posted=posted,
        )
        await self._ledger.add_line(
            entry=entry, line_number=1, account_id=ar.id, debit=amount, credit=Decimal("0")
        )
        await self._ledger.add_line(
            entry=entry, line_number=2, account_id=rev.id, debit=Decimal("0"), credit=net
        )
        if tax > 0 and gst:
            await self._ledger.add_line(
                entry=entry, line_number=3, account_id=gst.id, debit=Decimal("0"), credit=tax
            )
        return str(entry.id)

    async def _post_payment_journal(self, case: Case, amount: Decimal, *, posted: bool) -> None:
        bank = await self._ledger.get_account_by_code("1200")
        ar = await self._ledger.get_account_by_code("1300")
        if not bank or not ar:
            case.status = "manual_review"
            return
        status = "posted" if posted else "draft"
        entry = await self._ledger.create_journal_entry(
            case_id=case.id,
            case_number=case.case_number,
            status=status,
            entry_date=date.today(),
            description=f"AR Payment — {case.counterparty_name}",
            reference=case.case_number,
            currency=case.amount_currency or "SGD",
            total=amount,
            posted=posted,
        )
        await self._ledger.add_line(
            entry=entry, line_number=1, account_id=bank.id, debit=amount, credit=Decimal("0")
        )
        await self._ledger.add_line(
            entry=entry, line_number=2, account_id=ar.id, debit=Decimal("0"), credit=amount
        )

    async def _start_processing(self, case: Case) -> None:
        from_status = case.status
        case.status = "processing"
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="processing_started",
            from_status=from_status,
            to_status="processing",
            actor="ar-worker",
            description="AR Worker began processing",
        )

    async def _timeline_completed(
        self, case: Case, kind: str, ref: str | None, final: str, journal_id: str | None
    ) -> None:
        await self._cases.add_timeline(
            case_id=case.id,
            event_type="processing_completed",
            from_status="processing",
            to_status=final,
            actor="ar-worker",
            description=f"AR {kind} processed — {final}",
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
            actor_name="ar-worker",
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
            actor_name="ar-worker",
        )
