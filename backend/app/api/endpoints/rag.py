"""RAG query and indexing API endpoints."""

from fastapi import APIRouter, status

from app.rag.models import RAGQueryRequest, RAGQueryResponse
from app.rag.service import rag_service

router = APIRouter()


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute grounded travel policy and documentation RAG query",
    description="Retrieves relevant policy rules from Qdrant vector store, reranks with context deduplication, and generates an answer strictly grounded on citations.",
)
async def query_rag(request: RAGQueryRequest) -> RAGQueryResponse:
    """Handle natural language travel policy queries."""
    return rag_service.query(request)


@router.post(
    "/index",
    summary="Index processed documents into vector store",
    description="Loads documents from data/processed/, chunks them, and upserts dense vector embeddings into Qdrant.",
)
async def index_documents() -> dict:
    """Trigger manual vector store re-indexing."""
    count = rag_service.index_processed_documents()
    return {
        "status": "success",
        "indexed_chunks": count,
        "message": f"Successfully indexed {count} chunks into Qdrant.",
    }
