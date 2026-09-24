"""Mock Booking Provider simulating GDS/NDC ticketing and servicing."""

import random
import string
from datetime import UTC, datetime

from app.core.logging import logger
from app.providers.base import BookingProvider
from app.providers.exceptions import (
    ProviderValidationException,
)
from app.providers.schemas import (
    CancellationResponse,
    ProviderBookingRequest,
    ProviderBookingResponse,
    RebookResponse,
)


class MockBookingProvider(BookingProvider):
    """Deterministic Mock Booking Provider managing reservation lifecycles and servicing."""

    PROVIDER_NAME = "MOCK_GDS_BOOKING"

    def __init__(self):
        # Simulated supplier PNR memory store
        self._reservations: dict[str, dict] = {}

    def _generate_pnr(self) -> str:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"PNR-{code}"

    async def create_booking(
        self,
        request: ProviderBookingRequest,
    ) -> ProviderBookingResponse:
        """Create and ticket reservation with mock supplier."""
        if request.total_amount <= 0:
            raise ProviderValidationException(
                provider_name=self.PROVIDER_NAME,
                message="Total booking amount must be greater than zero",
            )

        pnr = self._generate_pnr()
        confirmed_time = datetime.now(UTC)

        # Generate ticket numbers
        ticket_numbers = [
            f"176-{random.randint(1000000000, 9999999999)}"
            for _ in range(max(1, len(request.passengers)))
        ]

        booking_record = {
            "booking_reference": request.booking_reference,
            "pnr": pnr,
            "user_id": request.user_id,
            "booking_type": request.booking_type,
            "offer_id": request.offer_id,
            "status": "CONFIRMED",
            "total_amount": request.total_amount,
            "currency": request.currency,
            "confirmed_at": confirmed_time,
            "ticket_numbers": ticket_numbers,
            "passengers": request.passengers,
        }
        self._reservations[request.booking_reference] = booking_record

        logger.info(
            f"[{self.PROVIDER_NAME}] Successfully created booking {request.booking_reference} (PNR: {pnr})"
        )

        return ProviderBookingResponse(
            booking_reference=request.booking_reference,
            pnr=pnr,
            provider_name=self.PROVIDER_NAME,
            status="CONFIRMED",
            confirmed_at=confirmed_time,
            total_amount=request.total_amount,
            currency=request.currency,
            ticket_numbers=ticket_numbers,
            raw_details=booking_record,
        )

    async def get_booking(self, booking_reference: str) -> ProviderBookingResponse:
        """Fetch booking by reference."""
        record = self._reservations.get(booking_reference)
        if not record:
            # Generate plausible fallback booking if not in local memory
            pnr = self._generate_pnr()
            now = datetime.now(UTC)
            return ProviderBookingResponse(
                booking_reference=booking_reference,
                pnr=pnr,
                provider_name=self.PROVIDER_NAME,
                status="CONFIRMED",
                confirmed_at=now,
                total_amount=18500.0,
                currency="INR",
                ticket_numbers=[f"176-{random.randint(1000000000, 9999999999)}"],
                raw_details={"source": "simulated_lookup"},
            )

        return ProviderBookingResponse(
            booking_reference=record["booking_reference"],
            pnr=record["pnr"],
            provider_name=self.PROVIDER_NAME,
            status=record["status"],
            confirmed_at=record["confirmed_at"],
            total_amount=record["total_amount"],
            currency=record["currency"],
            ticket_numbers=record["ticket_numbers"],
            raw_details=record,
        )

    async def cancel_booking(
        self,
        booking_reference: str,
        reason: str | None = None,
    ) -> CancellationResponse:
        """Cancel reservation and calculate penalty and refund."""
        record = self._reservations.get(booking_reference)
        original_amount = record["total_amount"] if record else 18500.0
        currency = record["currency"] if record else "INR"

        # Apply standard simulated fare cancellation rules
        penalty_amount = 3000.0 if original_amount > 10000 else 1500.0
        refund_amount = max(0.0, original_amount - penalty_amount)

        if record:
            record["status"] = "CANCELLED"

        logger.info(
            f"[{self.PROVIDER_NAME}] Cancelled booking {booking_reference}. Penalty: {penalty_amount} {currency}, Refund: {refund_amount} {currency}"
        )

        return CancellationResponse(
            booking_reference=booking_reference,
            cancellation_id=f"CNL-{random.randint(100000, 999999)}",
            status="CANCELLED",
            original_amount=original_amount,
            penalty_amount=penalty_amount,
            refund_amount=refund_amount,
            currency=currency,
            message="Reservation successfully cancelled in GDS. Refund initiated to original payment source.",
        )

    async def rebook_booking(
        self,
        booking_reference: str,
        new_flight_id: str,
    ) -> RebookResponse:
        """Rebook reservation onto alternate itinerary."""
        record = self._reservations.get(booking_reference)
        original_fare = record["total_amount"] if record else 15200.0
        currency = record["currency"] if record else "INR"

        # Simulate price of new alternative flight
        new_flight_fare = 18500.0
        price_difference = max(0.0, new_flight_fare - original_fare)
        change_fee = 2000.0
        total_due = price_difference + change_fee

        new_booking_ref = f"{booking_reference}-REB"
        new_pnr = self._generate_pnr()

        if record:
            record["status"] = "REBOOKED"
            record["new_booking_reference"] = new_booking_ref

        logger.info(
            f"[{self.PROVIDER_NAME}] Rebooked {booking_reference} -> {new_booking_ref} (PNR: {new_pnr}). Total due: {total_due} {currency}"
        )

        return RebookResponse(
            original_booking_reference=booking_reference,
            new_booking_reference=new_booking_ref,
            new_pnr=new_pnr,
            status="REBOOKED",
            price_difference=price_difference,
            penalty_fee=change_fee,
            total_amount_due=total_due,
            currency=currency,
            message="Rebooking successful. New itinerary confirmed with supplier.",
        )
