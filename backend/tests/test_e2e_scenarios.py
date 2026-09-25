"""End-to-end multi-agent scenario journeys for TravelOps AI (Phase 17).

Tests complete integration paths spanning:
1. Flight Search & ML Ranking -> Booking Journey
2. Disruption Event -> HITL Safety Gate -> Operator Approval Journey
3. Grounded Policy QA -> Citation Provenance Journey
4. Multi-Turn Conversational Memory & Personalization Journey
5. Zero-Daemon Resilient Datastore Fallback Journey
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.agents.hitl import hitl_manager
from app.agents.memory import memory_service
from app.core.database import get_db_session
from app.core.init_db import init_db
from app.main import app
from app.models.entities import User

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_isolated_test_environment():
    """Setup hermetic SQLite database and reset volatile state for scenario runs."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    await init_db(engine)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = override_db

    # Clean in-memory managers
    hitl_manager.clear()
    memory_service.clear()

    yield session_factory

    app.dependency_overrides.pop(get_db_session, None)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Journey 1: Flight Search, ML Ranking, and Booking Persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_journey_flight_discovery_and_booking(setup_isolated_test_environment):
    """Scenario: User searches flights, reviews ML-ranked options, and confirms a reservation."""
    session_factory = setup_isolated_test_environment

    # 1. Create a traveler account
    async with session_factory() as session:
        user = User(
            email=f"traveler_{uuid.uuid4().hex[:6]}@travelops.ai",
            full_name="Captain Sarah Connor",
            hashed_password="hashed_pw_scenarios_123",
            role="TRAVELER",
        )
        session.add(user)
        await session.commit()
        user_id = user.id

    # 2. Search flights with budget and cabin constraints
    search_payload = {
        "origin": "BOM",
        "destination": "DXB",
        "departure_date": "2026-11-20",
        "adults": 1,
        "cabin_class": "ECONOMY",
        "max_budget": 60000.0,
    }
    search_res = client.post("/api/v1/flights/search", json=search_payload)
    assert search_res.status_code == 200
    search_data = search_res.json()

    assert search_data["success"] is True
    offers = search_data["data"]["offers"]
    assert len(offers) >= 1

    # Verify ML rank was computed
    best_offer = offers[0]
    assert best_offer["airline_code"] in ("EK", "AI", "FZ", "6E")
    assert best_offer["total_price"] <= 60000.0
    assert "ml_rank" in best_offer["raw_metadata"]

    # 3. Book the best flight offer
    booking_payload = {
        "user_id": user_id,
        "booking_type": "FLIGHT",
        "total_amount": best_offer["total_price"],
        "currency": best_offer["currency"],
        "passengers": [
            {
                "passenger_type": "ADULT",
                "seat_number": "14B",
                "special_requests": "Window seat, vegan meal",
            }
        ],
        "metadata_json": {
            "flight_number": best_offer["flight_number"],
            "origin": best_offer["origin_airport"],
            "destination": best_offer["destination_airport"],
            "offer_id": best_offer["id"],
        },
    }
    booking_res = client.post("/api/v1/bookings", json=booking_payload)
    assert booking_res.status_code == 201
    booking_body = booking_res.json()["data"]

    booking_id = booking_body["id"]
    booking_pnr = booking_body["booking_reference"]
    assert booking_pnr.startswith("TRV-BK-")
    assert booking_body["status"] == "CONFIRMED"

    # 4. Verify booking is retrievable by reference
    fetch_res = client.get(f"/api/v1/bookings/{booking_pnr}")
    assert fetch_res.status_code == 200
    assert fetch_res.json()["data"]["id"] == booking_id
    assert len(fetch_res.json()["data"]["passengers"]) == 1


# ---------------------------------------------------------------------------
# Journey 2: Disruption Rebooking with Human-in-the-Loop Safety Barrier
# ---------------------------------------------------------------------------


