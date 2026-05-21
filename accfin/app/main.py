import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    approvals,
    audit,
    auth,
    cases,
    events,
    expense_claims,
    health,
    internal_jobs,
    mail,
    mail_escalations,
    metrics,
    notifications,
    reconciliation,
)
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS
from app.core.config import get_settings
from app.core.exceptions import AppHTTPException

settings = get_settings()

app = FastAPI(
    title="AI Finance Operations Platform API",
    version=settings.version,
    description="Phase 11b — executive email SOP, finance daily log, escalations.",
)


@app.middleware("http")
async def prometheus_request_metrics(request: Request, call_next):
    if not request.url.path.startswith("/metrics"):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        route = request.scope.get("route")
        endpoint = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(
            method=request.method, endpoint=endpoint, status=str(response.status_code)
        ).inc()
        HTTP_LATENCY.labels(method=request.method, endpoint=endpoint).observe(elapsed)
        return response
    return await call_next(request)

_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://finance.bp0.work",
    "https://admin.bp0.work",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(auth.router)
app.include_router(mail.router)
app.include_router(cases.router)
app.include_router(reconciliation.router)
app.include_router(approvals.router)
app.include_router(notifications.router)
app.include_router(events.router)
app.include_router(audit.router)
app.include_router(expense_claims.router)
app.include_router(internal_jobs.router)
app.include_router(mail_escalations.router)


@app.exception_handler(AppHTTPException)
async def app_http_exception_handler(_request, exc: AppHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.detail)
