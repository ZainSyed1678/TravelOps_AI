"""Tests for asynchronous repository implementations."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Booking, Passenger, Payment, Traveler, User
from app.repositories.travel_repositories import (
    AirlineRepository,
    AirportRepository,
    BookingRepository,
    FlightRepository,
    HotelRepository,
    PaymentRepository,
    PolicyRepository,
    SupplierRepository,
    TravelerRepository,
    UserRepository,
)


@pytest.mark.asyncio
async def test_user_and_traveler_repository(db_session: AsyncSession):
    """Test UserRepository and TravelerRepository CRUD operations."""
    user_repo = UserRepository(db_session)
    traveler_repo = TravelerRepository(db_session)

    user = User(
        email="alex.mercer@travelops.ai",
        full_name="Alex Mercer",
        hashed_password="mock_hashed_secret",
    )
    created_user = await user_repo.create(user)
    assert created_user.id is not None

    # Fetch by email (case-insensitive)
    found_user = await user_repo.get_by_email("ALEX.MERCER@travelops.ai")
    assert found_user is not None
    assert found_user.id == created_user.id

    # Create traveler profile
    traveler = Traveler(
        user_id=created_user.id,
        first_name="Alex",
        last_name="Mercer",
        email="alex.mercer@travelops.ai",
    )
    await traveler_repo.create(traveler)

    # List travelers by user
    travelers = await traveler_repo.list_by_user_id(created_user.id)
    assert len(travelers) == 1
    assert travelers[0].first_name == "Alex"


@pytest.mark.asyncio
async def test_airport_and_airline_repositories(seeded_session: AsyncSession):
    """Test AirportRepository and AirlineRepository lookups using seeded data."""
    airport_repo = AirportRepository(seeded_session)
    airline_repo = AirlineRepository(seeded_session)

    # Lookup airport by IATA
    bom = await airport_repo.get_by_iata("BOM")
    assert bom is not None
    assert bom.city == "Mumbai"

    # Search airports by query
    dubai_results = await airport_repo.search_by_query("dubai")
    assert len(dubai_results) >= 1
    assert any(a.id == "DXB" for a in dubai_results)

    # Lookup airline
    ek = await airline_repo.get_by_iata("EK")
    assert ek is not None
    assert ek.name == "Emirates"


@pytest.mark.asyncio
async def test_flight_search_repository(seeded_session: AsyncSession):
    """Test FlightRepository search functionality."""
    flight_repo = FlightRepository(seeded_session)

    # Search flights BOM -> DXB
    flights = await flight_repo.search_flights(origin="BOM", destination="DXB")
    assert len(flights) >= 1
    flight = flights[0]
    assert flight.flight_number == "EK505"
    assert flight.airline.name == "Emirates"
    assert flight.origin_airport.city == "Mumbai"
    assert flight.destination_airport.city == "Dubai"
    assert len(flight.segments) == 1

    # Fetch with details
    flight_details = await flight_repo.get_flight_with_details(flight.id)
    assert flight_details is not None
    assert flight_details.flight_number == "EK505"


@pytest.mark.asyncio
async def test_hotel_search_repository(seeded_session: AsyncSession):
    """Test HotelRepository filtering by city, rating, and max price."""
    hotel_repo = HotelRepository(seeded_session)

    # Search hotels in Dubai
    hotels = await hotel_repo.search_hotels(city="Dubai", min_star_rating=4.0)
    assert len(hotels) >= 1
    assert hotels[0].name == "Marina Bay Grand Hotel"
    assert len(hotels[0].rooms) >= 1

    # Search with budget cap
    budget_hotels = await hotel_repo.search_hotels(city="Dubai", max_price=10000.0)
    assert len(budget_hotels) >= 1
    # Very low price should filter out hotel
    expensive_only = await hotel_repo.search_hotels(city="Dubai", max_price=5000.0)
    assert len(expensive_only) == 0


@pytest.mark.asyncio
async def test_policy_and_supplier_repositories(seeded_session: AsyncSession):
    """Test PolicyRepository and SupplierRepository retrieval."""
    policy_repo = PolicyRepository(seeded_session)
    supplier_repo = SupplierRepository(seeded_session)

    # Find cancellation policy for Emirates
    policies = await policy_repo.find_policies(
        entity_type="AIRLINE", entity_id="EK", policy_type="CANCELLATION"
    )
    assert len(policies) >= 1
    assert "Cancellation" in policies[0].title
    assert policies[0].terms["fee_saver"] == 5000

    # Get supplier
    amadeus = await supplier_repo.get_by_code("AMADEUS")
    assert amadeus is not None
    assert amadeus.supplier_type == "GDS"


@pytest.mark.asyncio
async def test_booking_and_payment_repositories(db_session: AsyncSession):
    """Test BookingRepository and PaymentRepository with full relations."""
    user_repo = UserRepository(db_session)
    booking_repo = BookingRepository(db_session)
    payment_repo = PaymentRepository(db_session)

    user = await user_repo.create(
        User(
            email="booker@travelops.ai",
            full_name="Booking User",
            hashed_password="pw",
        )
    )

    booking = Booking(
        booking_reference="BK-TEST-7788",
        user_id=user.id,
        booking_type="FLIGHT",
        status="CONFIRMED",
        total_amount=38500.0,
        currency="INR",
        confirmation_required=True,
    )
    created_booking = await booking_repo.create(booking)

    # Add passenger & payment
    passenger = Passenger(
        booking_id=created_booking.id,
        passenger_type="ADULT",
        seat_number="15C",
    )
    payment = Payment(
        booking_id=created_booking.id,
        amount=38500.0,
        currency="INR",
        payment_method="UPI",
        status="SUCCESS",
        transaction_reference="TXN-UPI-991122",
    )
    db_session.add_all([passenger, payment])
    await db_session.commit()

    # Retrieve by reference
    loaded_booking = await booking_repo.get_by_reference("BK-TEST-7788")
    assert loaded_booking is not None
    assert loaded_booking.total_amount == 38500.0
    assert len(loaded_booking.passengers) == 1
    assert loaded_booking.passengers[0].seat_number == "15C"
    assert len(loaded_booking.payments) == 1

    # Payment repository list
    payments = await payment_repo.list_by_booking_id(created_booking.id)
    assert len(payments) == 1
    assert payments[0].transaction_reference == "TXN-UPI-991122"

    # User bookings list
    user_bookings = await booking_repo.list_user_bookings(user.id)
    assert len(user_bookings) == 1
    assert user_bookings[0].booking_reference == "BK-TEST-7788"
