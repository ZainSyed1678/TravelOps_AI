"""Comprehensive test suite for Phase 7: Travel ML (Flight Ranking and Fare Anomaly Detection)."""

import datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.ml.fare_intelligence import fare_intelligence
from app.ml.features import feature_extractor
from app.ml.ranker import flight_ranker
from app.ml.schemas import FareAnomalyRequest, UserPreferences
from app.providers.schemas import ProviderFlightOffer


@pytest.fixture
def sample_flight_offers():
    """Build a realistic set of flight offers for testing ranking."""
    now = datetime.datetime(2026, 10, 15, 9, 30)

    # 1. Ideal Flight: Non-stop, morning departure, top-tier carrier, competitive price
    offer_ideal = ProviderFlightOffer(
        id="offer-ideal-01",
        provider_name="MOCK",
        flight_number="EK505",
        airline_code="EK",
        airline_name="Emirates",
        origin_airport="BOM",
        destination_airport="DXB",
        departure_time=now.replace(hour=9, minute=30),
        arrival_time=now.replace(hour=13, minute=0),
        duration_minutes=210,
        stops=0,
        aircraft_type="B777",
        cabin_class="ECONOMY",
        base_fare=16000.0,
        taxes=2500.0,
        total_price=18500.0,
        currency="INR",
        is_refundable=True,
    )

    # 2. Medium Flight: Non-stop, redeye departure (03:15 AM), mid-tier carrier, higher price
    offer_redeye = ProviderFlightOffer(
        id="offer-redeye-02",
        provider_name="MOCK",
        flight_number="AI915",
        airline_code="AI",
        airline_name="Air India",
        origin_airport="BOM",
        destination_airport="DXB",
        departure_time=now.replace(hour=3, minute=15),
        arrival_time=now.replace(hour=7, minute=0),
        duration_minutes=225,
        stops=0,
        aircraft_type="A321",
        cabin_class="ECONOMY",
        base_fare=20000.0,
        taxes=2500.0,
        total_price=22500.0,
        currency="INR",
        is_refundable=False,
    )

    # 3. Poor Flight: 1-stop, long duration, expensive
    offer_poor = ProviderFlightOffer(
        id="offer-poor-03",
        provider_name="MOCK",
        flight_number="6E1451",
        airline_code="6E",
        airline_name="IndiGo",
        origin_airport="BOM",
        destination_airport="DXB",
        departure_time=now.replace(hour=1, minute=0),
        arrival_time=now.replace(hour=8, minute=0),
        duration_minutes=420,
        stops=1,
        aircraft_type="A320",
        cabin_class="ECONOMY",
        base_fare=26000.0,
        taxes=3000.0,
        total_price=29000.0,
        currency="INR",
        is_refundable=False,
    )

    return [offer_ideal, offer_redeye, offer_poor]


def test_flight_feature_extraction(sample_flight_offers):
    """Verify feature extractor extracts valid numerical signals."""
    ideal = sample_flight_offers[0]
    features = feature_extractor.extract_features(
        offer=ideal,
        route_median_price=20000.0,
        route_min_duration=210,
    )

    assert len(features) == len(feature_extractor.FEATURE_NAMES)
    # price_ratio: 18500 / 20000 = 0.925
    assert abs(features[0] - 0.925) < 0.01
    # duration_ratio: 210 / 210 = 1.0
    assert abs(features[1] - 1.0) < 0.01
    # stops: 0
    assert features[2] == 0.0
    # departure convenience: morning (09:30) is 1.0
    assert abs(features[3] - 1.0) < 0.01
    # airline reputation: EK is 0.92
    assert abs(features[5] - 0.92) < 0.01
    # is_refundable: 1.0
    assert abs(features[6] - 1.0) < 0.01


