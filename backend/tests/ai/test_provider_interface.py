"""Tests verifying BaseAIProvider interface compliance across all providers."""

import pytest
from pydantic import BaseModel

from app.infrastructure.ai.base import BaseAIProvider
from app.infrastructure.ai.gemini_provider import GeminiProvider
from app.infrastructure.ai.ollama_provider import OllamaProvider
from app.infrastructure.ai.openai_provider import OpenAIProvider


class DummySchema(BaseModel):
    title: str


def test_base_provider_cannot_be_instantiated_directly():
    """Verify that BaseAIProvider cannot be instantiated without implementing abstract methods."""
    with pytest.raises(TypeError):
        BaseAIProvider()  # type: ignore


@pytest.mark.parametrize("provider_cls,name", [
    (OllamaProvider, "qwen"),
    (GeminiProvider, "gemini"),
    (OpenAIProvider, "openai"),
])
def test_all_providers_implement_base_contract(provider_cls, name):
    """Verify each concrete provider implements provider_name, generate_text, generate_structured, and health."""
    provider = provider_cls()
    assert issubclass(provider_cls, BaseAIProvider)
    assert provider.provider_name == name
    assert hasattr(provider, "generate_text")
    assert callable(provider.generate_text)
    assert hasattr(provider, "generate_structured")
    assert callable(provider.generate_structured)
    assert hasattr(provider, "health")
    assert callable(provider.health)
