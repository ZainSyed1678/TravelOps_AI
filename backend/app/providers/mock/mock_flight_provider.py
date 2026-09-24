"""Mock Flight Provider simulating realistic GDS/NDC flight inventory."""

import time
from datetime import UTC, date, datetime, timedelta

from app.caching import cached
from app.core.logging import logger
from app.providers.base import FlightProvider
from app.providers.schemas import (
    FlightPricingResponse,
    FlightSearchResponse,
    FlightStatusResponse,
    ProviderFlightOffer,
)
from app.schemas.travel import FlightSearchQuery


class MockFlightProvider(FlightProvider):
    """Deterministic Mock Flight Provider with realistic airline networks and fare rules."""

    PROVIDER_NAME = "MOCK_GDS"

    def __init__(self, simulated_latency_ms: float = 20.0):
        self.simulated_latency_ms = simulated_latency_ms

    @cached(
        ttl_seconds=180,
        namespace="travelops:flights",
        tags=["flight_search"],
    )
    async def search_flights(self, query: FlightSearchQuery) -> FlightSearchResponse:
        """Generate realistic flight search offers for given route."""
        start_time = time.perf_counter()
        orig = query.origin.upper().strip()
        dest = query.destination.upper().strip()
        dep_date = query.departure_date

        logger.info(
            f"[{self.PROVIDER_NAME}] Searching flights {orig} -> {dest} for {dep_date} (passengers: {query.adults})"
        )

        offers: list[ProviderFlightOffer] = []

        # Route templates for common travel corridors
        if (orig == "BOM" and dest == "DXB") or (orig == "DXB" and dest == "BOM"):
            offers.extend(self._get_bom_dxb_offers(orig, dest, dep_date, query))
        elif (orig == "DEL" and dest == "LHR") or (orig == "LHR" and dest == "DEL"):
            offers.extend(self._get_del_lhr_offers(orig, dest, dep_date, query))
        else:
            # Generic fallback route offers
            offers.extend(self._get_generic_offers(orig, dest, dep_date, query))

        # Filter by budget if provided
        if query.max_budget is not None:
            offers = [o for o in offers if o.total_price <= query.max_budget]

        # Filter by stops if provided
        if query.max_stops is not None:
            offers = [o for o in offers if o.stops <= query.max_stops]

        latency = (time.perf_counter() - start_time) * 1000 + self.simulated_latency_ms

        return FlightSearchResponse(
            offers=offers,
            total_offers=len(offers),
            provider_source=self.PROVIDER_NAME,
            latency_ms=round(latency, 2),
        )

    async def price_flight(
        self,
        offer_id: str,
        fare_basis: str | None = None,
    ) -> FlightPricingResponse:
        """Confirm live pricing for an offer."""
        base_fare = 15000.0
        taxes = 3500.0
        if "AI" in offer_id:
            base_fare = 12500.0
            taxes = 2700.0
        elif "6E" in offer_id:
            base_fare = 10500.0
            taxes = 2400.0

        total_price = base_fare + taxes
        valid_until = datetime.now(UTC) + timedelta(minutes=30)

        return FlightPricingResponse(
            offer_id=offer_id,
            base_fare=base_fare,
            taxes=taxes,
            total_price=total_price,
            currency="INR",
            valid_until=valid_until,
            is_price_guaranteed=True,
            provider_source=self.PROVIDER_NAME,
        )

    async def get_flight_status(
        self,
        flight_number: str,
        departure_date: date,
    ) -> FlightStatusResponse:
        """Return operational or disruption flight status."""
        fn = flight_number.upper().strip()

        # Simulate disruption scenarios for testing
        if "CANCEL" in fn or fn == "EK505-CANCELLED":
            return FlightStatusResponse(
                flight_number=flight_number,
                departure_date=departure_date,
                status="CANCELLED",
                delay_minutes=0,
                remarks="Flight cancelled due to air traffic control restrictions. Eligible for rebooking/refund.",
            )
        elif "DELAY" in fn:
            return FlightStatusResponse(
                flight_number=flight_number,
                departure_date=departure_date,
                status="DELAYED",
                delay_minutes=150,
                terminal="Terminal 2",
                gate="B22",
                remarks="Delayed 2h 30m due to inbound aircraft delay.",
            )

        # Standard on-time status
        return FlightStatusResponse(
            flight_number=flight_number,
            departure_date=departure_date,
            status="ON_TIME",
            delay_minutes=0,
            terminal="Terminal 2",
            gate="A12",
            remarks="Flight operating on schedule.",
        )

    # --------------------------------------------------------------------------
    # Helper Route Builders
    # --------------------------------------------------------------------------

    def _get_bom_dxb_offers(
        self,
        orig: str,
        dest: str,
        dep_date: date,
        query: FlightSearchQuery,
    ) -> list[ProviderFlightOffer]:
        base_time = datetime.combine(dep_date, datetime.min.time()).replace(tzinfo=UTC)

        return [
            ProviderFlightOffer(
                id=f"off-mock-ek505-{dep_date.isoformat()}",
                provider_name=self.PROVIDER_NAME,
                flight_number="EK505",
                airline_code="EK",
                airline_name="Emirates",
                origin_airport=orig,
                destination_airport=dest,
                departure_time=base_time.replace(hour=10, minute=15),
                arrival_time=base_time.replace(hour=12, minute=45),
                duration_minutes=210,
                stops=0,
                aircraft_type="Boeing 777-300ER",
                cabin_class=query.cabin_class,
                base_fare=15200.0 * query.adults,
                taxes=3300.0 * query.adults,
                total_price=18500.0 * query.adults,
                currency="INR",
                is_refundable=True,
                baggage_allowance="30kg Check-in + 7kg Cabin",
                seats_available=7,
                raw_metadata={"fare_basis": "EE20SAVER", "alliance": None},
            ),
            ProviderFlightOffer(
                id=f"off-mock-ai915-{dep_date.isoformat()}",
                provider_name=self.PROVIDER_NAME,
                flight_number="AI915",
                airline_code="AI",
                airline_name="Air India",
                origin_airport=orig,
                destination_airport=dest,
                departure_time=base_time.replace(hour=7, minute=30),
                arrival_time=base_time.replace(hour=10, minute=15),
                duration_minutes=225,
                stops=0,
                aircraft_type="Airbus A321neo",
                cabin_class=query.cabin_class,
                base_fare=12400.0 * query.adults,
                taxes=2800.0 * query.adults,
                total_price=15200.0 * query.adults,
                currency="INR",
                is_refundable=True,
                baggage_allowance="25kg Check-in + 7kg Cabin",
                seats_available=9,
                raw_metadata={"fare_basis": "AIFLEX", "alliance": "Star Alliance"},
            ),
            ProviderFlightOffer(
                id=f"off-mock-6e1451-{dep_date.isoformat()}",
                provider_name=self.PROVIDER_NAME,
                flight_number="6E1451",
                airline_code="6E",
                airline_name="IndiGo",
                origin_airport=orig,
                destination_airport=dest,
                departure_time=base_time.replace(hour=16, minute=45),
                arrival_time=base_time.replace(hour=19, minute=20),
                duration_minutes=215,
                stops=0,
                aircraft_type="Airbus A320neo",
                cabin_class=query.cabin_class,
                base_fare=10800.0 * query.adults,
                taxes=2100.0 * query.adults,
                total_price=12900.0 * query.adults,
                currency="INR",
                is_refundable=False,
                baggage_allowance="15kg Check-in + 7kg Cabin",
                seats_available=14,
                raw_metadata={"fare_basis": "SAVER6E", "alliance": None},
            ),
        ]

    def _get_del_lhr_offers(
        self,
        orig: str,
        dest: str,
        dep_date: date,
        query: FlightSearchQuery,
    ) -> list[ProviderFlightOffer]:
        base_time = datetime.combine(dep_date, datetime.min.time()).replace(tzinfo=UTC)

        return [
            ProviderFlightOffer(
                id=f"off-mock-ba142-{dep_date.isoformat()}",
                provider_name=self.PROVIDER_NAME,
                flight_number="BA142",
                airline_code="BA",
                airline_name="British Airways",
                origin_airport=orig,
                destination_airport=dest,
                departure_time=base_time.replace(hour=3, minute=15),
                arrival_time=base_time.replace(hour=8, minute=20),
                duration_minutes=545,
                stops=0,
                aircraft_type="Boeing 787-9 Dreamliner",
                cabin_class=query.cabin_class,
                base_fare=48000.0 * query.adults,
                taxes=12000.0 * query.adults,
                total_price=60000.0 * query.adults,
                currency="INR",
                is_refundable=True,
                baggage_allowance="23kg Check-in + 10kg Cabin",
                seats_available=5,
                raw_metadata={"alliance": "Oneworld"},
            ),
        ]

    def _get_generic_offers(
        self,
        orig: str,
        dest: str,
        dep_date: date,
        query: FlightSearchQuery,
    ) -> list[ProviderFlightOffer]:
        base_time = datetime.combine(dep_date, datetime.min.time()).replace(tzinfo=UTC)

        return [
            ProviderFlightOffer(
                id=f"off-mock-gen1-{orig}-{dest}-{dep_date.isoformat()}",
                provider_name=self.PROVIDER_NAME,
                flight_number="TO101",
                airline_code="TO",
                airline_name="TravelOps Express",
                origin_airport=orig,
                destination_airport=dest,
                departure_time=base_time.replace(hour=9, minute=0),
                arrival_time=base_time.replace(hour=11, minute=30),
                duration_minutes=150,
                stops=0,
                aircraft_type="Airbus A320",
                cabin_class=query.cabin_class,
                base_fare=11000.0 * query.adults,
                taxes=2500.0 * query.adults,
                total_price=13500.0 * query.adults,
                currency="INR",
                is_refundable=True,
                baggage_allowance="20kg Check-in",
                seats_available=8,
            )
        ]
