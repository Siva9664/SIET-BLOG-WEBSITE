"""Unit tests verifying Gemini and OpenAI providers remain operational with mocks."""

import json
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from pydantic import BaseModel

from app.infrastructure.ai.exceptions import AIConfigurationError
from app.infrastructure.ai.gemini_provider import GeminiProvider
from app.infrastructure.ai.openai_provider import OpenAIProvider


class SimpleTestSchema(BaseModel):
    message: str


@pytest.mark.asyncio
async def test_gemini_provider_unconfigured_raises_error():
    """Verify GeminiProvider raises AIConfigurationError when no API key is provided."""
    provider = GeminiProvider(api_key="")
    with pytest.raises(AIConfigurationError):
        await provider.generate_text("Prompt")


@pytest.mark.asyncio
async def test_gemini_provider_text_and_structured_generation():
    """Verify GeminiProvider generates text and structured output with mocked API."""
    provider = GeminiProvider(api_key="mock-gemini-key")

    mock_gemini_response = httpx.Response(
        status_code=200,
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": json.dumps({"message": "Hello from Gemini"})}
                        ]
                    }
                }
            ]
        },
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_gemini_response

        # Structured generation
        obj = await provider.generate_structured("Say hello", SimpleTestSchema)
        assert isinstance(obj, SimpleTestSchema)
        assert obj.message == "Hello from Gemini"

        # Verify key is in URL
        called_url = mock_post.call_args[0][0]
        assert "key=mock-gemini-key" in called_url


@pytest.mark.asyncio
async def test_openai_provider_unconfigured_raises_error():
    """Verify OpenAIProvider raises AIConfigurationError when no API key is provided."""
    provider = OpenAIProvider(api_key="")
    with pytest.raises(AIConfigurationError):
        await provider.generate_text("Prompt")


@pytest.mark.asyncio
async def test_openai_provider_text_and_structured_generation():
    """Verify OpenAIProvider generates text and structured output with mocked API."""
    provider = OpenAIProvider(api_key="mock-openai-key")

    mock_openai_response = httpx.Response(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"message": "Hello from OpenAI"}),
                    }
                }
            ]
        },
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_openai_response

        obj = await provider.generate_structured("Say hello", SimpleTestSchema)
        assert isinstance(obj, SimpleTestSchema)
        assert obj.message == "Hello from OpenAI"

        # Verify authorization header
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer mock-openai-key"
