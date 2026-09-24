"""RAG data models, chunks, and query schemas."""

from typing import Any

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Structure-aware document chunk for vector indexing and citation."""

    chunk_id: str = Field(..., description="Unique chunk identifier e.g. doc-123#c0")
    document_id: str = Field(..., description="Parent document identifier")
    source: str = Field(..., description="Source filename or URI")
    content: str = Field(..., description="Chunk text content")
    page: int | None = Field(None, description="Page number if applicable")
    section: str | None = Field(None, description="Section header or title")
    document_type: str = Field(..., description="Document category")
    airline: str | None = Field(None, description="Airline code e.g. EK, AI")
    supplier: str | None = Field(None, description="Supplier code e.g. AMADEUS")
    policy_type: str | None = Field(None, description="Policy category e.g. CANCELLATION")
    effective_date: str | None = Field(None, description="Effective date ISO string")
    version: str = Field(default="1.0", description="Document version")
    char_count: int = Field(default=0, description="Character count")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class RAGQueryRequest(BaseModel):
    """Request payload for RAG retrieval and question answering."""

    query: str = Field(..., min_length=2, description="User question or query")
    airline: str | None = Field(None, description="Optional airline filter (e.g. EK, AI)")
    supplier: str | None = Field(None, description="Optional supplier filter")
    policy_type: str | None = Field(
        None, description="Optional policy type filter (e.g. CANCELLATION, BAGGAGE)"
    )
    document_type: str | None = Field(None, description="Optional document type filter")
    top_k: int = Field(default=4, ge=1, le=20, description="Number of chunks to retrieve")
    score_threshold: float | None = Field(
        default=0.2, ge=0.0, le=1.0, description="Minimum relevance threshold"
    )


class RAGCitation(BaseModel):
    """Provenance citation linking answer claims to source documents."""

    document: str = Field(..., description="Source document name or URL")
    page: int | None = Field(None, description="Source page number")
    section: str | None = Field(None, description="Section heading")
    relevance_score: float = Field(..., description="Retrieval / reranker relevance score")
    snippet: str | None = Field(None, description="Excerpt snippet text")


class RAGQueryResponse(BaseModel):
    """Grounded RAG answer with citations and timing observability."""

    answer: str = Field(..., description="Grounded answer text generated from citations")
    sources: list[RAGCitation] = Field(
        default_factory=list, description="Citations supporting the answer"
    )
    confidence_score: float = Field(default=1.0, description="Confidence assessment score")
    retrieval_latency_ms: float = Field(default=0.0, description="Vector retrieval duration in ms")
    total_latency_ms: float = Field(default=0.0, description="Total pipeline latency in ms")
