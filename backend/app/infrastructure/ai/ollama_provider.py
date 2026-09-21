"""Ollama local AI provider implementation for Qwen3 14B."""

import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.ai.base import BaseAIProvider, T
from app.infrastructure.ai.constants import DEFAULT_STRICT_GROUNDING_INSTRUCTION
from app.infrastructure.ai.exceptions import (
    AIProviderError,
    AIProviderUnavailableError,
    AISchemaValidationError,
    AITimeoutError,
)


class OllamaProvider(BaseAIProvider):
    """
    Local Ollama provider targeting qwen3:14b (or configured local model).
    Uses Ollama HTTP API (/api/chat) with support for system instructions,
    strict grounding, thinking token isolation, and native JSON Schema constrained decoding.
    """

    provider_name: str = "qwen"

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT

    def _build_messages(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        sys_prompt = system_instruction or DEFAULT_STRICT_GROUNDING_INSTRUCTION
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt.strip()})
        messages.append({"role": "user", "content": prompt.strip()})
        return messages

    def _clean_content(self, text: str) -> str:
        """Strips residual thinking blocks or markdown fences if present in content."""
        if not text:
            return ""
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```"):].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
        return cleaned.strip()

    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        target_model = model or self.model
        messages = self._build_messages(prompt, system_instruction)
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
            },
        }

        url = f"{self.base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload)
        except (httpx.ConnectError, httpx.NetworkError) as e:
            logger.error(f"[Ollama] Connection error to {url}: {e}")
            raise AIProviderUnavailableError(
                provider=self.provider_name,
                endpoint=self.base_url,
                message=f"Could not connect to Ollama at {self.base_url}: {e}",
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"[Ollama] Timeout after {self.timeout}s calling {url}")
            raise AITimeoutError(
                provider=self.provider_name,
                timeout_seconds=self.timeout,
            ) from e
        except Exception as e:
            logger.error(f"[Ollama] Unexpected error during request: {e}")
            raise AIProviderError(
                provider=self.provider_name,
                message=f"Ollama request failed: {e}",
            ) from e

        if res.status_code != 200:
            if res.status_code in (502, 503, 504):
                raise AIProviderUnavailableError(
                    provider=self.provider_name,
                    endpoint=self.base_url,
                    message=f"Ollama returned {res.status_code}: {res.text}",
                )
            raise AIProviderError(
                provider=self.provider_name,
                message=f"Ollama request failed with HTTP {res.status_code}: {res.text}",
            )

        data = res.json()
        raw_content = data.get("message", {}).get("content", "")
        return self._clean_content(raw_content)

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 1,
        **kwargs: Any,
    ) -> T:
        target_model = model or self.model
        schema_json = schema.model_json_schema()
        messages = self._build_messages(prompt, system_instruction)

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "format": schema_json,
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
            },
        }

        url = f"{self.base_url}/api/chat"
        attempt = 0
        last_raw_response = ""

        while attempt <= max_retries:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.post(url, json=payload)
            except (httpx.ConnectError, httpx.NetworkError) as e:
                logger.error(f"[Ollama] Connection error on structured generation: {e}")
                raise AIProviderUnavailableError(
                    provider=self.provider_name,
                    endpoint=self.base_url,
                    message=f"Could not connect to Ollama at {self.base_url}: {e}",
                ) from e
            except httpx.TimeoutException as e:
                logger.error(f"[Ollama] Timeout on structured generation after {self.timeout}s")
                raise AITimeoutError(
                    provider=self.provider_name,
                    timeout_seconds=self.timeout,
                ) from e
            except Exception as e:
                logger.error(f"[Ollama] Request error on structured generation: {e}")
                raise AIProviderError(
                    provider=self.provider_name,
                    message=f"Ollama structured request error: {e}",
                ) from e

            if res.status_code != 200:
                if res.status_code in (502, 503, 504):
                    raise AIProviderUnavailableError(
                        provider=self.provider_name,
                        endpoint=self.base_url,
                        message=f"Ollama returned {res.status_code}: {res.text}",
                    )
                raise AIProviderError(
                    provider=self.provider_name,
                    message=f"Ollama HTTP {res.status_code}: {res.text}",
                )

            data = res.json()
            raw_content = data.get("message", {}).get("content", "")
            last_raw_response = raw_content
            clean_text = self._clean_content(raw_content)

            try:
                parsed_json = json.loads(clean_text)
                return schema.model_validate(parsed_json)
            except (json.JSONDecodeError, ValidationError) as err:
                logger.warning(
                    f"[Ollama] Structured output validation failed (attempt {attempt}/{max_retries + 1}): {err}"
                )
                if attempt <= max_retries:
                    # Bounded explicit retry
                    retry_instruction = (
                        f"Previous output did not match the required schema. Validation error: {err}. "
                        f"Output ONLY valid JSON matching this schema: {json.dumps(schema_json)}"
                    )
                    payload["messages"].append({"role": "assistant", "content": clean_text})
                    payload["messages"].append({"role": "user", "content": retry_instruction})
                    continue

        raise AISchemaValidationError(
            provider=self.provider_name,
            schema_name=schema.__name__,
            raw_response=last_raw_response,
            message=f"Ollama failed to generate valid {schema.__name__} after {max_retries + 1} attempts.",
        )

    async def health(self) -> Dict[str, Any]:
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    model_names = [m.get("name") for m in data.get("models", [])]
                    is_model_present = any(
                        self.model in m or m in self.model for m in model_names
                    )
                    return {
                        "status": "healthy" if is_model_present else "degraded",
                        "provider": self.provider_name,
                        "endpoint": self.base_url,
                        "target_model": self.model,
                        "model_available": is_model_present,
                        "available_models": model_names,
                    }
                return {
                    "status": "unhealthy",
                    "provider": self.provider_name,
                    "endpoint": self.base_url,
                    "http_status": res.status_code,
                }
        except Exception as e:
            return {
                "status": "offline",
                "provider": self.provider_name,
                "endpoint": self.base_url,
                "error": str(e),
            }
