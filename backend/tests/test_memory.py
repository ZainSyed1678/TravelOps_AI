"""Tests for Phase 10: Agent Memory (Redis hot session cache + PostgreSQL durable tier)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory import (
    memory_service,
    postgres_memory_store,
    preference_extractor,
    redis_session_cache,
)
from app.agents.orchestrator import agent_orchestrator
from app.agents.state import AgentChatRequest
from app.core.database import get_db_session
from app.main import app


@pytest.fixture(autouse=True)
def reset_memory_cache():
    """Ensure in-memory/redis session cache is clean for every test."""
    redis_session_cache.clear()
    yield
    redis_session_cache.clear()


def test_redis_session_cache_lifecycle():
    """Verify session storage, retrieval, TTL, and deletion in hot tier."""
    thread_id = "th_cache_001"
    sample_state = {
        "thread_id": thread_id,
        "workflow": "SEARCH",
        "query": "Flights to London",
        "messages": [{"role": "user", "content": "Flights to London"}],
        "extracted_entities": {"AIRPORT": "LHR"},
    }

    # Store
    redis_session_cache.set_session(thread_id, sample_state, ttl_seconds=60)

    # Retrieve
    retrieved = redis_session_cache.get_session(thread_id)
    assert retrieved is not None
    assert retrieved["query"] == "Flights to London"
    assert retrieved["extracted_entities"]["AIRPORT"] == "LHR"

    # Messages helper
    msgs = redis_session_cache.get_messages(thread_id)
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Flights to London"

    # Delete
    deleted = redis_session_cache.delete_session(thread_id)
    assert deleted is True
    assert redis_session_cache.get_session(thread_id) is None


def test_preference_extractor_rules():
    """Verify rule-based extraction of traveler habits, seating, and airline loyalty."""
    # 1. Airline loyalty
    prefs1 = preference_extractor.extract_preferences(
        "I always fly Emirates for international trips"
    )
    assert any(p["key"] == "preferred_airline" and p["value"] == "Emirates" for p in prefs1)

    # 2. Seating and cabin
    prefs2 = preference_extractor.extract_preferences("Book a window seat in business class")
    assert any(p["key"] == "seat_preference" and p["value"] == "WINDOW" for p in prefs2)
    assert any(p["key"] == "cabin_class" and p["value"] == "BUSINESS" for p in prefs2)

    # 3. Base home airport & non-stop
    prefs3 = preference_extractor.extract_preferences(
        "I am based in Mumbai, looking for non-stop flights"
    )
    assert any(p["key"] == "home_airport" and p["value"] == "BOM" for p in prefs3)
    assert any(p["key"] == "prefer_nonstop" and p["value"] == "true" for p in prefs3)


@pytest.mark.asyncio
async def test_postgres_memory_store_sessions_and_messages(db_session: AsyncSession):
    """Verify PostgreSQL durable session upsert and message synchronization."""
    thread_id = "th_pg_101"
    state = {
        "query": "Find hotels in Dubai",
        "user_intent": "hotel_search",
        "workflow": "HOTEL_SEARCH",
        "extracted_entities": {"AIRPORT": "DXB"},
        "messages": [
            {"role": "user", "content": "Find hotels in Dubai"},
            {"role": "assistant", "content": "I found 3 luxury hotels in Dubai Marina."},
        ],
    }

    # 1. Save session
    session_obj = await postgres_memory_store.save_session(
        db=db_session,
        thread_id=thread_id,
        workflow="HOTEL_SEARCH",
        state=state,
        user_id="usr_test_01",
    )
    assert session_obj.id is not None
    assert session_obj.thread_id == thread_id
    assert session_obj.user_id == "usr_test_01"
    assert len(session_obj.messages) == 2

    # 2. Fetch messages
    messages = await postgres_memory_store.get_messages(db_session, thread_id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"

    # 3. Append subsequent message turn
    state["messages"].append({"role": "user", "content": "Which one has a rooftop pool?"})
    updated_session = await postgres_memory_store.save_session(
        db=db_session,
        thread_id=thread_id,
        workflow="HOTEL_SEARCH",
        state=state,
        user_id="usr_test_01",
    )
    assert len(updated_session.messages) == 3


@pytest.mark.asyncio
async def test_postgres_traveler_profile_upsert_and_retrieval(db_session: AsyncSession):
    """Verify storing and updating personalized traveler memory profile in PostgreSQL."""
    user_id = "usr_traveler_42"

    # Learn preference
    pref1 = await postgres_memory_store.upsert_preference(
        db=db_session,
        user_id=user_id,
        key="preferred_airline",
        value="Air India",
        confidence=0.9,
    )
    assert pref1.id is not None

    await postgres_memory_store.upsert_preference(
        db=db_session,
        user_id=user_id,
        key="seat_preference",
        value="AISLE",
        confidence=0.85,
    )

    profile = await postgres_memory_store.get_traveler_profile(db_session, user_id)
    assert profile["preferred_airline"] == "Air India"
    assert profile["seat_preference"] == "AISLE"

    # Update loyalty preference
    await postgres_memory_store.upsert_preference(
        db=db_session,
        user_id=user_id,
        key="preferred_airline",
        value="Emirates",
        confidence=0.98,
    )
    updated_profile = await postgres_memory_store.get_traveler_profile(db_session, user_id)
    assert updated_profile["preferred_airline"] == "Emirates"


@pytest.mark.asyncio
async def test_memory_service_cold_rehydration(db_session: AsyncSession):
    """Verify cold rehydration from PostgreSQL into Redis hot cache when cache misses."""
    thread_id = "th_cold_rehydrate"
    state = {
        "query": "Check Air India cancellation rules",
        "user_intent": "policy_inquiry",
        "workflow": "POLICY_QA",
        "messages": [
            {"role": "user", "content": "What are Air India cancellation fees?"},
            {"role": "assistant", "content": "Cancellation fees depend on fare class."},
        ],
    }

    # 1. Save to DB directly
    await postgres_memory_store.save_session(
        db=db_session,
        thread_id=thread_id,
        workflow="POLICY_QA",
        state=state,
    )

    # 2. Ensure cache is cold / empty
    memory_service.cache.clear()
    assert memory_service.cache.get_session(thread_id) is None

    # 3. Load via memory service — should rehydrate from DB and warm the cache
    rehydrated = await memory_service.load_thread_state(thread_id, db=db_session)
    assert rehydrated is not None
    assert rehydrated["thread_id"] == thread_id
    assert rehydrated["workflow"] == "POLICY_QA"
    assert len(rehydrated["messages"]) == 2

    # 4. Subsequent read should hit hot cache directly without DB
    cached = memory_service.cache.get_session(thread_id)
    assert cached is not None
    assert cached["thread_id"] == thread_id


@pytest.mark.asyncio
async def test_orchestrator_chat_async_with_memory_and_learning(db_session: AsyncSession):
    """Verify orchestrator runs async turn, checkpoints to DB, and extracts traveler preferences."""
    user_id = "usr_frequent_flyer_77"
    chat_req = AgentChatRequest(
        query="I need flights from Mumbai to Dubai next week. I always fly Emirates and prefer window seat.",
        user_id=user_id,
    )

    # Run chat async with db session
    chat_resp = await agent_orchestrator.chat_async(chat_req, db=db_session)
    assert chat_resp.workflow == "SEARCH"
    assert chat_resp.thread_id is not None
    assert len(chat_resp.messages) >= 2

    # Verify session and messages are persisted in DB
    session_obj = await postgres_memory_store.get_session(db_session, chat_resp.thread_id)
    assert session_obj is not None
    assert session_obj.user_id == user_id
    assert len(session_obj.messages) >= 2

    # Verify traveler preferences learned automatically from conversation
    prefs = await memory_service.get_traveler_preferences(user_id, db=db_session)
    assert prefs.get("preferred_airline") == "Emirates"
    assert prefs.get("seat_preference") == "WINDOW"

    # Second turn on same thread: continuity preserved
    chat_req2 = AgentChatRequest(
        query="What hotels are available near the airport?",
        thread_id=chat_resp.thread_id,
        user_id=user_id,
    )
    chat_resp2 = await agent_orchestrator.chat_async(chat_req2, db=db_session)
    assert len(chat_resp2.messages) >= 4


@pytest.mark.asyncio
async def test_memory_rest_api_endpoints(db_session: AsyncSession):
    """Verify FastAPI endpoints for sessions, history, profile retrieval, and eviction."""
    app.dependency_overrides[get_db_session] = lambda: db_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            user_id = "usr_rest_memory_01"

            # 1. Chat via REST to create session and learn preferences
            chat_payload = {
                "query": "Find flights from Mumbai to Dubai. I prefer Emirates.",
                "user_id": user_id,
            }
            chat_res = await client.post("/api/v1/agents/chat", json=chat_payload)
            assert chat_res.status_code == 200
            data = chat_res.json()
            thread_id = data["thread_id"]

            # 2. List sessions
            list_res = await client.get(f"/api/v1/agents/memory/sessions?user_id={user_id}")
            assert list_res.status_code == 200
            sessions = list_res.json()
            assert len(sessions) >= 1
            assert any(s["thread_id"] == thread_id for s in sessions)

            # 3. Get message history
            hist_res = await client.get(f"/api/v1/agents/memory/sessions/{thread_id}/history")
            assert hist_res.status_code == 200
            messages = hist_res.json()
            assert len(messages) >= 2

            # 4. Get learned profile
            prof_res = await client.get(f"/api/v1/agents/memory/profile/{user_id}")
            assert prof_res.status_code == 200
            profile = prof_res.json()
            assert profile.get("preferred_airline") == "Emirates"

            # 5. Record manual preference
            pref_update = {"key": "cabin_class", "value": "BUSINESS", "confidence": 1.0}
            post_pref = await client.post(
                f"/api/v1/agents/memory/profile/{user_id}", json=pref_update
            )
            assert post_pref.status_code == 200

            # 6. Delete session
            del_res = await client.delete(f"/api/v1/agents/memory/sessions/{thread_id}")
            assert del_res.status_code == 200
            assert del_res.json()["deleted"] is True

            # Verify eviction
            hist_after = await client.get(f"/api/v1/agents/memory/sessions/{thread_id}/history")
            assert hist_after.status_code == 200
            assert len(hist_after.json()) == 0
    finally:
        app.dependency_overrides.pop(get_db_session, None)
