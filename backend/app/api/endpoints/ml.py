"""API endpoints for Machine Learning operations: flight search ranking and fare anomaly detection."""

import time

from fastapi import APIRouter, HTTPException, status

from app.ml.fare_intelligence import fare_intelligence
from app.ml.ranker import flight_ranker
from app.ml.schemas import (
    FareAnomalyRequest,
    FareAnomalyResponse,
    FlightRankRequest,
    FlightRankResponse,
)

router = APIRouter()


@router.post(
    "/rank-flights",
    response_model=FlightRankResponse,
    summary="Rank Flight Search Offers",
    description="Score and sort flight search offers using Gradient Boosted Learning-to-Rank with feature attribution breakdown.",
)
async def rank_flight_offers(request: FlightRankRequest) -> FlightRankResponse:
    start_time = time.perf_counter()
    try:
        ranked = flight_ranker.rank_flight_offers(
            offers=request.offers,
            preferences=request.preferences,
        )
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return FlightRankResponse(
            total_offers=len(ranked),
            ranked_offers=ranked,
            ranking_latency_ms=latency,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Flight ranking execution failed: {str(exc)}",
        ) from exc


@router.post(
    "/fare-anomaly",
    response_model=FareAnomalyResponse,
    summary="Assess Route Fare Price Anomaly",
    description="Evaluate whether a quoted flight fare is a deal, typical, or surge-priced against historical route distributions.",
)
async def assess_fare_anomaly(request: FareAnomalyRequest) -> FareAnomalyResponse:
    try:
        return fare_intelligence.evaluate_fare_anomaly(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fare anomaly assessment failed: {str(exc)}",
        ) from exc
