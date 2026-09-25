"""System information and operational status endpoints."""

import sys
import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.api_response import ApiResponse, api_success
from app.core.config import settings

router = APIRouter()
START_TIME = time.time()


class SystemInfoData(BaseModel):
    """System capability and environment metadata."""

    project_name: str = Field(..., description="Platform project name")
    version: str = Field(..., description="Semantic version string")
    environment: str = Field(..., description="Deployment environment")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    python_version: str = Field(..., description="Python runtime version")
    rate_limiting_enabled: bool = Field(..., description="Whether rate limiting middleware is active")
    caching_enabled: bool = Field(..., description="Whether distributed caching layer is active")
    enabled_modules: list[str] = Field(..., description="List of enabled operational modules")
    datastores: dict[str, str] = Field(..., description="Configured datastore connections")


@router.get(
    "/info",
    response_model=ApiResponse[SystemInfoData],
    summary="Get System Capabilities & Status",
    description="Retrieve comprehensive platform information, runtime environment, datastore configs, and enabled capabilities.",
)
async def get_system_info() -> ApiResponse[SystemInfoData]:
    """Retrieve system information and operational status."""
    uptime = round(time.time() - START_TIME, 2)
    info = SystemInfoData(
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.APP_ENV,
        uptime_seconds=uptime,
        python_version=sys.version.split()[0],
        rate_limiting_enabled=settings.RATE_LIMIT_ENABLED,
        caching_enabled=True,
        enabled_modules=[
            "Data Ingestion & Extraction",
            "Production RAG",
            "Neo4j Knowledge Graph",
            "GraphRAG Intelligence Fusion",
            "Travel Machine Learning (Ranker & Anomaly)",
            "LangGraph Agentic Orchestrator",
            "Human-in-the-Loop Safety Barrier",
            "Dual-Tier Agent Memory",
            "Prometheus & Grafana Observability",
            "Distributed Caching Layer",
            "Production API (OpenAPI 3.1 & RFC 7807)",
        ],
        datastores={
            "postgresql": f"{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}",
            "redis": f"{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            "qdrant": f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
            "neo4j": settings.NEO4J_URI,
        },
    )
    return api_success(data=info, message="System operational status retrieved successfully")


@router.get(
    "/ping",
    summary="Fast Ping Probe",
    description="Ultra low-latency ping endpoint for ingress gateways and synthetic probes.",
)
async def ping() -> dict[str, Any]:
    """Instant health check probe."""
    return {"ping": "pong", "timestamp": time.time()}
