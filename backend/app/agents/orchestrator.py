import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import travel_agent_graph
from app.agents.memory import memory_service
from app.agents.state import AgentChatRequest, AgentChatResponse, AgentState
from app.core.logging import logger


class TravelAgentOrchestrator:
    """Manages conversational session threads and invokes the multi-agent state graph."""

    def __init__(self):
        # In-memory thread state store (mirrored to Redis + PostgreSQL)
        self._threads: dict[str, AgentState] = {}

    def chat(self, request: AgentChatRequest) -> AgentChatResponse:
        """Process incoming user prompt through the LangGraph state machine."""
        thread_id = request.thread_id or f"th_{uuid.uuid4().hex[:12]}"
        existing_state = self._threads.get(thread_id) or memory_service.cache.get_session(thread_id) or {}

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

        # Update local thread state and Redis hot cache
        self._threads[thread_id] = final_state
        memory_service.checkpoint_cache(thread_id, final_state)

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

    async def chat_async(
        self,
        request: AgentChatRequest,
        db: AsyncSession | None = None,
    ) -> AgentChatResponse:
        """Asynchronous execution with full dual-tier memory checkpointing (Redis + PostgreSQL)."""
        thread_id = request.thread_id or f"th_{uuid.uuid4().hex[:12]}"

        # Attempt to rehydrate from cache or DB if thread is continuing
        existing_state = await memory_service.load_thread_state(thread_id, db=db)
        if not existing_state:
            existing_state = self._threads.get(thread_id, {})

        # If user_id provided and preferences empty, preload from learned traveler memory
        prefs = request.preferences.model_dump() if request.preferences else {}
        if db and request.user_id:
            learned_prefs = await memory_service.get_traveler_preferences(request.user_id, db=db)
            if learned_prefs:
                for k, v in learned_prefs.items():
                    if k not in prefs or prefs[k] is None:
                        prefs[k] = v

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
            "preferences": prefs,
        }

        if existing_state and "messages" in existing_state:
            initial_state["messages"] = existing_state["messages"] + [user_msg]

        logger.info(f"Invoking TravelOps Agent Graph (async) for thread '{thread_id}'")
        final_state = travel_agent_graph.invoke(initial_state)

        # Checkpoint to both Redis hot tier and PostgreSQL durable tier
        self._threads[thread_id] = final_state
        await memory_service.checkpoint_turn(
            thread_id=thread_id,
            state=final_state,
            user_id=request.user_id,
            db=db,
        )

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
        return self._threads.get(thread_id) or memory_service.cache.get_session(thread_id)


agent_orchestrator = TravelAgentOrchestrator()

