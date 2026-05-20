"""Expense claim persistence — `19` §3."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.expense import ExpenseClaim, ExpenseLineItem, ExpensePolicy


class ExpenseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_claim(self, claim_id: UUID) -> ExpenseClaim | None:
        result = await self._session.execute(
            select(ExpenseClaim)
            .options(selectinload(ExpenseClaim.line_items))
            .where(ExpenseClaim.id == claim_id, ExpenseClaim.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_claim_by_case(self, case_id: UUID) -> ExpenseClaim | None:
        result = await self._session.execute(
            select(ExpenseClaim)
            .options(selectinload(ExpenseClaim.line_items))
            .where(ExpenseClaim.case_id == case_id, ExpenseClaim.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def find_duplicate(
        self,
        *,
        claimant_id: UUID,
        merchant: str,
        expense_date: date,
        amount: Decimal,
        exclude_id: UUID | None = None,
    ) -> ExpenseClaim | None:
        stmt = (
            select(ExpenseClaim)
            .join(ExpenseLineItem)
            .where(
                ExpenseClaim.claimant_id == claimant_id,
                ExpenseClaim.deleted_at.is_(None),
                ExpenseLineItem.merchant == merchant,
                ExpenseLineItem.expense_date == expense_date,
                ExpenseLineItem.amount_claimed == amount,
                ExpenseClaim.status.notin_(("rejected", "draft")),
            )
        )
        if exclude_id:
            stmt = stmt.where(ExpenseClaim.id != exclude_id)
        result = await self._session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def list_claims(
        self,
        *,
        claimant_id: UUID | None = None,
        status: str | None = None,
        category: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExpenseClaim]:
        stmt: Select = (
            select(ExpenseClaim)
            .options(selectinload(ExpenseClaim.line_items))
            .where(ExpenseClaim.deleted_at.is_(None))
        )
        if claimant_id:
            stmt = stmt.where(ExpenseClaim.claimant_id == claimant_id)
        if status:
            stmt = stmt.where(ExpenseClaim.status == status)
        if category:
            stmt = stmt.join(ExpenseLineItem).where(ExpenseLineItem.category == category)
        if from_date:
            stmt = stmt.where(ExpenseClaim.submission_date >= from_date)
        if to_date:
            stmt = stmt.where(ExpenseClaim.submission_date <= to_date)
        stmt = stmt.order_by(ExpenseClaim.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_active_policies(self) -> list[ExpensePolicy]:
        result = await self._session.execute(
            select(ExpensePolicy).where(ExpensePolicy.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def add_claim(self, claim: ExpenseClaim) -> ExpenseClaim:
        self._session.add(claim)
        await self._session.flush()
        return claim
