from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_ok():
    with (
        patch("app.api.routes.health.check_database", new_callable=AsyncMock, return_value="ok"),
        patch("app.api.routes.health.check_redis", new_callable=AsyncMock, return_value="ok"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["components"]["database"] == "ok"
    assert data["components"]["redis"] == "ok"
