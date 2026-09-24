"""FastAPI application factory and main entry point for TravelOps AI."""

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.api.api_v1.api import api_router
from app.api.endpoints.health import router as health_router
from app.api.endpoints.rag import router as rag_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import logger
from app.core.neo4j import close_neo4j_driver
from app.core.qdrant import close_qdrant_client
from app.core.redis import close_redis_client

# Prometheus core metrics
REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)


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
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME} resources...")
    await close_redis_client()
    await close_qdrant_client()
    await close_neo4j_driver()
    await engine.dispose()
    logger.info("All datastore connections gracefully terminated.")


def create_application() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Production Agentic AI + RAG + GraphRAG + ML Travel Operations Platform",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Correlation ID & Metrics Middleware
    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            response.headers["X-Request-ID"] = correlation_id
            response.headers["X-Response-Time-Ms"] = str(round(duration * 1000, 2))

            # Record metrics
            endpoint = request.url.path
            REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=endpoint,
                status=str(response.status_code),
            ).inc()
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(duration)

            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({round(duration * 1000, 2)}ms)"
            )
            return response
        except Exception as exc:
            duration = time.perf_counter() - start_time
            logger.error(
                f"Unhandled error processing {request.method} {request.url.path}: {exc}",
                exc_info=True,
            )
            REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=request.url.path,
                status="500",
            ).inc()
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "detail": "An unexpected error occurred. Please contact system administrator.",
                    "correlation_id": correlation_id,
                },
                headers={"X-Request-ID": correlation_id},
            )

    # Root Level Health, Ready & Version endpoints
    app.include_router(health_router, prefix="", tags=["Platform Health"])

    # Root Level RAG query endpoint (POST /rag/query)
    app.include_router(rag_router, prefix="/rag", tags=["Production RAG"])

    # API v1 prefix endpoints
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Prometheus metrics endpoint
    @app.get("/metrics", tags=["Observability"])
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_application()
