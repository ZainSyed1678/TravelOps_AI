"""Health, readiness, and version schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    status: str = Field(..., description="Service connection status: connected or error")
    latency_ms: float | None = Field(None, description="Check round-trip latency in milliseconds")
    message: str | None = Field(None, description="Detailed diagnostic message")


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Application liveness status")
    timestamp: datetime = Field(..., description="Timestamp of health check")
    version: str = Field(..., description="Application semantic version")


class ReadyResponse(BaseModel):
    status: str = Field(..., description="Readiness status: ready or degraded")
    timestamp: datetime = Field(..., description="Timestamp of readiness check")
    services: dict[str, ServiceStatus] = Field(
        ..., description="Connection status of backing datastores"
    )


class VersionResponse(BaseModel):
    name: str = Field(..., description="Platform name")
    version: str = Field(..., description="Semantic version")
    environment: str = Field(..., description="Deployment environment")
    status: str = Field(default="operational", description="System operational state")
