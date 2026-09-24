from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.hitl import (
    AuditLogEntry,
    HITLConfirmationRequest,
    HITLConfirmationResponse,
    HITLRejectionRequest,
    PendingAction,
    hitl_manager,
)
from app.agents.memory import memory_service
from app.agents.orchestrator import agent_orchestrator
from app.agents.state import AgentChatRequest, AgentChatResponse
from app.core.database import get_db_session

router = APIRouter()


class TravelerPreferenceRequest(BaseModel):
    """Payload to record or update a traveler preference fact."""

    key: str = Field(..., description="Preference attribute key, e.g. preferred_airline")
    value: str = Field(..., description="Preference attribute value, e.g. Emirates")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score between 0 and 1")


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Chat with TravelOps Multi-Agent System",
    description="Send a natural language instruction to the LangGraph multi-agent state machine with dual-tier Redis & PostgreSQL memory.",
)
async def agent_chat(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db_session),
) -> AgentChatResponse:
    try:
        return await agent_orchestrator.chat_async(request, db=db)
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
    res = hitl_manager.confirm_action(
        action_id=action_id,
        operator_id=request.operator_id,
        notes=request.notes,
        waiver_override=request.waiver_override,
    )
    try:
        from app.observability.metrics import record_hitl_decision

        action_type = res.action_type.value if hasattr(res.action_type, "value") else str(res.action_type)
        record_hitl_decision(action_type, "APPROVED")
    except Exception:
        pass
    return res


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
    res = hitl_manager.reject_action(
        action_id=action_id,
        operator_id=request.operator_id,
        reason=request.reason,
    )
    try:
        from app.observability.metrics import record_hitl_decision

        action_type = res.action_type.value if hasattr(res.action_type, "value") else str(res.action_type)
        record_hitl_decision(action_type, "REJECTED")
    except Exception:
        pass
    return res


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


# ==============================================================================
# Agent Memory & Session Persistence Endpoints (Phase 10)
# ==============================================================================


@router.get(
    "/memory/sessions",
    summary="List Agent Memory Sessions",
    description="List persistent agent conversation sessions from PostgreSQL.",
)
async def list_agent_memory_sessions(
    user_id: str | None = Query(None, description="Optional user ID filter"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    sessions = await memory_service.store.list_sessions(db, user_id=user_id, limit=limit)
    return [
        {
            "id": s.id,
            "thread_id": s.thread_id,
            "user_id": s.user_id,
            "workflow": s.workflow,
            "status": s.status,
            "state_metadata": s.state_metadata,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in sessions
    ]


@router.get(
    "/memory/sessions/{thread_id}/history",
    summary="Get Session Message History",
    description="Retrieve chronological conversation messages for a thread from PostgreSQL (falling back to Redis).",
)
async def get_session_message_history(
    thread_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    messages = await memory_service.store.get_messages(db, thread_id)
    if not messages:
        cached_msgs = memory_service.cache.get_messages(thread_id)
        if cached_msgs:
            return cached_msgs
    return [
        {
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "tokens": m.tokens,
            "metadata": m.metadata_json,
            "created_at": m.created_at,
        }
        for m in messages
    ]


@router.get(
    "/memory/profile/{user_id}",
    summary="Get Learned Traveler Profile",
    description="Retrieve all learned personalized preferences for a specific traveler.",
)
async def get_traveler_memory_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await memory_service.get_traveler_preferences(user_id, db=db)


@router.post(
    "/memory/profile/{user_id}",
    summary="Record Traveler Preference",
    description="Manually record or update a learned traveler preference in long-term memory.",
)
async def record_traveler_memory_preference(
    user_id: str,
    request: TravelerPreferenceRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await memory_service.record_preference(
        user_id=user_id,
        key=request.key,
        value=request.value,
        confidence=request.confidence,
        db=db,
    )
    return {
        "status": "success",
        "user_id": user_id,
        "key": request.key,
        "value": request.value,
    }


@router.delete(
    "/memory/sessions/{thread_id}",
    summary="Clear Session Memory",
    description="Evict conversation session from both Redis hot cache and PostgreSQL persistent storage.",
)
async def clear_session_memory(
    thread_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    deleted = await memory_service.delete_session(thread_id, db=db)
    return {
        "status": "success" if deleted else "not_found",
        "thread_id": thread_id,
        "deleted": deleted,
    }


