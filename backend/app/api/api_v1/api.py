"""API v1 router registry."""

from fastapi import APIRouter

from app.api.endpoints import agents, evaluation, graph, graphrag, health, ml, rag
from app.caching.router import router as cache_router

api_router = APIRouter()

# Health and diagnostics
api_router.include_router(health.router, tags=["Health & Diagnostics"])

# RAG Knowledge Retrieval
api_router.include_router(rag.router, prefix="/rag", tags=["Production RAG"])

# Neo4j Knowledge Graph & Lineage
api_router.include_router(graph.router, prefix="/graph", tags=["Knowledge Graph"])

# GraphRAG Intelligence Fusion
api_router.include_router(graphrag.router, prefix="/graphrag", tags=["GraphRAG"])

# Machine Learning & Ranking
api_router.include_router(ml.router, prefix="/ml", tags=["Travel Machine Learning"])

# Agentic AI Workflows
api_router.include_router(agents.router, prefix="/agents", tags=["Agentic AI"])

# Evaluation & Benchmark Suite
api_router.include_router(evaluation.router, prefix="/eval", tags=["AI Evaluation & Benchmarks"])

# Caching Diagnostics & Invalidation
api_router.include_router(cache_router, prefix="/cache", tags=["Distributed Caching"])
