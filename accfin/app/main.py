import time

from fastapi import APIRouter, FastAPI, Request
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
    admin,
    admin_counterparty,
    mail_actions,
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
    description="finance.mmlogistix.bp0.work — UI at /; REST API under /api (Traefik PathPrefix `/api`).",
)


@app.middleware("http")
async def prometheus_request_metrics(request: Request, call_next):
    if not request.url.path.startswith("/api/metrics"):
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(metrics.router)
api_router.include_router(auth.router)
api_router.include_router(mail.router)
api_router.include_router(cases.router)
api_router.include_router(reconciliation.router)
api_router.include_router(approvals.router)
api_router.include_router(notifications.router)
api_router.include_router(events.router)
api_router.include_router(audit.router)
api_router.include_router(expense_claims.router)
api_router.include_router(internal_jobs.router)
api_router.include_router(mail_actions.router)
api_router.include_router(admin.router)
api_router.include_router(admin_counterparty.router)
app.include_router(api_router)


@app.exception_handler(AppHTTPException)
async def app_http_exception_handler(_request, exc: AppHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.detail)
