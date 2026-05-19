from fastapi import FastAPI

from app.api.routes import health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="AI Finance Operations Platform API",
    version=settings.version,
    description="Phase 1 infrastructure — health and connectivity baseline.",
)

app.include_router(health.router)
