"""Tests for Travel Provider Abstraction Layer (Mocks, Amadeus Adapter, Normalization, Factory)."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from app.providers.amadeus.client import AmadeusClient
from app.providers.amadeus.flight_provider import AmadeusFlightProvider, parse_iso_duration
from app.providers.exceptions import (
    ProviderAuthenticationException,
    ProviderInventoryUnavailableException,
    ProviderValidationException,
)
from app.providers.factory import (
    get_booking_provider,
    get_flight_provider,
    get_hotel_provider,
)
from app.providers.mock.mock_booking_provider import MockBookingProvider
from app.providers.mock.mock_flight_provider import MockFlightProvider
from app.providers.mock.mock_hotel_provider import MockHotelProvider
from app.providers.schemas import ProviderBookingRequest
from app.schemas.travel import FlightSearchQuery, HotelSearchQuery

# ==============================================================================
# MockFlightProvider Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_mock_flight_provider_search():
    """Test flight search on BOM -> DXB route."""
    provider = MockFlightProvider()
    dep_date = date.today() + timedelta(days=7)
    query = FlightSearchQuery(
        origin="BOM",
        destination="DXB",
        departure_date=dep_date,
        adults=2,
    )

    response = await provider.search_flights(query)
    assert response.provider_source == "MOCK_GDS"
    assert response.total_offers >= 3
    assert any(o.flight_number == "EK505" for o in response.offers)
    assert any(o.flight_number == "AI915" for o in response.offers)

    # Verify passenger multiplication for 2 adults
    ek_offer = next(o for o in response.offers if o.flight_number == "EK505")
    assert ek_offer.total_price == 18500.0 * 2
    assert ek_offer.origin_airport == "BOM"
    assert ek_offer.destination_airport == "DXB"


@pytest.mark.asyncio
async def test_mock_flight_provider_budget_filtering():
    """Test flight search max budget filtering."""
    provider = MockFlightProvider()
    dep_date = date.today() + timedelta(days=7)
    query = FlightSearchQuery(
        origin="BOM",
        destination="DXB",
        departure_date=dep_date,
        adults=1,
        max_budget=14000.0,
    )

    response = await provider.search_flights(query)
    assert len(response.offers) >= 1
    # All returned offers must satisfy budget
    assert all(o.total_price <= 14000.0 for o in response.offers)


@pytest.mark.asyncio
async def test_mock_flight_provider_pricing_and_status():
    """Test pricing confirmation and operational status checks."""
    provider = MockFlightProvider()

    # Price flight
    price_resp = await provider.price_flight("off-mock-ek505-sample")
    assert price_resp.total_price > 0
    assert price_resp.currency == "INR"
    assert price_resp.is_price_guaranteed is True

    # Check on-time status
    status_resp = await provider.get_flight_status("EK505", date.today())
    assert status_resp.status == "ON_TIME"

    # Check simulated cancellation
    cancelled_resp = await provider.get_flight_status("EK505-CANCELLED", date.today())
    assert cancelled_resp.status == "CANCELLED"
    assert "rebooking" in cancelled_resp.remarks.lower()


# ==============================================================================
# MockHotelProvider Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_mock_hotel_provider_search():
    """Test hotel search in Dubai with star rating and budget constraints."""
    provider = MockHotelProvider()
    query = HotelSearchQuery(
        city="Dubai",
        check_in_date=date.today() + timedelta(days=5),
        check_out_date=date.today() + timedelta(days=8),  # 3 nights
        guests=2,
        min_star_rating=4.0,
    )

    response = await provider.search_hotels(query)
    assert response.total_offers >= 2
    assert all(h.star_rating >= 4.0 for h in response.offers)
    assert all(h.total_price == h.price_per_night * 3 for h in response.offers)


@pytest.mark.asyncio
async def test_mock_hotel_provider_details():
    """Test hotel details retrieval and missing inventory exception."""
    provider = MockHotelProvider()

    details = await provider.get_hotel_details("htl-mock-dxb-01")
    assert details.name == "Marina Bay Grand Hotel"
    assert len(details.rooms) >= 1

    with pytest.raises(ProviderInventoryUnavailableException):
        await provider.get_hotel_details("non-existent-hotel-id")


# ==============================================================================
# MockBookingProvider Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_mock_booking_provider_lifecycle():
    """Test booking creation, retrieval, cancellation, and rebooking workflow."""
    provider = MockBookingProvider()

    req = ProviderBookingRequest(
        booking_reference="BK-MOCK-101",
        user_id="user-123",
        booking_type="FLIGHT",
        offer_id="off-ek505",
        passengers=[{"name": "John Doe", "seat": "12A"}],
        total_amount=18500.0,
        currency="INR",
    )

    # 1. Create booking
    created = await provider.create_booking(req)
    assert created.status == "CONFIRMED"
    assert created.pnr.startswith("PNR-")
    assert len(created.ticket_numbers) == 1

    # 2. Get booking
    fetched = await provider.get_booking("BK-MOCK-101")
    assert fetched.booking_reference == "BK-MOCK-101"
    assert fetched.pnr == created.pnr

    # 3. Rebook booking
    rebook = await provider.rebook_booking("BK-MOCK-101", new_flight_id="off-ek507")
    assert rebook.status == "REBOOKED"
    assert rebook.new_booking_reference == "BK-MOCK-101-REB"
    assert rebook.penalty_fee > 0

    # 4. Cancel booking
    cancelled = await provider.cancel_booking("BK-MOCK-101")
    assert cancelled.status == "CANCELLED"
    assert cancelled.refund_amount > 0
    assert cancelled.penalty_amount > 0
    assert cancelled.refund_amount + cancelled.penalty_amount == 18500.0


@pytest.mark.asyncio
async def test_mock_booking_provider_validation():
    """Test validation on invalid booking amounts."""
    provider = MockBookingProvider()
    req = ProviderBookingRequest(
        booking_reference="BK-INVALID",
        user_id="user-123",
        booking_type="FLIGHT",
        offer_id="off-sample",
        total_amount=-500.0,
    )
    with pytest.raises(ProviderValidationException):
        await provider.create_booking(req)


# ==============================================================================
# Amadeus Client & Flight Provider Tests
# ==============================================================================


def test_parse_iso_duration():
    """Test ISO 8601 duration string parser."""
    assert parse_iso_duration("PT3H30M") == 210
    assert parse_iso_duration("PT1H15M") == 75
    assert parse_iso_duration("PT45M") == 45
    assert parse_iso_duration("PT5H") == 300
    assert parse_iso_duration("INVALID") == 180


@pytest.mark.asyncio
async def test_amadeus_client_missing_credentials():
    """Test client raises ProviderAuthenticationException when credentials missing."""
    client = AmadeusClient(client_id="", client_secret="")
    with pytest.raises(ProviderAuthenticationException):
        await client.get_access_token()


@pytest.mark.asyncio
async def test_amadeus_flight_provider_normalization():
    """Test transforming raw Amadeus JSON payload into canonical ProviderFlightOffer list."""
    mock_amadeus_payload = {
        "data": [
            {
                "id": "1",
                "numberOfBookableSeats": 4,
                "itineraries": [
                    {
                        "duration": "PT3H20M",
                        "segments": [
                            {
                                "departure": {"iataCode": "BOM", "at": "2026-10-01T10:00:00Z"},
                                "arrival": {"iataCode": "DXB", "at": "2026-10-01T12:20:00Z"},
                                "carrierCode": "EK",
                                "number": "505",
                                "aircraft": {"code": "77W"},
                            }
                        ],
                    }
                ],
                "price": {
                    "currency": "INR",
                    "total": "18200.00",
                    "base": "15000.00",
                    "grandTotal": "18200.00",
                },
                "travelerPricings": [
                    {
                        "fareDetailsBySegment": [
                            {
                                "cabin": "ECONOMY",
                                "includedCheckedBags": {"quantity": 1},
                            }
                        ]
                    }
                ],
            }
        ],
        "dictionaries": {
            "carriers": {"EK": "Emirates"},
        },
    }

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_amadeus_payload

    provider = AmadeusFlightProvider(client=mock_client)
    query = FlightSearchQuery(
        origin="BOM",
        destination="DXB",
        departure_date=date(2026, 10, 1),
    )

    response = await provider.search_flights(query)
    assert response.provider_source == "AMADEUS"
    assert response.total_offers == 1

    offer = response.offers[0]
    assert offer.flight_number == "EK505"
    assert offer.airline_name == "Emirates"
    assert offer.total_price == 18200.00
    assert offer.duration_minutes == 200
    assert offer.stops == 0


# ==============================================================================
# Provider Factory Tests
# ==============================================================================


def test_provider_factory_resolution():
    """Test resolution of flight, hotel, and booking providers."""
    flight_mock = get_flight_provider("mock")
    assert isinstance(flight_mock, MockFlightProvider)

    flight_amadeus = get_flight_provider("amadeus")
    assert isinstance(flight_amadeus, AmadeusFlightProvider)

    hotel_prov = get_hotel_provider()
    assert isinstance(hotel_prov, MockHotelProvider)

    booking_prov = get_booking_provider()
    assert isinstance(booking_prov, MockBookingProvider)
