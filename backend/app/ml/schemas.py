"""Pydantic schemas and DTOs for Travel ML models, ranking, and fare intelligence."""

from pydantic import BaseModel, Field

from app.providers.schemas import ProviderFlightOffer


class FeatureImpact(BaseModel):
    """Impact of an engineered feature on the flight's ranking score."""

    feature: str
    impact: float = Field(..., description="Signed contribution to score (positive or negative)")
    explanation: str = Field(..., description="Human-readable reason for score adjustment")


class UserPreferences(BaseModel):
    """Traveler preferences used to calibrate the ranking model."""

    price_sensitivity: float = Field(1.0, ge=0.0, le=2.0, description="Weight multiplier for fare price")
    duration_sensitivity: float = Field(1.0, ge=0.0, le=2.0, description="Weight multiplier for flight duration")
    preferred_airline: str | None = Field(None, description="Preferred airline carrier code e.g. EK, AI")
    prefer_nonstop: bool = Field(True, description="Strict preference for direct flights")


class FlightRankRequest(BaseModel):
    """Request payload for ranking flight offers."""

    offers: list[ProviderFlightOffer]
    preferences: UserPreferences | None = None


class RankedFlightOffer(BaseModel):
    """A scored and ranked flight offer with explainability details."""

    rank: int
    score: float = Field(..., description="Normalized utility score between 0.0 and 100.0")
    offer: ProviderFlightOffer
    score_breakdown: list[FeatureImpact] = Field(default_factory=list)


class FlightRankResponse(BaseModel):
    """Response payload containing ranked flights."""

    total_offers: int
    ranked_offers: list[RankedFlightOffer]
    ranking_latency_ms: float


class FareAnomalyRequest(BaseModel):
    """Request payload to assess fare price anomaly for a route."""

    origin: str = Field(..., min_length=3, max_length=3, description="Origin airport IATA code")
    destination: str = Field(..., min_length=3, max_length=3, description="Destination airport IATA code")
    airline: str | None = Field(None, description="Airline carrier code")
    fare_amount: float = Field(..., gt=0, description="Current quoted fare price")
    currency: str = Field("INR", description="Currency code")
    cabin_class: str = Field("ECONOMY", description="Cabin class e.g. ECONOMY, BUSINESS")


class FareAnomalyResponse(BaseModel):
    """Response payload detailing fare anomaly evaluation and pricing recommendations."""

    route: str
    fare_amount: float
    currency: str
    classification: str = Field(..., description="DEAL, NORMAL, or SURGE")
    historical_median: float
    historical_min: float
    historical_max: float
    percentage_difference: float = Field(..., description="Percentage above (+) or below (-) median")
    recommendation: str
    confidence: float = 1.0
