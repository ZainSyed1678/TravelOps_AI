"""Comprehensive test suite for Phase 8: Agentic AI (LangGraph State Machine)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.nodes.disruption import disruption_node
from app.agents.nodes.flight_search import flight_search_node
from app.agents.nodes.hotel_search import hotel_search_node
from app.agents.nodes.policy_qa import policy_qa_node
from app.agents.nodes.supervisor import supervisor_node
from app.agents.orchestrator import agent_orchestrator
from app.agents.state import AgentChatRequest, AgentState
from app.graph.ingestion import sync_knowledge_graph
from app.graph.service import graph_service
from app.main import app
from app.rag.service import rag_service


@pytest.fixture(autouse=True)
def setup_environment():
    """Ensure Knowledge Graph and vector store are synced for agent node queries."""
    sync_knowledge_graph(service=graph_service)
    rag_service.index_processed_documents()


def test_supervisor_intent_classification():
    """Verify supervisor accurately classifies queries into target workflows."""
    # 1. Search
    res_search = supervisor_node({"query": "Find flights from BOM to DXB"})
    assert res_search["workflow"] == "SEARCH"

    # 2. Policy
    res_pol = supervisor_node({"query": "What is the cancellation policy and refund rule?"})
    assert res_pol["workflow"] == "POLICY"

    # 3. Disruption
    res_disrupt = supervisor_node(
        {"query": "My flight EK505 was cancelled, please rebook booking BK-EK505-001"}
    )
    assert res_disrupt["workflow"] == "DISRUPTION_REBOOKING"

    # 4. Hotel
    res_htl = supervisor_node({"query": "Find me luxury hotels in Dubai for 3 nights"})
    assert res_htl["workflow"] == "HOTEL"


def test_flight_search_node():
    """Verify flight search node returns ML-ranked offers and formatted message."""
    state: AgentState = {
        "query": "Find flights from BOM to DXB",
        "extracted_entities": {"AIRPORT": "BOM"},
        "preferences": {"prefer_nonstop": True},
    }
    result = flight_search_node(state)

    assert len(result["flight_results"]) > 0
    assert "messages" in result
    msg_content = result["messages"][0]["content"]
    assert "BOM" in msg_content
    assert "DXB" in msg_content
    assert "Score:" in msg_content
    assert len(result["trace"]) > 0


def test_policy_qa_node():
    """Verify policy QA node answers policy questions using GraphRAG."""
    state: AgentState = {
        "query": "What is the Emirates cancellation policy?",
        "extracted_entities": {"AIRLINE": "EK", "POLICY_TYPE": "CANCELLATION"},
    }
    result = policy_qa_node(state)

    assert "policy_response" in result
    assert len(result["messages"]) > 0
    assert (
        "Emirates" in result["messages"][0]["content"]
        or "cancellation" in result["messages"][0]["content"].lower()
    )


def test_disruption_node_hitl_safeguard():
    """Verify disruption rebooking creates plan and flags safety checkpoint for human approval."""
    state: AgentState = {
        "query": "Flight EK505 cancelled, rebook reservation BK-EK505-001",
        "extracted_entities": {"FLIGHT": "EK505", "BOOKING_REF": "BK-EK505-001"},
    }
    result = disruption_node(state)

    assert result["requires_human_confirmation"] is True
    assert result["confirmation_status"] == "PENDING"
    assert result["pending_action"] is not None
    assert result["pending_action"]["action_type"] == "REBOOK_FLIGHT"
    assert result["pending_action"]["booking_reference"] == "BK-EK505-001"
    assert "Human-in-the-Loop Confirmation Required" in result["messages"][0]["content"]


def test_hotel_search_node():
    """Verify hotel search node retrieves destination accommodations."""
    state: AgentState = {
        "query": "Hotels in Dubai",
        "extracted_entities": {"AIRPORT": "DXB"},
    }
    result = hotel_search_node(state)

    assert len(result["hotel_results"]) > 0
    assert len(result["messages"]) > 0
    assert "DXB" in result["messages"][0]["content"]


def test_agent_orchestrator_chat_and_threads():
    """Verify orchestrator runs complete multi-agent workflow and persists thread state."""
    req = AgentChatRequest(query="Search flights from Mumbai to Dubai")
    resp = agent_orchestrator.chat(req)

    assert resp.workflow == "SEARCH"
    assert len(resp.flight_results) > 0
    assert len(resp.trace) >= 2
    assert resp.thread_id is not None

    # Follow-up message on same thread
    followup_req = AgentChatRequest(
        query="What is the baggage allowance for Emirates?",
        thread_id=resp.thread_id,
    )
    followup_resp = agent_orchestrator.chat(followup_req)

    assert followup_resp.thread_id == resp.thread_id
    assert followup_resp.workflow == "POLICY"
    assert len(followup_resp.messages) >= 3


@pytest.mark.asyncio
async def test_agent_api_endpoints():
    """Verify HTTP API endpoints for /agents/chat and /agents/state/{thread_id}."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Chat Endpoint
        payload = {"query": "Find flights from BOM to DXB"}
        res_chat = await client.post("/api/v1/agents/chat", json=payload)
        assert res_chat.status_code == 200
        data = res_chat.json()
        assert data["workflow"] == "SEARCH"
        assert len(data["flight_results"]) > 0
        thread_id = data["thread_id"]

        # 2. State Endpoint
        res_state = await client.get(f"/api/v1/agents/state/{thread_id}")
        assert res_state.status_code == 200
        state_data = res_state.json()
        assert state_data["thread_id"] == thread_id
        assert state_data["workflow"] == "SEARCH"

        # 3. Disruption HITL chat test via API
        disrupt_payload = {
            "query": "Flight EK505 cancelled, rebook reservation BK-EK505-001",
        }
        res_disrupt = await client.post("/api/v1/agents/chat", json=disrupt_payload)
        assert res_disrupt.status_code == 200
        disrupt_data = res_disrupt.json()
        assert disrupt_data["workflow"] == "DISRUPTION_REBOOKING"
        assert disrupt_data["requires_human_confirmation"] is True
        assert disrupt_data["confirmation_status"] == "PENDING"
        assert disrupt_data["pending_action"]["action_type"] == "REBOOK_FLIGHT"
