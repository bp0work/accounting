from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    approvals,
    auth,
    cases,
    events,
    health,
    mail,
    notifications,
    reconciliation,
)
from app.core.config import get_settings
from app.core.exceptions import AppHTTPException

settings = get_settings()

app = FastAPI(
    title="AI Finance Operations Platform API",
    version=settings.version,
    description="Phase 9 — auth, approvals, notifications, SSE, workers, and reconciliation.",
)

_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://finance.bp0.work",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(mail.router)
app.include_router(cases.router)
app.include_router(reconciliation.router)
app.include_router(approvals.router)
app.include_router(notifications.router)
app.include_router(events.router)


@app.exception_handler(AppHTTPException)
async def app_http_exception_handler(_request, exc: AppHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.detail)
