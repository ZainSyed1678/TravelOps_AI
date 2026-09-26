"""Prometheus metrics registry and telemetry collectors for TravelOps AI."""

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# 1. HTTP Gateway & Request Metrics
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "travelops_http_requests_total",
    "Total HTTP requests received by endpoint and status code",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "travelops_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

HTTP_ACTIVE_REQUESTS = Gauge(
    "travelops_http_active_requests",
    "Active in-flight HTTP requests",
    ["method", "endpoint"],
)

# ---------------------------------------------------------------------------
# 2. Agentic AI & LangGraph State Machine Metrics
# ---------------------------------------------------------------------------

AGENT_INVOCATIONS_TOTAL = Counter(
    "travelops_agent_invocations_total",
    "Total agent graph invocations by workflow and status",
    ["workflow", "status"],
)

AGENT_EXECUTION_DURATION_SECONDS = Histogram(
    "travelops_agent_execution_duration_seconds",
    "Agent graph end-to-end execution duration in seconds",
    ["workflow"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

AGENT_STATE_TRANSITIONS_TOTAL = Counter(
    "travelops_agent_state_transitions_total",
    "Agent state machine node transitions",
    ["from_node", "to_node"],
)

# ---------------------------------------------------------------------------
# 3. Human-in-the-Loop (HITL) Safety Metrics
# ---------------------------------------------------------------------------

HITL_PENDING_ACTIONS = Gauge(
    "travelops_hitl_pending_actions",
    "Current number of pending human-in-the-loop confirmation actions",
)

HITL_DECISIONS_TOTAL = Counter(
    "travelops_hitl_decisions_total",
    "Total human-in-the-loop decisions (confirm/reject)",
    ["action_type", "decision"],
)

# ---------------------------------------------------------------------------
# 4. RAG Retrieval & Knowledge Graph Metrics
# ---------------------------------------------------------------------------

RAG_QUERIES_TOTAL = Counter(
    "travelops_rag_queries_total",
    "Total RAG queries processed",
    ["status"],
)

RAG_RETRIEVAL_DURATION_SECONDS = Histogram(
    "travelops_rag_retrieval_duration_seconds",
    "RAG vector and hybrid retrieval latency in seconds",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

RAG_CITATIONS_COUNT = Histogram(
    "travelops_rag_citations_count",
    "Number of citations retrieved per RAG query",
    buckets=[0, 1, 2, 3, 5, 8, 12, 20],
)

# ---------------------------------------------------------------------------
# 5. Travel ML & Anomaly Detection Metrics
# ---------------------------------------------------------------------------

ML_RANKING_REQUESTS_TOTAL = Counter(
    "travelops_ml_ranking_requests_total",
    "Total flight offer ranking requests processed",
    ["status"],
)

ML_RANKING_DURATION_SECONDS = Histogram(
    "travelops_ml_ranking_duration_seconds",
    "Flight offer ranking duration in seconds",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

ML_ANOMALIES_DETECTED_TOTAL = Counter(
    "travelops_ml_anomalies_detected_total",
    "Total route fare anomalies detected",
    ["route"],
)

# ---------------------------------------------------------------------------
# 6. Provider Integration & GDS Metrics
# ---------------------------------------------------------------------------

PROVIDER_REQUESTS_TOTAL = Counter(
    "travelops_provider_requests_total",
    "Total outbound provider API calls",
    ["provider", "operation", "status"],
)

PROVIDER_LATENCY_SECONDS = Histogram(
    "travelops_provider_latency_seconds",
    "Outbound provider API latency in seconds",
    ["provider", "operation"],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
)


# ---------------------------------------------------------------------------
# Telemetry Helper Functions
# ---------------------------------------------------------------------------


def record_http_request(
    method: str, endpoint: str, status_code: int, duration_seconds: float
) -> None:
    """Record completed HTTP request metrics."""
    HTTP_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=method,
        endpoint=endpoint,
    ).observe(duration_seconds)


def record_agent_invocation(workflow: str, status: str, duration_seconds: float) -> None:
    """Record agent workflow execution."""
    AGENT_INVOCATIONS_TOTAL.labels(
        workflow=workflow,
        status=status,
    ).inc()
    AGENT_EXECUTION_DURATION_SECONDS.labels(
        workflow=workflow,
    ).observe(duration_seconds)


def record_hitl_action_created() -> None:
    """Increment pending HITL actions gauge."""
    HITL_PENDING_ACTIONS.inc()


def record_hitl_decision(action_type: str, decision: str) -> None:
    """Record human approval or rejection decision and decrement gauge."""
    HITL_DECISIONS_TOTAL.labels(
        action_type=action_type,
        decision=decision,
    ).inc()
    # Decrement pending gauge
    HITL_PENDING_ACTIONS.dec()


def record_rag_query(status: str, duration_seconds: float, citations_count: int) -> None:
    """Record RAG query latency and citation count."""
    RAG_QUERIES_TOTAL.labels(status=status).inc()
    RAG_RETRIEVAL_DURATION_SECONDS.observe(duration_seconds)
    RAG_CITATIONS_COUNT.observe(citations_count)


def record_ml_ranking(status: str, duration_seconds: float) -> None:
    """Record flight ranking ML inference."""
    ML_RANKING_REQUESTS_TOTAL.labels(status=status).inc()
    ML_RANKING_DURATION_SECONDS.observe(duration_seconds)


def record_fare_anomaly(route: str) -> None:
    """Record fare anomaly detection event."""
    ML_ANOMALIES_DETECTED_TOTAL.labels(route=route).inc()


def record_provider_call(
    provider: str, operation: str, status: str, duration_seconds: float
) -> None:
    """Record outbound GDS/supplier provider API call."""
    PROVIDER_REQUESTS_TOTAL.labels(
        provider=provider,
        operation=operation,
        status=status,
    ).inc()
    PROVIDER_LATENCY_SECONDS.labels(
        provider=provider,
        operation=operation,
    ).observe(duration_seconds)
