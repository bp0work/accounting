"""Prometheus scrape endpoint."""

from fastapi import APIRouter
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.metrics import metrics_payload

router = APIRouter(tags=["Monitoring"])


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    settings = get_settings()
    if not settings.prometheus_enabled:
        return Response(status_code=404, content="Metrics disabled")
    body, content_type = metrics_payload()
    return Response(content=body, media_type=content_type)