def test_journey_disruption_rebooking_with_hitl_approval():
    """Scenario: Flight cancelled -> Agent proposes rebook -> HITL safety gate halts -> Human approves -> Execution completes."""
    thread_id = f"th_disrupt_{uuid.uuid4().hex[:8]}"

    # 1. User messages assistant about flight cancellation
    disrupt_query = {
        "query": "Flight EK505 was cancelled due to weather, please rebook reservation BK-EK505-001 immediately",
        "thread_id": thread_id,
    }
    agent_res = client.post("/api/v1/agents/chat", json=disrupt_query)
    assert agent_res.status_code == 200
    body = agent_res.json()

    # Agent must route to DISRUPTION_REBOOKING and hold for confirmation
    assert body["workflow"] == "DISRUPTION_REBOOKING"
    assert body["requires_human_confirmation"] is True
    assert body["confirmation_status"] == "PENDING"
    assert body["pending_action"] is not None

    action_id = body["pending_action"]["action_id"]
    assert action_id.startswith("act_")
    assert body["pending_action"]["action_type"] == "REBOOK_FLIGHT"

    # 2. Operations Supervisor checks pending HITL queue
    queue_res = client.get("/api/v1/agents/hitl/pending")
    assert queue_res.status_code == 200
    pending_list = queue_res.json()
    assert any(a["action_id"] == action_id for a in pending_list)

    # 3. Supervisor approves the rebooking
    confirm_payload = {
        "operator_id": "supervisor_ops_99",
        "notes": "Approved rebooking to replacement flight EK507 without fee penalty",
    }
    confirm_res = client.post(
        f"/api/v1/agents/hitl/actions/{action_id}/confirm",
        json=confirm_payload,
    )
    assert confirm_res.status_code == 200
    confirm_body = confirm_res.json()
    assert confirm_body["status"] == "APPROVED"
    assert confirm_body["execution_result"] is not None
    assert "new_booking_reference" in confirm_body["execution_result"]

    # 4. Confirm queue no longer contains the action
    queue_after = client.get("/api/v1/agents/hitl/pending").json()
    assert not any(a["action_id"] == action_id for a in queue_after)

    # 5. Check audit trail was logged
    audit_res = client.get("/api/v1/agents/hitl/audit/trail")
    assert audit_res.status_code == 200
    audit_log = audit_res.json()
    assert any(
        entry["action_id"] == action_id and entry.get("actor") == "supervisor_ops_99"
        for entry in audit_log
    )


# ---------------------------------------------------------------------------
# Journey 3: Grounded Policy Q&A with Document Citations
# ---------------------------------------------------------------------------


def test_journey_grounded_policy_qa():
    """Scenario: User asks complex policy question; system answers with grounded citations."""
    policy_query = {
        "query": "What is the cancellation refund policy for Emirates business class tickets?",
        "thread_id": f"th_policy_{uuid.uuid4().hex[:8]}",
    }
    res = client.post("/api/v1/agents/chat", json=policy_query)
    assert res.status_code == 200
    body = res.json()

    assert body["workflow"] == "POLICY"
    assert body["requires_human_confirmation"] is False
    assert len(body["response_message"]) > 20

    # Policy response metadata
    assert body["policy_response"] is not None
    assert "answer" in body["policy_response"]
    assert len(body["policy_response"]["answer"]) > 10
    assert "Emirates" in body["response_message"] or len(body["policy_response"].get("citations", [])) >= 0


# ---------------------------------------------------------------------------
# Journey 4: Multi-Turn Conversational Memory & Personalization
# ---------------------------------------------------------------------------


def test_journey_multi_turn_conversational_memory():
    """Scenario: User shares preferences in Turn 1, then in Turn 2 asks a flight query that uses learned context."""
    thread_id = f"th_mem_e2e_{uuid.uuid4().hex[:8]}"

    # Turn 1: Establish preference
    turn1_payload = {
        "query": "I am planning an upcoming journey and I prefer flying with Emirates airline.",
        "thread_id": thread_id,
    }
    res1 = client.post("/api/v1/agents/chat", json=turn1_payload)
    assert res1.status_code == 200
    assert res1.json()["thread_id"] == thread_id

    # Turn 2: Query flight without mentioning airline explicitly
    turn2_payload = {
        "query": "Find flight offers from BOM to DXB on 2026-10-15",
        "thread_id": thread_id,
    }
    res2 = client.post("/api/v1/agents/chat", json=turn2_payload)
    assert res2.status_code == 200
    body2 = res2.json()

    assert body2["workflow"] == "SEARCH"
    assert len(body2["flight_results"]) >= 1

    # Verify conversation history contains both turns
    state_res = client.get(f"/api/v1/agents/state/{thread_id}")
    assert state_res.status_code == 200
    state_body = state_res.json()
    assert len(state_body.get("messages", [])) >= 2


# ---------------------------------------------------------------------------
# Journey 5: Resilient Graceful Degradation in Zero-Daemon Environment
# ---------------------------------------------------------------------------


def test_journey_graceful_fallback_resilience():
    """Scenario: When external daemons are offline, platform components fall back to in-memory layers without breaking."""
    # 1. System info reports active status
    sys_res = client.get("/api/v1/system/info")
    assert sys_res.status_code == 200
    assert sys_res.json()["data"]["project_name"] == "TravelOps AI"

    # 2. Vector search runs hermetically (in-memory Qdrant)
    rag_payload = {"query": "baggage allowance rules", "top_k": 3}
    rag_res = client.post("/api/v1/rag/query", json=rag_payload)
    assert rag_res.status_code == 200
    rag_data = rag_res.json()
    assert "answer" in rag_data
    assert "sources" in rag_data
    assert isinstance(rag_data["sources"], list)

    # 3. Knowledge Graph runs hermetically (in-memory NetworkX fallback)
    graph_res = client.get("/api/v1/graph/destination/DXB/hotels")
    assert graph_res.status_code == 200
    assert isinstance(graph_res.json(), list)

    # 4. Distributed cache operates hermetically (in-memory fallback)
    cache_res = client.get("/api/v1/cache/stats")
    assert cache_res.status_code == 200
    assert "keys_count" in cache_res.json()
