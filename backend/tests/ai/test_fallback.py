"""Tests for AIServiceManager routing, observable fallback, and resilience."""

from unittest.mock import AsyncMock
import pytest
from pydantic import BaseModel

from app.infrastructure.ai.base import BaseAIProvider
from app.infrastructure.ai.exceptions import (
    AIProviderError,
    AIProviderUnavailableError,
    AISchemaValidationError,
    AITimeoutError,
)
from app.infrastructure.ai.manager import AIServiceManager


class MockSchema(BaseModel):
    title: str


class MockSuccessProvider(BaseAIProvider):
    provider_name = "mock_success"

    def __init__(self, return_text="Mock success text"):
        self.return_text = return_text

    async def generate_text(self, prompt, **kwargs):
        return self.return_text

    async def generate_structured(self, prompt, schema, **kwargs):
        return schema(title="Mock structured success")

    async def health(self):
        return {"status": "ok"}


class MockFailingProvider(BaseAIProvider):
    provider_name = "mock_failing"

    def __init__(self, exc_to_raise=None):
        self.exc_to_raise = exc_to_raise or AIProviderUnavailableError("mock_failing", "http://localhost:11434")

    async def generate_text(self, prompt, **kwargs):
        raise self.exc_to_raise

    async def generate_structured(self, prompt, schema, **kwargs):
        raise self.exc_to_raise

    async def health(self):
        return {"status": "error"}


@pytest.mark.asyncio
async def test_manager_primary_success_no_fallback_needed():
    """Verify primary provider is used when healthy without fallback."""
    manager = AIServiceManager(primary_provider="qwen", fallback_provider="gemini")
    mock_qwen = MockSuccessProvider("Qwen generated text")
    manager.register_provider("qwen", mock_qwen)

    res = await manager.generate_text("Generate writeup")
    assert res == "Qwen generated text"
    assert manager.last_provider_used == "qwen"


@pytest.mark.asyncio
async def test_manager_observable_fallback_when_primary_unavailable():
    """Verify primary failure triggers observable fallback with clear metadata."""
    manager = AIServiceManager(primary_provider="qwen", fallback_provider="gemini")
    mock_qwen = MockFailingProvider(AIProviderUnavailableError("qwen", "http://localhost:11434"))
    mock_gemini = MockSuccessProvider("Gemini fallback text")

    manager.register_provider("qwen", mock_qwen)
    manager.register_provider("gemini", mock_gemini)

    res = await manager.generate_text("Generate writeup")
    assert res == "Gemini fallback text"
    assert "fallback from qwen" in manager.last_provider_used
    assert "gemini" in manager.last_provider_used


@pytest.mark.asyncio
async def test_manager_fallback_on_timeout():
    """Verify primary timeout triggers fallback."""
    manager = AIServiceManager(primary_provider="qwen", fallback_provider="gemini")
    mock_qwen = MockFailingProvider(AITimeoutError("qwen", 60.0))
    mock_gemini = MockSuccessProvider("Gemini text after timeout")

    manager.register_provider("qwen", mock_qwen)
    manager.register_provider("gemini", mock_gemini)

    res = await manager.generate_text("Prompt")
    assert res == "Gemini text after timeout"


@pytest.mark.asyncio
async def test_manager_structured_fallback():
    """Verify structured generation fails over cleanly to fallback."""
    manager = AIServiceManager(primary_provider="qwen", fallback_provider="gemini")
    mock_qwen = MockFailingProvider(AISchemaValidationError("qwen", "MockSchema"))
    mock_gemini = MockSuccessProvider()

    manager.register_provider("qwen", mock_qwen)
    manager.register_provider("gemini", mock_gemini)

    res = await manager.generate_structured("Extract", MockSchema)
    assert isinstance(res, MockSchema)
    assert res.title == "Mock structured success"


@pytest.mark.asyncio
async def test_manager_no_fallback_configured_raises_immediately():
    """Verify when fallback is disabled or 'none', error is raised without silent switch."""
    manager = AIServiceManager(primary_provider="qwen", fallback_provider="none")
    mock_qwen = MockFailingProvider(AIProviderUnavailableError("qwen", "http://localhost:11434"))
    manager.register_provider("qwen", mock_qwen)

    with pytest.raises(AIProviderUnavailableError):
        await manager.generate_text("Prompt")


@pytest.mark.asyncio
async def test_manager_both_primary_and_fallback_fail_raises_composite_error():
    """Verify when both primary and fallback fail, an explicit error detailing both is raised."""
    manager = AIServiceManager(primary_provider="qwen", fallback_provider="gemini")
    mock_qwen = MockFailingProvider(AIProviderUnavailableError("qwen", "http://localhost:11434"))
    mock_gemini = MockFailingProvider(AIProviderError("gemini", "Gemini API quota exceeded"))

    manager.register_provider("qwen", mock_qwen)
    manager.register_provider("gemini", mock_gemini)

    with pytest.raises(AIProviderError) as exc_info:
        await manager.generate_text("Prompt")

    assert "Both primary provider 'qwen'" in str(exc_info.value)
    assert "fallback provider 'gemini'" in str(exc_info.value)
