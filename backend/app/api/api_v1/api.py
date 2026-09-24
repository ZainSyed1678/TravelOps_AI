"""API v1 router registry."""

from fastapi import APIRouter

from app.api.endpoints import graph, health, rag

api_router = APIRouter()

# Health and diagnostics
api_router.include_router(health.router, tags=["Health & Diagnostics"])

# RAG Knowledge Retrieval
api_router.include_router(rag.router, prefix="/rag", tags=["Production RAG"])

# Neo4j Knowledge Graph & Lineage
api_router.include_router(graph.router, prefix="/graph", tags=["Knowledge Graph"])
