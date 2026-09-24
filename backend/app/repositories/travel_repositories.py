"""Domain-specific asynchronous repositories for TravelOps AI."""

from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import (
    Airline,
    Airport,
    Booking,
    Flight,
    Hotel,
    Passenger,
    Payment,
    Policy,
    Supplier,
    Traveler,
    User,
)
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """User account repository."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch user by unique email."""
        query = select(User).where(func.lower(User.email) == email.lower().strip())
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class TravelerRepository(BaseRepository[Traveler]):
    """Traveler profile repository."""

    def __init__(self, session: AsyncSession):
        super().__init__(Traveler, session)

    async def list_by_user_id(self, user_id: str) -> list[Traveler]:
        """Fetch all traveler profiles linked to a user account."""
        query = (
            select(Traveler)
            .where(Traveler.user_id == user_id)
            .options(selectinload(Traveler.documents))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class AirportRepository(BaseRepository[Airport]):
    """Airport reference repository."""

    def __init__(self, session: AsyncSession):
        super().__init__(Airport, session)

    async def get_by_iata(self, iata_code: str) -> Airport | None:
        """Fetch airport by IATA code."""
        return await self.get_by_id(iata_code.upper().strip())

    async def search_by_query(self, query_str: str, limit: int = 10) -> list[Airport]:
        """Search airports by city, country, or code."""
        pattern = f"%{query_str.lower().strip()}%"
        query = (
            select(Airport)
            .where(
                or_(
                    func.lower(Airport.id).like(pattern),
                    func.lower(Airport.name).like(pattern),
                    func.lower(Airport.city).like(pattern),
                    func.lower(Airport.country).like(pattern),
                )
            )
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class AirlineRepository(BaseRepository[Airline]):
    """Airline reference repository."""

    def __init__(self, session: AsyncSession):
        super().__init__(Airline, session)

    async def get_by_iata(self, iata_code: str) -> Airline | None:
        """Fetch airline by 2-letter IATA code."""
        return await self.get_by_id(iata_code.upper().strip())


class FlightRepository(BaseRepository[Flight]):
    """Flight search and inventory repository."""

    def __init__(self, session: AsyncSession):
        super().__init__(Flight, session)

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date | None = None,
        max_stops: int | None = None,
        limit: int = 20,
    ) -> list[Flight]:
        """Search flight routes matching origin, destination, and departure filters."""
        query = (
            select(Flight)
            .where(
                Flight.origin_airport_code == origin.upper().strip(),
                Flight.destination_airport_code == destination.upper().strip(),
            )
            .options(
                selectinload(Flight.airline),
                selectinload(Flight.origin_airport),
                selectinload(Flight.destination_airport),
                selectinload(Flight.segments),
            )
        )

        if departure_date is not None:
            # Match date bounds
            start_dt = datetime.combine(departure_date, datetime.min.time())
            end_dt = datetime.combine(departure_date, datetime.max.time())
            query = query.where(Flight.departure_time >= start_dt, Flight.departure_time <= end_dt)

        if max_stops is not None:
            query = query.where(Flight.stops <= max_stops)

        query = query.order_by(Flight.departure_time).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_flight_with_details(self, flight_id: str) -> Flight | None:
        """Fetch flight with airline, airports, and segments loaded."""
        query = (
            select(Flight)
            .where(Flight.id == flight_id)
            .options(
                selectinload(Flight.airline),
                selectinload(Flight.origin_airport),
                selectinload(Flight.destination_airport),
                selectinload(Flight.segments),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class HotelRepository(BaseRepository[Hotel]):
    """Hotel property repository."""

    def __init__(self, session: AsyncSession):
        super().__init__(Hotel, session)

    async def search_hotels(
        self,
        city: str,
        min_star_rating: float | None = None,
        max_price: float | None = None,
        limit: int = 20,
    ) -> list[Hotel]:
        """Search hotels in a destination city with rating and price constraints."""
        query = (
            select(Hotel)
            .where(func.lower(Hotel.city) == city.lower().strip())
            .options(selectinload(Hotel.rooms))
        )

        if min_star_rating is not None:
            query = query.where(Hotel.star_rating >= min_star_rating)

        query = query.limit(limit)
        result = await self.session.execute(query)
        hotels = list(result.scalars().all())

        if max_price is not None:
            # Filter hotels having at least one room under max_price
            hotels = [
                h for h in hotels if any(r.base_price_per_night <= max_price for r in h.rooms)
            ]

        return hotels


class BookingRepository(BaseRepository[Booking]):
    """Booking transaction repository with eager graph loading."""

    def __init__(self, session: AsyncSession):
        super().__init__(Booking, session)

    async def get_by_reference(self, booking_ref: str) -> Booking | None:
        """Fetch booking by PNR / Booking reference code."""
        query = (
            select(Booking)
            .where(Booking.booking_reference == booking_ref.strip().upper())
            .options(
                selectinload(Booking.passengers).selectinload(Passenger.traveler),
                selectinload(Booking.payments),
                selectinload(Booking.hotel_bookings),
                selectinload(Booking.supplier),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_user_bookings(self, user_id: str, limit: int = 50) -> list[Booking]:
        """List bookings made by a user."""
        query = (
            select(Booking)
            .where(Booking.user_id == user_id)
            .options(
                selectinload(Booking.passengers),
                selectinload(Booking.payments),
            )
            .order_by(Booking.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class PolicyRepository(BaseRepository[Policy]):
    """Travel policy repository."""

    def __init__(self, session: AsyncSession):
        super().__init__(Policy, session)

    async def find_policies(
        self,
        entity_type: str,
        entity_id: str,
        policy_type: str | None = None,
    ) -> list[Policy]:
        """Retrieve policy documents matching entity and type."""
        query = select(Policy).where(
            Policy.entity_type == entity_type.upper().strip(),
            Policy.entity_id == entity_id.upper().strip(),
        )
        if policy_type is not None:
            query = query.where(Policy.policy_type == policy_type.upper().strip())

        result = await self.session.execute(query)
        return list(result.scalars().all())


class SupplierRepository(BaseRepository[Supplier]):
    """Supplier repository."""

    def __init__(self, session: AsyncSession):
        super().__init__(Supplier, session)

    async def get_by_code(self, code: str) -> Supplier | None:
        """Fetch supplier by unique code."""
        query = select(Supplier).where(Supplier.code == code.upper().strip())
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class PaymentRepository(BaseRepository[Payment]):
    """Payment repository."""

    def __init__(self, session: AsyncSession):
        super().__init__(Payment, session)

    async def list_by_booking_id(self, booking_id: str) -> list[Payment]:
        """List all payments for a booking."""
        query = (
            select(Payment)
            .where(Payment.booking_id == booking_id)
            .order_by(Payment.processed_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
