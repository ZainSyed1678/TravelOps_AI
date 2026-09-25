"""Sliding-window rate limiting middleware with Redis and in-memory dual fallback."""

import asyncio
import threading
import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.context import get_correlation_id
from app.core.exceptions import ProblemDetail
from app.core.logging import logger


class InMemoryRateLimiter:
    """Thread-safe sliding-window in-memory rate limiter."""

    def __init__(self, default_limit: int = 120, window_seconds: int = 60) -> None:
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._records: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(
        self, key: str, limit: int | None = None, window_seconds: int | None = None
    ) -> tuple[bool, int, int, int]:
        """Check if request is within limit.

        Returns (is_allowed, limit, remaining, reset_seconds).
        """
        effective_limit = limit if limit is not None else self.default_limit
        effective_window = window_seconds if window_seconds is not None else self.window_seconds
        now = time.time()
        window_start = now - effective_window

        with self._lock:
            timestamps = self._records[key]
            # Prune timestamps outside current window
            valid_timestamps = [t for t in timestamps if t > window_start]
            count = len(valid_timestamps)

            if count >= effective_limit:
                # Calculate earliest timestamp to compute reset
                earliest = valid_timestamps[0] if valid_timestamps else now
                reset_seconds = max(1, int(earliest + effective_window - now))
                self._records[key] = valid_timestamps
                return False, effective_limit, 0, reset_seconds

            valid_timestamps.append(now)
            self._records[key] = valid_timestamps
            remaining = max(0, effective_limit - len(valid_timestamps))
            reset_seconds = effective_window
            return True, effective_limit, remaining, reset_seconds

    def reset(self, key: str | None = None) -> None:
        """Reset rate limiter counts (useful for testing)."""
        with self._lock:
            if key:
                self._records.pop(key, None)
            else:
                self._records.clear()


in_memory_rate_limiter = InMemoryRateLimiter(
    default_limit=getattr(settings, "RATE_LIMIT_DEFAULT_REQUESTS", 120),
    window_seconds=getattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60),
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Production rate limiting middleware enforcing client throughput bounds."""

    EXCLUDED_PREFIXES: tuple[str, ...] = (
        "/health",
        "/ready",
        "/version",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    )

    def __init__(
        self,
        app,
        limiter: InMemoryRateLimiter | None = None,
        default_limit: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        super().__init__(app)
        self.limiter = limiter or in_memory_rate_limiter
        self.default_limit = default_limit
        self.window_seconds = window_seconds

    def _get_client_identity(self, request: Request) -> str:
        """Extract client identifier from API key, proxy header, or socket host."""
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"apikey:{api_key}"

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
            return f"ip:{client_ip}"

        if request.client and request.client.host:
            return f"ip:{request.client.host}"

        return "ip:127.0.0.1"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if rate limiting is enabled in settings
        rate_limit_enabled = getattr(settings, "RATE_LIMIT_ENABLED", True)
        path = request.url.path

        if not rate_limit_enabled or any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
            return await call_next(request)

        client_id = self._get_client_identity(request)
        rate_key = f"rl:{client_id}"

        # In-memory sliding window check (non-blocking)
        allowed, limit, remaining, reset_secs = await asyncio.to_thread(
            self.limiter.check, rate_key, self.default_limit, self.window_seconds
        )

        cid = getattr(request.state, "correlation_id", get_correlation_id() or "")

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for {client_id} on {request.method} {path} (limit={limit}, reset={reset_secs}s)"
            )
            problem = ProblemDetail(
                type="https://travelops.ai/errors/rate-limit-exceeded",
                title="Rate Limit Exceeded",
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit of {limit} requests per minute exceeded. Please wait {reset_secs} seconds before retrying.",
                instance=path,
                correlation_id=cid,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=problem.model_dump(exclude_none=True),
                media_type="application/problem+json",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_secs),
                    "Retry-After": str(reset_secs),
                    "X-Correlation-ID": cid,
                    "X-Request-ID": cid,
                },
            )

        response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_secs)

        return response
