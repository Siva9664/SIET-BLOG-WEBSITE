import pytest
import httpx

from app.modules.magazine import ai_service
from app.modules.magazine import llm_provider
from app.modules.magazine.llm_provider import (
    BaseLLMProvider,
    OllamaProvider,
    GeminiProvider,
    OpenAIProvider,
    get_provider,
    get_llm_config,
)


def _clear_llm_env(monkeypatch):
    for key in [
        "MAGAZINE_LLM_PROVIDER",
        "MAGAZINE_LLM_MODEL",
        "MAGAZINE_OLLAMA_MODEL",
        "OLLAMA_MODEL",
        "MAGAZINE_OLLAMA_BASE_URL",
        "OLLAMA_BASE_URL",
        "MAGAZINE_GEMINI_MODEL",
        "MAGAZINE_OPENAI_MODEL",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "MAGAZINE_LLM_TIMEOUT_SECONDS",
        "MAGAZINE_LLM_MAX_RETRIES",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_auto_provider_defaults_to_ollama_qwen_without_cloud_keys(monkeypatch):
    _clear_llm_env(monkeypatch)

    config = llm_provider.get_llm_config()

    assert config.provider == "ollama"
    assert "qwen" in config.model.lower()
    assert config.base_url == "http://localhost:11434"


def test_auto_provider_preserves_existing_gemini_preference(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    config = llm_provider.get_llm_config(model_name="gemini-1.5-pro")

    assert config.provider == "gemini"
    assert config.model == "gemini-1.5-pro"


def test_provider_factory_hierarchy(monkeypatch):
    _clear_llm_env(monkeypatch)
    
    ollama_p = get_provider(provider="ollama")
    assert isinstance(ollama_p, BaseLLMProvider)
    assert isinstance(ollama_p, OllamaProvider)

    gemini_p = get_provider(provider="gemini")
    assert isinstance(gemini_p, BaseLLMProvider)
    assert isinstance(gemini_p, GeminiProvider)

    openai_p = get_provider(provider="openai")
    assert isinstance(openai_p, BaseLLMProvider)
    assert isinstance(openai_p, OpenAIProvider)


@pytest.mark.asyncio
async def test_ollama_json_call_uses_qwen_model_and_json_format(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("MAGAZINE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("MAGAZINE_OLLAMA_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("MAGAZINE_OLLAMA_BASE_URL", "http://ollama.test")

    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "<think>private notes</think>{\"ok\": true}"}}

    class FakeAsyncClient:
        def __init__(self, timeout):
            calls["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, headers=None):
            calls["url"] = url
            calls["json"] = json
            calls["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", FakeAsyncClient)

    result = await llm_provider.call_llm_json("Return JSON")

    assert result == {"ok": True}
    assert calls["url"] == "http://ollama.test/api/chat"
    assert calls["json"]["model"] == "qwen2.5:7b"
    assert calls["json"]["format"] == "json"
    assert calls["json"]["stream"] is False
    assert calls["json"]["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_ollama_retry_on_connection_error_then_success(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("MAGAZINE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("MAGAZINE_LLM_MAX_RETRIES", "2")

    attempts = {"count": 0}

    class FlakyAsyncClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, headers=None):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise httpx.ConnectError("Connection refused by daemon")
            
            class SuccessResponse:
                def raise_for_status(self):
                    return None
                def json(self):
                    return {"message": {"content": "Retry succeeded!"}}
            return SuccessResponse()

    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", FlakyAsyncClient)

    provider = get_provider("ollama")
    result = await provider.generate("Test prompt")

    assert result == "Retry succeeded!"
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_ollama_404_model_not_found_handling(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("MAGAZINE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("MAGAZINE_OLLAMA_MODEL", "nonexistent-model:latest")

    class NotFoundClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, headers=None):
            req = httpx.Request("POST", url)
            resp = httpx.Response(status_code=404, request=req, text="model not found")
            raise httpx.HTTPStatusError("Model not found", request=req, response=resp)

    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", NotFoundClient)

    provider = get_provider("ollama")
    result = await provider.generate("Test prompt")

    assert result == ""


@pytest.mark.asyncio
async def test_ollama_is_available_check(monkeypatch):
    _clear_llm_env(monkeypatch)

    class HealthClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            req = httpx.Request("GET", url)
            return httpx.Response(status_code=200, request=req, json={"models": [{"name": "qwen2.5:7b"}]})

    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", HealthClient)

    provider = get_provider("ollama")
    is_live = await provider.is_available()
    assert is_live is True


@pytest.mark.asyncio
async def test_provider_failure_returns_empty_string(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("MAGAZINE_LLM_PROVIDER", "ollama")

    class FailingAsyncClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, headers=None):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", FailingAsyncClient)

    result = await llm_provider.call_llm("hello")

    assert result == ""


@pytest.mark.asyncio
async def test_legacy_call_llm_delegates_to_provider(monkeypatch):
    observed = {}

    async def fake_call_llm(prompt, *, model_name=None):
        observed["prompt"] = prompt
        observed["model_name"] = model_name
        return "ok"

    monkeypatch.setattr(ai_service, "call_llm", fake_call_llm)

    result = await ai_service._call_llm("hello", model_name="gemini-1.5-flash")

    assert result == "ok"
    assert observed == {
        "prompt": "hello",
        "model_name": "gemini-1.5-flash",
    }
