"""Normalized provider exceptions."""

from typing import Any


class ProviderException(Exception):
    """Base exception for all travel provider errors."""

    def __init__(
        self,
        message: str,
        provider_name: str,
        error_code: str = "PROVIDER_ERROR",
        status_code: int = 502,
        raw_error: Any | None = None,
    ):
        super().__init__(f"[{provider_name}] {error_code}: {message}")
        self.message = message
        self.provider_name = provider_name
        self.error_code = error_code
        self.status_code = status_code
        self.raw_error = raw_error


class ProviderTimeoutException(ProviderException):
    """Raised when an external travel provider API times out."""

    def __init__(self, provider_name: str, message: str = "Provider API request timed out"):
        super().__init__(
            message=message,
            provider_name=provider_name,
            error_code="PROVIDER_TIMEOUT",
            status_code=504,
        )


class ProviderRateLimitException(ProviderException):
    """Raised when external travel provider rate limit is exceeded."""

    def __init__(self, provider_name: str, retry_after_seconds: int | None = None):
        super().__init__(
            message=f"Provider rate limit exceeded. Retry after {retry_after_seconds or 60}s",
            provider_name=provider_name,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
        )
        self.retry_after_seconds = retry_after_seconds


class ProviderAuthenticationException(ProviderException):
    """Raised when credentials or token authentication fails for a provider."""

    def __init__(self, provider_name: str, message: str = "Provider authentication failed"):
        super().__init__(
            message=message,
            provider_name=provider_name,
            error_code="AUTHENTICATION_FAILED",
            status_code=401,
        )


class ProviderInventoryUnavailableException(ProviderException):
    """Raised when requested flight, room, or fare is no longer available."""

    def __init__(
        self, provider_name: str, message: str = "Requested travel inventory is unavailable"
    ):
        super().__init__(
            message=message,
            provider_name=provider_name,
            error_code="INVENTORY_UNAVAILABLE",
            status_code=409,
        )


class ProviderValidationException(ProviderException):
    """Raised when provider rejects request due to invalid parameters."""

    def __init__(self, provider_name: str, message: str):
        super().__init__(
            message=message,
            provider_name=provider_name,
            error_code="INVALID_REQUEST",
            status_code=400,
        )
