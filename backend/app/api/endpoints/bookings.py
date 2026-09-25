"""Production Booking Management REST API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.api_response import ApiResponse, api_success
from app.core.database import get_db_session
from app.core.exceptions import NotFoundError
from app.models.entities import Booking, Passenger
from app.schemas.travel import BookingCreate, BookingRead

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[list[BookingRead]],
    summary="List Bookings",
    description="Retrieve travel reservations filtered by user, status, with pagination support.",
)
async def list_bookings(
    user_id: str | None = Query(default=None, description="Filter by user ID"),
    booking_status: str | None = Query(default=None, alias="status", description="Filter by status (e.g. CONFIRMED, PENDING)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[BookingRead]]:
    """List bookings with pagination and filters."""
    query = select(Booking).options(selectinload(Booking.passengers), selectinload(Booking.payments))
    count_query = select(func.count(Booking.id))

    if user_id:
        query = query.where(Booking.user_id == user_id)
        count_query = count_query.where(Booking.user_id == user_id)
    if booking_status:
        query = query.where(Booking.status == booking_status.upper())
        count_query = count_query.where(Booking.status == booking_status.upper())

    total_count_res = await session.execute(count_query)
    total_count = total_count_res.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Booking.created_at.desc())

    result = await session.execute(query)
    bookings = result.scalars().all()

    # Convert to Pydantic models
    dtos = [BookingRead.model_validate(b) for b in bookings]

    return api_success(
        data=dtos,
        message=f"Retrieved {len(dtos)} bookings",
        total=total_count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{booking_id}",
    response_model=ApiResponse[BookingRead],
    summary="Get Booking Details",
    description="Retrieve full reservation details by unique booking ID or PNR booking reference.",
)
async def get_booking(
    booking_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[BookingRead]:
    """Retrieve a booking by UUID or booking reference."""
    query = (
        select(Booking)
        .options(selectinload(Booking.passengers), selectinload(Booking.payments))
        .where((Booking.id == booking_id) | (Booking.booking_reference == booking_id))
    )
    result = await session.execute(query)
    booking = result.scalar_one_or_none()

    if not booking:
        raise NotFoundError(f"Booking with identifier '{booking_id}' was not found")

    return api_success(
        data=BookingRead.model_validate(booking),
        message=f"Booking {booking.booking_reference} retrieved successfully",
    )


@router.post(
    "",
    response_model=ApiResponse[BookingRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create Travel Booking",
    description="Persist a new flight, hotel, or multi-modal booking with associated passengers.",
)
async def create_booking(
    payload: BookingCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[BookingRead]:
    """Create and persist a new travel booking."""
    booking_ref = f"TRV-BK-{uuid.uuid4().hex[:6].upper()}"

    booking = Booking(
        booking_reference=booking_ref,
        user_id=payload.user_id,
        trip_id=payload.trip_id,
        supplier_id=payload.supplier_id,
        booking_type=payload.booking_type.upper(),
        status="CONFIRMED",
        total_amount=payload.total_amount,
        currency=payload.currency,
        confirmation_required=False,
        metadata_json=payload.metadata_json or {},
    )
    session.add(booking)
    await session.flush()

    for p in payload.passengers:
        passenger = Passenger(
            booking_id=booking.id,
            traveler_id=p.traveler_id,
            passenger_type=p.passenger_type,
            seat_number=p.seat_number,
            ticket_number=f"TKT-{uuid.uuid4().hex[:8].upper()}",
            special_requests=p.special_requests,
        )
        session.add(passenger)

    await session.commit()

    # Re-query with relations loaded
    query = (
        select(Booking)
        .options(selectinload(Booking.passengers), selectinload(Booking.payments))
        .where(Booking.id == booking.id)
    )
    res = await session.execute(query)
    saved_booking = res.scalar_one()

    return api_success(
        data=BookingRead.model_validate(saved_booking),
        message=f"Booking {booking_ref} created successfully",
        status_code=status.HTTP_201_CREATED,
    )
