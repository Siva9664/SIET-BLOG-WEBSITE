import json
import os
import pytest
import httpx

from app.modules.magazine.llm_provider import (
    OllamaProvider,
    get_provider,
    call_llm_json,
)
from app.modules.magazine.ai_service import generate_full_magazine_content


SAMPLE_EVENT_NOTES = """
SIET Annual Robotics & IoT Exhibition 2026
Held on September 12, 2026 at Sri Shakthi Institute of Engineering & Technology.
Organized by Department of Mechatronics and AI Research Labs.
Over 25 student teams demonstrated functional robotic systems.
Key highlight was Team QuadRobo winning the top prize for their quadruped autonomous terrain robot.
Industry mentors from Titan Robotics commended the real-time sensor fusion architecture.
"""


@pytest.mark.asyncio
async def test_ollama_qwen_magazine_content_extraction_integration(monkeypatch):
    """
    Integration test: sends a realistic magazine content extraction request
    to the Ollama local Qwen model provider and validates structured output.
    """
    monkeypatch.setenv("MAGAZINE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("MAGAZINE_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("MAGAZINE_OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("MAGAZINE_LLM_TIMEOUT_SECONDS", "120.0")

    # Mock the wire to guarantee fast, deterministic integration test execution
    # simulating exact Qwen format response from Ollama API
    qwen_sample_output = {
        "message": {
            "content": json.dumps({
                "magazine_issue_title": "SIET Robotics & IoT Expo 2026",
                "description": "Sri Shakthi Institute of Engineering & Technology hosted the 2026 Robotics & IoT Exhibition featuring 25 innovative student engineering teams.",
                "writeup": (
                    "# Breakthrough Autonomous Systems at SIET Expo 2026\n\n"
                    "The Mechatronics Department and AI Research Labs at SIET hosted the Annual Robotics & IoT Exhibition 2026. "
                    "Over twenty-five student teams demonstrated field-ready prototypes ranging from precision agricultural drones "
                    "to autonomous terrain navigation platforms.\n\n"
                    "Team QuadRobo earned the championship trophy for their four-legged autonomous robot utilizing real-time sensor fusion."
                ),
                "captions": [
                    "Team QuadRobo demonstrating quadruped terrain robot.",
                    "Industry mentors inspecting telemetry and sensor arrays."
                ],
                "toc_summary": "Coverage of 25 student robotics prototypes and top awards."
            })
        }
    }

    class MockOllamaClient:
        def __init__(self, timeout):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, url, json=None, headers=None):
            req = httpx.Request("POST", url)
            return httpx.Response(status_code=200, request=req, json=qwen_sample_output)

    monkeypatch.setattr("app.modules.magazine.llm_provider.httpx.AsyncClient", MockOllamaClient)

    provider = get_provider("ollama")
    assert isinstance(provider, OllamaProvider)
    assert "qwen" in provider.config.model.lower()

    extraction_prompt = f"""You are the official editor for SIET Engineering Magazine.
Extract and structure content for this event:
{SAMPLE_EVENT_NOTES}

Return ONLY valid JSON matching this schema:
{{
  "magazine_issue_title": "Title",
  "description": "Overview",
  "writeup": "Full article",
  "captions": ["caption 1"],
  "toc_summary": "TOC summary"
}}
"""

    result = await call_llm_json(
        extraction_prompt,
        provider="ollama",
        model_name="qwen3:4b",
    )

    assert result is not None
    assert isinstance(result, dict)
    assert "magazine_issue_title" in result
    assert "description" in result
    assert "writeup" in result
    assert len(result["writeup"]) > 50
    assert "SIET" in result["magazine_issue_title"] or "Robotics" in result["magazine_issue_title"]


@pytest.mark.asyncio
async def test_ollama_full_magazine_service_flow(monkeypatch):
    """
    Verifies that ai_service.generate_full_magazine_content works cleanly with Ollama/Qwen.
    """
    monkeypatch.setenv("MAGAZINE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("MAGAZINE_OLLAMA_MODEL", "qwen3:4b")

    qwen_response = {
        "message": {
            "content": json.dumps({
                "magazine_issue_title": "SIET AI Robotics Digest",
                "description": "Proceedings from the annual robotics symposium at SIET.",
                "writeup": "Students demonstrated autonomous navigation and sensor algorithms across 25 prototypes.",
                "captions": ["Live robotics demonstration."],
                "toc_summary": "Robotics symposium proceedings."
            })
        }
    }

    class MockClient:
        def __init__(self, timeout):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, url, json=None, headers=None):
            req = httpx.Request("POST", url)
            return httpx.Response(status_code=200, request=req, json=qwen_response)

    monkeypatch.setattr("app.modules.magazine.llm_provider.httpx.AsyncClient", MockClient)

    content = await generate_full_magazine_content(
        event_name="Robotics Exhibition",
        event_date="2026-09-12",
        raw_notes=SAMPLE_EVENT_NOTES,
        photo_count=1,
    )

    assert content["magazine_issue_title"] == "SIET AI Robotics Digest"
    assert "description" in content
    assert "writeup_headline" in content
    assert "writeup_html" in content
    assert "sections" in content


@pytest.mark.skipif(os.getenv("RUN_LIVE_OLLAMA") != "1", reason="Set RUN_LIVE_OLLAMA=1 to test live inference against running daemon")
@pytest.mark.asyncio
async def test_live_ollama_qwen_inference():
    """
    Live test against running Ollama daemon if explicitly enabled via RUN_LIVE_OLLAMA=1.
    """
    provider = get_provider("ollama", model_name="qwen3:4b")
    assert await provider.is_available() is True
    res = await call_llm_json(
        "Return json with key 'status' and value 'ready'",
        provider="ollama",
        model_name="qwen3:4b",
    )
    assert res is not None
    assert res.get("status") == "ready"
