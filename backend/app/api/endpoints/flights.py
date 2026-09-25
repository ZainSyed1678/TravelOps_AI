"""Production Flight Operations REST API endpoints."""

import time
from datetime import date
from typing import Any

from fastapi import APIRouter, Query, status

from app.caching import cached
from app.core.api_response import ApiResponse, api_success
from app.ml.ranker import flight_ranker
from app.providers.factory import get_flight_provider
from app.providers.schemas import FlightSearchResponse, FlightStatusResponse
from app.schemas.travel import FlightSearchQuery

router = APIRouter()


@router.post(
    "/search",
    response_model=ApiResponse[FlightSearchResponse],
    status_code=status.HTTP_200_OK,
    summary="Search & ML-Rank Flight Offers",
    description="Search real-time flight offers across integrated GDS/NDC providers and rank them using the TravelOps Gradient Boosted ranking engine.",
)
async def search_flights(query: FlightSearchQuery) -> ApiResponse[FlightSearchResponse]:
    """Search and rank available flight options."""
    start_time = time.perf_counter()
    provider = get_flight_provider()

    raw_response = await provider.search_flights(query)

    # Apply ML ranking if offers are available
    if raw_response.offers:
        from app.ml.schemas import UserPreferences

        prefs = UserPreferences(
            preferred_airline="EK" if "DXB" in (query.origin, query.destination) else "AI",
            prefer_nonstop=query.max_stops == 0 if query.max_stops is not None else False,
        )
        ranked = flight_ranker.rank_flight_offers(raw_response.offers, preferences=prefs)
        for r in ranked:
            r.offer.raw_metadata["ml_rank"] = r.rank
            r.offer.raw_metadata["ml_score"] = r.score
        raw_response.offers = [r.offer for r in ranked]

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    raw_response.latency_ms = duration_ms

    return api_success(
        data=raw_response,
        message=f"Retrieved {len(raw_response.offers)} flight offers for route {query.origin}->{query.destination}",
        total=len(raw_response.offers),
        execution_time_ms=duration_ms,
        extra_meta={
            "provider_source": raw_response.provider_source,
            "origin": query.origin,
            "destination": query.destination,
            "departure_date": query.departure_date.isoformat(),
        },
    )


@router.get(
    "/routes",
    response_model=ApiResponse[list[dict[str, Any]]],
    summary="List Major Flight Routes",
    description="Retrieve available flight routes with carrier coverage, typical duration, and service frequencies.",
)
@cached(ttl_seconds=600, namespace="travelops:routes", tags=["flight_routes"])
async def list_routes() -> ApiResponse[list[dict[str, Any]]]:
    """List major served airline routes."""
    routes = [
        {
            "route_code": "DEL-BOM",
            "origin": "DEL",
            "destination": "BOM",
            "origin_name": "Indira Gandhi International Airport, Delhi",
            "destination_name": "Chhatrapati Shivaji Maharaj International Airport, Mumbai",
            "distance_km": 1148,
            "typical_duration_min": 130,
            "carriers": ["AI", "6E", "UK"],
            "daily_flights": 42,
        },
        {
            "route_code": "BOM-DXB",
            "origin": "BOM",
            "destination": "DXB",
            "origin_name": "Chhatrapati Shivaji Maharaj International Airport, Mumbai",
            "destination_name": "Dubai International Airport, Dubai",
            "distance_km": 1928,
            "typical_duration_min": 210,
            "carriers": ["EK", "AI", "6E", "FZ"],
            "daily_flights": 18,
        },
        {
            "route_code": "DEL-LHR",
            "origin": "DEL",
            "destination": "LHR",
            "origin_name": "Indira Gandhi International Airport, Delhi",
            "destination_name": "London Heathrow Airport, London",
            "distance_km": 6710,
            "typical_duration_min": 560,
            "carriers": ["AI", "BA", "VS"],
            "daily_flights": 8,
        },
        {
            "route_code": "BLR-DEL",
            "origin": "BLR",
            "destination": "DEL",
            "origin_name": "Kempegowda International Airport, Bengaluru",
            "destination_name": "Indira Gandhi International Airport, Delhi",
            "distance_km": 1740,
            "typical_duration_min": 165,
            "carriers": ["AI", "6E", "UK", "QP"],
            "daily_flights": 35,
        },
    ]
    return api_success(
        data=routes,
        message="Flight routes retrieved successfully",
        total=len(routes),
    )


@router.get(
    "/status/{flight_number}",
    response_model=ApiResponse[FlightStatusResponse],
    summary="Get Real-Time Flight Status",
    description="Retrieve live operational departure, arrival, gate, and disruption delay information.",
)
async def get_flight_status(
    flight_number: str,
    departure_date: date = Query(default_factory=date.today, description="Flight departure date"),
) -> ApiResponse[FlightStatusResponse]:
    """Retrieve operational status for a specific flight."""
    provider = get_flight_provider()
    status_res = await provider.get_flight_status(flight_number, departure_date)
    return api_success(
        data=status_res,
        message=f"Operational status for flight {flight_number}: {status_res.status}",
    )
