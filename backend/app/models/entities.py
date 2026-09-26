"""SQLAlchemy 2.0 Domain Entities for TravelOps AI Platform."""

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utc_now


def generate_uuid() -> str:
    """Generate string UUIDv4."""
    return str(uuid.uuid4())


# ==============================================================================
# 1. User & Traveler Management
# ==============================================================================


class User(Base, TimestampMixin):
    """User account entity representing travelers, travel managers, or agents."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50), default="TRAVELER", nullable=False
    )  # TRAVELER, AGENT, ADMIN
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    travelers: Mapped[list["Traveler"]] = relationship(
        "Traveler", back_populates="user", cascade="all, delete-orphan"
    )
    trips: Mapped[list["Trip"]] = relationship(
        "Trip", back_populates="user", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="user")


class Traveler(Base, TimestampMixin):
    """Traveler profile containing passport, loyalty, and biographical details."""

    __tablename__ = "travelers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(3), nullable=True)  # ISO 3166-1 alpha-3
    passport_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frequent_flyer_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="travelers")
    documents: Mapped[list["TravelDocument"]] = relationship(
        "TravelDocument", back_populates="traveler", cascade="all, delete-orphan"
    )
    passengers: Mapped[list["Passenger"]] = relationship("Passenger", back_populates="traveler")


class TravelDocument(Base, TimestampMixin):
    """Travel identity documents (Passport, Visa, Boarding Pass, Insurance)."""

    __tablename__ = "travel_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    traveler_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("travelers.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # PASSPORT, VISA, TICKET, INSURANCE
    document_number: Mapped[str] = mapped_column(String(100), nullable=False)
    issuing_country: Mapped[str] = mapped_column(String(3), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    traveler: Mapped["Traveler"] = relationship("Traveler", back_populates="documents")


# ==============================================================================
# 2. Aviation & Geography
# ==============================================================================


class Airport(Base, TimestampMixin):
    """Airport reference data."""

    __tablename__ = "airports"

    id: Mapped[str] = mapped_column(
        String(3), primary_key=True
    )  # IATA 3-letter code (e.g., BOM, DXB, JFK)
    icao_code: Mapped[str | None] = mapped_column(String(4), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)


class Airline(Base, TimestampMixin):
    """Airline carrier reference data."""

    __tablename__ = "airlines"

    id: Mapped[str] = mapped_column(
        String(2), primary_key=True
    )  # IATA 2-letter code (e.g., EK, AI, BA)
    icao_code: Mapped[str | None] = mapped_column(String(3), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    alliance: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # Star Alliance, SkyTeam, Oneworld
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    flights: Mapped[list["Flight"]] = relationship("Flight", back_populates="airline")
    fares: Mapped[list["Fare"]] = relationship("Fare", back_populates="airline")


class Flight(Base, TimestampMixin):
    """Scheduled or search flight option."""

    __tablename__ = "flights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    flight_number: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False
    )  # e.g., EK505
    airline_code: Mapped[str] = mapped_column(String(2), ForeignKey("airlines.id"), nullable=False)
    origin_airport_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("airports.id"), nullable=False
    )
    destination_airport_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("airports.id"), nullable=False
    )
    departure_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    stops: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    aircraft_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="SCHEDULED", nullable=False
    )  # SCHEDULED, DELAYED, CANCELLED

    # Relationships
    airline: Mapped["Airline"] = relationship("Airline", back_populates="flights")
    origin_airport: Mapped["Airport"] = relationship("Airport", foreign_keys=[origin_airport_code])
    destination_airport: Mapped["Airport"] = relationship(
        "Airport", foreign_keys=[destination_airport_code]
    )
    segments: Mapped[list["FlightSegment"]] = relationship(
        "FlightSegment", back_populates="flight", cascade="all, delete-orphan"
    )


class FlightSegment(Base, TimestampMixin):
    """Individual segment in a multi-leg or connection flight."""

    __tablename__ = "flight_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    flight_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("flights.id", ondelete="CASCADE"), nullable=False
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_airport_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("airports.id"), nullable=False
    )
    destination_airport_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("airports.id"), nullable=False
    )
    departure_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operating_carrier: Mapped[str] = mapped_column(
        String(2), ForeignKey("airlines.id"), nullable=False
    )
    marketing_carrier: Mapped[str] = mapped_column(
        String(2), ForeignKey("airlines.id"), nullable=False
    )
    aircraft_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    flight: Mapped["Flight"] = relationship("Flight", back_populates="segments")


class Fare(Base, TimestampMixin):
    """Airline fare basis rules and conditions."""

    __tablename__ = "fares"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    airline_code: Mapped[str] = mapped_column(String(2), ForeignKey("airlines.id"), nullable=False)
    fare_basis_code: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # e.g., YFLEX, BSAVER
    cabin_class: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST
    is_refundable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    change_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cancellation_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    baggage_allowance: Mapped[str] = mapped_column(
        String(100), default="1 piece (23kg)", nullable=False
    )
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    airline: Mapped["Airline"] = relationship("Airline", back_populates="fares")


# ==============================================================================
# 3. Hospitality & Accommodation
# ==============================================================================


class Hotel(Base, TimestampMixin):
    """Hotel property entity."""

    __tablename__ = "hotels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    chain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    star_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    amenities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    rooms: Mapped[list["Room"]] = relationship(
        "Room", back_populates="hotel", cascade="all, delete-orphan"
    )
    hotel_bookings: Mapped[list["HotelBooking"]] = relationship(
        "HotelBooking", back_populates="hotel"
    )


class Room(Base, TimestampMixin):
    """Room inventory type in a hotel property."""

    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    hotel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False
    )
    room_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # STANDARD, DELUXE, EXECUTIVE_SUITE
    max_occupancy: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    base_price_per_night: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    amenities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    hotel: Mapped["Hotel"] = relationship("Hotel", back_populates="rooms")
    hotel_bookings: Mapped[list["HotelBooking"]] = relationship(
        "HotelBooking", back_populates="room"
    )


# ==============================================================================
# 4. Suppliers & Travel Policies
# ==============================================================================


class Supplier(Base, TimestampMixin):
    """Travel supplier / GDS / NDC aggregator provider entity."""

    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )  # AMADEUS, SABRE, NDC_EK
    supplier_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # GDS, NDC, AGGREGATOR, DIRECT
    api_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="supplier")


class Policy(Base, TimestampMixin):
    """Travel policy and fare condition document."""

    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_type: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # AIRLINE, HOTEL, CORPORATE
    entity_id: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # Airline code or Corporate ID
    policy_type: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # CANCELLATION, REFUND, BAGGAGE, DISRUPTION
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    terms: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)


# ==============================================================================
# 5. Trips, Bookings, Passengers & Payments
# ==============================================================================


class Trip(Base, TimestampMixin):
    """Aggregate trip itinerary container."""

    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="PLANNED", nullable=False
    )  # PLANNED, ACTIVE, COMPLETED, CANCELLED
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="trips")
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="trip")


class Booking(Base, TimestampMixin):
    """Core transaction entity for flight, hotel, or package reservation."""

    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    booking_reference: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )  # PNR: e.g. TRV-BK-1234
    trip_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("trips.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    booking_type: Mapped[str] = mapped_column(String(50), nullable=False)  # FLIGHT, HOTEL, PACKAGE
    status: Mapped[str] = mapped_column(
        String(50), index=True, default="PENDING", nullable=False
    )  # PENDING, CONFIRMED, CANCELLED, DISRUPTED, MODIFIED
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    supplier_reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # External GDS / Amadeus PNR
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="bookings")
    trip: Mapped[Optional["Trip"]] = relationship("Trip", back_populates="bookings")
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier", back_populates="bookings")
    passengers: Mapped[list["Passenger"]] = relationship(
        "Passenger", back_populates="booking", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="booking", cascade="all, delete-orphan"
    )
    hotel_bookings: Mapped[list["HotelBooking"]] = relationship(
        "HotelBooking", back_populates="booking", cascade="all, delete-orphan"
    )


class Passenger(Base, TimestampMixin):
    """Passenger attached to a booking ticket."""

    __tablename__ = "passengers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    booking_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    traveler_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("travelers.id", ondelete="SET NULL"), nullable=True
    )
    passenger_type: Mapped[str] = mapped_column(
        String(20), default="ADULT", nullable=False
    )  # ADULT, CHILD, INFANT
    seat_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ticket_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # E-ticket number (e.g., 176-1234567890)
    special_requests: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="passengers")
    traveler: Mapped[Optional["Traveler"]] = relationship("Traveler", back_populates="passengers")


class HotelBooking(Base, TimestampMixin):
    """Specific hotel reservation leg within a booking."""

    __tablename__ = "hotel_bookings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    booking_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    hotel_id: Mapped[str] = mapped_column(String(36), ForeignKey("hotels.id"), nullable=False)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id"), nullable=False)
    check_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_out_date: Mapped[date] = mapped_column(Date, nullable=False)
    number_of_guests: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="CONFIRMED", nullable=False)

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="hotel_bookings")
    hotel: Mapped["Hotel"] = relationship("Hotel", back_populates="hotel_bookings")
    room: Mapped["Room"] = relationship("Room", back_populates="hotel_bookings")


class Payment(Base, TimestampMixin):
    """Financial transaction record attached to a booking."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    booking_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    payment_method: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # CREDIT_CARD, UPI, CORPORATE_BILLING
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", nullable=False
    )  # PENDING, SUCCESS, FAILED, REFUNDED
    transaction_reference: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    booking: Mapped["Booking"] = relationship("Booking", back_populates="payments")


