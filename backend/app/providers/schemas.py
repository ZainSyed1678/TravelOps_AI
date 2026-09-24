"""Canonical Provider Data Transfer Objects (DTOs)."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

# ==============================================================================
# Flight Provider DTOs
# ==============================================================================


class ProviderFlightOffer(BaseModel):
    """Normalized flight offer returned by any flight provider."""

    id: str = Field(..., description="Unique provider offer ID")
    provider_name: str = Field(..., description="Source provider (e.g. MOCK, AMADEUS)")
    flight_number: str = Field(..., description="Flight number code e.g. EK505")
    airline_code: str = Field(..., description="2-letter IATA airline code")
    airline_name: str = Field(..., description="Marketing carrier full name")
    origin_airport: str = Field(..., description="3-letter IATA origin")
    destination_airport: str = Field(..., description="3-letter IATA destination")
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    stops: int = 0
    aircraft_type: str | None = None
    cabin_class: str = "ECONOMY"
    base_fare: float
    taxes: float
    total_price: float
    currency: str = "INR"
    is_refundable: bool = False
    baggage_allowance: str = "1 piece (23kg)"
    seats_available: int = 9
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class FlightSearchResponse(BaseModel):
    """Normalized search results across flight providers."""

    offers: list[ProviderFlightOffer] = Field(default_factory=list)
    total_offers: int = 0
    provider_source: str
    latency_ms: float


class FlightPricingResponse(BaseModel):
    """Confirmed flight pricing offer."""

    offer_id: str
    base_fare: float
    taxes: float
    total_price: float
    currency: str = "INR"
    valid_until: datetime
    is_price_guaranteed: bool = True
    provider_source: str


class FlightStatusResponse(BaseModel):
    """Flight operational status."""

    flight_number: str
    departure_date: date
    status: str = Field(..., description="ON_TIME, DELAYED, CANCELLED")
    delay_minutes: int = 0
    actual_departure: datetime | None = None
    actual_arrival: datetime | None = None
    terminal: str | None = None
    gate: str | None = None
    remarks: str | None = None


# ==============================================================================
# Hotel Provider DTOs
# ==============================================================================


class ProviderHotelOffer(BaseModel):
    """Normalized hotel offer returned by any hotel provider."""

    id: str
    provider_name: str
    hotel_id: str
    name: str
    address: str
    city: str
    country: str
    star_rating: float | None = None
    room_type: str
    price_per_night: float
    total_price: float
    currency: str = "INR"
    free_cancellation: bool = True
    breakfast_included: bool = False
    amenities: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class HotelSearchResponse(BaseModel):
    """Normalized hotel search response."""

    offers: list[ProviderHotelOffer] = Field(default_factory=list)
    total_offers: int = 0
    provider_source: str
    latency_ms: float


class HotelDetailsResponse(BaseModel):
    """Detailed hotel information."""

    hotel_id: str
    name: str
    description: str
    address: str
    city: str
    country: str
    star_rating: float | None = None
    rooms: list[dict[str, Any]] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)
    amenities: list[str] = Field(default_factory=list)


# ==============================================================================
# Booking Provider DTOs
# ==============================================================================


class ProviderBookingRequest(BaseModel):
    """Request payload sent to booking provider."""

    booking_reference: str
    user_id: str
    booking_type: str  # FLIGHT, HOTEL, PACKAGE
    offer_id: str
    passengers: list[dict[str, Any]] = Field(default_factory=list)
    total_amount: float
    currency: str = "INR"
    special_requests: str | None = None


class ProviderBookingResponse(BaseModel):
    """Confirmed booking response from provider."""

    booking_reference: str
    pnr: str
    provider_name: str
    status: str  # CONFIRMED, PENDING, FAILED
    confirmed_at: datetime | None = None
    total_amount: float
    currency: str = "INR"
    ticket_numbers: list[str] = Field(default_factory=list)
    raw_details: dict[str, Any] = Field(default_factory=dict)


class CancellationResponse(BaseModel):
    """Response from provider cancellation."""

    booking_reference: str
    cancellation_id: str
    status: str  # CANCELLED, REJECTED
    original_amount: float
    penalty_amount: float
    refund_amount: float
    currency: str = "INR"
    message: str


class RebookResponse(BaseModel):
    """Response from provider rebooking."""

    original_booking_reference: str
    new_booking_reference: str
    new_pnr: str
    status: str  # REBOOKED, FAILED
    price_difference: float
    penalty_fee: float
    total_amount_due: float
    currency: str = "INR"
    message: str
