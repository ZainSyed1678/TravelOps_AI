"""Standardized API response envelopes for TravelOps AI REST v1 endpoints."""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.context import get_correlation_id

T = TypeVar("T")


class ApiMeta(BaseModel):
    """Metadata envelope included with API responses."""

    correlation_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    version: str = "0.1.0"
    total: int | None = None
    page: int | None = None
    page_size: int | None = None
    execution_time_ms: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel, Generic[T]):
    """Standardized top-level API envelope."""

    success: bool = True
    status_code: int = 200
    message: str = "Success"
    data: T | None = None
    meta: ApiMeta = Field(default_factory=ApiMeta)


def api_success(
    data: T | None = None,
    message: str = "Success",
    status_code: int = 200,
    total: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
    execution_time_ms: float | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> ApiResponse[T]:
    """Factory helper to construct a standardized success envelope."""
    cid = get_correlation_id()
    meta = ApiMeta(
        correlation_id=cid if cid else None,
        total=total,
        page=page,
        page_size=page_size,
        execution_time_ms=execution_time_ms,
        extra=extra_meta or {},
    )
    return ApiResponse[T](
        success=True,
        status_code=status_code,
        message=message,
        data=data,
        meta=meta,
    )
