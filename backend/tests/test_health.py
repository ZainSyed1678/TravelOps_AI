"""Tests for /health, /version, /ready, and observability middleware."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    """Test GET /health returns 200 OK and valid health payload."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data
    assert "X-Request-ID" in response.headers
    assert "X-Response-Time-Ms" in response.headers


@pytest.mark.asyncio
async def test_version_endpoint(async_client: AsyncClient):
    """Test GET /version returns 200 OK and platform version info."""
    response = await async_client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "TravelOps AI"
    assert data["version"] == "0.1.0"
    assert data["status"] == "operational"


@pytest.mark.asyncio
async def test_ready_endpoint_all_healthy(async_client: AsyncClient):
    """Test GET /ready returns 200 OK when all backing services are connected."""
    with (
        patch(
            "app.api.endpoints.health.check_database_connection",
            new_callable=AsyncMock,
            return_value={
                "status": "connected",
                "latency_ms": 1.2,
                "message": "PostgreSQL healthy",
            },
        ),
        patch(
            "app.api.endpoints.health.check_redis_connection",
            new_callable=AsyncMock,
            return_value={"status": "connected", "latency_ms": 0.5, "message": "Redis healthy"},
        ),
        patch(
            "app.api.endpoints.health.check_qdrant_connection",
            new_callable=AsyncMock,
            return_value={"status": "connected", "latency_ms": 2.1, "message": "Qdrant healthy"},
        ),
        patch(
            "app.api.endpoints.health.check_neo4j_connection",
            new_callable=AsyncMock,
            return_value={"status": "connected", "latency_ms": 3.4, "message": "Neo4j healthy"},
        ),
    ):
        response = await async_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["services"]["postgres"]["status"] == "connected"
        assert data["services"]["redis"]["status"] == "connected"
        assert data["services"]["qdrant"]["status"] == "connected"
        assert data["services"]["neo4j"]["status"] == "connected"


@pytest.mark.asyncio
async def test_ready_endpoint_degraded(async_client: AsyncClient):
    """Test GET /ready returns 503 Service Unavailable when a dependency fails."""
    with (
        patch(
            "app.api.endpoints.health.check_database_connection",
            new_callable=AsyncMock,
            return_value={
                "status": "connected",
                "latency_ms": 1.0,
                "message": "PostgreSQL healthy",
            },
        ),
        patch(
            "app.api.endpoints.health.check_redis_connection",
            new_callable=AsyncMock,
            return_value={"status": "error", "latency_ms": 2000.0, "message": "Connection refused"},
        ),
        patch(
            "app.api.endpoints.health.check_qdrant_connection",
            new_callable=AsyncMock,
            return_value={"status": "connected", "latency_ms": 1.5, "message": "Qdrant healthy"},
        ),
        patch(
            "app.api.endpoints.health.check_neo4j_connection",
            new_callable=AsyncMock,
            return_value={"status": "connected", "latency_ms": 2.0, "message": "Neo4j healthy"},
        ),
    ):
        response = await async_client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["postgres"]["status"] == "connected"
        assert data["services"]["redis"]["status"] == "error"
        assert "Connection refused" in data["services"]["redis"]["message"]


@pytest.mark.asyncio
async def test_metrics_endpoint(async_client: AsyncClient):
    """Test GET /metrics returns Prometheus format."""
    response = await async_client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


@pytest.mark.asyncio
async def test_custom_request_id_preserved(async_client: AsyncClient):
    """Test custom X-Request-ID header is propagated in response headers."""
    custom_id = "test-corr-id-12345"
    response = await async_client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id
