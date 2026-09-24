"""Health, readiness, and version API endpoints."""

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import check_database_connection
from app.core.neo4j import check_neo4j_connection
from app.core.qdrant import check_qdrant_connection
from app.core.redis import check_redis_connection
from app.schemas.health import HealthResponse, ReadyResponse, ServiceStatus, VersionResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns 200 if the FastAPI application process is alive and responding.",
)
async def get_health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC),
        version=settings.VERSION,
    )


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Application version information",
    description="Returns platform name, semantic version, and runtime environment.",
)
async def get_version() -> VersionResponse:
    return VersionResponse(
        name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.APP_ENV,
        status="operational",
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    description="Verifies end-to-end connectivity to PostgreSQL, Redis, Qdrant, and Neo4j.",
    responses={
        status.HTTP_200_OK: {"description": "All backend dependencies are connected."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "One or more dependencies are unreachable."
        },
    },
)
async def get_ready() -> JSONResponse:
    # Run all datastore checks in parallel
    results = await asyncio.gather(
        check_database_connection(),
        check_redis_connection(),
        check_qdrant_connection(),
        check_neo4j_connection(),
        return_exceptions=True,
    )

    services_data = {}
    names = ["postgres", "redis", "qdrant", "neo4j"]
    all_connected = True

    for name, res in zip(names, results, strict=True):
        if isinstance(res, Exception):
            services_data[name] = ServiceStatus(
                status="error",
                message=str(res),
            ).model_dump()
            all_connected = False
        elif isinstance(res, dict):
            status_val = res.get("status", "error")
            if status_val != "connected":
                all_connected = False
            services_data[name] = ServiceStatus(
                status=status_val,
                latency_ms=res.get("latency_ms"),
                message=res.get("message"),
            ).model_dump()
        else:
            all_connected = False
            services_data[name] = ServiceStatus(
                status="error",
                message="Unknown check failure",
            ).model_dump()

    response_payload = {
        "status": "ready" if all_connected else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "services": services_data,
    }

    http_status = status.HTTP_200_OK if all_connected else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=http_status, content=response_payload)
