"""Ollama HTTP client for Hermes — `04` §8."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE = os.environ.get("HERMES_OLLAMA_BASE_URL", "http://ollama:11434")
EXTRACTION_MODEL = os.environ.get("HERMES_EXTRACTION_MODEL", "qwen2.5:7b")
VISION_MODEL = os.environ.get("HERMES_VISION_MODEL", "qwen2.5vl:7b")


class OllamaError(Exception):
    pass


async def generate_json(
    *,
    prompt: str,
    model: str | None = None,
    num_ctx: int = 8192,
    num_predict: int = 2048,
    timeout: float = 120.0,
) -> dict[str, Any]:
    payload = {
        "model": model or EXTRACTION_MODEL,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
        },
    }
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
    if resp.status_code >= 400:
        raise OllamaError(f"Ollama HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    raw = data.get("response", "")
    if not raw:
        raise OllamaError("Empty Ollama response")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OllamaError(f"Invalid JSON from Ollama: {raw[:300]}") from exc
    if not isinstance(parsed, dict):
        raise OllamaError("Ollama JSON root must be an object")
    logger.debug(
        "Ollama generate_json model=%s ms=%d",
        payload["model"],
        int((time.perf_counter() - started) * 1000),
    )
    return parsed


async def describe_image(
    *,
    image_base64: str,
    mime_type: str,
    instruction: str,
    model: str | None = None,
    timeout: float = 120.0,
) -> str:
    """Extract text from receipt/invoice image using Ollama vision chat."""
    payload = {
        "model": model or VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": instruction,
                "images": [image_base64],
            }
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2048},
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
    if resp.status_code >= 400:
        raise OllamaError(f"Ollama vision HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    message = data.get("message") or {}
    content = message.get("content", "")
    if not content.strip():
        raise OllamaError("Empty vision response")
    return content.strip()
