"""Comprehensive test suite for Phase 5: Neo4j Knowledge Graph & Traversal."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.graph.ingestion import sync_knowledge_graph
from app.graph.service import GraphService, graph_service
from app.main import app


@pytest.fixture
def clean_graph_service():
    """Provides a fresh isolated GraphService instance for testing."""
    service = GraphService()
    # Ensure memory graph is clean
    service._mem_graph.clear()
    return service


def test_graph_schema_initialization(clean_graph_service):
    """Verify schema constraints can be called without errors."""
    clean_graph_service.initialize_schema()
    assert True


def test_upsert_all_twelve_entities_and_relationships(clean_graph_service):
    """Verify upsert of all 12 travel domain entities and their relationships."""
    # 1. Country & City
    clean_graph_service.upsert_country("France")
    clean_graph_service.upsert_city("Paris", "France")
    assert clean_graph_service._mem_graph.has_node("France")
    assert clean_graph_service._mem_graph.has_node("Paris")
    assert clean_graph_service._mem_graph.has_edge("Paris", "France")

    # 2. Airport
    clean_graph_service.upsert_airport(
        id="CDG",
        name="Charles de Gaulle Airport",
        city_name="Paris",
        country_name="France",
        icao="LFPG",
        latitude=49.0097,
        longitude=2.5479,
        timezone="Europe/Paris",
    )
    assert clean_graph_service._mem_graph.has_node("CDG")
    assert clean_graph_service._mem_graph.has_edge("CDG", "Paris")

    # Destination Airport
    clean_graph_service.upsert_city("Nice", "France")
    clean_graph_service.upsert_airport(
        id="NCE",
        name="Nice Cote d'Azur Airport",
        city_name="Nice",
        country_name="France",
    )

    # 3. Airline
    clean_graph_service.upsert_airline(
        id="AF",
        name="Air France",
        country="France",
        alliance="SkyTeam",
    )
    assert clean_graph_service._mem_graph.has_node("AF")

    # 4. Route
    clean_graph_service.upsert_route(origin="CDG", destination="NCE", distance_km=680.0)
    assert clean_graph_service._mem_graph.has_node("CDG-NCE")
    assert clean_graph_service._mem_graph.has_edge("CDG-NCE", "CDG")
    assert clean_graph_service._mem_graph.has_edge("CDG-NCE", "NCE")

    # 5. Flight
    clean_graph_service.upsert_flight(
        flight_number="AF7700",
        airline_code="AF",
        origin_code="CDG",
        destination_code="NCE",
        departure_time="09:00",
        arrival_time="10:30",
        duration_minutes=90,
        stops=0,
        aircraft_type="A320",
    )
    assert clean_graph_service._mem_graph.has_node("AF7700")
    assert clean_graph_service._mem_graph.has_edge("AF", "AF7700")
    assert clean_graph_service._mem_graph.has_edge("AF7700", "CDG")
    assert clean_graph_service._mem_graph.has_edge("AF7700", "NCE")

    # 6. Hotel
    clean_graph_service.upsert_hotel(
        id="HTL-NCE-01",
        name="Hotel Negresco",
        city_name="Nice",
        address="37 Promenade des Anglais",
        star_rating=5.0,
    )
    assert clean_graph_service._mem_graph.has_node("HTL-NCE-01")
    assert clean_graph_service._mem_graph.has_edge("HTL-NCE-01", "Nice")

    # 7. Supplier
    clean_graph_service.upsert_supplier(code="1A", name="Amadeus", supplier_type="GDS")
    clean_graph_service.link_supplier_flight("1A", "AF7700")
    assert clean_graph_service._mem_graph.has_node("1A")
    assert clean_graph_service._mem_graph.has_edge("1A", "AF7700")

    # 8. Policy & 9. Document
    clean_graph_service.upsert_policy(
        id="POL-AF-01",
        entity_type="AIRLINE",
        entity_id="AF",
        policy_type="CANCELLATION",
        title="Air France Cancellation Rules",
        content="Free cancellation within 24 hours.",
    )
    assert clean_graph_service._mem_graph.has_node("POL-AF-01")
    assert clean_graph_service._mem_graph.has_edge("AF", "POL-AF-01")

    clean_graph_service.upsert_document(
        id="DOC-AF-01",
        title="AF Policy Doc",
        source="af_policy.html",
        document_type="POLICY",
        policy_id="POL-AF-01",
    )
    assert clean_graph_service._mem_graph.has_node("DOC-AF-01")
    assert clean_graph_service._mem_graph.has_edge("DOC-AF-01", "POL-AF-01")

    # 10. Fare
    clean_graph_service.upsert_fare(
        id="FARE-AF7700-01",
        fare_basis="AF-FLEX",
        cabin_class="ECONOMY",
        refundable=True,
        change_fee=0.0,
        cancellation_fee=100.0,
        flight_number="AF7700",
    )
    assert clean_graph_service._mem_graph.has_node("FARE-AF7700-01")
    assert clean_graph_service._mem_graph.has_edge("AF7700", "FARE-AF7700-01")

    # 11. Booking
    clean_graph_service.upsert_booking(
        reference="BK-AF-999",
        flight_number="AF7700",
        status="CONFIRMED",
        total_amount=150.0,
        currency="EUR",
    )
    assert clean_graph_service._mem_graph.has_node("BK-AF-999")
    assert clean_graph_service._mem_graph.has_edge("BK-AF-999", "AF7700")


def test_flight_full_context_traversal(clean_graph_service):
    """Verify multi-hop flight context retrieval traversing nodes and edges."""
    clean_graph_service.upsert_city("Mumbai", "India")
    clean_graph_service.upsert_city("Dubai", "United Arab Emirates")
    clean_graph_service.upsert_airport(id="BOM", name="Mumbai Airport", city_name="Mumbai", country_name="India")
    clean_graph_service.upsert_airport(id="DXB", name="Dubai Airport", city_name="Dubai", country_name="United Arab Emirates")
    clean_graph_service.upsert_airline(id="EK", name="Emirates", country="UAE")
    clean_graph_service.upsert_flight("EK505", "EK", "BOM", "DXB", "10:00", "12:30", 210)
    clean_graph_service.upsert_fare("FARE-EK", "EK-SAVER", "ECONOMY", True, 5000.0, 7000.0, "EK505")
    clean_graph_service.upsert_policy("POL-EK", "AIRLINE", "EK", "CANCELLATION", "EK Canc Policy", "Content")
    clean_graph_service.upsert_document("DOC-EK", "EK Doc", "doc.html", "POLICY", policy_id="POL-EK")

    ctx = clean_graph_service.get_flight_context("EK505")
    assert ctx is not None
    assert ctx.flight_number == "EK505"
    assert ctx.airline["name"] == "Emirates"
    assert ctx.origin_airport["id"] == "BOM"
    assert ctx.destination_airport["id"] == "DXB"
    assert ctx.destination_city["name"] == "Dubai"
    assert len(ctx.fares) >= 1
    assert len(ctx.policies) >= 1
    assert len(ctx.documents) >= 1


def test_airline_policies_and_filtering(clean_graph_service):
    """Verify airline policies and policy_type filter."""
    clean_graph_service.upsert_airline(id="AI", name="Air India", country="India")
    clean_graph_service.upsert_policy("POL-AI-1", "AIRLINE", "AI", "CANCELLATION", "Cancellation Rules", "Rules")
    clean_graph_service.upsert_policy("POL-AI-2", "AIRLINE", "AI", "BAGGAGE", "Baggage Rules", "Rules")

    all_policies = clean_graph_service.get_airline_policies("AI")
    assert len(all_policies) == 2

    cancellation_only = clean_graph_service.get_airline_policies("AI", policy_type="CANCELLATION")
    assert len(cancellation_only) == 1
    assert cancellation_only[0]["policy"]["id"] == "POL-AI-1"


def test_destination_hotels_traversal(clean_graph_service):
    """Verify destination hotel discovery through Airport -> City <- Hotel."""
    clean_graph_service.upsert_city("Dubai", "UAE")
    clean_graph_service.upsert_airport(id="DXB", name="Dubai Airport", city_name="Dubai", country_name="UAE")
    clean_graph_service.upsert_hotel("HTL-1", "Hotel One", "Dubai", "Address 1", 4.5)
    clean_graph_service.upsert_hotel("HTL-2", "Hotel Two", "Dubai", "Address 2", 5.0)

    hotels = clean_graph_service.get_destination_hotels("DXB", limit=5)
    assert len(hotels) == 2
    hotel_ids = {h["id"] for h in hotels}
    assert "HTL-1" in hotel_ids
    assert "HTL-2" in hotel_ids


def test_booking_context_traversal(clean_graph_service):
    """Verify booking lineage back to flight, airline, and policies."""
    clean_graph_service.upsert_city("Delhi", "India")
    clean_graph_service.upsert_city("London", "UK")
    clean_graph_service.upsert_airport(id="DEL", name="Delhi Airport", city_name="Delhi", country_name="India")
    clean_graph_service.upsert_airport(id="LHR", name="Heathrow", city_name="London", country_name="UK")
    clean_graph_service.upsert_airline(id="BA", name="British Airways", country="UK")
    clean_graph_service.upsert_flight("BA142", "BA", "DEL", "LHR", "03:15", "08:20", 545)
    clean_graph_service.upsert_policy("POL-BA", "AIRLINE", "BA", "CANCELLATION", "BA Policy", "Content")
    clean_graph_service.upsert_booking("BK-BA-123", flight_number="BA142", status="CONFIRMED", total_amount=500.0)

    b_ctx = clean_graph_service.get_booking_context("BK-BA-123")
    assert b_ctx is not None
    assert b_ctx.booking_reference == "BK-BA-123"
    assert b_ctx.status == "CONFIRMED"
    assert b_ctx.airline is not None
    assert b_ctx.airline["name"] == "British Airways"
    assert b_ctx.origin["id"] == "DEL"
    assert b_ctx.destination["id"] == "LHR"
    assert len(b_ctx.applicable_policies) >= 1


def test_graph_ingestion_pipeline():
    """Verify batch ingestion pipeline runs and returns populated counts."""
    stats = sync_knowledge_graph(service=graph_service)
    assert stats["airports"] >= 8
    assert stats["airlines"] >= 5
    assert stats["routes"] >= 4
    assert stats["flights"] >= 5
    assert stats["hotels"] >= 3
    assert stats["suppliers"] >= 5
    assert stats["policies"] >= 3
    assert stats["fares"] >= 5
    assert stats["bookings"] >= 3


@pytest.mark.asyncio
async def test_graph_api_endpoints():
    """Verify HTTP endpoints for graph traversal and sync."""
    # Ensure graph is synchronized
    sync_knowledge_graph(service=graph_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Flight context endpoint
        res = await client.get("/api/v1/graph/flight/EK505")
        assert res.status_code == 200
        data = res.json()
        assert data["flight_number"] == "EK505"
        assert data["origin_airport"]["id"] == "BOM"
        assert data["destination_airport"]["id"] == "DXB"
        assert len(data["fares"]) > 0

        # Flight not found -> 404
        res_404 = await client.get("/api/v1/graph/flight/NONEXISTENT99")
        assert res_404.status_code == 404

        # 2. Airline policies endpoint
        res_pol = await client.get("/api/v1/graph/airline/AI/policies")
        assert res_pol.status_code == 200
        pol_data = res_pol.json()
        assert len(pol_data) >= 1
        assert "policy" in pol_data[0]

        # 3. Destination hotels endpoint
        res_htl = await client.get("/api/v1/graph/destination/DXB/hotels")
        assert res_htl.status_code == 200
        htl_data = res_htl.json()
        assert len(htl_data) >= 1

        # 4. Booking context endpoint
        res_bk = await client.get("/api/v1/graph/booking/BK-EK505-001")
        assert res_bk.status_code == 200
        bk_data = res_bk.json()
        assert bk_data["booking_reference"] == "BK-EK505-001"
        assert bk_data["status"] == "CONFIRMED"

        # Booking not found -> 404
        res_bk_404 = await client.get("/api/v1/graph/booking/UNKNOWN_REF")
        assert res_bk_404.status_code == 404

        # 5. Graph sync endpoint
        res_sync = await client.post("/api/v1/graph/sync")
        assert res_sync.status_code == 200
        sync_res = res_sync.json()
        assert sync_res["status"] == "SUCCESS"
        assert sync_res["entities_synced"]["flights"] >= 5
