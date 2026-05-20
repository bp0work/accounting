from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes import auth, health, mail
from app.core.config import get_settings
from app.core.exceptions import AppHTTPException

settings = get_settings()

app = FastAPI(
    title="AI Finance Operations Platform API",
    version=settings.version,
    description="Phase 3 — auth, RBAC, and Mail Gateway intake.",
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(mail.router)


@app.exception_handler(AppHTTPException)
async def app_http_exception_handler(_request, exc: AppHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.detail)
