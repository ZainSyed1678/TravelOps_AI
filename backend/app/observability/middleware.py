"""HTTP Observability Middleware for request tracing, latency histograms, and error telemetry."""

import re
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import logger
from app.observability.metrics import (
    HTTP_ACTIVE_REQUESTS,
    record_http_request,
)


def normalize_path(path: str) -> str:
    """Normalize dynamic URL segments into parameterized route templates to prevent cardinality explosion."""
    # Strip trailing slash if present
    cleaned = path.rstrip("/") if path != "/" else "/"

    # Replace UUIDs
    cleaned = re.sub(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "{id}",
        cleaned,
    )
    # Replace thread IDs
    cleaned = re.sub(r"th_[a-zA-Z0-9_-]+", "{thread_id}", cleaned)
    # Replace action IDs
    cleaned = re.sub(r"act_[a-zA-Z0-9_-]+", "{action_id}", cleaned)
    # Replace eval run IDs
    cleaned = re.sub(r"eval_[a-zA-Z0-9_-]+", "{run_id}", cleaned)
    # Replace user IDs
    cleaned = re.sub(r"usr_[a-zA-Z0-9_-]+", "{user_id}", cleaned)

    # Replace parameterized graph paths
    cleaned = re.sub(r"/api/v1/graph/flight/[A-Za-z0-9]+", "/api/v1/graph/flight/{flight_number}", cleaned)
    cleaned = re.sub(
        r"/api/v1/graph/airline/[A-Za-z0-9]+/policies",
        "/api/v1/graph/airline/{airline_code}/policies",
        cleaned,
    )
    cleaned = re.sub(
        r"/api/v1/graph/destination/[A-Za-z0-9]+/hotels",
        "/api/v1/graph/destination/{airport_code}/hotels",
        cleaned,
    )

    return cleaned


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware capturing Prometheus metrics and distributed correlation IDs."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        normalized_endpoint = normalize_path(request.url.path)
        method = request.method

        # Increment active in-flight gauge
        HTTP_ACTIVE_REQUESTS.labels(method=method, endpoint=normalized_endpoint).inc()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time

            # Record Prometheus metrics
            record_http_request(
                method=method,
                endpoint=normalized_endpoint,
                status_code=response.status_code,
                duration_seconds=duration,
            )

            # Response tracing headers
            response.headers["X-Request-ID"] = correlation_id
            response.headers["X-Response-Time-Ms"] = str(round(duration * 1000, 2))

            logger.info(
                f"{method} {request.url.path} -> {response.status_code} ({round(duration * 1000, 2)}ms)"
            )
            return response

        except Exception as exc:
            duration = time.perf_counter() - start_time
            record_http_request(
                method=method,
                endpoint=normalized_endpoint,
                status_code=500,
                duration_seconds=duration,
            )
            logger.error(
                f"Unhandled error processing {method} {request.url.path}: {exc}",
                exc_info=True,
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "detail": "An unexpected error occurred. Please contact system administrator.",
                    "correlation_id": correlation_id,
                },
                headers={"X-Request-ID": correlation_id},
            )
        finally:
            # Decrement active in-flight gauge
            HTTP_ACTIVE_REQUESTS.labels(method=method, endpoint=normalized_endpoint).dec()
