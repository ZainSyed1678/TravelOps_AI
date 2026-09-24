"""API v1 router registry."""

from fastapi import APIRouter

from app.api.endpoints import health, rag

api_router = APIRouter()

# Health and diagnostics
api_router.include_router(health.router, tags=["Health & Diagnostics"])

# RAG Knowledge Retrieval
api_router.include_router(rag.router, prefix="/rag", tags=["Production RAG"])
