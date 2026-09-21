"""Live integration tests for local Qwen3 14B on Ollama.
Skipped automatically if Ollama or qwen3:14b is not available locally.
"""

import httpx
import pytest
from pydantic import BaseModel

from app.infrastructure.ai.ollama_provider import OllamaProvider
from app.infrastructure.ai.schemas import MagazineEditorialContent


def is_ollama_qwen_available() -> bool:
    try:
        res = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if res.status_code == 200:
            models = [m.get("name", "") for m in res.json().get("models", [])]
            return any("qwen3:14b" in m for m in models)
    except Exception:
        return False
    return False


@pytest.mark.skipif(
    not is_ollama_qwen_available(),
    reason="Local Ollama server or qwen3:14b model is not available",
)
@pytest.mark.asyncio
async def test_live_qwen_health():
    """Verify live Ollama reports healthy for qwen3:14b."""
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3:14b")
    health = await provider.health()
    assert health["status"] == "healthy"
    assert health["model_available"] is True


@pytest.mark.skipif(
    not is_ollama_qwen_available(),
    reason="Local Ollama server or qwen3:14b model is not available",
)
@pytest.mark.asyncio
async def test_live_qwen_generate_text():
    """Verify live text generation from Qwen3 14B."""
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3:14b")
    out = await provider.generate_text("Reply with exactly: SIET Innovates")
    assert "SIET" in out


@pytest.mark.skipif(
    not is_ollama_qwen_available(),
    reason="Local Ollama server or qwen3:14b model is not available",
)
@pytest.mark.asyncio
async def test_live_qwen_structured_generation():
    """Verify live structured generation adheres to Pydantic schema."""
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3:14b")
    prompt = """Generate a magazine issue summary for the following campus event:
Event: SIET RoboWars 2026
Date: March 12, 2026
Notes: Over 20 student teams competed in autonomous robot combat. Team Titan took first prize."""

    result = await provider.generate_structured(prompt, MagazineEditorialContent)
    assert isinstance(result, MagazineEditorialContent)
    assert len(result.magazine_issue_title) > 0
    assert len(result.description) > 0
    assert len(result.writeup) > 0
    assert len(result.toc_summary) > 0
