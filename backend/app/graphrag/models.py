"""Data models and schemas for GraphRAG (Graph-guided Retrieval-Augmented Generation)."""

from typing import Any

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    """Travel domain entity recognized from natural language query."""

    entity_type: str  # FLIGHT, AIRLINE, AIRPORT, CITY, BOOKING_REF, POLICY_TYPE
    value: str
    confidence: float = 1.0
    normalized_id: str | None = None


class RetrievedChunk(BaseModel):
    """Retrieved document chunk with score and provenance."""

    chunk_id: str
    document_id: str
    source: str
    content: str
    score: float = 0.0
    section_title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphFact(BaseModel):
    """Structured relationship triple extracted from Knowledge Graph traversal."""

    subject: str
    subject_type: str
    predicate: str
    object: str
    object_type: str
    properties: dict[str, Any] = Field(default_factory=dict)

    def to_readable_sentence(self) -> str:
        """Convert triple to human-readable sentence for prompt context."""
        pred = self.predicate.replace("_", " ").lower()
        if self.predicate == "OPERATES":
            return f"Airline {self.subject} operates flight {self.object}."
        elif self.predicate == "DEPARTS_FROM":
            return f"Flight {self.subject} departs from {self.object}."
        elif self.predicate == "ARRIVES_AT":
            return f"Flight {self.subject} arrives at {self.object}."
        elif self.predicate == "LOCATED_IN":
            return f"{self.subject} ({self.subject_type}) is located in {self.object} ({self.object_type})."
        elif self.predicate == "HAS_POLICY":
            return f"{self.subject_type} {self.subject} has policy {self.object}."
        elif self.predicate == "HAS_FARE":
            fare_basis = self.properties.get("fare_basis", "")
            refund = "refundable" if self.properties.get("refundable") else "non-refundable"
            fee = self.properties.get("cancellation_fee", 0.0)
            return (
                f"Flight {self.subject} offers fare {self.object} (Basis: {fare_basis}, "
                f"Status: {refund}, Cancellation Fee: {fee})."
            )
        elif self.predicate == "FOR_FLIGHT":
            return f"Booking {self.subject} is reserved for flight {self.object}."
        elif self.predicate == "PROVIDES":
            return f"Supplier {self.subject} provides inventory for flight {self.object}."
        return f"{self.subject} {pred} {self.object}."


class FusedContext(BaseModel):
    """Combined context containing structured graph facts and unstructured text chunks."""

    graph_facts: list[GraphFact] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    extracted_entities: list[ExtractedEntity] = Field(default_factory=list)
    formatted_prompt_context: str = ""


class GraphRAGRequest(BaseModel):
    """Request payload for GraphRAG query."""

    query: str
    airline: str | None = None
    flight_number: str | None = None
    booking_reference: str | None = None
    policy_type: str | None = None
    top_k: int = Field(5, ge=1, le=20)
    score_threshold: float = Field(0.0, ge=0.0, le=1.0)


class GraphRAGExplanation(BaseModel):
    """Detailed diagnostic explanation of GraphRAG retrieval and fusion."""

    query: str
    extracted_entities: list[ExtractedEntity]
    graph_facts_count: int
    graph_facts: list[GraphFact]
    vector_chunks_count: int
    vector_chunks: list[dict[str, Any]]
    entity_filters_applied: dict[str, Any]
    retrieval_latency_ms: float
    total_latency_ms: float


class GraphRAGResponse(BaseModel):
    """Response payload for GraphRAG query."""

    query: str
    answer: str
    graph_facts: list[GraphFact] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[ExtractedEntity] = Field(default_factory=list)
    retrieval_latency_ms: float
    total_latency_ms: float
