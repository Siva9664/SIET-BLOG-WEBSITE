"""AI Service Manager providing primary routing, observable fallback, and health monitoring."""

from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.ai.base import BaseAIProvider, T
from app.infrastructure.ai.exceptions import (
    AIConfigurationError,
    AIError,
    AIProviderError,
    AIProviderUnavailableError,
    AISchemaValidationError,
    AITimeoutError,
)
from app.infrastructure.ai.gemini_provider import GeminiProvider
from app.infrastructure.ai.ollama_provider import OllamaProvider
from app.infrastructure.ai.openai_provider import OpenAIProvider


class AIServiceManager:
    """
    Central orchestration manager for AI providers.
    Directs requests to primary provider (default: local Qwen3 14B via Ollama)
    and observably falls back to configured fallback provider (e.g. Gemini/OpenAI) upon failure.
    """

    def __init__(
        self,
        primary_provider: Optional[str] = None,
        fallback_provider: Optional[str] = None,
    ):
        self.primary_name = (primary_provider or settings.AI_PROVIDER).lower()
        fb = fallback_provider if fallback_provider is not None else settings.AI_FALLBACK_PROVIDER
        self.fallback_name = fb.lower() if fb else None

        self._providers: Dict[str, BaseAIProvider] = {
            "qwen": OllamaProvider(),
            "gemini": GeminiProvider(),
            "openai": OpenAIProvider(),
        }
        self.last_provider_used: str = self.primary_name

    def get_provider(self, name: str) -> BaseAIProvider:
        prov = self._providers.get(name.lower())
        if not prov:
            raise AIConfigurationError(
                provider=name,
                message=f"Unknown AI provider '{name}'. Available: {list(self._providers.keys())}",
            )
        return prov

    def register_provider(self, name: str, provider: BaseAIProvider) -> None:
        self._providers[name.lower()] = provider

    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Executes text generation on primary provider, with observable fallback if unavailable or failing.
        """
        primary = self.get_provider(self.primary_name)
        try:
            result = await primary.generate_text(
                prompt,
                system_instruction=system_instruction,
                model=model,
                **kwargs,
            )
            self.last_provider_used = self.primary_name
            return result
        except (AIProviderUnavailableError, AITimeoutError, AIProviderError) as primary_err:
            if not self.fallback_name or self.fallback_name == "none" or self.fallback_name == self.primary_name:
                logger.error(
                    f"[AI Service] Primary provider '{self.primary_name}' failed and no fallback is configured: {primary_err}"
                )
                raise primary_err

            logger.warning(
                f"[AI Fallback Triggered] Primary provider '{self.primary_name}' failed ({type(primary_err).__name__}: {primary_err}). "
                f"Falling back to configured provider '{self.fallback_name}'."
            )

            fallback = self.get_provider(self.fallback_name)
            try:
                result = await fallback.generate_text(
                    prompt,
                    system_instruction=system_instruction,
                    **kwargs,
                )
                self.last_provider_used = f"{self.fallback_name} (fallback from {self.primary_name})"
                logger.info(
                    f"[AI Fallback Succeeded] Generation served via fallback provider '{self.fallback_name}'."
                )
                return result
            except Exception as fallback_err:
                logger.error(
                    f"[AI Fallback Failed] Fallback provider '{self.fallback_name}' also failed: {fallback_err}"
                )
                raise AIProviderError(
                    provider=f"{self.primary_name}->{self.fallback_name}",
                    message=(
                        f"Both primary provider '{self.primary_name}' ({primary_err}) "
                        f"and fallback provider '{self.fallback_name}' ({fallback_err}) failed."
                    ),
                    details={
                        "primary_error": str(primary_err),
                        "fallback_error": str(fallback_err),
                    },
                ) from fallback_err

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> T:
        """
        Executes structured Pydantic generation on primary provider with observable fallback.
        """
        primary = self.get_provider(self.primary_name)
        try:
            result = await primary.generate_structured(
                prompt,
                schema,
                system_instruction=system_instruction,
                model=model,
                **kwargs,
            )
            self.last_provider_used = self.primary_name
            return result
        except (AIProviderUnavailableError, AITimeoutError, AISchemaValidationError, AIProviderError) as primary_err:
            if not self.fallback_name or self.fallback_name == "none" or self.fallback_name == self.primary_name:
                logger.error(
                    f"[AI Service] Primary provider '{self.primary_name}' structured generation failed and no fallback configured: {primary_err}"
                )
                raise primary_err

            logger.warning(
                f"[AI Fallback Triggered] Primary '{self.primary_name}' structured generation failed ({type(primary_err).__name__}: {primary_err}). "
                f"Falling back to '{self.fallback_name}'."
            )

            fallback = self.get_provider(self.fallback_name)
            try:
                result = await fallback.generate_structured(
                    prompt,
                    schema,
                    system_instruction=system_instruction,
                    **kwargs,
                )
                self.last_provider_used = f"{self.fallback_name} (fallback from {self.primary_name})"
                logger.info(
                    f"[AI Fallback Succeeded] Structured generation served via fallback '{self.fallback_name}'."
                )
                return result
            except Exception as fallback_err:
                logger.error(
                    f"[AI Fallback Failed] Fallback provider '{self.fallback_name}' structured generation failed: {fallback_err}"
                )
                raise AIProviderError(
                    provider=f"{self.primary_name}->{self.fallback_name}",
                    message=(
                        f"Both primary provider '{self.primary_name}' ({primary_err}) "
                        f"and fallback provider '{self.fallback_name}' ({fallback_err}) failed for schema '{schema.__name__}'."
                    ),
                    details={
                        "primary_error": str(primary_err),
                        "fallback_error": str(fallback_err),
                    },
                ) from fallback_err

    async def health(self) -> Dict[str, Any]:
        """Diagnostic health check covering primary and fallback providers."""
        primary = self.get_provider(self.primary_name)
        primary_health = await primary.health()

        fallback_health = None
        if self.fallback_name and self.fallback_name != "none":
            fallback = self.get_provider(self.fallback_name)
            fallback_health = await fallback.health()

        return {
            "status": primary_health.get("status", "unknown"),
            "configured_primary": self.primary_name,
            "configured_fallback": self.fallback_name,
            "last_provider_used": self.last_provider_used,
            "primary": primary_health,
            "fallback": fallback_health,
        }


# Singleton manager instance
_ai_service: Optional[AIServiceManager] = None


def get_ai_service() -> AIServiceManager:
    """Returns or initializes the singleton AIServiceManager."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIServiceManager()
    return _ai_service
