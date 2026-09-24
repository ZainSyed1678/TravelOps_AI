"""Machine Learning module for flight search ranking, feature engineering, and fare intelligence."""

from app.ml.fare_intelligence import FareIntelligenceService, fare_intelligence
from app.ml.features import FlightFeatureExtractor, feature_extractor
from app.ml.ranker import FlightRanker, flight_ranker
from app.ml.schemas import (
    FareAnomalyRequest,
    FareAnomalyResponse,
    FeatureImpact,
    FlightRankRequest,
    FlightRankResponse,
    RankedFlightOffer,
    UserPreferences,
)

__all__ = [
    "FlightFeatureExtractor",
    "feature_extractor",
    "FlightRanker",
    "flight_ranker",
    "FareIntelligenceService",
    "fare_intelligence",
    "FlightRankRequest",
    "FlightRankResponse",
    "RankedFlightOffer",
    "FeatureImpact",
    "UserPreferences",
    "FareAnomalyRequest",
    "FareAnomalyResponse",
]
