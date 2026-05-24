"""Manager escalation email action links — `05` §8.8a."""

from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import AppHTTPException
from app.services.escalation_service import EscalationService
from app.services.mail_escalation_pages import (
    html_escalation_confirmation,
    html_escalation_form,
)

router = APIRouter(prefix="/mail/escalations", tags=["Mail Gateway"])


def _confirmation_html(result, *, case_number: str) -> str:
    return html_escalation_confirmation(
        case_number=case_number,
        action=result.action,
        comment=getattr(result, "manager_comment", None),
        target_email=result.target_email,
        message=result.message,
    )


@router.get("/{escalation_id}/respond")
async def respond_escalation_get(
    request: Request,
    escalation_id: UUID,
    action: str = Query(...),
    token: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
):
    service = EscalationService(session)
    try:
        ctx = await service.get_respond_context(
            escalation_id, action=action, wire_token=token
        )
    except AppHTTPException as exc:
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return HTMLResponse(
            f"<html><body><h1>Error</h1><p>{exc.detail.get('error', {}).get('message', 'Invalid request')}</p></body></html>",
            status_code=exc.status_code,
        )

    if "application/json" in request.headers.get("accept", ""):
        if ctx.already_responded and ctx.result:
            return ctx.result
        return {
            "escalation_id": str(ctx.escalation_id),
            "case_id": str(ctx.case_id),
            "case_number": ctx.case_number,
            "action": ctx.action,
            "status": ctx.status,
            "pending": ctx.status == "pending",
        }

    if ctx.already_responded and ctx.result:
        return HTMLResponse(
            _confirmation_html(ctx.result, case_number=ctx.case_number)
        )

    return HTMLResponse(
        html_escalation_form(
            escalation_id=ctx.escalation_id,
            case_number=ctx.case_number,
            action=ctx.action,
            token=token,
        )
    )


@router.post("/{escalation_id}/respond")
async def respond_escalation_post(
    request: Request,
    escalation_id: UUID,
    action: str = Query(...),
    token: str = Query(...),
    comment: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    if comment is None:
        comment = request.query_params.get("comment")
    service = EscalationService(session)
    result = await service.respond(
        escalation_id,
        action=action,
        wire_token=token,
        comment=comment,
    )
    case_number = await service.get_case_number(result.case_id)
    if "application/json" in request.headers.get("accept", ""):
        payload = result.model_dump()
        payload["case_number"] = case_number
        return payload
    return HTMLResponse(
        _confirmation_html(result, case_number=case_number or str(result.case_id))
    )
