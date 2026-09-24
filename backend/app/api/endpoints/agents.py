"""API endpoints for Agentic AI conversational workflows."""

from typing import Any

from fastapi import APIRouter, HTTPException, status

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
