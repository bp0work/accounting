"""Chart of Accounts API — expense account lookup for parsing confirmation UI."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import require_permission
from app.models.ledger import CoaAccount
from app.schemas.auth import TokenData

router = APIRouter(prefix="/coa-accounts", tags=["Chart of Accounts"])


class CoaAccountResponse(BaseModel):
    id: UUID
    account_code: str
    account_name: str
    account_subtype: str | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[CoaAccountResponse])
async def list_coa_accounts(
    account_type: str | None = Query(None),
    is_active: bool = Query(True),
    session: AsyncSession = Depends(get_db_session),
    _: TokenData = Depends(require_permission("expenses:read")),
) -> list[CoaAccountResponse]:
    q = select(CoaAccount).where(CoaAccount.is_active == is_active)
    if account_type:
        q = q.where(CoaAccount.account_type == account_type)
    q = q.order_by(CoaAccount.account_code)
    result = await session.execute(q)
    return list(result.scalars().all())
