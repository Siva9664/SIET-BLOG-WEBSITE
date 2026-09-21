"""Base provider interface for AI / LLM services."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseAIProvider(ABC):
    """Abstract base class defining the AI provider interface."""

    provider_name: str = "base"

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generates raw text response for a given prompt and optional system instruction.
        """
        pass

    @abstractmethod
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
        Generates structured output validated against a Pydantic schema model.
        Rejects invalid output with AISchemaValidationError rather than accepting arbitrary text.
        """
        pass

    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        """
        Performs an operational health check on the provider endpoint and model availability.
        Returns a dictionary with status, provider, and diagnostic details.
        """
        pass