def test_flight_ranking_ordering_and_attribution(sample_flight_offers):
    """Verify that ideal flight ranks #1 and score attribution explains why."""
    ranked = flight_ranker.rank_flight_offers(sample_flight_offers)

    assert len(ranked) == 3
    assert ranked[0].offer.id == "offer-ideal-01"
    assert ranked[0].rank == 1
    assert ranked[0].score > ranked[1].score > ranked[2].score

    # Check score breakdown on #1 offer
    breakdown = ranked[0].score_breakdown
    assert len(breakdown) > 0
    features_cited = {b.feature for b in breakdown}
    assert "Stops" in features_cited
    assert "Fare Price" in features_cited


def test_user_preference_calibration(sample_flight_offers):
    """Verify user preferences dynamically calibrate ranking scores."""
    # When user explicitly prefers Air India, AI offer receives a preference boost
    prefs = UserPreferences(preferred_airline="AI", prefer_nonstop=True)
    ranked = flight_ranker.rank_flight_offers(sample_flight_offers, preferences=prefs)

    ai_offer = next(r for r in ranked if r.offer.airline_code == "AI")
    assert any(b.feature == "Preferred Carrier" for b in ai_offer.score_breakdown)


def test_fare_anomaly_deal_classification():
    """Verify low fare on BOM-DXB is detected as a DEAL."""
    req = FareAnomalyRequest(
        origin="BOM",
        destination="DXB",
        fare_amount=15500.0,
        currency="INR",
        cabin_class="ECONOMY",
    )
    resp = fare_intelligence.evaluate_fare_anomaly(req)

    assert resp.route == "BOM-DXB"
    assert resp.classification == "DEAL"
    assert resp.percentage_difference < -10.0
    assert "Deal" in resp.recommendation


def test_fare_anomaly_surge_classification():
    """Verify high fare on BOM-DXB is detected as SURGE."""
    req = FareAnomalyRequest(
        origin="BOM",
        destination="DXB",
        fare_amount=32000.0,
        currency="INR",
        cabin_class="ECONOMY",
    )
    resp = fare_intelligence.evaluate_fare_anomaly(req)

    assert resp.route == "BOM-DXB"
    assert resp.classification == "SURGE"
    assert resp.percentage_difference > 15.0
    assert "Surge" in resp.recommendation


def test_fare_anomaly_normal_classification():
    """Verify typical fare on BOM-DXB is classified as NORMAL."""
    req = FareAnomalyRequest(
        origin="BOM",
        destination="DXB",
        fare_amount=21000.0,
        currency="INR",
        cabin_class="ECONOMY",
    )
    resp = fare_intelligence.evaluate_fare_anomaly(req)

    assert resp.route == "BOM-DXB"
    assert resp.classification == "NORMAL"
    assert abs(resp.percentage_difference) < 15.0


@pytest.mark.asyncio
async def test_ml_api_rank_and_anomaly_endpoints(sample_flight_offers):
    """Verify HTTP API endpoints for /ml/rank-flights and /ml/fare-anomaly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Rank Flights Endpoint
        payload = {
            "offers": [o.model_dump(mode="json") for o in sample_flight_offers],
            "preferences": {"prefer_nonstop": True},
        }
        res_rank = await client.post("/api/v1/ml/rank-flights", json=payload)
        assert res_rank.status_code == 200
        rank_data = res_rank.json()
        assert rank_data["total_offers"] == 3
        assert len(rank_data["ranked_offers"]) == 3
        assert rank_data["ranked_offers"][0]["rank"] == 1
        assert rank_data["ranking_latency_ms"] >= 0

        # 2. Fare Anomaly Endpoint
        anomaly_payload = {
            "origin": "BOM",
            "destination": "DXB",
            "fare_amount": 16000.0,
            "currency": "INR",
            "cabin_class": "ECONOMY",
        }
        res_anom = await client.post("/api/v1/ml/fare-anomaly", json=anomaly_payload)
        assert res_anom.status_code == 200
        anom_data = res_anom.json()
        assert anom_data["classification"] == "DEAL"
        assert "recommendation" in anom_data
