"""Agent Orchestrator Service managing session threads and invoking the LangGraph state machine."""

import uuid

from app.agents.graph import travel_agent_graph
from app.agents.state import AgentChatRequest, AgentChatResponse, AgentState
from app.core.logging import logger


class TravelAgentOrchestrator:
    """Manages conversational session threads and invokes the multi-agent state graph."""

    def __init__(self):
        # In-memory thread state store (persisted in PostgreSQL/Redis in Phase 10)
        self._threads: dict[str, AgentState] = {}

    def chat(self, request: AgentChatRequest) -> AgentChatResponse:
        """Process incoming user prompt through the LangGraph state machine."""
        thread_id = request.thread_id or f"th_{uuid.uuid4().hex[:12]}"
        existing_state = self._threads.get(thread_id, {})

        # Prepare user message
        user_msg = {"role": "user", "content": request.query}

        initial_state: AgentState = {
            "query": request.query,
            "thread_id": thread_id,
            "messages": [user_msg],
            "workflow": "UNKNOWN",
            "user_intent": "unknown",
            "extracted_entities": {},
            "flight_results": [],
            "hotel_results": [],
            "policy_response": None,
            "disruption_plan": None,
            "pending_action": None,
            "requires_human_confirmation": False,
            "confirmation_status": "NONE",
            "trace": [f"orchestrator: received query on thread {thread_id}"],
            "preferences": request.preferences.model_dump() if request.preferences else {},
        }

        # Carry forward prior conversation messages if continuing thread
        if existing_state and "messages" in existing_state:
            initial_state["messages"] = existing_state["messages"] + [user_msg]

        logger.info(f"Invoking TravelOps Agent Graph for thread '{thread_id}' with query: '{request.query}'")
        final_state = travel_agent_graph.invoke(initial_state)

        # Update thread state cache
        self._threads[thread_id] = final_state

        # Extract assistant response message
        response_text = ""
        for m in reversed(final_state.get("messages", [])):
            if m.get("role") == "assistant":
                response_text = m.get("content", "")
                break

        return AgentChatResponse(
            thread_id=thread_id,
            workflow=final_state.get("workflow", "SEARCH"),
            response_message=response_text,
            messages=final_state.get("messages", []),
            flight_results=final_state.get("flight_results", []),
            hotel_results=final_state.get("hotel_results", []),
            policy_response=final_state.get("policy_response"),
            disruption_plan=final_state.get("disruption_plan"),
            pending_action=final_state.get("pending_action"),
            requires_human_confirmation=final_state.get("requires_human_confirmation", False),
            confirmation_status=final_state.get("confirmation_status", "NONE"),
            trace=final_state.get("trace", []),
        )

    def get_thread_state(self, thread_id: str) -> AgentState | None:
        """Fetch current state for an active session thread."""
        return self._threads.get(thread_id)


agent_orchestrator = TravelAgentOrchestrator()
