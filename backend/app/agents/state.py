"""State definitions and request/response schemas for the LangGraph Agentic AI platform."""

from typing import Annotated, Any

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.ml.schemas import UserPreferences


def merge_lists(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    """Reducer combining list items across graph state updates."""
    l_list = left or []
    r_list = right or []
    return l_list + r_list


class AgentState(TypedDict, total=False):
    """LangGraph operational state shared across all agent nodes."""

    query: str
    thread_id: str
    messages: Annotated[list[dict[str, Any]], merge_lists]
    workflow: str  # SEARCH, POLICY, DISRUPTION_REBOOKING, HOTEL, UNKNOWN
    user_intent: str
    extracted_entities: dict[str, Any]
    flight_results: list[dict[str, Any]]
    hotel_results: list[dict[str, Any]]
    policy_response: dict[str, Any] | None
    disruption_plan: dict[str, Any] | None
    pending_action: dict[str, Any] | None
    requires_human_confirmation: bool
    confirmation_status: str  # PENDING, APPROVED, REJECTED, NONE
    trace: Annotated[list[str], merge_lists]
    preferences: dict[str, Any] | None


class AgentChatRequest(BaseModel):
    """User request payload for interacting with the AI Travel Agent."""

    query: str = Field(..., min_length=2, description="User instruction or question")
    thread_id: str | None = Field(None, description="Session thread ID for conversation memory")
    preferences: UserPreferences | None = Field(default_factory=UserPreferences, description="Traveler preferences")


class AgentChatResponse(BaseModel):
    """Unified response payload from the Agentic State Machine."""

    thread_id: str
    workflow: str
    response_message: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    flight_results: list[dict[str, Any]] = Field(default_factory=list)
    hotel_results: list[dict[str, Any]] = Field(default_factory=list)
    policy_response: dict[str, Any] | None = None
    disruption_plan: dict[str, Any] | None = None
    pending_action: dict[str, Any] | None = None
    requires_human_confirmation: bool = False
    confirmation_status: str = "NONE"
    trace: list[str] = Field(default_factory=list)
