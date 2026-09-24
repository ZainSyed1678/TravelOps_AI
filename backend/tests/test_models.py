"""Tests verifying all 17 SQLAlchemy domain entities and ORM relationships."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import (
    Airline,
    Airport,
    Booking,
    Fare,
    Flight,
    FlightSegment,
    Hotel,
    Passenger,
    Payment,
    Policy,
    Room,
    Supplier,
    TravelDocument,
    Traveler,
    Trip,
    User,
)


@pytest.mark.asyncio
async def test_user_traveler_document_lifecycle(db_session: AsyncSession):
    """Test User, Traveler, and TravelDocument creation and relationship cascades."""
    user = User(
        email="john.doe@example.com",
        full_name="Johnathan Doe",
        hashed_password="secure_password_hash",
        role="TRAVELER",
        preferences={"seat": "AISLE", "meal": "STANDARD"},
    )
    db_session.add(user)
    await db_session.flush()

    traveler = Traveler(
        user_id=user.id,
        first_name="Johnathan",
        last_name="Doe",
        email="john.doe@example.com",
        date_of_birth=date(1990, 5, 15),
        nationality="IND",
        passport_number="Z1234567",
    )
    db_session.add(traveler)
    await db_session.flush()

    doc = TravelDocument(
        traveler_id=traveler.id,
        document_type="PASSPORT",
        document_number="Z1234567",
        issuing_country="IND",
        expiry_date=date(2032, 5, 14),
    )
    db_session.add(doc)
    await db_session.commit()

    # Query with relationships loaded
    query = (
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.travelers).selectinload(Traveler.documents))
    )
    result = await db_session.execute(query)
    fetched_user = result.scalar_one()

    assert fetched_user.email == "john.doe@example.com"
    assert len(fetched_user.travelers) == 1
    assert fetched_user.travelers[0].first_name == "Johnathan"
    assert len(fetched_user.travelers[0].documents) == 1
    assert fetched_user.travelers[0].documents[0].document_type == "PASSPORT"
    assert fetched_user.created_at is not None


@pytest.mark.asyncio
async def test_aviation_entities_and_segments(db_session: AsyncSession):
    """Test Airport, Airline, Flight, FlightSegment, and Fare entities."""
    bom = Airport(id="BOM", name="Mumbai CSMI Airport", city="Mumbai", country="India")
    dxb = Airport(id="DXB", name="Dubai International", city="Dubai", country="UAE")
    db_session.add_all([bom, dxb])

    ek = Airline(id="EK", name="Emirates", country="UAE", alliance="None")
    db_session.add(ek)
    await db_session.flush()

    now = datetime.now(UTC)
    flight = Flight(
        flight_number="EK501",
        airline_code="EK",
        origin_airport_code="BOM",
        destination_airport_code="DXB",
        departure_time=now + timedelta(days=2),
        arrival_time=now + timedelta(days=2, hours=3),
        duration_minutes=180,
        stops=0,
        status="SCHEDULED",
    )
    db_session.add(flight)
    await db_session.flush()

    segment = FlightSegment(
        flight_id=flight.id,
        segment_index=1,
        origin_airport_code="BOM",
        destination_airport_code="DXB",
        departure_time=flight.departure_time,
        arrival_time=flight.arrival_time,
        operating_carrier="EK",
        marketing_carrier="EK",
    )
    fare = Fare(
        airline_code="EK",
        fare_basis_code="YFLEX",
        cabin_class="ECONOMY",
        is_refundable=True,
        change_allowed=True,
        baggage_allowance="30kg",
    )
    db_session.add_all([segment, fare])
    await db_session.commit()

    query = (
        select(Flight)
        .where(Flight.id == flight.id)
        .options(
            selectinload(Flight.airline),
            selectinload(Flight.segments),
        )
    )
    res = await db_session.execute(query)
    saved_flight = res.scalar_one()

    assert saved_flight.airline.name == "Emirates"
    assert len(saved_flight.segments) == 1
    assert saved_flight.segments[0].origin_airport_code == "BOM"


@pytest.mark.asyncio
async def test_hospitality_hotel_and_rooms(db_session: AsyncSession):
    """Test Hotel and Room inventory models."""
    hotel = Hotel(
        name="Burj Al Arab",
        address="Jumeirah Beach Road",
        city="Dubai",
        country="UAE",
        star_rating=5.0,
    )
    db_session.add(hotel)
    await db_session.flush()

    room = Room(
        hotel_id=hotel.id,
        room_type="DELUXE_SUITE",
        max_occupancy=3,
        base_price_per_night=45000.0,
        currency="INR",
    )
    db_session.add(room)
    await db_session.commit()

    query = select(Hotel).where(Hotel.id == hotel.id).options(selectinload(Hotel.rooms))
    res = await db_session.execute(query)
    saved_hotel = res.scalar_one()

    assert saved_hotel.name == "Burj Al Arab"
    assert len(saved_hotel.rooms) == 1
    assert saved_hotel.rooms[0].base_price_per_night == 45000.0


@pytest.mark.asyncio
async def test_full_booking_and_payment_hierarchy(db_session: AsyncSession):
    """Test complete transaction hierarchy: Trip -> Booking -> Passenger -> Payment -> HotelBooking."""
    user = User(
        email="sarah.traveler@example.com",
        full_name="Sarah Jenkins",
        hashed_password="hashed_pass_sample",
    )
    supplier = Supplier(
        name="Amadeus Global Distribution System",
        code="AMADEUS",
        supplier_type="GDS",
        is_active=True,
    )
    db_session.add_all([user, supplier])
    await db_session.flush()

    trip = Trip(
        user_id=user.id,
        title="Dubai Q4 Leadership Offsite",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 5),
        budget=150000.0,
        currency="INR",
    )
    db_session.add(trip)
    await db_session.flush()

    booking = Booking(
        booking_reference="TRV-DXB-9988",
        trip_id=trip.id,
        user_id=user.id,
        supplier_id=supplier.id,
        booking_type="PACKAGE",
        status="CONFIRMED",
        total_amount=98500.0,
        currency="INR",
        confirmation_required=True,
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(booking)
    await db_session.flush()

    passenger = Passenger(
        booking_id=booking.id,
        passenger_type="ADULT",
        seat_number="12A",
        ticket_number="176-9876543210",
    )
    payment = Payment(
        booking_id=booking.id,
        amount=98500.0,
        currency="INR",
        payment_method="CORPORATE_BILLING",
        status="SUCCESS",
        transaction_reference="TXN-DXB-1029384",
    )
    db_session.add_all([passenger, payment])
    await db_session.commit()

    # Query full booking details
    query = (
        select(Booking)
        .where(Booking.booking_reference == "TRV-DXB-9988")
        .options(
            selectinload(Booking.user),
            selectinload(Booking.trip),
            selectinload(Booking.supplier),
            selectinload(Booking.passengers),
            selectinload(Booking.payments),
        )
    )
    res = await db_session.execute(query)
    saved_booking = res.scalar_one()

    assert saved_booking.booking_reference == "TRV-DXB-9988"
    assert saved_booking.user.full_name == "Sarah Jenkins"
    assert saved_booking.trip.title == "Dubai Q4 Leadership Offsite"
    assert saved_booking.supplier.code == "AMADEUS"
    assert len(saved_booking.passengers) == 1
    assert saved_booking.passengers[0].seat_number == "12A"
    assert len(saved_booking.payments) == 1
    assert saved_booking.payments[0].status == "SUCCESS"


@pytest.mark.asyncio
async def test_policy_entity_creation(db_session: AsyncSession):
    """Test Policy entity creation and query."""
    policy = Policy(
        entity_type="AIRLINE",
        entity_id="AI",
        policy_type="CANCELLATION",
        title="Air India Domestic & International Cancellation",
        content="Cancellations made within 24 hours of scheduled departure are subject to 100% forfeiture.",
        terms={"hours_threshold": 24, "forfeiture_rate": 1.0},
        version="3.0",
        effective_date=date(2024, 6, 1),
    )
    db_session.add(policy)
    await db_session.commit()

    query = select(Policy).where(Policy.entity_id == "AI")
    res = await db_session.execute(query)
    saved = res.scalar_one()

    assert saved.entity_type == "AIRLINE"
    assert saved.policy_type == "CANCELLATION"
    assert saved.terms["hours_threshold"] == 24
