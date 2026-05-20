from datetime import UTC, datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import check_database
from app.core.metrics import HEALTH_COMPONENT
from app.core.redis_client import check_redis

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Get system health")
async def get_health():
    """Matches `21_openapi.yaml` HealthResponse — Phase 1: database + redis only."""
    components: dict[str, str] = {}
    overall = "ok"

    try:
        components["database"] = await check_database()
        HEALTH_COMPONENT.labels(component="database").set(
            1 if components["database"] == "ok" else 0
        )
    except Exception as exc:  # noqa: BLE001 — health probe must not raise
        components["database"] = f"error: {exc}"
        HEALTH_COMPONENT.labels(component="database").set(0)
        overall = "degraded"

    try:
        components["redis"] = await check_redis()
        HEALTH_COMPONENT.labels(component="redis").set(1 if components["redis"] == "ok" else 0)
    except Exception as exc:  # noqa: BLE001
        components["redis"] = f"error: {exc}"
        HEALTH_COMPONENT.labels(component="redis").set(0)
        overall = "degraded"

    body = {
        "status": overall,
        "version": get_settings().version,
        "timestamp": datetime.now(UTC).isoformat(),
        "components": components,
    }
    code = status.HTTP_200_OK if overall == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=code, content=body)
