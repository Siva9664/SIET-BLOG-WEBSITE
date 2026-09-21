"""Unit tests for OllamaProvider with mocked HTTP API."""

import json
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from pydantic import BaseModel

from app.core.config import settings
from app.infrastructure.ai.constants import DEFAULT_STRICT_GROUNDING_INSTRUCTION
from app.infrastructure.ai.exceptions import (
    AIProviderError,
    AIProviderUnavailableError,
    AISchemaValidationError,
    AITimeoutError,
)
from app.infrastructure.ai.ollama_provider import OllamaProvider
from app.infrastructure.ai.schemas import MagazineEditorialContent


class SampleEventSchema(BaseModel):
    event_title: str
    summary: str
    participant_count: int


@pytest.mark.asyncio
async def test_ollama_request_construction():
    """Verify OllamaProvider constructs correct HTTP URL, payload, and headers."""
    provider = OllamaProvider(
        base_url="http://mock-ollama:11434",
        model="qwen3:14b",
        timeout=15.0,
    )

    mock_response = httpx.Response(
        status_code=200,
        json={
            "message": {
                "role": "assistant",
                "content": "Innovations in Robotics at SIET",
            }
        },
        request=httpx.Request("POST", "http://mock-ollama:11434/api/chat"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        res = await provider.generate_text("Describe the event.")
        assert res == "Innovations in Robotics at SIET"

        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        call_json = mock_post.call_args[1]["json"]

        assert call_url == "http://mock-ollama:11434/api/chat"
        assert call_json["model"] == "qwen3:14b"
        assert call_json["stream"] is False
        assert len(call_json["messages"]) == 2
        assert call_json["messages"][0]["role"] == "system"
        assert DEFAULT_STRICT_GROUNDING_INSTRUCTION in call_json["messages"][0]["content"]
        assert call_json["messages"][1]["role"] == "user"
        assert call_json["messages"][1]["content"] == "Describe the event."


@pytest.mark.asyncio
async def test_ollama_configured_model_name():
    """Verify configured model name from settings is respected."""
    provider = OllamaProvider()
    assert provider.model == settings.OLLAMA_MODEL


@pytest.mark.asyncio
async def test_ollama_thinking_token_stripping():
    """Verify any residual <think> tags are cleanly stripped from content."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434")

    mock_response = httpx.Response(
        status_code=200,
        json={
            "message": {
                "role": "assistant",
                "content": "<think>Deliberating internal reasoning steps...</think>Clean Final Editorial Content",
            }
        },
        request=httpx.Request("POST", "http://mock-ollama:11434/api/chat"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        res = await provider.generate_text("Generate headline")
        assert res == "Clean Final Editorial Content"


@pytest.mark.asyncio
async def test_ollama_generate_structured_success():
    """Verify structured response is parsed and validated against Pydantic schema."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434")

    valid_json = {
        "event_title": "SIET Hackathon 2026",
        "summary": "Annual campus hackathon featuring 250 students.",
        "participant_count": 250,
    }

    mock_response = httpx.Response(
        status_code=200,
        json={
            "message": {
                "role": "assistant",
                "content": json.dumps(valid_json),
            }
        },
        request=httpx.Request("POST", "http://mock-ollama:11434/api/chat"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        obj = await provider.generate_structured(
            prompt="Extract event details",
            schema=SampleEventSchema,
        )

        assert isinstance(obj, SampleEventSchema)
        assert obj.event_title == "SIET Hackathon 2026"
        assert obj.participant_count == 250

        # Verify format parameter includes JSON schema
        call_json = mock_post.call_args[1]["json"]
        assert "format" in call_json
        assert call_json["format"]["type"] == "object"
        assert "event_title" in call_json["format"]["properties"]


@pytest.mark.asyncio
async def test_ollama_generate_structured_magazine_editorial_schema():
    """Verify MagazineEditorialContent schema generation."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434")

    valid_content = {
        "magazine_issue_title": "SIET Innovation Digest 2026",
        "description": "Sri Shakthi Institute hosted student researchers in robotics and clean tech.",
        "writeup": "Key highlights from the symposium with faculty and industry mentors.",
        "captions": ["Team QuadRobo showcasing prototype", "Keynote address"],
        "toc_summary": "Coverage of SIET Innovation Symposium.",
    }

    mock_response = httpx.Response(
        status_code=200,
        json={"message": {"role": "assistant", "content": json.dumps(valid_content)}},
        request=httpx.Request("POST", "http://mock-ollama:11434/api/chat"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        res = await provider.generate_structured(
            prompt="Generate magazine issue",
            schema=MagazineEditorialContent,
        )

        assert isinstance(res, MagazineEditorialContent)
        assert res.magazine_issue_title == "SIET Innovation Digest 2026"
        assert len(res.captions) == 2


@pytest.mark.asyncio
async def test_ollama_malformed_json_bounded_retry_recovery():
    """Verify malformed JSON triggers an explicit bounded retry pass which succeeds on attempt 2."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434")

    # Attempt 1 returns broken JSON, Attempt 2 returns valid JSON
    bad_response = httpx.Response(
        status_code=200,
        json={"message": {"role": "assistant", "content": "Not valid json {title: missing"}},
        request=httpx.Request("POST", "http://mock-ollama:11434/api/chat"),
    )
    good_response = httpx.Response(
        status_code=200,
        json={
            "message": {
                "role": "assistant",
                "content": json.dumps({
                    "event_title": "Recovered Title",
                    "summary": "Recovered summary",
                    "participant_count": 100,
                }),
            }
        },
        request=httpx.Request("POST", "http://mock-ollama:11434/api/chat"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [bad_response, good_response]

        res = await provider.generate_structured(
            prompt="Generate event",
            schema=SampleEventSchema,
            max_retries=1,
        )

        assert mock_post.call_count == 2
        assert res.event_title == "Recovered Title"


@pytest.mark.asyncio
async def test_ollama_malformed_json_exhausted_retries_raises_validation_error():
    """Verify exhausted retries on invalid schema raises AISchemaValidationError."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434")

    bad_response = httpx.Response(
        status_code=200,
        json={"message": {"role": "assistant", "content": "{'invalid': 'json'}"}},
        request=httpx.Request("POST", "http://mock-ollama:11434/api/chat"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = bad_response

        with pytest.raises(AISchemaValidationError) as exc_info:
            await provider.generate_structured(
                prompt="Generate event",
                schema=SampleEventSchema,
                max_retries=1,
            )

        assert exc_info.value.provider == "qwen"
        assert exc_info.value.schema_name == "SampleEventSchema"


@pytest.mark.asyncio
async def test_ollama_unavailable_raises_provider_unavailable():
    """Verify connection failure raises AIProviderUnavailableError."""
    provider = OllamaProvider(base_url="http://offline-ollama:11434")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(AIProviderUnavailableError) as exc_info:
            await provider.generate_text("Prompt")

        assert exc_info.value.provider == "qwen"
        assert "Could not connect to Ollama" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ollama_timeout_raises_timeout_error():
    """Verify timeout raises AITimeoutError."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434", timeout=5.0)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ReadTimeout("Read timed out")

        with pytest.raises(AITimeoutError) as exc_info:
            await provider.generate_text("Prompt")

        assert exc_info.value.provider == "qwen"
        assert exc_info.value.timeout_seconds == 5.0


@pytest.mark.asyncio
async def test_ollama_health_reporting():
    """Verify operational health check reports availability accurately."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434", model="qwen3:14b")

    mock_tags = httpx.Response(
        status_code=200,
        json={"models": [{"name": "qwen3:14b"}, {"name": "mistral:latest"}]},
        request=httpx.Request("GET", "http://mock-ollama:11434/api/tags"),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_tags

        health = await provider.health()
        assert health["status"] == "healthy"
        assert health["model_available"] is True
        assert "qwen3:14b" in health["available_models"]
