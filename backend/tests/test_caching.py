"""Tests for Phase 13 Caching Layer: CacheManager, @cached decorators, tags, and REST endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.caching.decorators import cached
from app.caching.manager import CacheManager, CacheStats, hash_key
from app.main import app

# ---------------------------------------------------------------------------
# 1. CacheManager Core Operations & TTL Expiration
# ---------------------------------------------------------------------------


def test_cache_manager_basic_get_set_delete():
    mgr = CacheManager(namespace="test_basic")
    mgr.flush()

    assert mgr.get("user_1") is None

    mgr.set("user_1", {"name": "Alice", "role": "admin"}, ttl_seconds=60)
    cached_val = mgr.get("user_1")
    assert cached_val == {"name": "Alice", "role": "admin"}

    mgr.delete("user_1")
    assert mgr.get("user_1") is None


def test_cache_manager_ttl_expiration():
    mgr = CacheManager(namespace="test_ttl")
    mgr.set("ephemeral_key", "temporary_value", ttl_seconds=1)

    assert mgr.get("ephemeral_key") == "temporary_value"

    # Simulate time passing by artificially advancing expiration
    full_key = mgr._format_key("ephemeral_key")
    mgr._mem_expiry[full_key] = datetime.now(UTC) - timedelta(seconds=1)

    assert mgr.get("ephemeral_key") is None


# ---------------------------------------------------------------------------
# 2. Tag-Based Invalidation & Prefix Invalidation
# ---------------------------------------------------------------------------


def test_cache_manager_tag_invalidation():
    mgr = CacheManager(namespace="test_tags")
    mgr.flush()

    mgr.set("flight_ek1", {"flight": "EK505"}, tags=["airline:EK", "route:BOM-DXB"])
    mgr.set("flight_ek2", {"flight": "EK506"}, tags=["airline:EK", "route:DXB-BOM"])
    mgr.set("flight_ai1", {"flight": "AI101"}, tags=["airline:AI", "route:DEL-JFK"])

    assert mgr.get("flight_ek1") is not None
    assert mgr.get("flight_ek2") is not None
    assert mgr.get("flight_ai1") is not None

    # Invalidate all EK flights
    count = mgr.invalidate_tag("airline:EK")
    assert count >= 2

    assert mgr.get("flight_ek1") is None
    assert mgr.get("flight_ek2") is None
    assert mgr.get("flight_ai1") == {"flight": "AI101"}


def test_cache_manager_prefix_invalidation():
    mgr = CacheManager(namespace="test_prefix")
    mgr.set("search:BOM-DXB", [1, 2, 3])
    mgr.set("search:DEL-LHR", [4, 5, 6])
    mgr.set("pricing:BOM-DXB", {"fare": 20000})

    count = mgr.invalidate_prefix("search:")
    assert count == 2

    assert mgr.get("search:BOM-DXB") is None
    assert mgr.get("search:DEL-LHR") is None
    assert mgr.get("pricing:BOM-DXB") == {"fare": 20000}


# ---------------------------------------------------------------------------
# 3. Decorator Tests (@cached for Sync and Async Functions)
# ---------------------------------------------------------------------------


class SampleModel(BaseModel):
    id: str
    score: float


invocations_sync = 0
invocations_async = 0


@cached(ttl_seconds=60, namespace="test_dec")
def sample_sync_function(x: int, y: int) -> int:
    global invocations_sync
    invocations_sync += 1
    return x + y


@cached(ttl_seconds=60, namespace="test_dec")
async def sample_async_function(name: str) -> SampleModel:
    global invocations_async
    invocations_async += 1
    return SampleModel(id=name, score=0.99)


def test_cached_decorator_sync():
    global invocations_sync
    invocations_sync = 0

    val1 = sample_sync_function(10, 20)
    assert val1 == 30
    assert invocations_sync == 1

    # Second invocation should hit cache and NOT invoke function
    val2 = sample_sync_function(10, 20)
    assert val2 == 30
    assert invocations_sync == 1


@pytest.mark.asyncio
async def test_cached_decorator_async():
    global invocations_async
    invocations_async = 0

    res1 = await sample_async_function("route_alpha")
    assert isinstance(res1, SampleModel)
    assert res1.id == "route_alpha"
    assert invocations_async == 1

    # Second invocation should hit cache and reconstitute model
    res2 = await sample_async_function("route_alpha")
    assert isinstance(res2, SampleModel)
    assert res2.id == "route_alpha"
    assert res2.score == 0.99
    assert invocations_async == 1


# ---------------------------------------------------------------------------
# 4. Cache Telemetry & Statistics
# ---------------------------------------------------------------------------


def test_cache_stats():
    mgr = CacheManager(namespace="test_stats")
    mgr.flush()

    mgr.set("k1", "v1")
    mgr.get("k1")  # Hit
    mgr.get("nonexistent")  # Miss

    stats = mgr.get_stats()
    assert isinstance(stats, CacheStats)
    assert stats.hits >= 1
    assert stats.misses >= 1
    assert 0.0 <= stats.hit_rate <= 1.0
    assert stats.backend in ("redis", "in_memory")


def test_hash_key_determinism():
    h1 = hash_key("arg1", param="value")
    h2 = hash_key("arg1", param="value")
    h3 = hash_key("arg2", param="value")

    assert h1 == h2
    assert h1 != h3


# ---------------------------------------------------------------------------
# 5. REST API Endpoint Tests
# ---------------------------------------------------------------------------


client = TestClient(app)


def test_api_cache_stats():
    response = client.get("/api/v1/cache/stats")
    assert response.status_code == 200
    data = response.json()
    assert "backend" in data
    assert "hits" in data
    assert "misses" in data
    assert "hit_rate" in data
    assert "keys_count" in data


def test_api_cache_invalidate_by_tag():
    # Prime cache via manager
    from app.caching import cache_manager

    cache_manager.set("test_tag_key", {"msg": "hello"}, tags=["test_api_tag"])

    # Invalidate via API
    resp = client.post(
        "/api/v1/cache/invalidate",
        json={"tag": "test_api_tag"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert resp.json()["invalidated_count"] >= 1


def test_api_cache_invalidate_by_prefix():
    from app.caching import cache_manager

    cache_manager.set("api_prefix_1", 100)
    cache_manager.set("api_prefix_2", 200)

    resp = client.post(
        "/api/v1/cache/invalidate",
        json={"prefix": "api_prefix_"},
    )
    assert resp.status_code == 200
    assert resp.json()["invalidated_count"] >= 2


def test_api_cache_invalidate_error_when_empty():
    resp = client.post("/api/v1/cache/invalidate", json={})
    assert resp.status_code == 400
    assert "Must provide at least one" in resp.json()["detail"]


def test_api_cache_flush():
    resp = client.delete("/api/v1/cache/flush?namespace=test_flush_ns")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
