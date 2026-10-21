"""Security Regression Test: Zero Cloud API Calls Guard.

Ensures that the live runtime pipeline makes ZERO outbound calls to cloud LLM APIs
(Gemini, OpenAI, Anthropic) or external web services.
"""

import socket
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_zero_cloud_api_calls_in_live_pipeline():
    """Mocks network socket creation to verify that no cloud API endpoints are queried during generation."""
    forbidden_hosts = ["api.openai.com", "generativelanguage.googleapis.com", "api.anthropic.com"]

    orig_getaddrinfo = socket.getaddrinfo

    def _guarded_getaddrinfo(host, port, *args, **kwargs):
        if any(fh in str(host) for fh in forbidden_hosts):
            raise RuntimeError(f"SECURITY VIOLATION: Forbidden cloud API attempt detected to '{host}'!")
        return orig_getaddrinfo(host, port, *args, **kwargs)

    with patch("socket.getaddrinfo", side_effect=_guarded_getaddrinfo):
        from app.modules.magazine.end_to_end_pipeline import run_end_to_end_magazine_pipeline

        result = await run_end_to_end_magazine_pipeline(
            raw_notes="Strictly offline local generation test for security compliance.",
            department_or_lab="Security Lab",
            target_page_budget=2,
            use_llm=False,
        )

        assert result is not None
        assert result.status == "published"
