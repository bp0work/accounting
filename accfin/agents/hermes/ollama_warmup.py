"""Pre-load Ollama extraction model on Hermes startup — avoids cold-start HERMES_TIMEOUT."""

from __future__ import annotations

import logging

from agents.hermes.ollama_client import (
    EXTRACTION_MODEL,
    OllamaError,
    OLLAMA_WARMUP_ENABLED,
    generate_json,
)

logger = logging.getLogger(__name__)


async def warmup_extraction_model() -> None:
    if not OLLAMA_WARMUP_ENABLED:
        logger.info("Ollama warmup disabled (HERMES_OLLAMA_WARMUP=false)")
        return
    try:
        await generate_json(
            prompt='Return JSON only: {"ready": true}',
            model=EXTRACTION_MODEL,
            num_predict=16,
        )
        logger.info("Ollama extraction model warmed: %s", EXTRACTION_MODEL)
    except OllamaError as exc:
        logger.warning("Ollama warmup failed (Hermes will still start): %s", exc)
