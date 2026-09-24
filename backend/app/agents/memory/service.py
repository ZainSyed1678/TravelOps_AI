"""Agent Memory Service: Unified memory coordinator combining Redis (hot tier) and PostgreSQL (durable tier)."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory.postgres_store import postgres_memory_store
from app.agents.memory.preference_extractor import preference_extractor
from app.agents.memory.session_store import redis_session_cache
from app.agents.state import AgentState
from app.core.logging import logger


class AgentMemoryService:
    """Unified memory manager coordinating fast cache and durable relational persistence."""

    def __init__(self):
        self.cache = redis_session_cache
        self.store = postgres_memory_store

    def checkpoint_cache(self, thread_id: str, state: AgentState) -> None:
        """Quick synchronous checkpoint into hot Redis/in-memory cache."""
        state_dict = dict(state)
        self.cache.set_session(thread_id, state_dict)

    async def checkpoint_turn(
        self,
        thread_id: str,
        state: AgentState,
        user_id: str | None = None,
        db: AsyncSession | None = None,
    ) -> None:
        """Full checkpoint: updates hot cache, persists to database, and extracts traveler preferences."""
        state_dict = dict(state)
        # 1. Update hot cache
        self.cache.set_session(thread_id, state_dict)

        if not db:
            return

        workflow = state.get("workflow", "SEARCH")
        try:
            # 2. Persist to PostgreSQL
            session_obj = await self.store.save_session(
                db=db,
                thread_id=thread_id,
                workflow=workflow,
                state=state_dict,
                user_id=user_id,
            )

            # 3. Extract and learn traveler preferences from recent user messages
            if user_id:
                for msg in state.get("messages", []):
                    if msg.get("role") == "user":
                        prefs = preference_extractor.extract_preferences(msg.get("content", ""))
                        for p in prefs:
                            await self.store.upsert_preference(
                                db=db,
                                user_id=user_id,
                                key=p["key"],
                                value=p["value"],
                                confidence=p.get("confidence", 1.0),
                                source_session_id=session_obj.id,
                            )
        except Exception as e:
            logger.warning(f"[Memory] Failed to persist turn to PostgreSQL: {e}")

    async def load_thread_state(
        self,
        thread_id: str,
        db: AsyncSession | None = None,
    ) -> AgentState | None:
        """Load conversation state: checks hot cache first, then PostgreSQL."""
        # 1. Hot cache lookup (<1ms)
        cached = self.cache.get_session(thread_id)
        if cached:
            return cached  # type: ignore[return-value]

        if not db:
            return None

        # 2. Durable database lookup (cold rehydration)
        try:
            session_obj = await self.store.get_session(db, thread_id)
            if not session_obj:
                return None

            messages = [
                {"role": m.role, "content": m.content, "metadata": m.metadata_json}
                for m in session_obj.messages
            ]

            metadata = session_obj.state_metadata or {}
            rehydrated: AgentState = {
                "thread_id": session_obj.thread_id,
                "workflow": session_obj.workflow,
                "query": metadata.get("query", ""),
                "user_intent": metadata.get("user_intent", "unknown"),
                "extracted_entities": metadata.get("extracted_entities", {}),
                "messages": messages,
                "flight_results": [],
                "hotel_results": [],
                "policy_response": None,
                "disruption_plan": None,
                "pending_action": None,
                "requires_human_confirmation": metadata.get("requires_human_confirmation", False),
                "confirmation_status": metadata.get("confirmation_status", "NONE"),
                "trace": metadata.get("trace", []),
                "preferences": metadata.get("preferences", {}),
            }

            # Rewarm hot cache
            self.cache.set_session(thread_id, dict(rehydrated))
            logger.info(f"[Memory] Rehydrated thread '{thread_id}' from PostgreSQL into hot cache.")
            return rehydrated
        except Exception as e:
            logger.warning(f"[Memory] Cold rehydration from PostgreSQL failed: {e}")
            return None

    async def get_traveler_preferences(
        self,
        user_id: str,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Retrieve learned preferences for personalization."""
        if not db or not user_id:
            return {}
        try:
            return await self.store.get_traveler_profile(db, user_id)
        except Exception as e:
            logger.warning(f"[Memory] Failed to load traveler profile: {e}")
            return {}

    async def record_preference(
        self,
        user_id: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        db: AsyncSession | None = None,
    ) -> None:
        """Manually record or update a traveler preference fact."""
        if not db:
            return
        await self.store.upsert_preference(db, user_id, key, value, confidence)

    async def delete_session(
        self,
        thread_id: str,
        db: AsyncSession | None = None,
    ) -> bool:
        """Evict session from both hot cache and database."""
        cache_deleted = self.cache.delete_session(thread_id)
        db_deleted = False
        if db:
            try:
                db_deleted = await self.store.delete_session(db, thread_id)
            except Exception as e:
                logger.warning(f"[Memory] Failed to delete session from DB: {e}")
        return cache_deleted or db_deleted


# Global singleton instance
memory_service = AgentMemoryService()
