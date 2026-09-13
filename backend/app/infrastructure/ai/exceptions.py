"""Domain exceptions for AI providers and LLM infrastructure."""


class AIError(Exception):
    """Base exception for all AI provider operations."""

    def __init__(self, message: str = "AI service error", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AIProviderUnavailableError(AIError):
    """Raised when an AI provider endpoint is unreachable, offline, or returns 503/504."""

    def __init__(
        self,
        provider: str,
        endpoint: str = "",
        message: str | None = None,
        details: dict | None = None,
    ):
        msg = message or f"AI provider '{provider}' is unavailable at endpoint '{endpoint}'"
        super().__init__(msg, details)
        self.provider = provider
        self.endpoint = endpoint


class AITimeoutError(AIError):
    """Raised when an AI provider call times out."""

    def __init__(
        self,
        provider: str,
        timeout_seconds: float,
        message: str | None = None,
        details: dict | None = None,
    ):
        msg = (
            message
            or f"AI provider '{provider}' request timed out after {timeout_seconds}s"
        )
        super().__init__(msg, details)
        self.provider = provider
        self.timeout_seconds = timeout_seconds


class AISchemaValidationError(AIError):
    """Raised when model response cannot be parsed or validated against the requested Pydantic schema."""

    def __init__(
        self,
        provider: str,
        schema_name: str,
        raw_response: str = "",
        message: str | None = None,
        details: dict | None = None,
    ):
        msg = (
            message
            or f"AI provider '{provider}' failed to produce valid schema '{schema_name}'"
        )
        super().__init__(msg, details)
        self.provider = provider
        self.schema_name = schema_name
        self.raw_response = raw_response


class AIConfigurationError(AIError):
    """Raised when AI provider configuration is invalid or missing required credentials."""

    def __init__(self, provider: str, message: str, details: dict | None = None):
        super().__init__(message, details)
        self.provider = provider


class AIProviderError(AIError):
    """Raised when an unexpected provider error occurs during generation."""

    def __init__(self, provider: str, message: str, details: dict | None = None):
        super().__init__(message, details)
        self.provider = provider
