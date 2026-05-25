"""Metrics endpoint smoke test."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_text():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/metrics")
    assert response.status_code == 200
    assert b"finance_http_requests_total" in response.content
