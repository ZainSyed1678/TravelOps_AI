"""Pydantic schemas for TravelOps AI domain entities and requests."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ==============================================================================
# User & Traveler Schemas
# ==============================================================================


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "TRAVELER"
    is_active: bool = True
    preferences: dict[str, Any] = Field(default_factory=dict)


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TravelerBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    frequent_flyer_number: str | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)


class TravelerCreate(TravelerBase):
    user_id: str | None = None


class TravelerRead(TravelerBase):
    id: str
    user_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Airport & Airline Schemas
# ==============================================================================


class AirportRead(BaseModel):
    id: str  # IATA
    icao_code: str | None = None
    name: str
    city: str
    country: str
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AirlineRead(BaseModel):
    id: str  # IATA
    icao_code: str | None = None
    name: str
    country: str
    alliance: str | None = None
    logo_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Flight & Search Schemas
# ==============================================================================


class FlightSegmentRead(BaseModel):
    id: str
    segment_index: int
    origin_airport_code: str
    destination_airport_code: str
    departure_time: datetime
    arrival_time: datetime
    operating_carrier: str
    marketing_carrier: str
    aircraft_type: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FlightRead(BaseModel):
    id: str
    flight_number: str
    airline_code: str
    origin_airport_code: str
    destination_airport_code: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    stops: int
    aircraft_type: str | None = None
    status: str
    segments: list[FlightSegmentRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class FlightSearchQuery(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3, description="3-letter IATA origin code")
    destination: str = Field(
        ..., min_length=3, max_length=3, description="3-letter IATA destination code"
    )
    departure_date: date
    return_date: date | None = None
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=9)
    cabin_class: str = Field(default="ECONOMY")
    max_budget: float | None = None
    max_stops: int | None = None


# ==============================================================================
# Hotel & Search Schemas
# ==============================================================================


class RoomRead(BaseModel):
    id: str
    room_type: str
    max_occupancy: int
    base_price_per_night: float
    currency: str
    amenities: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class HotelRead(BaseModel):
    id: str
    name: str
    chain: str | None = None
    address: str
    city: str
    country: str
    star_rating: float | None = None
    amenities: dict[str, Any] = Field(default_factory=dict)
    rooms: list[RoomRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class HotelSearchQuery(BaseModel):
    city: str
    check_in_date: date
    check_out_date: date
    guests: int = Field(default=1, ge=1)
    min_star_rating: float | None = None
    max_price_per_night: float | None = None


# ==============================================================================
# Policy & Supplier Schemas
# ==============================================================================


class PolicyRead(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    policy_type: str
    title: str
    content: str
    terms: dict[str, Any] = Field(default_factory=dict)
    version: str
    effective_date: date

    model_config = ConfigDict(from_attributes=True)


class SupplierRead(BaseModel):
    id: str
    name: str
    code: str
    supplier_type: str
    api_endpoint: str | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Booking, Passenger & Payment Schemas
# ==============================================================================


class PassengerCreate(BaseModel):
    traveler_id: str | None = None
    passenger_type: str = "ADULT"
    seat_number: str | None = None
    special_requests: str | None = None


class PassengerRead(BaseModel):
    id: str
    traveler_id: str | None = None
    passenger_type: str
    seat_number: str | None = None
    ticket_number: str | None = None
    special_requests: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PaymentRead(BaseModel):
    id: str
    amount: float
    currency: str
    payment_method: str
    status: str
    transaction_reference: str | None = None
    processed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingCreate(BaseModel):
    user_id: str
    trip_id: str | None = None
    supplier_id: str | None = None
    booking_type: str  # FLIGHT, HOTEL, PACKAGE
    total_amount: float
    currency: str = "INR"
    passengers: list[PassengerCreate] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class BookingRead(BaseModel):
    id: str
    booking_reference: str
    user_id: str
    trip_id: str | None = None
    supplier_id: str | None = None
    booking_type: str
    status: str
    total_amount: float
    currency: str
    supplier_reference: str | None = None
    confirmation_required: bool
    confirmed_at: datetime | None = None
    passengers: list[PassengerRead] = Field(default_factory=list)
    payments: list[PaymentRead] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingConfirmationRequest(BaseModel):
    confirmed: bool = Field(..., description="Explicit user confirmation flag")
    user_notes: str | None = None
