"""Environment-driven LLM provider abstraction for magazine generation.

Architecture:
Magazine Service (ai_service.py / orchestrator.py)
      ↓
AI Provider Interface (BaseLLMProvider)
      ↓
 ┌────┼──────────┐
 ↓    ↓          ↓
Ollama Gemini   OpenAI
 ↓
Qwen

The magazine pipeline asks language models to decide content and metadata. It
does not ask them to draw pages. Rendering stays deterministic elsewhere.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import os
import re
from typing import Any, Dict, List, Literal, Optional, Type

import httpx

from app.core.logging import logger

LLMResponseFormat = Literal["text", "json"]


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: str
    model: str
    base_url: str
    timeout_seconds: float
    temperature: float
    max_retries: int = 2


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _provider_from_env(explicit_provider: str | None = None) -> str:
    provider = (explicit_provider or _env("MAGAZINE_LLM_PROVIDER", "auto")).lower()
    if provider != "auto":
        return provider
    if _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY"):
        return "gemini"
    if _env("OPENAI_API_KEY"):
        return "openai"
    return "ollama"


def _configured_float(name: str, default: float) -> float:
    value = _env(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _configured_int(name: str, default: int) -> int:
    value = _env(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _is_gemini_model(model_name: str | None) -> bool:
    return bool(model_name and model_name.lower().startswith("gemini"))


def _is_openai_model(model_name: str | None) -> bool:
    if not model_name:
        return False
    name = model_name.lower()
    return name.startswith("gpt-") or name.startswith("o")


def get_llm_config(
    *,
    provider: str | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
) -> LLMProviderConfig:
    """Resolves provider/model settings from environment variables."""
    resolved_provider = _provider_from_env(provider)
    generic_model = _env("MAGAZINE_LLM_MODEL")

    if resolved_provider == "ollama":
        model = (
            _env("MAGAZINE_OLLAMA_MODEL")
            or _env("OLLAMA_MODEL")
            or (generic_model if generic_model and not _is_gemini_model(generic_model) else "")
            or (model_name if model_name and not _is_gemini_model(model_name) else "")
            or "qwen3:8b"
        )
        base_url = (
            _env("MAGAZINE_OLLAMA_BASE_URL")
            or _env("OLLAMA_BASE_URL")
            or "http://localhost:11434"
        )
    elif resolved_provider == "gemini":
        model = (
            _env("MAGAZINE_GEMINI_MODEL")
            or (generic_model if _is_gemini_model(generic_model) else "")
            or (model_name if _is_gemini_model(model_name) else "")
            or "gemini-1.5-flash"
        )
        base_url = "https://generativelanguage.googleapis.com/v1beta"
    elif resolved_provider == "openai":
        model = (
            _env("MAGAZINE_OPENAI_MODEL")
            or (generic_model if _is_openai_model(generic_model) else "")
            or (model_name if _is_openai_model(model_name) else "")
            or "gpt-3.5-turbo"
        )
        base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")
    else:
        model = model_name or generic_model or "qwen3:8b"
        base_url = ""

    return LLMProviderConfig(
        provider=resolved_provider,
        model=model,
        base_url=base_url.rstrip("/"),
        timeout_seconds=_configured_float("MAGAZINE_LLM_TIMEOUT_SECONDS", 45.0),
        temperature=temperature
        if temperature is not None
        else _configured_float("MAGAZINE_LLM_TEMPERATURE", 0.2),
        max_retries=_configured_int("MAGAZINE_LLM_MAX_RETRIES", 2),
    )


def _strip_response_wrappers(text: str) -> str:
    clean = re.sub(r"<think>.*?</think>", "", text.strip(), flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"^\s*```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*```\s*$", "", clean)
    return clean.strip()


def extract_json_payload(text: str) -> str:
    """Extracts the most likely JSON object/array from an LLM response."""
    clean = _strip_response_wrappers(text)
    if clean.startswith("{") or clean.startswith("["):
        return clean

    object_start = clean.find("{")
    array_start = clean.find("[")
    starts = [idx for idx in [object_start, array_start] if idx >= 0]
    if not starts:
        return clean

    start = min(starts)
    end_char = "}" if clean[start] == "{" else "]"
    end = clean.rfind(end_char)
    if end <= start:
        return clean
    return clean[start : end + 1].strip()


# ─── PROVIDER ABSTRACTION HIERARCHY ──────────────────────────────────────────


class BaseLLMProvider(ABC):
    """Abstract base provider interface for magazine language model services."""

    def __init__(self, config: LLMProviderConfig):
        self.config = config

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        response_format: LLMResponseFormat = "text",
        temperature: float | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        """Generates raw or structured content from the model."""
        pass

    async def is_available(self) -> bool:
        """Health check verifying whether the provider endpoint is reachable."""
        return True


class OllamaProvider(BaseLLMProvider):
    """
    Local LLM Provider for Ollama hosting Qwen and open-weight models.
    Supports structured JSON format, configurable models, timeouts, and exponential backoff retry.
    """

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.config.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        response_format: LLMResponseFormat = "text",
        temperature: float | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        temp = self.config.temperature if temperature is None else temperature
        payload: dict[str, Any] = {
            "model": self.config.model,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": temp},
        }

        if response_format == "json":
            payload["format"] = json_schema or "json"
            payload["messages"].insert(
                0,
                {
                    "role": "system",
                    "content": "Return only strict JSON. Do not include markdown blocks or commentary.",
                },
            )

        endpoint = f"{self.config.base_url}/api/chat"
        retries = self.config.max_retries
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                message = data.get("message", {})
                content = message.get("content") or data.get("response") or ""
                return _strip_response_wrappers(str(content))
            except httpx.ConnectError as e:
                last_error = e
                logger.warning(
                    f"[OllamaProvider] Connection failed at {self.config.base_url} (attempt {attempt + 1}/{retries + 1}). "
                    f"Ensure Ollama daemon is running (`ollama serve`)."
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 404:
                    logger.warning(
                        f"[OllamaProvider] Model '{self.config.model}' not found in Ollama (404). "
                        f"Pull it using `ollama pull {self.config.model}`."
                    )
                    break
                logger.warning(f"[OllamaProvider] HTTP status error {e.response.status_code}: {e}")
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"[OllamaProvider] Request timed out after {self.config.timeout_seconds}s (attempt {attempt + 1}/{retries + 1})."
                )
            except Exception as e:
                last_error = e
                logger.warning(f"[OllamaProvider] Error during call (attempt {attempt + 1}/{retries + 1}): {e}")

            if attempt < retries:
                backoff = 0.25 * (2 ** attempt)
                await asyncio.sleep(backoff)

        logger.error(f"[OllamaProvider] All attempts failed for model '{self.config.model}': {last_error}")
        return ""


class GeminiProvider(BaseLLMProvider):
    """Cloud LLM Provider for Google Gemini."""

    async def generate(
        self,
        prompt: str,
        response_format: LLMResponseFormat = "text",
        temperature: float | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        api_key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
        if not api_key:
            return ""

        temp = self.config.temperature if temperature is None else temperature
        generation_config: dict[str, Any] = {"temperature": temp}
        if response_format == "json":
            generation_config["responseMimeType"] = "application/json"

        url = f"{self.config.base_url}/models/{self.config.model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }

        retries = self.config.max_retries
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
                return _strip_response_wrappers(text)
            except Exception as e:
                logger.warning(f"[GeminiProvider] Attempt {attempt + 1}/{retries + 1} failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
        return ""


class OpenAIProvider(BaseLLMProvider):
    """Cloud LLM Provider for OpenAI."""

    async def generate(
        self,
        prompt: str,
        response_format: LLMResponseFormat = "text",
        temperature: float | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        api_key = _env("OPENAI_API_KEY")
        if not api_key:
            return ""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        temp = self.config.temperature if temperature is None else temperature
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temp,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        retries = self.config.max_retries
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.config.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                response.raise_for_status()
                data = response.json()
                return _strip_response_wrappers(data["choices"][0]["message"]["content"])
            except Exception as e:
                logger.warning(f"[OpenAIProvider] Attempt {attempt + 1}/{retries + 1} failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
        return ""


class FineTunedQwenProvider(BaseLLMProvider):
    """
    Optional LLM Provider using the fine-tuned SIET Qwen LoRA adapter.
    Preserves default production models and operates as an opt-in provider.
    """

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        adapter_path = _env("MAGAZINE_QWEN_ADAPTER_DIR", "models/siet-qwen-magazine-v1.0.0")
        self.adapter_path = adapter_path
        self._inference_engine = None

    def _get_engine(self):
        if self._inference_engine is None:
            try:
                from app.modules.datasets.qwen_inference import QwenMagazineInference
                self._inference_engine = QwenMagazineInference(self.adapter_path)
            except Exception as e:
                logger.warning(f"[FineTunedQwenProvider] Could not load inference engine: {e}")
        return self._inference_engine

    async def generate(
        self,
        prompt: str,
        response_format: LLMResponseFormat = "text",
        temperature: float | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        engine = self._get_engine()
        temp = temperature if temperature is not None else self.config.temperature
        if not engine:
            return ""

        instruction = (
            "You are the official editorial AI for the SIET Engineering Magazine. "
            "Generate concise, structured content following the house style guidelines."
        )
        return engine.generate(instruction=instruction, input_text=prompt, temperature=temp)

    async def is_available(self) -> bool:
        return os.path.exists(self.adapter_path)


PROVIDER_REGISTRY: dict[str, Type[BaseLLMProvider]] = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "fine_tuned_qwen": FineTunedQwenProvider,
    "qwen_lora": FineTunedQwenProvider,
}


def get_provider(
    provider: str | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
) -> BaseLLMProvider:
    """Factory creating the appropriate LLM provider instance based on config."""
    config = get_llm_config(
        provider=provider,
        model_name=model_name,
        temperature=temperature,
    )
    provider_cls = PROVIDER_REGISTRY.get(config.provider.lower())
    if not provider_cls:
        logger.warning(f"Unknown magazine LLM provider '{config.provider}'. Using Ollama provider.")
        return OllamaProvider(config)
    return provider_cls(config)


# ─── BACKWARD COMPATIBLE CONVENIENCE HELPERS ─────────────────────────────────


async def _call_ollama(
    prompt: str,
    config: LLMProviderConfig,
    response_format: LLMResponseFormat,
    json_schema: dict[str, Any] | None = None,
) -> str:
    provider = OllamaProvider(config)
    return await provider.generate(
        prompt=prompt,
        response_format=response_format,
        json_schema=json_schema,
    )


async def _call_gemini(
    prompt: str,
    config: LLMProviderConfig,
    response_format: LLMResponseFormat,
) -> str:
    provider = GeminiProvider(config)
    return await provider.generate(
        prompt=prompt,
        response_format=response_format,
    )


async def _call_openai(
    prompt: str,
    config: LLMProviderConfig,
    response_format: LLMResponseFormat,
) -> str:
    provider = OpenAIProvider(config)
    return await provider.generate(
        prompt=prompt,
        response_format=response_format,
    )


async def call_llm(
    prompt: str,
    *,
    model_name: str | None = None,
    provider: str | None = None,
    response_format: LLMResponseFormat = "text",
    temperature: float | None = None,
    json_schema: dict[str, Any] | None = None,
) -> str:
    """
    Calls the configured magazine LLM provider via the provider abstraction.
    Returns an empty string on failure so existing deterministic fallbacks continue to work.
    """
    config = get_llm_config(
        provider=provider,
        model_name=model_name,
        temperature=temperature,
    )
    if config.provider in {"none", "disabled", "off"}:
        return ""

    try:
        p = get_provider(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
        )
        return await p.generate(
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
            json_schema=json_schema,
        )
    except Exception as error:
        logger.warning(
            "Magazine LLM provider '%s' failed: %s. Using fallback.",
            config.provider,
            error,
        )
        return ""


async def call_llm_json(
    prompt: str,
    *,
    model_name: str | None = None,
    provider: str | None = None,
    temperature: float | None = 0.0,
    json_schema: dict[str, Any] | None = None,
) -> Any:
    """Calls the configured provider and parses a strict JSON response."""
    response_text = await call_llm(
        prompt,
        model_name=model_name,
        provider=provider,
        response_format="json",
        temperature=temperature,
        json_schema=json_schema,
    )
    if not response_text:
        return None
    try:
        return json.loads(extract_json_payload(response_text))
    except json.JSONDecodeError as error:
        logger.warning("Magazine LLM JSON parse failed: %s", error)
        return None
