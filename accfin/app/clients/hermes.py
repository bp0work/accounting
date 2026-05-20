"""Hermes HTTP client — `04` §6."""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.schemas.hermes import ClassifyEmailRequest, ClassifyEmailResponse

logger = logging.getLogger(__name__)


class HermesError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        super().__init__(message)


class HermesClient:
    def __init__(self, base_url: str | None = None, *, timeout: float = 30.0) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.hermes_base_url).rstrip("/")
        self._timeout = timeout

    async def classify_email(self, request: ClassifyEmailRequest) -> ClassifyEmailResponse:
        url = f"{self._base_url}/classify/email"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=request.model_dump(mode="json"))
        except httpx.TimeoutException as exc:
            raise HermesError("HERMES_TIMEOUT", str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HermesError("HERMES_UNAVAILABLE", str(exc)) from exc

        if resp.status_code >= 500:
            raise HermesError("HERMES_UNAVAILABLE", resp.text)
        if resp.status_code >= 400:
            raise HermesError("HERMES_PARSE_ERROR", resp.text)

        data = resp.json()
        result = ClassifyEmailResponse.model_validate(data)
        if not result.success:
            raise HermesError(
                result.error_code or "HERMES_PARSE_ERROR",
                result.error_message or "Classification failed",
            )
        return result
