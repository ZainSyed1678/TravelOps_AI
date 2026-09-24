"""Cache administration and performance diagnostics REST endpoints."""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.caching.manager import CacheStats, cache_manager

router = APIRouter()


class InvalidationRequest(BaseModel):
    """Payload to selectively invalidate cached entries."""

    key: str | None = Field(None, description="Exact cache key to remove")
    prefix: str | None = Field(None, description="Prefix pattern to invalidate")
    tag: str | None = Field(None, description="Semantic tag to invalidate (e.g. airline:EK)")
    namespace: str | None = Field(None, description="Optional namespace (defaults to 'travelops')")


class InvalidationResponse(BaseModel):
    """Result of cache invalidation operation."""

    status: str
    invalidated_count: int
    message: str


@router.get(
    "/stats",
    response_model=CacheStats,
    status_code=status.HTTP_200_OK,
    summary="Retrieve cache performance metrics",
    description="Returns cache hit/miss counts, hit ratio, total cardinality, and active storage engine.",
)
async def get_cache_statistics() -> CacheStats:
    """Fetch current cache telemetry and hit rate."""
    return cache_manager.get_stats()


@router.post(
    "/invalidate",
    response_model=InvalidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Selectively invalidate cache entries",
    description="Invalidate by explicit key, wildcard prefix, or semantic tag.",
)
async def invalidate_cache(request: InvalidationRequest) -> InvalidationResponse:
    """Invalidate cached entries by key, prefix, or tag."""
    if request.tag:
        count = cache_manager.invalidate_tag(request.tag)
        return InvalidationResponse(
            status="success",
            invalidated_count=count,
            message=f"Invalidated {count} keys matching tag '{request.tag}'.",
        )

    if request.prefix is not None:
        count = cache_manager.invalidate_prefix(request.prefix, namespace=request.namespace)
        return InvalidationResponse(
            status="success",
            invalidated_count=count,
            message=f"Invalidated {count} keys matching prefix '{request.prefix}'.",
        )

    if request.key:
        ok = cache_manager.delete(request.key, namespace=request.namespace)
        count = 1 if ok else 0
        return InvalidationResponse(
            status="success",
            invalidated_count=count,
            message=f"Invalidated single key '{request.key}'.",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Must provide at least one of 'key', 'prefix', or 'tag' to invalidate.",
    )


@router.delete(
    "/flush",
    response_model=InvalidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Flush cache namespace",
    description="Evicts all keys within the specified namespace or the entire default store.",
)
async def flush_cache(
    namespace: str = Query(default="travelops", description="Namespace to flush"),
) -> InvalidationResponse:
    """Flush all keys in the target namespace."""
    count = cache_manager.flush(namespace=namespace)
    return InvalidationResponse(
        status="success",
        invalidated_count=count,
        message=f"Flushed namespace '{namespace}' ({count} keys removed).",
    )
