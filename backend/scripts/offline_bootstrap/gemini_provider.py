"""Google Gemini AI provider implementation."""

import json
import os
import re
from typing import Any, Dict, List, Optional, Type
import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.ai.base import BaseAIProvider, T
from app.infrastructure.ai.constants import DEFAULT_STRICT_GROUNDING_INSTRUCTION
from app.infrastructure.ai.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIProviderUnavailableError,
    AISchemaValidationError,
    AITimeoutError,
)


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini provider using Google Generative Language REST API.
    Acts as primary or fallback editorial provider.
    """

    provider_name: str = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        configured_key = (
            api_key
            or (settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else "")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        )
        self.api_key = configured_key
        self.model = model or settings.GEMINI_MODEL
        self.timeout = timeout

    def _clean_content(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"```$", "", cleaned.strip()).strip()
        return cleaned

    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        if not self.api_key:
            raise AIConfigurationError(
                provider=self.provider_name,
                message="Gemini API key is not configured.",
            )

        target_model = model or self.model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={self.api_key}"

        sys_prompt = system_instruction or DEFAULT_STRICT_GROUNDING_INSTRUCTION
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt.strip()}]}],
        }
        if sys_prompt:
            payload["systemInstruction"] = {"parts": [{"text": sys_prompt.strip()}]}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload)
        except (httpx.ConnectError, httpx.NetworkError) as e:
            logger.error(f"[Gemini] Connection error: {e}")
            raise AIProviderUnavailableError(
                provider=self.provider_name,
                endpoint="generativelanguage.googleapis.com",
                message=f"Could not connect to Gemini API: {e}",
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"[Gemini] Timeout after {self.timeout}s")
            raise AITimeoutError(
                provider=self.provider_name,
                timeout_seconds=self.timeout,
            ) from e
        except Exception as e:
            logger.error(f"[Gemini] Unexpected request error: {e}")
            raise AIProviderError(
                provider=self.provider_name,
                message=f"Gemini API request error: {e}",
            ) from e

        if res.status_code != 200:
            if res.status_code in (502, 503, 504):
                raise AIProviderUnavailableError(
                    provider=self.provider_name,
                    endpoint="generativelanguage.googleapis.com",
                    message=f"Gemini API unavailable with HTTP {res.status_code}",
                )
            raise AIProviderError(
                provider=self.provider_name,
                message=f"Gemini API returned HTTP {res.status_code}: {res.text}",
            )

        data = res.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])
        if parts and "text" in parts[0]:
            return self._clean_content(parts[0]["text"])
        return ""

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
        schema_json = schema.model_json_schema()
        structured_prompt = (
            f"{prompt}\n\n"
            f"IMPORTANT: Respond ONLY with valid JSON matching this exact JSON schema:\n"
            f"{json.dumps(schema_json, indent=2)}\n"
            f"Do NOT include explanations or markdown fences. Output raw valid JSON only."
        )

        attempt = 0
        last_raw = ""
        while attempt <= max_retries:
            attempt += 1
            raw_text = await self.generate_text(
                structured_prompt,
                system_instruction=system_instruction,
                model=model,
                **kwargs,
            )
            last_raw = raw_text
            clean_text = self._clean_content(raw_text)

            try:
                parsed_json = json.loads(clean_text)
                return schema.model_validate(parsed_json)
            except (json.JSONDecodeError, ValidationError) as err:
                logger.warning(
                    f"[Gemini] Structured output validation failed (attempt {attempt}/{max_retries + 1}): {err}"
                )
                if attempt <= max_retries:
                    structured_prompt += f"\nValidation failed: {err}. Please fix the JSON and adhere strictly to the schema."
                    continue

        raise AISchemaValidationError(
            provider=self.provider_name,
            schema_name=schema.__name__,
            raw_response=last_raw,
            message=f"Gemini failed to generate valid {schema.__name__} after {max_retries + 1} attempts.",
        )

    async def health(self) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "status": "unconfigured",
                "provider": self.provider_name,
                "message": "Gemini API key is not set.",
            }
        return {
            "status": "configured",
            "provider": self.provider_name,
            "target_model": self.model,
        }
