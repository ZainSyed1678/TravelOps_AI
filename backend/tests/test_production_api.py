"""Tests for Phase 15 Production API: OpenAPI 3.1, RFC 7807 error format, correlation IDs, and rate limiting."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_db_session
from app.core.init_db import init_db
from app.core.rate_limit import in_memory_rate_limiter
from app.main import app
from app.models.entities import User

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Setup isolated in-memory SQLite database for all production API tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    await init_db(engine)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = override_db
    yield session_factory
    app.dependency_overrides.pop(get_db_session, None)
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. Correlation ID & Latency Tracing Headers
# ---------------------------------------------------------------------------


def test_correlation_id_generated_when_missing():
    """Verify system generates a valid UUID correlation ID if none is supplied."""
    res = client.get("/api/v1/system/ping")
    assert res.status_code == 200
    assert "X-Correlation-ID" in res.headers
    assert "X-Request-ID" in res.headers
    cid = res.headers["X-Correlation-ID"]
    assert len(cid) > 0
    # Must equal X-Request-ID
    assert res.headers["X-Request-ID"] == cid


def test_correlation_id_propagated_when_provided():
    """Verify custom X-Correlation-ID is preserved and echoed back."""
    custom_cid = "corr-test-trace-12345"
    res = client.get("/api/v1/system/ping", headers={"X-Correlation-ID": custom_cid})
    assert res.status_code == 200
    assert res.headers["X-Correlation-ID"] == custom_cid
    assert res.headers["X-Request-ID"] == custom_cid


def test_response_time_header_presence():
    """Verify X-Response-Time-Ms header reports request processing latency."""
    res = client.get("/api/v1/system/ping")
    assert res.status_code == 200
    assert "X-Response-Time-Ms" in res.headers
    latency = float(res.headers["X-Response-Time-Ms"])
    assert latency >= 0.0


# ---------------------------------------------------------------------------
# 2. RFC 7807 Problem Details & Exception Handling
# ---------------------------------------------------------------------------


def test_rfc7807_on_404_not_found():
    """Verify non-existent endpoints return RFC 7807 Problem Details."""
    res = client.get("/api/v1/non-existent-endpoint-test-route")
    assert res.status_code == 404
    assert "application/problem+json" in res.headers.get("content-type", "")

    body = res.json()
    assert body["status"] == 404
    assert body["title"] == "Resource Not Found"
    assert "type" in body
    assert body["instance"] == "/api/v1/non-existent-endpoint-test-route"
    assert "correlation_id" in body
    assert body["correlation_id"] == res.headers["X-Correlation-ID"]
    assert "timestamp" in body


def test_rfc7807_on_422_validation_error():
    """Verify schema validation failures return RFC 7807 Problem Details with invalid_params list."""
    invalid_payload = {
        "origin": "DX",  # Must be 3 chars
        "destination": "BOM",
        "departure_date": "not-a-valid-date",
        "adults": 0,  # ge=1
    }
    res = client.post("/api/v1/flights/search", json=invalid_payload)
    assert res.status_code == 422
    assert "application/problem+json" in res.headers.get("content-type", "")

    body = res.json()
    assert body["status"] == 422
    assert body["title"] == "Unprocessable Entity"
    assert body["type"] == "https://travelops.ai/errors/validation-error"
    assert "invalid_params" in body
    assert isinstance(body["invalid_params"], list)
    assert len(body["invalid_params"]) >= 1

    # Check structure of parameter failures
    fields = [item["field"] for item in body["invalid_params"]]
    assert any("origin" in f for f in fields)


def test_rfc7807_domain_app_exception():
    """Verify custom AppException returns RFC 7807 Problem Details."""
    res = client.get("/api/v1/bookings/non-existent-booking-test-id")
    assert res.status_code == 404
    assert "application/problem+json" in res.headers.get("content-type", "")

    body = res.json()
    assert body["status"] == 404
    assert body["title"] == "Resource Not Found"
    assert body["type"] == "https://travelops.ai/errors/not-found"
    assert "non-existent-booking-test-id" in body["detail"]
    assert body["correlation_id"] == res.headers["X-Correlation-ID"]


# ---------------------------------------------------------------------------
# 3. Rate Limiting Middleware
# ---------------------------------------------------------------------------


def test_rate_limiting_headers_present():
    """Verify rate limit tracking headers are returned on API requests."""
    res = client.get("/api/v1/system/info")
    assert res.status_code == 200
    assert "X-RateLimit-Limit" in res.headers
    assert "X-RateLimit-Remaining" in res.headers
    assert "X-RateLimit-Reset" in res.headers

    limit = int(res.headers["X-RateLimit-Limit"])
    remaining = int(res.headers["X-RateLimit-Remaining"])
    assert limit > 0
    assert 0 <= remaining <= limit


def test_rate_limiting_throttling_exceeded():
    """Verify exceeding rate limit triggers HTTP 429 Too Many Requests with RFC 7807 Problem Details."""
    test_key = f"test-client-{uuid.uuid4().hex[:8]}"
    rate_key = f"rl:apikey:{test_key}"

    # Pre-exhaust the limiter bucket
    in_memory_rate_limiter.reset(rate_key)
    for _ in range(in_memory_rate_limiter.default_limit):
        in_memory_rate_limiter.check(rate_key)

    # Next request with this key should be throttled
    res = client.get("/api/v1/system/info", headers={"X-API-Key": test_key})
    assert res.status_code == 429
    assert "application/problem+json" in res.headers.get("content-type", "")
    assert "Retry-After" in res.headers
    assert res.headers["X-RateLimit-Remaining"] == "0"

    body = res.json()
    assert body["status"] == 429
    assert body["title"] == "Rate Limit Exceeded"
    assert body["type"] == "https://travelops.ai/errors/rate-limit-exceeded"

    # Cleanup
    in_memory_rate_limiter.reset(rate_key)


# ---------------------------------------------------------------------------
# 4. Standardized System & Health Endpoints
# ---------------------------------------------------------------------------


def test_system_info_standardized_envelope():
    """Verify /api/v1/system/info returns ApiResponse[SystemInfoData] envelope."""
    res = client.get("/api/v1/system/info")
    assert res.status_code == 200
    body = res.json()

    assert body["success"] is True
    assert body["status_code"] == 200
    assert "data" in body
    assert "meta" in body

    data = body["data"]
    assert data["project_name"] == "TravelOps AI"
    assert data["version"] == "0.1.0"
    assert data["uptime_seconds"] >= 0
    assert len(data["enabled_modules"]) >= 5
    assert "postgresql" in data["datastores"]

    meta = body["meta"]
    assert meta["correlation_id"] == res.headers["X-Correlation-ID"]


def test_fast_ping_probe():
    """Verify /api/v1/system/ping returns low-latency probe."""
    res = client.get("/api/v1/system/ping")
    assert res.status_code == 200
    body = res.json()
    assert body["ping"] == "pong"
    assert "timestamp" in body


# ---------------------------------------------------------------------------
# 5. Production Flight Operations Endpoints
# ---------------------------------------------------------------------------


def test_flight_search_production_endpoint():
    """Verify /api/v1/flights/search validates query, executes search, and applies ML ranking."""
    payload = {
        "origin": "BOM",
        "destination": "DXB",
        "departure_date": "2026-10-15",
        "adults": 1,
        "cabin_class": "ECONOMY",
        "max_budget": 50000.0,
    }
    res = client.post("/api/v1/flights/search", json=payload)
    assert res.status_code == 200

    body = res.json()
    assert body["success"] is True
    assert body["status_code"] == 200
    assert body["meta"]["total"] >= 1
    assert body["meta"]["extra"]["origin"] == "BOM"
    assert body["meta"]["extra"]["destination"] == "DXB"

    offers = body["data"]["offers"]
    assert len(offers) >= 1
    # Verify ranking metadata injected into offers
    first_offer = offers[0]
    assert "flight_number" in first_offer
    assert "total_price" in first_offer
    assert "airline_code" in first_offer


def test_flight_routes_endpoint():
    """Verify /api/v1/flights/routes returns major served routes."""
    res = client.get("/api/v1/flights/routes")
    assert res.status_code == 200

    body = res.json()
    assert body["success"] is True
    assert body["meta"]["total"] >= 4
    routes = body["data"]
    codes = [r["route_code"] for r in routes]
    assert "DEL-BOM" in codes
    assert "BOM-DXB" in codes


def test_flight_status_endpoint():
    """Verify /api/v1/flights/status/{flight_number} returns operational status."""
    res = client.get("/api/v1/flights/status/AI101?departure_date=2026-10-15")
    assert res.status_code == 200

    body = res.json()
    assert body["success"] is True
    assert body["data"]["flight_number"] == "AI101"
    assert body["data"]["status"] in ("ON_TIME", "DELAYED", "CANCELLED")


# ---------------------------------------------------------------------------
# 6. Production Bookings Endpoints & Database Integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bookings_crud_workflow():
    """Verify full booking lifecycle: create booking, retrieve by reference, and list bookings."""
    # Set up dedicated isolated SQLite engine
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    await init_db(engine)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Create a test user
        user = User(
            email=f"test_user_{uuid.uuid4().hex[:6]}@travelops.ai",
            full_name="Dr. Travel Ops",
            hashed_password="hashed_secure_password_test",
            role="TRAVELER",
        )
        session.add(user)
        await session.commit()
        user_id = user.id

    async def override_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = override_db

    try:
        # 1. Create a booking
        booking_payload = {
            "user_id": user_id,
            "booking_type": "FLIGHT",
            "total_amount": 14500.0,
            "currency": "INR",
            "passengers": [
                {
                    "passenger_type": "ADULT",
                    "seat_number": "12A",
                    "special_requests": "Vegetarian meal",
                }
            ],
            "metadata_json": {"flight_number": "EK505", "cabin": "ECONOMY"},
        }
        create_res = client.post("/api/v1/bookings", json=booking_payload)
        assert create_res.status_code == 201
        created_body = create_res.json()
        assert created_body["success"] is True
        booking_data = created_body["data"]
        booking_ref = booking_data["booking_reference"]
        booking_id = booking_data["id"]
        assert booking_ref.startswith("TRV-BK-")
        assert len(booking_data["passengers"]) == 1
        assert booking_data["passengers"][0]["seat_number"] == "12A"

        # 2. Retrieve booking by ID
        get_res = client.get(f"/api/v1/bookings/{booking_id}")
        assert get_res.status_code == 200
        get_body = get_res.json()
        assert get_body["data"]["booking_reference"] == booking_ref

        # 3. Retrieve booking by booking_reference
        get_ref_res = client.get(f"/api/v1/bookings/{booking_ref}")
        assert get_ref_res.status_code == 200
        assert get_ref_res.json()["data"]["id"] == booking_id

        # 4. List bookings for user
        list_res = client.get(f"/api/v1/bookings?user_id={user_id}")
        assert list_res.status_code == 200
        list_body = list_res.json()
        assert list_body["meta"]["total"] >= 1
        assert any(b["id"] == booking_id for b in list_body["data"])

    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()


# ---------------------------------------------------------------------------
# 7. OpenAPI 3.1 Specification Validation
# ---------------------------------------------------------------------------


def test_openapi_specification_metadata_and_tags():
    """Verify OpenAPI specification adheres to schema standard with proper documentation."""
    res = client.get("/openapi.json")
    assert res.status_code == 200

    schema = res.json()
    assert "openapi" in schema
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "TravelOps AI"
    assert schema["info"]["version"] == "0.1.0"

    paths = schema.get("paths", {})
    # Core Phase 15 routes
    assert "/api/v1/system/info" in paths
    assert "/api/v1/system/ping" in paths
    assert "/api/v1/flights/search" in paths
    assert "/api/v1/flights/routes" in paths
    assert "/api/v1/bookings" in paths

    # Tag metadata coverage
    tag_names = [t["name"] for t in schema.get("tags", [])]
    assert "System & Diagnostics" in tag_names
    assert "Flight Operations" in tag_names
    assert "Bookings & Reservations" in tag_names
    assert "Production RAG" in tag_names
    assert "Knowledge Graph" in tag_names
    assert "Travel Machine Learning" in tag_names
    assert "Agentic AI" in tag_names
