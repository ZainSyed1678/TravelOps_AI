# TravelOps AI — Production Operations & Incident Response Runbook

## 1. System Topology & Service Port Matrix

| Service | Port | Host Bind | Purpose | Health Endpoint |
|---|---|---|---|---|
| **FastAPI Gateway** | `8000` | `0.0.0.0:8000` | REST API, Agent Graph, Security Layer | `GET /health` |
| **React Console** | `3000` | `0.0.0.0:3000` | Operations Console & Chat UI | `GET /` |
| **PostgreSQL 16** | `5432` | `127.0.0.1:5432` | Durable entity storage & Agent memory | `pg_isready` |
| **Redis 7** | `6379` | `127.0.0.1:6379` | Ephemeral caching & Session hot tier | `redis-cli ping` |
| **Qdrant Vector DB** | `6333` | `127.0.0.1:6333` | Vector embedding storage & HNSW search | `GET /healthz` |
| **Neo4j 5 Graph DB** | `7474`, `7687` | `127.0.0.1:7687` | Knowledge graph & multi-hop Cypher queries | `GET http://localhost:7474` |
| **Prometheus** | `9090` | `0.0.0.0:9090` | Telemetry scraping & metric aggregation | `GET /-/healthy` |
| **Grafana** | `3001` | `0.0.0.0:3001` | Operational telemetry dashboard | `GET /api/health` |

---

## 2. Standard Operating Procedures (SOP)

### 2.1. Local & Production Deployment
```bash
# Start all 8 core services via Docker Compose
docker compose up -d --build

# Verify all containers are running and healthy
docker compose ps

# Inspect unified system logs
docker compose logs -f backend
```

### 2.2. Health & Readiness Verification
```bash
# Check gateway liveness probe
curl http://localhost:8000/health

# Check gateway readiness probe (validates DB, Redis, Qdrant, Neo4j)
curl http://localhost:8000/ready

# Check system diagnostic telemetry
curl http://localhost:8000/api/v1/system/info
```

### 2.3. Database Migrations (PostgreSQL / Alembic)
```bash
# Inspect current database revision
alembic current

# Run pending database migrations
alembic upgrade head

# Roll back last migration
alembic downgrade -1
```

### 2.4. Cache Management Operations
```bash
# Inspect live cache statistics & hit rates
curl http://localhost:8000/api/v1/cache/stats

# Selectively invalidate cache entries by airline tag (e.g. EK)
curl -X POST http://localhost:8000/api/v1/cache/invalidate \
  -H "Content-Type: application/json" \
  -d '{"tag": "airline:EK"}'

# Flush an entire cache namespace
curl -X DELETE "http://localhost:8000/api/v1/cache/flush?namespace=travelops:flights"
```

---

## 3. Incident Response Playbooks

### Playbook A: Degraded Datastore / Gateway Unreadiness
- **Symptom**: `GET /ready` returns HTTP 503 with `"status": "unhealthy"`.
- **Triage Steps**:
  1. Inspect component breakdown in `/ready` response payload (`postgres`, `redis`, `qdrant`, `neo4j`).
  2. Verify individual container health:
     ```bash
     docker compose ps
     ```
  3. If Redis is down, check whether the in-memory fallback cache has engaged:
     ```bash
     curl http://localhost:8000/api/v1/cache/stats
     ```
  4. If Neo4j is unreachable, verify that the in-memory NetworkX DiGraph fallback is servicing GraphRAG requests:
     ```bash
     curl http://localhost:8000/api/v1/graphrag/stats
     ```
  5. Restart the affected container:
     ```bash
     docker compose restart <service_name>
     ```

### Playbook B: HITL Action Queue Backlog Spike
- **Symptom**: Prometheus alert `travelops_hitl_pending_actions > 20` or supervisor dashboard queue warning.
- **Triage Steps**:
  1. Inspect pending actions queue depth:
     ```bash
     curl http://localhost:8000/api/v1/agents/hitl/pending
     ```
  2. Identify if an upstream airline disruption is causing bulk cancellation proposals (e.g. weather event at DXB or BOM).
  3. Direct operational team to the HITL Review Queue in the React console (`http://localhost:3000`).
  4. Process pending proposals via bulk supervisor review or API confirmation endpoints.

### Playbook C: Adversarial Prompt Injection Spike
- **Symptom**: Prometheus metric `travelops_security_violations_total` spiking or repeated `SECURITY_BLOCKED` states in chat logs.
- **Triage Steps**:
  1. Query security audit ledger:
     ```bash
     curl http://localhost:8000/api/v1/security/audit-logs?limit=50
     ```
  2. Extract offending client IPs, correlation IDs, and attack patterns (`JAILBREAK_ATTEMPT`, `DELIMITER_HIJACKING`, `TOOL_PATH_TRAVERSAL`).
  3. Temporarily ban offending IP at reverse proxy / load balancer level.
  4. Update heuristic pattern regexes in `backend/app/security/injection_guard.py` if a novel vector is detected.

### Playbook D: High Latency / Rate Limit Saturation
- **Symptom**: Clients receiving HTTP 429 Too Many Requests (`Retry-After: 60`).
- **Triage Steps**:
  1. Check rate limit headers returned by gateway (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`).
  2. Inspect high-traffic callers by `X-Correlation-ID` or client IP.
  3. Adjust default rate limit threshold in environment configuration if legitimate operational traffic exceeds threshold:
     ```env
     RATE_LIMIT_DEFAULT_REQUESTS=300
     RATE_LIMIT_DEFAULT_WINDOW_SECONDS=60
     ```
  4. Restart backend service to reload configuration.

---

## 4. Telemetry & Metric Reference

| Metric Name | Type | Description | Alert Threshold |
|---|---|---|---|
| `travelops_http_requests_total` | Counter | Total HTTP requests by method, route, and status | N/A |
| `travelops_http_request_duration_seconds` | Histogram | Request latency across API endpoints | p95 > 2.0s |
| `travelops_agent_invocations_total` | Counter | LangGraph agent executions by workflow | N/A |
| `travelops_hitl_pending_actions` | Gauge | Depth of actions awaiting human operator approval | > 20 pending |
| `travelops_rag_queries_total` | Counter | RAG retrieval queries processed | N/A |
| `travelops_ml_ranking_requests_total` | Counter | GBDT flight ranking inferences | N/A |
| `travelops_ml_anomalies_detected_total` | Counter | Route fare price surge / deal anomalies | N/A |
| `travelops_cache_hits_total` | Counter | Distributed cache hits | Hit rate < 60% |
