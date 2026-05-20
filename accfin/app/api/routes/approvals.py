"""Approvals API — `05` §7."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.core.exceptions import AppHTTPException
from app.repositories.approval import ApprovalRepository
from app.repositories.case import CaseRepository
from app.schemas.approval import (
    ApprovalActionResponse,
    ApprovalDetailResponse,
    ApprovalListItem,
    ApprovalListResponse,
    ApproveRequest,
    MoneyAmount,
    RejectRequest,
    UserRef,
)
from app.schemas.auth import TokenData
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def _to_list_item(approval, case, approver) -> ApprovalListItem:
    amount = None
    if approval.amount_value is not None:
        amount = MoneyAmount(
            value=str(approval.amount_value), currency=approval.amount_currency or "SGD"
        )
    requested_from = None
    if approver:
        requested_from = UserRef(
            id=approver.id, name=approver.display_name, email=approver.email
        )
    return ApprovalListItem(
        id=approval.id,
        case_id=case.id,
        case_number=case.case_number,
        case_type=case.type,
        tier=approval.tier,
        status=approval.status,
        subject=case.subject,
        description=approval.comments,
        amount=amount,
        risk_flags=case.risk_flags or [],
        sla_deadline=case.sla_deadline,
        sla_status=case.sla_status,
        requested_from=requested_from,
        created_at=approval.created_at,
        responded_at=approval.decided_at,
        response_note=approval.comments if approval.status != "pending" else None,
    )


@router.get("", response_model=ApprovalListResponse)
async def list_approvals(
    status: str | None = Query(default=None),
    tier: int | None = Query(default=None),
    case_id: UUID | None = Query(default=None),
    my_pending: bool = Query(default=False),
    _user: TokenData = Depends(require_permission("approvals:read")),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalListResponse:
    repo = ApprovalRepository(session)
    rows = await repo.list_approvals(
        status=status,
        tier=tier,
        case_id=case_id,
        my_pending_user_id=_user.user_id if my_pending else None,
        limit=50,
    )
    items = []
    for approval, case in rows:
        approver = await repo.get_user(approval.approver_id) if approval.approver_id else None
        items.append(_to_list_item(approval, case, approver))
    return ApprovalListResponse(data=items)


@router.get("/{approval_id}", response_model=ApprovalDetailResponse)
async def get_approval(
    approval_id: UUID,
    _user: TokenData = Depends(require_permission("approvals:read")),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalDetailResponse:
    repo = ApprovalRepository(session)
    approval = await repo.get(approval_id)
    if approval is None:
        raise AppHTTPException(404, "NOT_FOUND", "Approval not found")
    case = await CaseRepository(session).get(approval.case_id)
    if case is None:
        raise AppHTTPException(404, "CASE_NOT_FOUND", "Case not found")
    approver = await repo.get_user(approval.approver_id) if approval.approver_id else None
    base = _to_list_item(approval, case, approver)
    return ApprovalDetailResponse(**base.model_dump(), journal_entry_id=approval.journal_entry_id)


@router.post("/{approval_id}/approve", response_model=ApprovalActionResponse)
async def approve_approval(
    approval_id: UUID,
    body: ApproveRequest,
    user: TokenData = Depends(require_permission("approvals:approve")),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalActionResponse:
    service = ApprovalService(session)
    approval = await service.approve(
        approval_id, user, note=body.note, journal_entry_id=body.journal_entry_id
    )
    await session.commit()
    return ApprovalActionResponse(
        id=approval.id,
        status=approval.status,
        decided_at=approval.decided_at,
        comments=approval.comments,
    )


@router.post("/{approval_id}/reject", response_model=ApprovalActionResponse)
async def reject_approval(
    approval_id: UUID,
    body: RejectRequest,
    user: TokenData = Depends(require_permission("approvals:approve")),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovalActionResponse:
    service = ApprovalService(session)
    approval = await service.reject(
        approval_id, user, reason=body.reason, return_to=body.return_to
    )
    await session.commit()
    return ApprovalActionResponse(
        id=approval.id,
        status=approval.status,
        decided_at=approval.decided_at,
        comments=approval.comments,
    )
