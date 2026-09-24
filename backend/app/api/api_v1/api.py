"""API v1 router registry."""

from fastapi import APIRouter

from app.api.endpoints import health

api_router = APIRouter()

# Health and diagnostics
api_router.include_router(health.router, tags=["Health & Diagnostics"])