# ==============================================================================
# 6. Agent Memory & Conversational Sessions
# ==============================================================================


class AgentSession(Base, TimestampMixin):
    """Persistent agent conversation session and thread state."""

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    thread_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    workflow: Mapped[str] = mapped_column(String(50), default="SEARCH", nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="ACTIVE", nullable=False
    )  # ACTIVE, COMPLETED, ARCHIVED
    state_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")
    messages: Mapped[list["AgentMessage"]] = relationship(
        "AgentMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentMessage.created_at",
        lazy="selectin",
    )


class AgentMessage(Base, TimestampMixin):
    """Individual conversational message within an agent session."""

    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    session: Mapped["AgentSession"] = relationship("AgentSession", back_populates="messages")


class TravelerMemoryProfile(Base, TimestampMixin):
    """Long-term personalized memory and learned traveler preferences."""

    __tablename__ = "traveler_memory_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    preference_key: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False
    )  # preferred_airline, seat_preference, home_airport, cabin_class
    preference_value: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")


# Index definitions for high-frequency queries
Index(
    "idx_flight_origin_dest_date",
    Flight.origin_airport_code,
    Flight.destination_airport_code,
    Flight.departure_time,
)
Index("idx_booking_user_status", Booking.user_id, Booking.status)
Index("idx_policy_entity_type", Policy.entity_type, Policy.entity_id, Policy.policy_type)
Index("idx_agent_session_user_status", AgentSession.user_id, AgentSession.status)
Index("idx_agent_message_session", AgentMessage.session_id, AgentMessage.created_at)
Index(
    "idx_traveler_profile_user_key",
    TravelerMemoryProfile.user_id,
    TravelerMemoryProfile.preference_key,
)
