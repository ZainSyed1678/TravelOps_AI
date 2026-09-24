"""FastAPI application factory and main entry point for TravelOps AI."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.api_v1.api import api_router
from app.api.endpoints.health import router as health_router
from app.api.endpoints.rag import router as rag_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import logger
from app.core.neo4j import close_neo4j_driver
from app.core.qdrant import close_qdrant_client
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

    # Observability & Metrics Middleware
    app.add_middleware(ObservabilityMiddleware)

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
