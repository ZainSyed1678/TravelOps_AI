"""Database initialization and baseline travel seed data."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.base import Base
from app.models.entities import (
    Airline,
    Airport,
    Fare,
    Flight,
    FlightSegment,
    Hotel,
    Policy,
    Room,
    Supplier,
    User,
)


async def init_db(engine: AsyncEngine) -> None:
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_initial_data(session: AsyncSession) -> None:
    """Seed baseline travel data (Airports, Airlines, Suppliers, Policies, Flights, Hotels)."""
    # 1. Airports
    airports = [
        Airport(
            id="BOM",
            icao_code="VABB",
            name="Chhatrapati Shivaji Maharaj International Airport",
            city="Mumbai",
            country="India",
            latitude=19.0896,
            longitude=72.8656,
            timezone="Asia/Kolkata",
        ),
        Airport(
            id="DXB",
            icao_code="OMDB",
            name="Dubai International Airport",
            city="Dubai",
            country="United Arab Emirates",
            latitude=25.2532,
            longitude=55.3657,
            timezone="Asia/Dubai",
        ),
        Airport(
            id="DEL",
            icao_code="VIDP",
            name="Indira Gandhi International Airport",
            city="Delhi",
            country="India",
            latitude=28.5562,
            longitude=77.1000,
            timezone="Asia/Kolkata",
        ),
        Airport(
            id="LHR",
            icao_code="EGLL",
            name="Heathrow Airport",
            city="London",
            country="United Kingdom",
            latitude=51.4700,
            longitude=-0.4543,
            timezone="Europe/London",
        ),
    ]
    for ap in airports:
        await session.merge(ap)

    # 2. Airlines
    airlines = [
        Airline(
            id="EK",
            icao_code="UAE",
            name="Emirates",
            country="United Arab Emirates",
            alliance=None,
            logo_url="https://assets.travelops.ai/logos/ek.png",
        ),
        Airline(
            id="AI",
            icao_code="AIC",
            name="Air India",
            country="India",
            alliance="Star Alliance",
            logo_url="https://assets.travelops.ai/logos/ai.png",
        ),
        Airline(
            id="6E",
            icao_code="IGO",
            name="IndiGo",
            country="India",
            alliance=None,
            logo_url="https://assets.travelops.ai/logos/6e.png",
        ),
    ]
    for al in airlines:
        await session.merge(al)

    # 3. Suppliers
    suppliers = [
        Supplier(
            id="sup-amadeus-1",
            name="Amadeus GDS",
            code="AMADEUS",
            supplier_type="GDS",
            api_endpoint="https://test.api.amadeus.com",
            is_active=True,
        ),
        Supplier(
            id="sup-sabre-1",
            name="Sabre Travel Network",
            code="SABRE",
            supplier_type="GDS",
            api_endpoint="https://api.sabre.com",
            is_active=True,
        ),
        Supplier(
            id="sup-ek-ndc",
            name="Emirates NDC Gateway",
            code="NDC_EK",
            supplier_type="NDC",
            api_endpoint="https://ndc.emirates.com",
            is_active=True,
        ),
    ]
    for sp in suppliers:
        await session.merge(sp)

    # 4. Policies
    policies = [
        Policy(
            id="pol-ek-canc-01",
            entity_type="AIRLINE",
            entity_id="EK",
            policy_type="CANCELLATION",
            title="Emirates Standard Cancellation & Refund Policy",
            content="Flexible fares may be cancelled up to 24 hours prior to departure for a full refund minus a 2,000 INR administrative fee. Saver fares incur a 5,000 INR cancellation fee. Special fares are non-refundable.",
            terms={"fee_saver": 5000, "fee_flex": 2000, "deadline_hours": 24, "currency": "INR"},
            version="2.1",
            effective_date=date(2024, 1, 1),
        ),
        Policy(
            id="pol-ek-bag-01",
            entity_type="AIRLINE",
            entity_id="EK",
            policy_type="BAGGAGE",
            title="Emirates Baggage Allowance Guidelines",
            content="Economy Class passengers are entitled to up to 25kg on Special and Saver tickets, 30kg on Flex tickets, and 35kg on Flex Plus. Cabin baggage is limited to 1 piece of up to 7kg.",
            terms={"cabin_limit_kg": 7, "checkin_saver_kg": 25, "checkin_flex_kg": 30},
            version="1.5",
            effective_date=date(2024, 1, 1),
        ),
    ]
    for pol in policies:
        await session.merge(pol)

    # 5. Hotels & Rooms
    hotel = Hotel(
        id="htl-dxb-marina-1",
        name="Marina Bay Grand Hotel",
        chain="Grand Luxury Hotels",
        address="Dubai Marina, Al Marsa Street",
        city="Dubai",
        country="United Arab Emirates",
        star_rating=4.5,
        latitude=25.0772,
        longitude=55.1333,
        amenities={"wifi": True, "pool": True, "breakfast": True, "gym": True},
    )
    await session.merge(hotel)

    rooms = [
        Room(
            id="rm-std-101",
            hotel_id="htl-dxb-marina-1",
            room_type="STANDARD_KING",
            max_occupancy=2,
            base_price_per_night=8500.0,
            currency="INR",
            amenities={"bed": "King", "view": "City"},
        ),
        Room(
            id="rm-dlx-201",
            hotel_id="htl-dxb-marina-1",
            room_type="DELUXE_MARINA_VIEW",
            max_occupancy=2,
            base_price_per_night=12000.0,
            currency="INR",
            amenities={"bed": "King", "view": "Marina", "balcony": True},
        ),
    ]
    for rm in rooms:
        await session.merge(rm)

    # 6. Sample Flight (BOM -> DXB)
    now = datetime.now(UTC)
    dep_time = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=7)
    arr_time = dep_time + timedelta(hours=3, minutes=30)

    flight = Flight(
        id="flt-ek505-sample",
        flight_number="EK505",
        airline_code="EK",
        origin_airport_code="BOM",
        destination_airport_code="DXB",
        departure_time=dep_time,
        arrival_time=arr_time,
        duration_minutes=210,
        stops=0,
        aircraft_type="Boeing 777-300ER",
        status="SCHEDULED",
    )
    await session.merge(flight)

    segment = FlightSegment(
        id="seg-ek505-1",
        flight_id="flt-ek505-sample",
        segment_index=1,
        origin_airport_code="BOM",
        destination_airport_code="DXB",
        departure_time=dep_time,
        arrival_time=arr_time,
        operating_carrier="EK",
        marketing_carrier="EK",
        aircraft_type="Boeing 777-300ER",
    )
    await session.merge(segment)

    fare = Fare(
        id="fare-ek-saver-1",
        airline_code="EK",
        fare_basis_code="EE20SAVER",
        cabin_class="ECONOMY",
        is_refundable=True,
        change_allowed=True,
        cancellation_fee=5000.0,
        change_fee=2500.0,
        baggage_allowance="1 piece (25kg)",
        rules={"fare_type": "SAVER", "penalty_before_departure": 5000},
    )
    await session.merge(fare)

    # 7. Sample Default User
    demo_user = User(
        id="usr-demo-traveler",
        email="traveler@travelops.ai",
        full_name="Alex Mercer",
        hashed_password="hashed_demo_password",
        role="TRAVELER",
        is_active=True,
        preferences={
            "seat_preference": "WINDOW",
            "meal_preference": "VEG",
            "cabin_class": "ECONOMY",
        },
    )
    await session.merge(demo_user)

    await session.commit()
