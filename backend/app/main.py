"""FastAPI application factory and main entry point for TravelOps AI."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.api_v1.api import api_router
from app.api.endpoints.health import router as health_router
from app.api.endpoints.rag import router as rag_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import logger
from app.core.neo4j import close_neo4j_driver
from app.core.qdrant import close_qdrant_client
from app.core.rate_limit import RateLimitMiddleware
from app.core.redis import close_redis_client
from app.observability.middleware import ObservabilityMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown hooks."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.APP_ENV}]")
    try:
        from app.rag.service import rag_service

        count = rag_service.index_processed_documents()
        logger.info(f"RAG vector store initialized with {count} document chunks.")
    except Exception as exc:
        logger.warning(f"RAG vector store initialization note: {exc}")

    try:
        from app.graph.ingestion import sync_knowledge_graph

        stats = sync_knowledge_graph()
        logger.info(f"Knowledge Graph initialized: {stats}")
    except Exception as exc:
        logger.warning(f"Knowledge Graph initialization note: {exc}")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME} resources...")
    await close_redis_client()
    await close_qdrant_client()
    await close_neo4j_driver()
    await engine.dispose()
    logger.info("All datastore connections gracefully terminated.")

OPENAPI_TAGS = [
    {
        "name": "System & Diagnostics",
        "description": "Platform capability discovery, runtime environment introspection, and low-latency ping probes.",
    },
    {
        "name": "Platform Health",
        "description": "Kubernetes-compatible liveness (/health), readiness (/ready), and version (/version) probes.",
    },
    {
        "name": "Flight Operations",
        "description": "Flight route search, pricing, status, and ML-driven ranking across GDS/NDC providers.",
    },
    {
        "name": "Bookings & Reservations",
        "description": "Transactional reservation management, passenger manifest creation, and booking state machine.",
    },
    {
        "name": "Production RAG",
        "description": "Grounded retrieval-augmented generation over airline policies, fare rules, and supplier guidelines.",
    },
    {
        "name": "Knowledge Graph",
        "description": "Neo4j multi-hop entity graph traversals, route topology, and schema lineage.",
    },
    {
        "name": "GraphRAG",
        "description": "Graph-fused intelligence combining vector similarity with knowledge graph topological extraction.",
    },
    {
        "name": "Travel Machine Learning",
        "description": "Gradient Boosted flight offer ranking and route fare anomaly surge/deal detection.",
    },
    {
        "name": "Agentic AI",
        "description": "Autonomous multi-agent orchestration, intent classification, memory sessions, and HITL safety.",
    },
    {
        "name": "AI Evaluation & Benchmarks",
        "description": "Systematic evaluation benchmarks for RAG quality, NDCG flight ranking, and agent safety.",
    },
    {
        "name": "Distributed Caching",
        "description": "Redis distributed cache metrics, telemetry, and tag-based atomic invalidation.",
    },
    {
        "name": "Security & Guardrails",
        "description": "Adversarial prompt injection detection, tool execution sandboxing, and security audit logs.",
    },
    {
        "name": "Observability",
        "description": "Prometheus metrics exposition endpoint (/metrics) for Grafana scraping.",
    },
]


def create_application() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    from app.security.middleware import SecurityHeadersMiddleware

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Production Agentic AI + RAG + GraphRAG + ML Travel Operations Platform",
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs" if settings.API_DOCS_ENABLED else None,
        redoc_url="/redoc" if settings.API_DOCS_ENABLED else None,
        openapi_url="/openapi.json" if settings.API_DOCS_ENABLED else None,
        lifespan=lifespan,
    )

    # Register Global Exception Handlers (RFC 7807 Problem Details)
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Security Defensive Headers & Input Inspection Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate Limiting Middleware
    app.add_middleware(RateLimitMiddleware)

    # Observability & Metrics Middleware (Captures correlation IDs & telemetry)
    app.add_middleware(ObservabilityMiddleware)

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root Level Health, Ready & Version endpoints
    app.include_router(health_router, prefix="", tags=["Platform Health"])

    # Root Level RAG query endpoint (POST /rag/query)
    app.include_router(rag_router, prefix="/rag", tags=["Production RAG"])

    # API v1 prefix endpoints
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Prometheus metrics exposition endpoint
    @app.get("/metrics", tags=["Observability"])
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_application()
