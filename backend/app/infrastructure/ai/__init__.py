"""AI Infrastructure package for SIET Editorial Intelligence."""

from app.infrastructure.ai.base import BaseAIProvider
from app.infrastructure.ai.constants import (
    DEFAULT_STRICT_GROUNDING_INSTRUCTION,
    EDITORIAL_ROLE_INSTRUCTION,
)
from app.infrastructure.ai.exceptions import (
    AIConfigurationError,
    AIError,
    AIProviderError,
    AIProviderUnavailableError,
    AISchemaValidationError,
    AITimeoutError,
)
from app.infrastructure.ai.gemini_provider import GeminiProvider
from app.infrastructure.ai.manager import AIServiceManager, get_ai_service
from app.infrastructure.ai.ollama_provider import OllamaProvider
from app.infrastructure.ai.openai_provider import OpenAIProvider
from app.infrastructure.ai.schemas import (
    EditorialPlan,
    EditorialReview,
    EditorialSectionPlan,
    GeneratedMagazineSections,
    MagazineEditorialContent,
    StructuredMagazineStoryContent,
)

__all__ = [
    "BaseAIProvider",
    "OllamaProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "AIServiceManager",
    "get_ai_service",
    "AIError",
    "AIProviderError",
    "AIProviderUnavailableError",
    "AITimeoutError",
    "AISchemaValidationError",
    "AIConfigurationError",
    "DEFAULT_STRICT_GROUNDING_INSTRUCTION",
    "EDITORIAL_ROLE_INSTRUCTION",
    "MagazineEditorialContent",
    "StructuredMagazineStoryContent",
    "EditorialPlan",
    "EditorialReview",
    "EditorialSectionPlan",
    "GeneratedMagazineSections",
]

