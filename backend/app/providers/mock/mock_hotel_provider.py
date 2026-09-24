"""Mock Hotel Provider simulating hospitality inventory aggregators."""

import time

from app.core.logging import logger
from app.providers.base import HotelProvider
from app.providers.exceptions import ProviderInventoryUnavailableException
from app.providers.schemas import (
    HotelDetailsResponse,
    HotelSearchResponse,
    ProviderHotelOffer,
)
from app.schemas.travel import HotelSearchQuery


class MockHotelProvider(HotelProvider):
    """Deterministic Mock Hotel Provider with realistic properties and room rates."""

    PROVIDER_NAME = "MOCK_HOTEL_AGGREGATOR"

    def __init__(self, simulated_latency_ms: float = 15.0):
        self.simulated_latency_ms = simulated_latency_ms

    async def search_hotels(self, query: HotelSearchQuery) -> HotelSearchResponse:
        """Search hotels in destination city with price and rating filters."""
        start_time = time.perf_counter()
        city = query.city.strip()
        nights = max(1, (query.check_out_date - query.check_in_date).days)

        logger.info(
            f"[{self.PROVIDER_NAME}] Searching hotels in '{city}' for {nights} nights (guests: {query.guests})"
        )

        all_offers = self._get_city_inventory(city, nights)

        # Filter by minimum star rating
        if query.min_star_rating is not None:
            all_offers = [h for h in all_offers if (h.star_rating or 0.0) >= query.min_star_rating]

        # Filter by maximum price per night
        if query.max_price_per_night is not None:
            all_offers = [h for h in all_offers if h.price_per_night <= query.max_price_per_night]

        latency = (time.perf_counter() - start_time) * 1000 + self.simulated_latency_ms

        return HotelSearchResponse(
            offers=all_offers,
            total_offers=len(all_offers),
            provider_source=self.PROVIDER_NAME,
            latency_ms=round(latency, 2),
        )

    async def get_hotel_details(self, hotel_id: str) -> HotelDetailsResponse:
        """Return full property details."""
        if hotel_id == "htl-mock-dxb-01":
            return HotelDetailsResponse(
                hotel_id=hotel_id,
                name="Marina Bay Grand Hotel",
                description="Luxury waterfront resort overlooking Dubai Marina with private beach access and rooftop dining.",
                address="Dubai Marina, Al Marsa Street",
                city="Dubai",
                country="United Arab Emirates",
                star_rating=4.5,
                rooms=[
                    {"room_type": "DELUXE_MARINA_VIEW", "price_per_night": 9500.0, "max_guests": 2},
                    {"room_type": "EXECUTIVE_SUITE", "price_per_night": 16000.0, "max_guests": 3},
                ],
                policies=[
                    "Free cancellation up to 48 hours prior to check-in.",
                    "Check-in time: 15:00, Check-out time: 12:00.",
                ],
                amenities=[
                    "Infinity Pool",
                    "Free High-Speed Wi-Fi",
                    "Full Service Spa",
                    "Valet Parking",
                ],
            )
        elif hotel_id == "htl-mock-dxb-02":
            return HotelDetailsResponse(
                hotel_id=hotel_id,
                name="Downtown Palace Suites",
                description="Ultra-luxury suites in central Downtown Dubai within walking distance of Dubai Mall and Burj Khalifa.",
                address="Sheikh Mohammed bin Rashid Blvd, Downtown Dubai",
                city="Dubai",
                country="United Arab Emirates",
                star_rating=5.0,
                rooms=[
                    {"room_type": "BURJ_VIEW_SUITE", "price_per_night": 14000.0, "max_guests": 2},
                ],
                policies=["Non-refundable within 7 days of arrival."],
                amenities=["Burj Khalifa Views", "Michelin-starred Dining", "Butler Service"],
            )

        raise ProviderInventoryUnavailableException(
            provider_name=self.PROVIDER_NAME,
            message=f"Hotel property '{hotel_id}' not found in supplier inventory",
        )

    def _get_city_inventory(self, city: str, nights: int) -> list[ProviderHotelOffer]:
        city_lower = city.lower()
        if "dubai" in city_lower or "dxb" in city_lower:
            return [
                ProviderHotelOffer(
                    id="off-htl-dxb-01",
                    provider_name=self.PROVIDER_NAME,
                    hotel_id="htl-mock-dxb-01",
                    name="Marina Bay Grand Hotel",
                    address="Dubai Marina, Al Marsa Street",
                    city="Dubai",
                    country="United Arab Emirates",
                    star_rating=4.5,
                    room_type="DELUXE_MARINA_VIEW",
                    price_per_night=8500.0,
                    total_price=8500.0 * nights,
                    currency="INR",
                    free_cancellation=True,
                    breakfast_included=True,
                    amenities=["Pool", "Free WiFi", "Breakfast", "Gym", "Marina View"],
                ),
                ProviderHotelOffer(
                    id="off-htl-dxb-02",
                    provider_name=self.PROVIDER_NAME,
                    hotel_id="htl-mock-dxb-02",
                    name="Downtown Palace Suites",
                    address="Sheikh Mohammed bin Rashid Blvd, Downtown Dubai",
                    city="Dubai",
                    country="United Arab Emirates",
                    star_rating=5.0,
                    room_type="BURJ_VIEW_SUITE",
                    price_per_night=14000.0,
                    total_price=14000.0 * nights,
                    currency="INR",
                    free_cancellation=False,
                    breakfast_included=True,
                    amenities=["Burj Khalifa View", "Luxury Spa", "Fine Dining", "Valet"],
                ),
                ProviderHotelOffer(
                    id="off-htl-dxb-03",
                    provider_name=self.PROVIDER_NAME,
                    hotel_id="htl-mock-dxb-03",
                    name="CityMax Business Inn",
                    address="Al Barsha 1, Near Mall of the Emirates",
                    city="Dubai",
                    country="United Arab Emirates",
                    star_rating=3.5,
                    room_type="STANDARD_ROOM",
                    price_per_night=4200.0,
                    total_price=4200.0 * nights,
                    currency="INR",
                    free_cancellation=True,
                    breakfast_included=False,
                    amenities=["Free WiFi", "Metro Access", "Coffee Shop"],
                ),
            ]
        else:
            # Generic fallback hotel
            return [
                ProviderHotelOffer(
                    id=f"off-htl-gen-{city.lower()}",
                    provider_name=self.PROVIDER_NAME,
                    hotel_id=f"htl-mock-{city.lower()}-01",
                    name=f"Grand Central Hotel {city.title()}",
                    address=f"100 City Center Road, {city.title()}",
                    city=city.title(),
                    country="International",
                    star_rating=4.0,
                    room_type="DELUXE_ROOM",
                    price_per_night=7500.0,
                    total_price=7500.0 * nights,
                    currency="INR",
                    free_cancellation=True,
                    breakfast_included=True,
                    amenities=["WiFi", "Breakfast", "AC"],
                )
            ]
