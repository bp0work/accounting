"""Expense claim API and submission — `05` §18, `19` §4."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppHTTPException
from app.models.case import Case, CaseAttachment
from app.models.expense import ExpenseClaim, ExpenseLineItem
from app.models.user import User
from app.repositories.case import CaseRepository
from app.repositories.expense import ExpenseRepository
from app.schemas.expense import API_CATEGORY_MAP, ExpenseClaimSubmitRequest
from app.services.queue_router import enqueue_accounts
from fastapi import status


class ExpenseClaimService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cases = CaseRepository(session)
        self._expense = ExpenseRepository(session)

    async def submit_claim(
        self, user: User, body: ExpenseClaimSubmitRequest
    ) -> ExpenseClaim:
        if body.receipt_date > date.today():
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_ERROR",
                "receipt_date cannot be in the future",
            )
        try:
            amount = Decimal(body.amount_value)
        except InvalidOperation as exc:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_ERROR",
                "amount_value must be a decimal",
            ) from exc
        if amount <= 0:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_ERROR",
                "amount_value must be greater than zero",
            )

        category = API_CATEGORY_MAP[body.category]
        duplicate = await self._expense.find_duplicate(
            claimant_id=user.id,
            merchant=body.merchant,
            expense_date=body.receipt_date,
            amount=amount,
        )
        if duplicate:
            raise AppHTTPException(
                status.HTTP_409_CONFLICT,
                "DUPLICATE_CLAIM",
                "Duplicate expense claim detected",
                message=f"Duplicate claim exists: {duplicate.case_number}",
            )

        case = await self._cases.create_manual_case(
            case_type="expense_claim",
            subject=f"Expense — {body.merchant}",
            description=body.purpose,
            amount_value=amount,
            amount_currency=body.amount_currency,
            priority="medium",
        )
        case.status = "classified"
        case.stp_eligible = False
        await self._session.flush()

        receipt_id = body.attachment_ids[0]
        existing_att = await self._session.get(CaseAttachment, receipt_id)
        if existing_att is None:
            self._session.add(
                CaseAttachment(
                    id=receipt_id,
                    case_id=case.id,
                    filename="receipt.pdf",
                    mime_type="application/pdf",
                    size_bytes=1,
                    storage_path=f"/data/attachments/{receipt_id}.pdf",
                    uploaded_by=user.id,
                )
            )
            await self._session.flush()
        elif existing_att.case_id != case.id:
            raise AppHTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_ERROR",
                "attachment_ids must belong to this claim case",
            )

        claim = ExpenseClaim(
            case_id=case.id,
            case_number=case.case_number,
            claimant_id=user.id,
            claimant_name=user.display_name,
            submission_date=date.today(),
            claim_period_from=body.receipt_date,
            claim_period_to=body.receipt_date,
            purpose=body.purpose,
            department=user.department,
            currency=body.amount_currency,
            total_claimed=amount,
            status="processing",
            submitted_via="ui",
            workflow_metadata={"source": "api", "attachment_ids": [str(a) for a in body.attachment_ids]},
        )
        line = ExpenseLineItem(
            line_number=1,
            expense_date=body.receipt_date,
            category=category,
            description=body.purpose[:500],
            merchant=body.merchant,
            currency=body.amount_currency,
            amount_claimed=amount,
            amount_sgd=amount if body.amount_currency == "SGD" else None,
            receipt_attachment_id=receipt_id,
        )
        claim.line_items.append(line)
        await self._expense.add_claim(claim)
        case.status = "processing"
        await self._session.flush()

        await enqueue_accounts(
            case_id=case.id,
            case_type="expense_claim",
            case_number=case.case_number,
            priority=case.priority,
            stp_eligible=False,
            confidence_score=1.0,
        )
        await self._session.commit()
        return claim

    async def list_for_user(
        self,
        *,
        user_id: UUID,
        can_read_all: bool,
        claimant_id: str | None,
        status_filter: str | None,
        category: str | None,
        from_date: date | None,
        to_date: date | None,
        limit: int,
    ) -> list[ExpenseClaim]:
        filter_claimant = user_id
        if can_read_all and claimant_id == "all":
            filter_claimant = None
        elif can_read_all and claimant_id not in (None, "me"):
            try:
                filter_claimant = UUID(claimant_id)
            except ValueError:
                filter_claimant = user_id
        return await self._expense.list_claims(
            claimant_id=filter_claimant,
            status=status_filter,
            category=API_CATEGORY_MAP.get(category, category) if category else None,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )

    async def get_detail(self, claim_id: UUID) -> ExpenseClaim:
        claim = await self._expense.get_claim(claim_id)
        if claim is None:
            raise AppHTTPException(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Expense claim not found"
            )
        return claim

    async def withdraw(self, claim_id: UUID, user_id: UUID) -> ExpenseClaim:
        claim = await self.get_detail(claim_id)
        if claim.claimant_id != user_id:
            raise AppHTTPException(
                status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Only the claimant may withdraw"
            )
        if claim.status not in ("submitted", "processing", "draft"):
            raise AppHTTPException(
                status.HTTP_409_CONFLICT,
                "INVALID_STATUS",
                "Claim cannot be withdrawn in its current status",
            )
        claim.status = "rejected"
        claim.rejection_reason = "withdrawn by claimant"
        case = await self._cases.get(claim.case_id)
        if case:
            case.status = "rejected"
        await self._session.commit()
        return claim
