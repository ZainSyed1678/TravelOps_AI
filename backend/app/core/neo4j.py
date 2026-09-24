"""Neo4j Knowledge Graph driver connection and management."""

import time
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import settings

_neo4j_driver: AsyncDriver | None = None


def get_neo4j_driver() -> AsyncDriver:
    """Get or create singleton Neo4j AsyncDriver."""
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=5.0,
            max_connection_lifetime=3600,
        )
    return _neo4j_driver


async def close_neo4j_driver() -> None:
    """Close Neo4j driver connection."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        await _neo4j_driver.close()
        _neo4j_driver = None


async def check_neo4j_connection() -> dict[str, Any]:
    """Check Neo4j connectivity and latency."""
    start_time = time.perf_counter()
    try:
        driver = get_neo4j_driver()
        await driver.verify_connectivity()
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "connected",
            "latency_ms": latency_ms,
            "message": "Neo4j connection healthy",
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "error",
            "latency_ms": latency_ms,
            "message": str(exc),
        }
