"""API endpoints for Agentic AI conversational workflows."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.agents.hitl import (
    AuditLogEntry,
    HITLConfirmationRequest,
    HITLConfirmationResponse,
    HITLRejectionRequest,
    PendingAction,
    hitl_manager,
)
from app.agents.orchestrator import agent_orchestrator
from app.agents.state import AgentChatRequest, AgentChatResponse

router = APIRouter()


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Chat with TravelOps Multi-Agent System",
    description="Send a natural language instruction to the LangGraph multi-agent state machine across Search, Policy, Disruption, and Hotel workflows.",
)
async def agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    try:
        return agent_orchestrator.chat(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent workflow execution failed: {str(exc)}",
        ) from exc


@router.get(
    "/state/{thread_id}",
    response_model=dict[str, Any],
    summary="Get Agent Thread State",
    description="Retrieve the current execution state and trace history for an active conversational thread.",
)
async def get_agent_thread_state(thread_id: str) -> dict[str, Any]:
    state = agent_orchestrator.get_thread_state(thread_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )
    return state


# ==============================================================================
# Human-in-the-Loop (HITL) Safety Checkpoint Endpoints
# ==============================================================================


@router.get(
    "/hitl/pending",
    response_model=list[PendingAction],
    summary="List Pending HITL Actions",
    description="Retrieve all queued financial or itinerary mutation proposals awaiting human operator approval.",
)
async def list_pending_hitl_actions(
    thread_id: str | None = Query(None, description="Optional conversational thread filter"),
    action_type: str | None = Query(None, description="Optional action type filter (e.g. REBOOK_FLIGHT)"),
) -> list[PendingAction]:
    return hitl_manager.list_pending_actions(thread_id=thread_id, action_type=action_type)


@router.get(
    "/hitl/actions/{action_id}",
    response_model=PendingAction,
    summary="Get HITL Action Details",
    description="Retrieve proposal details, risk level, and financial impact for a specific pending action.",
)
async def get_hitl_action(action_id: str) -> PendingAction:
    action = hitl_manager.get_action(action_id)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action '{action_id}' not found.",
        )
    return action


@router.post(
    "/hitl/actions/{action_id}/confirm",
    response_model=HITLConfirmationResponse,
    summary="Confirm & Execute Pending Action",
    description="Authorize and execute an action proposal through the HITL safety barrier with audit trail logging.",
)
async def confirm_hitl_action(
    action_id: str,
    request: HITLConfirmationRequest,
) -> HITLConfirmationResponse:
    return hitl_manager.confirm_action(
        action_id=action_id,
        operator_id=request.operator_id,
        notes=request.notes,
        waiver_override=request.waiver_override,
    )


@router.post(
    "/hitl/actions/{action_id}/reject",
    response_model=HITLConfirmationResponse,
    summary="Reject Pending Action Proposal",
    description="Reject a proposed mutation, recording operator rationale and updating the conversational state.",
)
async def reject_hitl_action(
    action_id: str,
    request: HITLRejectionRequest,
) -> HITLConfirmationResponse:
    return hitl_manager.reject_action(
        action_id=action_id,
        operator_id=request.operator_id,
        reason=request.reason,
    )


@router.get(
    "/hitl/audit/trail",
    response_model=list[AuditLogEntry],
    summary="Get HITL Audit Trail",
    description="Inspect immutable operational log recording all created, approved, rejected, and executed actions.",
)
async def get_hitl_audit_trail(
    action_id: str | None = Query(None, description="Optional action ID filter"),
) -> list[AuditLogEntry]:
    return hitl_manager.get_audit_trail(action_id=action_id)

