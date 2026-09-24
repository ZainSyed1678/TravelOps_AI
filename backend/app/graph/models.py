"""Graph entity definitions and relationship models for Neo4j Knowledge Graph."""

from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """Base graph node."""

    id: str
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    """Directed graph relationship between two entities."""

    source_id: str
    source_label: str
    target_id: str
    target_label: str
    rel_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class FlightGraphContext(BaseModel):
    """Contextual graph subgraph for a flight."""

    flight_number: str
    airline: dict[str, Any]
    origin_airport: dict[str, Any]
    origin_city: dict[str, Any]
    destination_airport: dict[str, Any]
    destination_city: dict[str, Any]
    destination_country: dict[str, Any]
    fares: list[dict[str, Any]] = Field(default_factory=list)
    policies: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)


class BookingGraphContext(BaseModel):
    """Contextual graph lineage for a booking reference."""

    booking_reference: str
    status: str
    flight: dict[str, Any] | None = None
    airline: dict[str, Any] | None = None
    origin: dict[str, Any] | None = None
    destination: dict[str, Any] | None = None
    applicable_policies: list[dict[str, Any]] = Field(default_factory=list)
    policy_documents: list[dict[str, Any]] = Field(default_factory=list)
