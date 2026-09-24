"""Knowledge Graph API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.graph.ingestion import sync_knowledge_graph
from app.graph.models import BookingGraphContext, FlightGraphContext
from app.graph.service import graph_service

router = APIRouter()


class GraphSyncResponse(BaseModel):
    """Response model for graph synchronization."""

    status: str
    message: str
    entities_synced: dict[str, int]


@router.get(
    "/flight/{flight_number}",
    response_model=FlightGraphContext,
    summary="Get Flight Knowledge Subgraph",
    description="Traverse knowledge graph to retrieve multi-hop context for a flight including airline, airports, cities, country, fares, policies, and documents.",
)
async def get_flight_graph(flight_number: str):
    context = graph_service.get_flight_context(flight_number.upper())
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight '{flight_number}' not found in knowledge graph.",
        )
    return context


@router.get(
    "/airline/{airline_code}/policies",
    response_model=list[dict[str, Any]],
    summary="Get Airline Policies and Documents",
    description="Retrieve structured travel policies and linked documents for a given airline carrier code.",
)
async def get_airline_policies(
    airline_code: str,
    policy_type: str | None = Query(None, description="Optional filter e.g. CANCELLATION, BAGGAGE"),
):
    policies = graph_service.get_airline_policies(airline_code.upper(), policy_type=policy_type)
    return policies


@router.get(
    "/destination/{airport_code}/hotels",
    response_model=list[dict[str, Any]],
    summary="Get Destination Hotels by Airport Code",
    description="Traverse airport -> city -> hotel relationships to discover accommodations at the destination.",
)
async def get_destination_hotels(
    airport_code: str,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of hotels to return"),
):
    hotels = graph_service.get_destination_hotels(airport_code.upper(), limit=limit)
    return hotels


@router.get(
    "/booking/{booking_reference}",
    response_model=BookingGraphContext,
    summary="Get Booking Graph Context",
    description="Retrieve complete lineage, flight details, and applicable policies for a booking reservation.",
)
async def get_booking_graph(booking_reference: str):
    context = graph_service.get_booking_context(booking_reference.upper())
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking '{booking_reference}' not found in knowledge graph.",
        )
    return context


@router.post(
    "/sync",
    response_model=GraphSyncResponse,
    summary="Synchronize Knowledge Graph",
    description="Ingest airports, airlines, routes, hotels, suppliers, policies, fares, and bookings into the graph.",
)
async def sync_graph():
    try:
        stats = sync_knowledge_graph()
        return GraphSyncResponse(
            status="SUCCESS",
            message="Knowledge graph synchronization successfully completed.",
            entities_synced=stats,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph synchronization failed: {str(exc)}",
        ) from exc
