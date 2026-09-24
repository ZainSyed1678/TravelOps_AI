"""Initial travel schema with 17 core entities and indexes.

Revision ID: 0001_initial_travel_schema
Revises:
Create Date: 2026-09-24 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_travel_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="TRAVELER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_users_email", "users", ["email"])

    # 2. travelers
    op.create_table(
        "travelers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("nationality", sa.String(3), nullable=True),
        sa.Column("passport_number", sa.String(50), nullable=True),
        sa.Column("frequent_flyer_number", sa.String(100), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 3. travel_documents
    op.create_table(
        "travel_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "traveler_id",
            sa.String(36),
            sa.ForeignKey("travelers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("document_number", sa.String(100), nullable=False),
        sa.Column("issuing_country", sa.String(3), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("document_url", sa.String(500), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 4. airports
    op.create_table(
        "airports",
        sa.Column("id", sa.String(3), primary_key=True),
        sa.Column("icao_code", sa.String(4), unique=True, nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_airports_city", "airports", ["city"])
    op.create_index("idx_airports_country", "airports", ["country"])

    # 5. airlines
    op.create_table(
        "airlines",
        sa.Column("id", sa.String(2), primary_key=True),
        sa.Column("icao_code", sa.String(3), unique=True, nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("alliance", sa.String(50), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 6. flights
    op.create_table(
        "flights",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("flight_number", sa.String(20), nullable=False),
        sa.Column("airline_code", sa.String(2), sa.ForeignKey("airlines.id"), nullable=False),
        sa.Column(
            "origin_airport_code", sa.String(3), sa.ForeignKey("airports.id"), nullable=False
        ),
        sa.Column(
            "destination_airport_code", sa.String(3), sa.ForeignKey("airports.id"), nullable=False
        ),
        sa.Column("departure_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("stops", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("aircraft_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="SCHEDULED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_flight_origin_dest_date",
        "flights",
        ["origin_airport_code", "destination_airport_code", "departure_time"],
    )

    # 7. flight_segments
    op.create_table(
        "flight_segments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "flight_id",
            sa.String(36),
            sa.ForeignKey("flights.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column(
            "origin_airport_code", sa.String(3), sa.ForeignKey("airports.id"), nullable=False
        ),
        sa.Column(
            "destination_airport_code", sa.String(3), sa.ForeignKey("airports.id"), nullable=False
        ),
        sa.Column("departure_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("operating_carrier", sa.String(2), sa.ForeignKey("airlines.id"), nullable=False),
        sa.Column("marketing_carrier", sa.String(2), sa.ForeignKey("airlines.id"), nullable=False),
        sa.Column("aircraft_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 8. fares
    op.create_table(
        "fares",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("airline_code", sa.String(2), sa.ForeignKey("airlines.id"), nullable=False),
        sa.Column("fare_basis_code", sa.String(50), nullable=False),
        sa.Column("cabin_class", sa.String(50), nullable=False),
        sa.Column("is_refundable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("change_allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("cancellation_fee", sa.Float(), nullable=True),
        sa.Column("change_fee", sa.Float(), nullable=True),
        sa.Column(
            "baggage_allowance", sa.String(100), nullable=False, server_default="1 piece (23kg)"
        ),
        sa.Column("rules", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_fares_code", "fares", ["fare_basis_code"])

    # 9. hotels
    op.create_table(
        "hotels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("chain", sa.String(100), nullable=True),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("star_rating", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("amenities", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_hotels_city", "hotels", ["city"])

    # 10. rooms
    op.create_table(
        "rooms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "hotel_id",
            sa.String(36),
            sa.ForeignKey("hotels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("room_type", sa.String(100), nullable=False),
        sa.Column("max_occupancy", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("base_price_per_night", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("amenities", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 11. suppliers
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("supplier_type", sa.String(50), nullable=False),
        sa.Column("api_endpoint", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_suppliers_code", "suppliers", ["code"])

    # 12. policies
    op.create_table(
        "policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(50), nullable=False),
        sa.Column("policy_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("terms", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_policy_entity_type",
        "policies",
        ["entity_type", "entity_id", "policy_type"],
    )

    # 13. trips
    op.create_table(
        "trips",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PLANNED"),
        sa.Column("budget", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 14. bookings
    op.create_table(
        "bookings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_reference", sa.String(20), nullable=False, unique=True),
        sa.Column(
            "trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "supplier_id",
            sa.String(36),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("booking_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("supplier_reference", sa.String(100), nullable=True),
        sa.Column(
            "confirmation_required", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_booking_ref", "bookings", ["booking_reference"])
    op.create_index("idx_booking_user_status", "bookings", ["user_id", "status"])

    # 15. passengers
    op.create_table(
        "passengers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "booking_id",
            sa.String(36),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "traveler_id",
            sa.String(36),
            sa.ForeignKey("travelers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("passenger_type", sa.String(20), nullable=False, server_default="ADULT"),
        sa.Column("seat_number", sa.String(10), nullable=True),
        sa.Column("ticket_number", sa.String(50), nullable=True),
        sa.Column("special_requests", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 16. hotel_bookings
    op.create_table(
        "hotel_bookings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "booking_id",
            sa.String(36),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hotel_id", sa.String(36), sa.ForeignKey("hotels.id"), nullable=False),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("check_in_date", sa.Date(), nullable=False),
        sa.Column("check_out_date", sa.Date(), nullable=False),
        sa.Column("number_of_guests", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_price", sa.Float(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="CONFIRMED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 17. payments
    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "booking_id",
            sa.String(36),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("payment_method", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("transaction_reference", sa.String(100), nullable=True, unique=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("hotel_bookings")
    op.drop_table("passengers")
    op.drop_table("bookings")
    op.drop_table("trips")
    op.drop_table("policies")
    op.drop_table("suppliers")
    op.drop_table("rooms")
    op.drop_table("hotels")
    op.drop_table("fares")
    op.drop_table("flight_segments")
    op.drop_table("flights")
    op.drop_table("airlines")
    op.drop_table("airports")
    op.drop_table("travel_documents")
    op.drop_table("travelers")
    op.drop_table("users")
