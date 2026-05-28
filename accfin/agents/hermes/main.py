import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI

from agents.hermes.classify import classify_email_stub
from agents.hermes.document_text import extract_document_text
from agents.hermes.expense_extract import extract_expense_claim_llm
from agents.hermes.llm_extract import extract_invoice_llm, extract_payment_advice_llm
from agents.hermes.reconcile import suggest_matches_stub
from agents.hermes.extract import (
    check_duplicate_stub,
    generate_soa_stub,
    validate_po_match_stub,
)
from app.schemas.hermes import (
    CheckDuplicateRequest,
    CheckDuplicateResponse,
    ClassifyEmailRequest,
    ClassifyEmailResponse,
    DocumentTextRequest,
    DocumentTextResponse,
    ExtractExpenseClaimRequest,
    ExtractExpenseClaimResponse,
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
)

OLLAMA_BASE = os.environ.get("HERMES_OLLAMA_BASE_URL", "http://ollama:11434")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from agents.hermes.ollama_warmup import warmup_extraction_model

    await warmup_extraction_model()
    yield


app = FastAPI(
    title="Hermes",
    version="0.7.0-ollama-keepalive",
    lifespan=_lifespan,
)


@app.get("/health")
async def health():
    components: dict[str, str] = {"hermes": "ok"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            components["ollama"] = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        components["ollama"] = f"error: {exc}"

    status = "ok" if components.get("ollama") == "ok" else "degraded"
    return {
        "status": status,
        "timestamp": datetime.now(UTC).isoformat(),
        "components": components,
    }


@app.post("/classify/email", response_model=ClassifyEmailResponse)
async def classify_email(request: ClassifyEmailRequest) -> ClassifyEmailResponse:
    return classify_email_stub(request)


@app.post("/extract/invoice", response_model=ExtractInvoiceResponse)
async def extract_invoice(request: ExtractInvoiceRequest) -> ExtractInvoiceResponse:
    return await extract_invoice_llm(request)


@app.post("/extract/payment-advice", response_model=ExtractPaymentAdviceResponse)
async def extract_payment_advice(
    request: ExtractPaymentAdviceRequest,
) -> ExtractPaymentAdviceResponse:
    return await extract_payment_advice_llm(request)


@app.post("/extract/expense-claim", response_model=ExtractExpenseClaimResponse)
async def extract_expense_claim(
    request: ExtractExpenseClaimRequest,
) -> ExtractExpenseClaimResponse:
    return await extract_expense_claim_llm(request)


@app.post("/extract/document-text", response_model=DocumentTextResponse)
async def extract_document_text_route(
    request: DocumentTextRequest,
) -> DocumentTextResponse:
    return await extract_document_text(request)


@app.post("/validate/duplicate", response_model=CheckDuplicateResponse)
async def check_duplicate(request: CheckDuplicateRequest) -> CheckDuplicateResponse:
    return check_duplicate_stub(request)


@app.post("/generate/soa", response_model=GenerateSOAResponse)
async def generate_soa(request: GenerateSOARequest) -> GenerateSOAResponse:
    return generate_soa_stub(request)


@app.post("/validate/po-match", response_model=ValidatePOMatchResponse)
async def validate_po_match(request: ValidatePOMatchRequest) -> ValidatePOMatchResponse:
    return validate_po_match_stub(request)


@app.post("/reconciliation/suggest-matches", response_model=SuggestMatchesResponse)
async def suggest_matches(request: SuggestMatchesRequest) -> SuggestMatchesResponse:
    return suggest_matches_stub(request)
