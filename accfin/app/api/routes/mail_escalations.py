"""Manager escalation email links — `05` §8.8a."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.executive_mail import EscalationRespondResult
from app.services.escalation_service import EscalationService

router = APIRouter(prefix="/mail/escalations", tags=["Mail Gateway"])


def _html_confirmation(action: str, case_id: UUID) -> str:
    return f"""<!DOCTYPE html><html><body>
<h1>Escalation {action.title()}</h1>
<p>Case <code>{case_id}</code> has been updated.</p>
</body></html>"""


@router.get("/{escalation_id}/respond")
async def respond_escalation_get(
    request: Request,
    escalation_id: UUID,
    action: str = Query(...),
    token: str = Query(...),
    comment: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    service = EscalationService(session)
    result = await service.respond(
        escalation_id, action=action, wire_token=token, comment=comment
    )
    if "application/json" in request.headers.get("accept", ""):
        return result
    return HTMLResponse(_html_confirmation(result.action, result.case_id))


@router.post("/{escalation_id}/respond")
async def respond_escalation_post(
    escalation_id: UUID,
    action: str = Query(...),
    token: str = Query(...),
    comment: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    service = EscalationService(session)
    result = await service.respond(
        escalation_id, action=action, wire_token=token, comment=comment
    )
    return HTMLResponse(_html_confirmation(result.action, result.case_id))
