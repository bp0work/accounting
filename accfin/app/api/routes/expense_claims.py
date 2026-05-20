"""Expense claims API — `05` §18."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.repositories.user import UserRepository
from app.schemas.auth import TokenData
from app.schemas.expense import (
    ExpenseClaimDetail,
    ExpenseClaimDetailEnvelope,
    ExpenseClaimListItem,
    ExpenseClaimListResponse,
    ExpenseClaimStatusUpdate,
    ExpenseClaimSubmitEnvelope,
    ExpenseClaimSubmitRequest,
    ExpenseClaimSubmitResponse,
    ExpenseLineItemResponse,
)
from app.services.expense_claim_service import ExpenseClaimService

router = APIRouter(prefix="/expense-claims", tags=["Expense Claims"])


def _list_item(claim) -> ExpenseClaimListItem:
    first = claim.line_items[0] if claim.line_items else None
    return ExpenseClaimListItem(
        expense_claim_id=claim.id,
        case_number=claim.case_number,
        merchant=first.merchant if first else None,
        category=first.category if first else None,
        amount_value=str(claim.total_claimed),
        amount_currency=claim.currency,
        receipt_date=first.expense_date if first else None,
        status=claim.status,
        risk_flags=list(claim.risk_flags or []),
        created_at=claim.created_at,
    )


def _detail(claim) -> ExpenseClaimDetail:
    first = claim.line_items[0] if claim.line_items else None
    meta = claim.workflow_metadata or {}
    return ExpenseClaimDetail(
        id=claim.id,
        case_id=claim.case_id,
        case_number=claim.case_number,
        claimant_user_id=claim.claimant_id,
        category=first.category if first else None,
        merchant=first.merchant if first else None,
        amount_value=str(claim.total_claimed),
        amount_currency=claim.currency,
        receipt_date=first.expense_date if first else None,
        purpose=claim.purpose,
        status=claim.status,
        risk_flags=list(claim.risk_flags or []),
        policy_violations=claim.policy_violations or [],
        partial_extraction=bool(meta.get("missing_fields")),
        line_items=[
            ExpenseLineItemResponse(
                id=li.id,
                line_number=li.line_number,
                expense_date=li.expense_date,
                category=li.category,
                description=li.description,
                merchant=li.merchant,
                amount_claimed=str(li.amount_claimed),
                amount_currency=li.currency,
                policy_compliant=li.policy_compliant,
            )
            for li in claim.line_items
        ],
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


@router.post("", response_model=ExpenseClaimSubmitEnvelope, status_code=status.HTTP_201_CREATED)
async def submit_expense_claim(
    body: ExpenseClaimSubmitRequest,
    user: TokenData = Depends(require_permission("expenses:write")),
    session: AsyncSession = Depends(get_db_session),
) -> ExpenseClaimSubmitEnvelope:
    db_user = await UserRepository(session).get_by_id(user.user_id)
    if db_user is None:
        raise ValueError("user not found")
    claim = await ExpenseClaimService(session).submit_claim(db_user, body)
    return ExpenseClaimSubmitEnvelope(
        data=ExpenseClaimSubmitResponse(
            expense_claim_id=claim.id,
            case_id=claim.case_id,
            case_number=claim.case_number,
            status=claim.status,
            created_at=claim.created_at,
        )
    )


@router.get("", response_model=ExpenseClaimListResponse)
async def list_expense_claims(
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    claimant_id: str | None = Query("me"),
    limit: int = Query(50, ge=1, le=200),
    user: TokenData = Depends(require_permission("expenses:read")),
    session: AsyncSession = Depends(get_db_session),
) -> ExpenseClaimListResponse:
    can_read_all = "expenses:approve" in user.permissions
    claims = await ExpenseClaimService(session).list_for_user(
        user_id=user.user_id,
        can_read_all=can_read_all,
        claimant_id=claimant_id,
        status_filter=status_filter,
        category=category,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )
    return ExpenseClaimListResponse(data=[_list_item(c) for c in claims])


@router.get("/{claim_id}", response_model=ExpenseClaimDetailEnvelope)
async def get_expense_claim(
    claim_id: UUID,
    _user: TokenData = Depends(require_permission("expenses:read")),
    session: AsyncSession = Depends(get_db_session),
) -> ExpenseClaimDetailEnvelope:
    claim = await ExpenseClaimService(session).get_detail(claim_id)
    return ExpenseClaimDetailEnvelope(data=_detail(claim))


@router.patch("/{claim_id}/status", response_model=ExpenseClaimDetailEnvelope)
async def update_expense_claim_status(
    claim_id: UUID,
    body: ExpenseClaimStatusUpdate,
    user: TokenData = Depends(require_permission("expenses:write")),
    session: AsyncSession = Depends(get_db_session),
) -> ExpenseClaimDetailEnvelope:
    claim = await ExpenseClaimService(session).withdraw(claim_id, user.user_id)
    return ExpenseClaimDetailEnvelope(data=_detail(claim))
