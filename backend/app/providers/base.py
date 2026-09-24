"""Abstract base classes defining travel provider interfaces."""

from abc import ABC, abstractmethod
from datetime import date

from app.providers.schemas import (
    CancellationResponse,
    FlightPricingResponse,
    FlightSearchResponse,
    FlightStatusResponse,
    HotelDetailsResponse,
    HotelSearchResponse,
    ProviderBookingRequest,
    ProviderBookingResponse,
    RebookResponse,
)
from app.schemas.travel import FlightSearchQuery, HotelSearchQuery


class FlightProvider(ABC):
    """Abstract interface for flight search, pricing, and operational status providers."""

    @abstractmethod
    async def search_flights(self, query: FlightSearchQuery) -> FlightSearchResponse:
        """Search available flight itineraries for given route and dates."""
        pass

    @abstractmethod
    async def price_flight(
        self,
        offer_id: str,
        fare_basis: str | None = None,
    ) -> FlightPricingResponse:
        """Confirm live pricing and fare conditions for a selected flight offer."""
        pass

    @abstractmethod
    async def get_flight_status(
        self,
        flight_number: str,
        departure_date: date,
    ) -> FlightStatusResponse:
        """Retrieve real-time flight operation and disruption status."""
        pass


class HotelProvider(ABC):
    """Abstract interface for hotel accommodation providers."""

    @abstractmethod
    async def search_hotels(self, query: HotelSearchQuery) -> HotelSearchResponse:
        """Search hotel properties matching destination and criteria."""
        pass

    @abstractmethod
    async def get_hotel_details(self, hotel_id: str) -> HotelDetailsResponse:
        """Retrieve full details, room categories, and property policies."""
        pass


class BookingProvider(ABC):
    """Abstract interface for booking creation, retrieval, cancellation, and rebooking."""

    @abstractmethod
    async def create_booking(
        self,
        request: ProviderBookingRequest,
    ) -> ProviderBookingResponse:
        """Create and ticket a reservation with supplier."""
        pass

    @abstractmethod
    async def get_booking(self, booking_reference: str) -> ProviderBookingResponse:
        """Retrieve reservation details from supplier."""
        pass

    @abstractmethod
    async def cancel_booking(
        self,
        booking_reference: str,
        reason: str | None = None,
    ) -> CancellationResponse:
        """Cancel a reservation and compute penalties/refunds."""
        pass

    @abstractmethod
    async def rebook_booking(
        self,
        booking_reference: str,
        new_flight_id: str,
    ) -> RebookResponse:
        """Rebook an existing reservation onto a new itinerary."""
        pass
