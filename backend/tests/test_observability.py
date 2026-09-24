"""Tests for Phase 12 Observability: Prometheus telemetry, Middleware, and Grafana provisioning."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability.metrics import (
    AGENT_EXECUTION_DURATION_SECONDS,
    AGENT_INVOCATIONS_TOTAL,
    HITL_DECISIONS_TOTAL,
    HITL_PENDING_ACTIONS,
    HTTP_ACTIVE_REQUESTS,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    ML_ANOMALIES_DETECTED_TOTAL,
    ML_RANKING_DURATION_SECONDS,
    ML_RANKING_REQUESTS_TOTAL,
    PROVIDER_LATENCY_SECONDS,
    PROVIDER_REQUESTS_TOTAL,
    RAG_CITATIONS_COUNT,
    RAG_QUERIES_TOTAL,
    RAG_RETRIEVAL_DURATION_SECONDS,
    record_agent_invocation,
    record_fare_anomaly,
    record_hitl_action_created,
    record_hitl_decision,
    record_http_request,
    record_ml_ranking,
    record_provider_call,
    record_rag_query,
)
from app.observability.middleware import normalize_path

# ---------------------------------------------------------------------------
# 1. Telemetry Helpers & Metric Registration
# ---------------------------------------------------------------------------


def test_metric_collectors_exist():
    assert HTTP_REQUESTS_TOTAL is not None
    assert HTTP_REQUEST_DURATION_SECONDS is not None
    assert HTTP_ACTIVE_REQUESTS is not None
    assert AGENT_INVOCATIONS_TOTAL is not None
    assert AGENT_EXECUTION_DURATION_SECONDS is not None
    assert HITL_PENDING_ACTIONS is not None
    assert HITL_DECISIONS_TOTAL is not None
    assert RAG_QUERIES_TOTAL is not None
    assert RAG_RETRIEVAL_DURATION_SECONDS is not None
    assert RAG_CITATIONS_COUNT is not None
    assert ML_RANKING_REQUESTS_TOTAL is not None
    assert ML_RANKING_DURATION_SECONDS is not None
    assert ML_ANOMALIES_DETECTED_TOTAL is not None
    assert PROVIDER_REQUESTS_TOTAL is not None
    assert PROVIDER_LATENCY_SECONDS is not None


def test_record_telemetry_functions():
    # HTTP metrics
    record_http_request("GET", "/health", 200, 0.012)

    # Agent metrics
    record_agent_invocation("SEARCH", "success", 0.45)
    record_agent_invocation("POLICY", "success", 0.32)

    # HITL metrics
    initial_gauge = HITL_PENDING_ACTIONS._value.get()
    record_hitl_action_created()
    assert HITL_PENDING_ACTIONS._value.get() == initial_gauge + 1

    record_hitl_decision("REBOOK_FLIGHT", "APPROVED")
    assert HITL_PENDING_ACTIONS._value.get() == initial_gauge

    # RAG metrics
    record_rag_query("success", 0.08, 4)

    # ML ranking metrics
    record_ml_ranking("success", 0.025)

    # Anomaly detection metrics
    record_fare_anomaly("BOM-DXB")

    # Provider metrics
    record_provider_call("AMADEUS", "flight_offers_search", "success", 0.15)


# ---------------------------------------------------------------------------
# 2. Path Normalization Tests (Prevent High Cardinality)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_path,expected",
    [
        ("/health", "/health"),
        ("/api/v1/agents/state/th_123456789abc", "/api/v1/agents/state/{thread_id}"),
        ("/api/v1/agents/hitl/actions/act_9876543210ab/confirm", "/api/v1/agents/hitl/actions/{action_id}/confirm"),
        ("/api/v1/agents/memory/sessions/th_abcdef012345/history", "/api/v1/agents/memory/sessions/{thread_id}/history"),
        ("/api/v1/agents/memory/profile/usr_alice99", "/api/v1/agents/memory/profile/{user_id}"),
        ("/api/v1/graph/flight/EK505", "/api/v1/graph/flight/{flight_number}"),
        ("/api/v1/graph/airline/AI/policies", "/api/v1/graph/airline/{airline_code}/policies"),
        ("/api/v1/graph/destination/DXB/hotels", "/api/v1/graph/destination/{airport_code}/hotels"),
    ],
)
def test_normalize_path(raw_path: str, expected: str):
    assert normalize_path(raw_path) == expected


# ---------------------------------------------------------------------------
# 3. HTTP Middleware Tracing Headers & Prometheus /metrics Endpoint
# ---------------------------------------------------------------------------


client = TestClient(app)


def test_middleware_headers_and_metrics_emission():
    # Make request to /health
    response = client.get("/health")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert "x-response-time-ms" in response.headers

    # Fetch Prometheus /metrics endpoint
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "text/plain" in metrics_resp.headers["content-type"]

    body = metrics_resp.text
    # Verify core metric series are present in the output
    assert "travelops_http_requests_total" in body
    assert "travelops_http_request_duration_seconds" in body
    assert "travelops_agent_invocations_total" in body
    assert "travelops_hitl_pending_actions" in body
    assert "travelops_rag_queries_total" in body
    assert "travelops_ml_ranking_requests_total" in body


# ---------------------------------------------------------------------------
# 4. Grafana Dashboard JSON Specification Validation
# ---------------------------------------------------------------------------


def test_grafana_dashboard_json_validity():
    dashboard_path = (
        Path(__file__).resolve().parent.parent.parent
        / "infrastructure"
        / "grafana"
        / "provisioning"
        / "dashboards"
        / "travelops_overview.json"
    )
    assert dashboard_path.exists(), f"Dashboard JSON missing at {dashboard_path}"

    with open(dashboard_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["uid"] == "travelops-overview-dashboard"
    assert data["title"] == "TravelOps AI - Platform Observability"
    assert "panels" in data
    assert len(data["panels"]) >= 10

    # Verify PromQL expressions inside panels
    for panel in data["panels"]:
        if "targets" in panel:
            for target in panel["targets"]:
                expr = target.get("expr", "")
                assert "travelops_" in expr or "vector(0)" in expr
