"""Document models and metadata structures for TravelOps AI data ingestion."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


class DocumentType(StrEnum):
    """Supported travel domain document categories."""

    AIRPORT_DATA = "AIRPORT_DATA"
    AIRLINE_DATA = "AIRLINE_DATA"
    FLIGHT_ROUTE = "FLIGHT_ROUTE"
    HOTEL_DATA = "HOTEL_DATA"
    TRAVEL_POLICY = "TRAVEL_POLICY"
    FARE_RULE = "FARE_RULE"
    NDC_DOCUMENTATION = "NDC_DOCUMENTATION"
    SUPPLIER_API_DOC = "SUPPLIER_API_DOC"


class IngestedDocument(BaseModel):
    """Canonical document representation with complete lineage and audit provenance."""

    document_id: str = Field(..., description="Unique deterministic or generated document ID")
    source: str = Field(..., description="Source origin (filename, API name, or supplier)")
    source_url: str = Field(..., description="URI or filesystem path of source document")
    version: str = Field(default="1.0", description="Document revision version")
    hash: str = Field(..., description="SHA-256 checksum of raw document payload")
    created_at: datetime = Field(default_factory=utc_now, description="Initial ingestion timestamp")
    updated_at: datetime = Field(default_factory=utc_now, description="Last update timestamp")
    document_type: DocumentType = Field(..., description="Classification category")
    title: str = Field(..., description="Human-readable title")
    content: str = Field(..., description="Cleaned, extracted text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Domain-specific attributes")
    raw_data: Any | None = Field(default=None, description="Original parsed structured data")


class IngestionResult(BaseModel):
    """Outcome report for an ingestion execution."""

    document_id: str
    source: str
    document_type: DocumentType
    status: str = Field(..., description="INGESTED, SKIPPED, or FAILED")
    hash: str
    message: str
    records_count: int = 0
    duration_ms: float = 0.0


class IngestionManifest(BaseModel):
    """Persistent catalog tracking ingested documents and their hashes for idempotency."""

    version: str = "1.0"
    last_updated: datetime = Field(default_factory=utc_now)
    documents: dict[str, dict[str, Any]] = Field(default_factory=dict)
