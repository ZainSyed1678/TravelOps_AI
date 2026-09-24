"""Qdrant Vector Database connection and management."""

import time
from typing import Any

from qdrant_client import AsyncQdrantClient

from app.core.config import settings

_qdrant_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    """Get or create singleton AsyncQdrantClient."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY or None,
            timeout=5.0,
        )
    return _qdrant_client


async def close_qdrant_client() -> None:
    """Close Qdrant client connection."""
    global _qdrant_client
    if _qdrant_client is not None:
        await _qdrant_client.close()
        _qdrant_client = None


async def check_qdrant_connection() -> dict[str, Any]:
    """Check Qdrant connectivity and latency."""
    start_time = time.perf_counter()
    try:
        client = get_qdrant_client()
        # Ping or get collections to verify connection
        collections_response = await client.get_collections()
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "connected",
            "latency_ms": latency_ms,
            "message": f"Qdrant healthy ({len(collections_response.collections)} collections found)",
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "message": str(exc),
        }
