"""Tests for Phase 9: Human-in-the-Loop (HITL) confirmation checkpoints and safety barrier."""

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.agents.hitl import (
    ActionStatus,
    ActionType,
    HITLBarrierException,
    HITLConfirmationRequest,
    hitl_manager,
)
from app.agents.orchestrator import agent_orchestrator
from app.agents.state import AgentChatRequest
from app.main import app


@pytest.fixture(autouse=True)
def reset_hitl_state():
    """Ensure clean HITL state before each test."""
    hitl_manager.clear()
    yield
    hitl_manager.clear()


def test_hitl_create_and_get_action():
    """Verify creation and retrieval of pending action proposals."""
    action = hitl_manager.create_pending_action(
        action_type=ActionType.REBOOK_FLIGHT.value,
        summary="Rebook flight due to delay",
        details={"booking_reference": "BK-TEST-100", "new_flight": "EK502"},
        risk_level="HIGH",
        financial_impact={"amount": 0.0, "currency": "INR", "waiver_applied": True},
    )

    assert action.action_id.startswith("act_")
    assert action.status == ActionStatus.PENDING.value
    assert action.risk_level == "HIGH"
    assert action.details["booking_reference"] == "BK-TEST-100"

    retrieved = hitl_manager.get_action(action.action_id)
    assert retrieved is not None
    assert retrieved.action_id == action.action_id


def test_hitl_safety_barrier_blocks_unauthorized_mutation():
    """Verify that the safety barrier strictly blocks financial/booking actions without approval."""
    # 1. Blocked when no action_id provided
    with pytest.raises(HITLBarrierException) as exc_info:
        hitl_manager.enforce_safety_guard(ActionType.REBOOK_FLIGHT.value, None)
    assert "requires explicit Human-in-the-Loop approval" in str(exc_info.value)

    # 2. Blocked when action is still PENDING
    action = hitl_manager.create_pending_action(
        action_type=ActionType.CANCEL_BOOKING.value,
        summary="Cancel reservation",
        details={"booking_reference": "BK-TEST-101"},
    )
    with pytest.raises(HITLBarrierException) as exc_info:
        hitl_manager.enforce_safety_guard(ActionType.CANCEL_BOOKING.value, action.action_id)
    assert "Execution requires 'APPROVED' status" in str(exc_info.value)

    # Verify audit log captures blocked attempts
    audit_trail = hitl_manager.get_audit_trail()
    blocked_events = [e for e in audit_trail if e.event_type == "BLOCKED"]
    assert len(blocked_events) >= 2


def test_hitl_confirm_rebook_action_executes_and_updates_thread():
    """Verify confirming a disruption rebooking executes with provider and updates conversational state."""
    # 1. Trigger disruption query in agent orchestrator
    chat_req = AgentChatRequest(query="Flight EK505 is cancelled, help me rebook")
    chat_resp = agent_orchestrator.chat(chat_req)

    assert chat_resp.workflow == "DISRUPTION_REBOOKING"
    assert chat_resp.requires_human_confirmation is True
    assert chat_resp.confirmation_status == "PENDING"
    assert chat_resp.pending_action is not None
    action_id = chat_resp.pending_action["action_id"]

    # 2. Operator confirms the action
    res = hitl_manager.confirm_action(
        action_id=action_id,
        operator_id="duty_manager_01",
        notes="Confirmed with passenger on call; fee waiver applied",
    )

    assert res.status == ActionStatus.APPROVED.value
    assert res.resolved_by == "duty_manager_01"
    assert res.execution_result is not None
    assert res.execution_result["status"] == "CONFIRMED"
    assert "new_pnr" in res.execution_result
    assert res.execution_result["waiver_applied"] is True
    assert res.execution_result["total_amount_due"] == 0.0

    # 3. Verify safety guard now allows execution
    hitl_manager.enforce_safety_guard(ActionType.REBOOK_FLIGHT.value, action_id)

    # 4. Verify agent thread state has been updated
    thread_state = agent_orchestrator.get_thread_state(chat_resp.thread_id)
    assert thread_state is not None
    assert thread_state["requires_human_confirmation"] is False
    assert thread_state["confirmation_status"] == "APPROVED"
    assert thread_state["pending_action"] is None
    latest_msg = thread_state["messages"][-1]["content"]
    assert "Action Confirmed & Executed" in latest_msg
    assert res.execution_result["new_pnr"] in latest_msg


