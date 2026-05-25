"""Wasabi storage for Client Admin regulatory / policy PDFs."""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import status
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.core.exceptions import AppHTTPException

logger = logging.getLogger(__name__)

TRAVEL_EXPENSE_POLICY_PATH = "transactions/regulatory/travel-expense-policy.pdf"


class RegulatoryStorageService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _client(self):
        return boto3.client(
            "s3",
            endpoint_url=self._settings.wasabi_endpoint_url,
            aws_access_key_id=self._settings.wasabi_access_key_id,
            aws_secret_access_key=self._settings.wasabi_secret_access_key,
            region_name=self._settings.wasabi_region,
            config=Config(signature_version="s3v4"),
        )

    def _put_sync(self, *, key: str, body: bytes, content_type: str) -> None:
        self._client().put_object(
            Bucket=self._settings.wasabi_bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    def _get_sync(self, *, key: str) -> tuple[bytes, str]:
        resp = self._client().get_object(Bucket=self._settings.wasabi_bucket, Key=key)
        data = resp["Body"].read()
        ctype = resp.get("ContentType") or "application/pdf"
        return data, ctype

    def _presign_sync(self, *, key: str, expires: int = 3600) -> str:
        return self._client().generate_presigned_url(
            "get_object",
            Params={"Bucket": self._settings.wasabi_bucket, "Key": key},
            ExpiresIn=expires,
        )

    async def upload_bytes(self, *, key: str, body: bytes, content_type: str) -> None:
        if not self._settings.wasabi_configured:
            raise AppHTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "WASABI_NOT_CONFIGURED",
                "Object storage is not configured; contact the platform administrator.",
            )
        try:
            await asyncio.to_thread(
                self._put_sync, key=key, body=body, content_type=content_type
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Wasabi upload failed for %s: %s", key, exc)
            raise AppHTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "STORAGE_UPLOAD_FAILED",
                "Failed to upload document to storage.",
            ) from exc

    async def download_response(self, *, key: str, filename: str) -> StreamingResponse:
        if not self._settings.wasabi_configured:
            raise AppHTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "WASABI_NOT_CONFIGURED",
                "Object storage is not configured.",
            )
        try:
            data, ctype = await asyncio.to_thread(self._get_sync, key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "NoSuchKey":
                raise AppHTTPException(
                    status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Document file not found in storage."
                ) from exc
            raise AppHTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "STORAGE_DOWNLOAD_FAILED",
                "Failed to download document.",
            ) from exc
        except BotoCoreError as exc:
            raise AppHTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "STORAGE_DOWNLOAD_FAILED",
                "Failed to download document.",
            ) from exc
        return StreamingResponse(
            BytesIO(data),
            media_type=ctype,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    async def presigned_url(self, *, key: str) -> str | None:
        if not self._settings.wasabi_configured:
            return None
        try:
            return await asyncio.to_thread(self._presign_sync, key=key)
        except (BotoCoreError, ClientError):
            return None
