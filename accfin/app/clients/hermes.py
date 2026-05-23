"""Hermes HTTP client — `04` §6."""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.schemas.hermes import (
    CheckDuplicateRequest,
    CheckDuplicateResponse,
    ClassifyEmailRequest,
    ClassifyEmailResponse,
    DocumentTextRequest,
    DocumentTextResponse,
    ExtractInvoiceRequest,
    ExtractInvoiceResponse,
    ExtractPaymentAdviceRequest,
    ExtractPaymentAdviceResponse,
    GenerateSOARequest,
    GenerateSOAResponse,
    ValidatePOMatchRequest,
    ValidatePOMatchResponse,
    SuggestMatchesRequest,
    SuggestMatchesResponse,
    ExtractExpenseClaimRequest,
    ExtractExpenseClaimResponse,
    ExtractExpenseClaimOutput,
)

logger = logging.getLogger(__name__)


class HermesError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        super().__init__(message)


class HermesClient:
    def __init__(self, base_url: str | None = None, *, timeout: float = 120.0) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.hermes_base_url).rstrip("/")
        self._timeout = timeout

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise HermesError("HERMES_TIMEOUT", str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HermesError("HERMES_UNAVAILABLE", str(exc)) from exc

        if resp.status_code >= 500:
            raise HermesError("HERMES_UNAVAILABLE", resp.text)
        if resp.status_code >= 400:
            raise HermesError("HERMES_PARSE_ERROR", resp.text)
        return resp.json()

    async def classify_email(self, request: ClassifyEmailRequest) -> ClassifyEmailResponse:
        data = await self._post("/classify/email", request.model_dump(mode="json"))
        result = ClassifyEmailResponse.model_validate(data)
        if not result.success:
            raise HermesError(
                result.error_code or "HERMES_PARSE_ERROR",
                result.error_message or "Classification failed",
            )
        return result

    async def extract_invoice(self, request: ExtractInvoiceRequest) -> ExtractInvoiceResponse:
        data = await self._post("/extract/invoice", request.model_dump(mode="json"))
        return ExtractInvoiceResponse.model_validate(data)

    async def extract_payment_advice(
        self, request: ExtractPaymentAdviceRequest
    ) -> ExtractPaymentAdviceResponse:
        data = await self._post("/extract/payment-advice", request.model_dump(mode="json"))
        return ExtractPaymentAdviceResponse.model_validate(data)

    async def check_duplicate(self, request: CheckDuplicateRequest) -> CheckDuplicateResponse:
        data = await self._post("/validate/duplicate", request.model_dump(mode="json"))
        return CheckDuplicateResponse.model_validate(data)

    async def generate_soa(self, request: GenerateSOARequest) -> GenerateSOAResponse:
        data = await self._post("/generate/soa", request.model_dump(mode="json"))
        return GenerateSOAResponse.model_validate(data)

    async def validate_po_match(
        self, request: ValidatePOMatchRequest
    ) -> ValidatePOMatchResponse:
        data = await self._post("/validate/po-match", request.model_dump(mode="json"))
        return ValidatePOMatchResponse.model_validate(data)

    async def suggest_matches(
        self, request: SuggestMatchesRequest
    ) -> SuggestMatchesResponse:
        data = await self._post(
            "/reconciliation/suggest-matches", request.model_dump(mode="json")
        )
        return SuggestMatchesResponse.model_validate(data)

    async def extract_expense_claim(
        self, request: ExtractExpenseClaimRequest
    ) -> ExtractExpenseClaimOutput:
        data = await self._post(
            "/extract/expense-claim", request.model_dump(mode="json")
        )
        parsed = ExtractExpenseClaimResponse.model_validate(data)
        if not parsed.success or parsed.output is None:
            raise HermesError(
                "HERMES_PARSE_ERROR",
                parsed.error_message or "Expense extraction failed",
            )
        return parsed.output

    async def extract_document_text(
        self,
        *,
        filename: str,
        mime_type: str,
        content_base64: bytes | str,
    ) -> str:
        import base64

        if isinstance(content_base64, bytes):
            encoded = base64.b64encode(content_base64).decode("ascii")
        else:
            encoded = content_base64
        req = DocumentTextRequest(
            filename=filename,
            mime_type=mime_type,
            content_base64=encoded,
        )
        data = await self._post("/extract/document-text", req.model_dump(mode="json"))
        parsed = DocumentTextResponse.model_validate(data)
        if not parsed.success or not parsed.extracted_text.strip():
            raise HermesError(
                "HERMES_PARSE_ERROR",
                parsed.error_message or "Document text extraction failed",
            )
        return parsed.extracted_text
