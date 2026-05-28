"""Unit tests — Ollama client keep-alive and timeout defaults."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.hermes import ollama_client as oc


@pytest.mark.asyncio
async def test_generate_json_includes_keep_alive(monkeypatch):
    monkeypatch.setattr(oc, "OLLAMA_KEEP_ALIVE", "24h")
    monkeypatch.setattr(oc, "OLLAMA_TIMEOUT_SECONDS", 180.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": '{"ok": true}'}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("agents.hermes.ollama_client.httpx.AsyncClient", return_value=mock_client):
        result = await oc.generate_json(prompt='{"x":1}', num_predict=8)

    assert result == {"ok": True}
    call_kwargs = mock_client.post.call_args
    payload = call_kwargs.kwargs["json"]
    assert payload["keep_alive"] == "24h"
