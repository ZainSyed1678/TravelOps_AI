"""API endpoints for GraphRAG operations."""

from fastapi import APIRouter, HTTPException, status

from app.graphrag.models import GraphRAGExplanation, GraphRAGRequest, GraphRAGResponse
from app.graphrag.service import graphrag_service

router = APIRouter()


@router.post(
    "/query",
    response_model=GraphRAGResponse,
    summary="Query TravelOps GraphRAG",
    description="Query knowledge graph entities fused with dense vector retrieval for high-precision, grounded travel intelligence.",
)
async def query_graphrag(request: GraphRAGRequest) -> GraphRAGResponse:
    try:
        return graphrag_service.query(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GraphRAG query execution failed: {str(exc)}",
        ) from exc


@router.post(
    "/explain",
    response_model=GraphRAGExplanation,
    summary="Explain GraphRAG Retrieval Breakdown",
    description="Inspect the extracted travel entities, structural knowledge graph facts, and retrieved vector chunks before synthesis.",
)
async def explain_graphrag(request: GraphRAGRequest) -> GraphRAGExplanation:
    try:
        return graphrag_service.explain(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GraphRAG explanation failed: {str(exc)}",
        ) from exc