def test_hitl_reject_action_updates_thread():
    """Verify rejecting an action proposal leaves itinerary untouched and updates conversation."""
    chat_req = AgentChatRequest(query="Flight EK505 is delayed, what are alternate flights?")
    chat_resp = agent_orchestrator.chat(chat_req)
    action_id = chat_resp.pending_action["action_id"]

    res = hitl_manager.reject_action(
        action_id=action_id,
        operator_id="traveler_app",
        reason="Passenger prefers next day departure instead",
    )

    assert res.status == ActionStatus.REJECTED.value
    assert res.resolved_by == "traveler_app"
    assert res.execution_result is None

    # Verify agent thread state has been updated
    thread_state = agent_orchestrator.get_thread_state(chat_resp.thread_id)
    assert thread_state is not None
    assert thread_state["requires_human_confirmation"] is False
    assert thread_state["confirmation_status"] == "REJECTED"
    latest_msg = thread_state["messages"][-1]["content"]
    assert "Action Rejected" in latest_msg
    assert "Passenger prefers next day departure" in latest_msg


def test_hitl_confirm_cancellation_action():
    """Verify confirming a cancellation proposal computes penalties and refunds correctly."""
    action = hitl_manager.create_pending_action(
        action_type=ActionType.CANCEL_BOOKING.value,
        summary="Cancel booking TRV-BK-999",
        details={"booking_reference": "TRV-BK-999", "reason": "Medical emergency"},
        risk_level="HIGH",
    )

    confirm_res = hitl_manager.confirm_action(
        action_id=action.action_id,
        operator_id="supervisor_jenny",
        notes="Medical certificate verified",
    )

    assert confirm_res.status == ActionStatus.APPROVED.value
    assert confirm_res.execution_result["operation"] == "CANCEL_BOOKING"
    assert confirm_res.execution_result["status"] == "CANCELLED"
    assert confirm_res.execution_result["refund_amount"] > 0
    assert "cancellation_id" in confirm_res.execution_result


def test_hitl_double_resolution_prohibited():
    """Verify actions cannot be resolved more than once."""
    action = hitl_manager.create_pending_action(
        action_type=ActionType.REBOOK_FLIGHT.value,
        summary="Rebook flight",
        details={"booking_reference": "BK-123", "new_flight": "EK505"},
    )

    hitl_manager.confirm_action(action.action_id, "op1")

    # Second confirmation should be rejected with HTTP 400
    with pytest.raises(HTTPException) as exc_info:
        hitl_manager.confirm_action(action.action_id, "op2")
    assert exc_info.value.status_code == 400

    # Rejection of approved action should also fail
    with pytest.raises(HTTPException) as exc_info:
        hitl_manager.reject_action(action.action_id, "op2", "too late")
    assert exc_info.value.status_code == 400


def test_hitl_action_expiration():
    """Verify expired actions are updated and excluded from active pending list."""
    action = hitl_manager.create_pending_action(
        action_type=ActionType.REBOOK_FLIGHT.value,
        summary="Time sensitive rebooking",
        details={"booking_reference": "BK-EXP-01"},
        ttl_minutes=-5,  # Pre-expired
    )

    retrieved = hitl_manager.get_action(action.action_id)
    assert retrieved.status == ActionStatus.EXPIRED.value

    pending_list = hitl_manager.list_pending_actions()
    assert all(a.action_id != action.action_id for a in pending_list)

    with pytest.raises(HTTPException) as exc_info:
        hitl_manager.confirm_action(action.action_id, "op1")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_hitl_rest_endpoints():
    """Verify REST API endpoints for listing, viewing, confirming, and rejecting HITL proposals."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create action via manager
        action = hitl_manager.create_pending_action(
            action_type=ActionType.REBOOK_FLIGHT.value,
            summary="Emergency flight rebook",
            details={"booking_reference": "BK-REST-505", "new_flight": "EK501"},
            risk_level="CRITICAL",
        )

        # 2. List pending
        list_res = await ac.get("/api/v1/agents/hitl/pending")
        assert list_res.status_code == 200
        pending_items = list_res.json()
        assert len(pending_items) >= 1
        assert any(item["action_id"] == action.action_id for item in pending_items)

        # 3. Get single action
        get_res = await ac.get(f"/api/v1/agents/hitl/actions/{action.action_id}")
        assert get_res.status_code == 200
        assert get_res.json()["action_id"] == action.action_id

        # 4. Confirm action via REST
        confirm_body = HITLConfirmationRequest(
            operator_id="ops_rest_01",
            notes="Confirmed via operations console",
        ).model_dump()
        conf_res = await ac.post(
            f"/api/v1/agents/hitl/actions/{action.action_id}/confirm",
            json=confirm_body,
        )
        assert conf_res.status_code == 200
        data = conf_res.json()
        assert data["status"] == "APPROVED"
        assert data["resolved_by"] == "ops_rest_01"
        assert data["execution_result"]["new_pnr"] is not None

        # 5. Check audit trail endpoint
        audit_res = await ac.get("/api/v1/agents/hitl/audit/trail")
        assert audit_res.status_code == 200
        trail = audit_res.json()
        assert len(trail) >= 2
        assert any(e["action_id"] == action.action_id for e in trail)
