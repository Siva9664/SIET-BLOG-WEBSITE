"""Tests verifying strict RAG grounding instructions and prompt construction."""

from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.infrastructure.ai.constants import DEFAULT_STRICT_GROUNDING_INSTRUCTION
from app.infrastructure.ai.ollama_provider import OllamaProvider


@pytest.mark.asyncio
async def test_strict_grounding_instruction_content():
    """Verify strict grounding rules contain the 4 core mandatory mandates."""
    assert "Use ONLY supplied source / RAG context" in DEFAULT_STRICT_GROUNDING_INSTRUCTION
    assert "Never invent names, dates, achievements" in DEFAULT_STRICT_GROUNDING_INSTRUCTION
    assert "Missing information must be represented as null or empty values" in DEFAULT_STRICT_GROUNDING_INSTRUCTION
    assert "Do NOT fabricate content to fill a template" in DEFAULT_STRICT_GROUNDING_INSTRUCTION


@pytest.mark.asyncio
async def test_strict_grounding_injected_in_ollama_messages():
    """Verify OllamaProvider automatically injects strict grounding into system role message."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434")

    mock_response = httpx.Response(
        status_code=200,
        json={"message": {"role": "assistant", "content": "Grounded Response"}},
        request=httpx.Request("POST", "http://mock-ollama:11434/api/chat"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        await provider.generate_text("Prompt without explicit system instruction")

        call_json = mock_post.call_args[1]["json"]
        system_msg = next(
            (m for m in call_json["messages"] if m["role"] == "system"), None
        )
        assert system_msg is not None
        assert DEFAULT_STRICT_GROUNDING_INSTRUCTION in system_msg["content"]
