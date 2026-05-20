import os
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI

from agents.hermes.classify import classify_email_stub
from app.schemas.hermes import ClassifyEmailRequest, ClassifyEmailResponse

app = FastAPI(title="Hermes", version="0.2.0-phase5-stub")

OLLAMA_BASE = os.environ.get("HERMES_OLLAMA_BASE_URL", "http://ollama:11434")


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
    """MVP classifier — rule-based stub; Ollama integration in a later phase."""
    return classify_email_stub(request)
