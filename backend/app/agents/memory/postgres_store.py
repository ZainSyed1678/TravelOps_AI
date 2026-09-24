"""PostgreSQL durable storage for conversational sessions, message history, and traveler memory profiles."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.models.entities import AgentMessage, AgentSession, TravelerMemoryProfile


class PostgresMemoryStore:
    """Async database operations for long-term agent memory persistence."""

    async def save_session(
        self,
        db: AsyncSession,
        thread_id: str,
        workflow: str,
        state: dict[str, Any],
        user_id: str | None = None,
    ) -> AgentSession:
        """Upsert agent session entity and synchronize messages."""
        # Find existing session by thread_id
        stmt = (
            select(AgentSession)
            .where(AgentSession.thread_id == thread_id)
            .options(selectinload(AgentSession.messages))
        )
        result = await db.execute(stmt)
        session_obj = result.scalar_one_or_none()

        metadata = {
            "query": state.get("query"),
            "user_intent": state.get("user_intent"),
            "extracted_entities": state.get("extracted_entities", {}),
            "trace": state.get("trace", []),
            "preferences": state.get("preferences", {}),
            "requires_human_confirmation": state.get("requires_human_confirmation", False),
            "confirmation_status": state.get("confirmation_status", "NONE"),
        }

        if not session_obj:
            session_obj = AgentSession(
                thread_id=thread_id,
                user_id=user_id,
                workflow=workflow,
                status="ACTIVE",
                state_metadata=metadata,
            )
            db.add(session_obj)
            await db.flush()
            logger.info(f"[Memory] Created persistent agent session for thread '{thread_id}'")
        else:
            session_obj.workflow = workflow
            session_obj.state_metadata = metadata
            if user_id and not session_obj.user_id:
                session_obj.user_id = user_id
            await db.flush()

        # Synchronize messages
        incoming_messages = state.get("messages", [])
        msg_stmt = (
            select(AgentMessage)
            .where(AgentMessage.session_id == session_obj.id)
            .order_by(AgentMessage.created_at)
        )
        msg_res = await db.execute(msg_stmt)
        existing_msgs = list(msg_res.scalars().all())
        existing_count = len(existing_msgs)

        # Only add new messages that are not yet persisted
        if len(incoming_messages) > existing_count:
            new_msgs = incoming_messages[existing_count:]
            for m in new_msgs:
                msg_record = AgentMessage(
                    session_id=session_obj.id,
                    role=m.get("role", "user"),
                    content=m.get("content", ""),
                    metadata_json=m.get("metadata", {}),
                )
                db.add(msg_record)

        await db.commit()

        # Re-fetch session with selectinload to return a fully populated, safe object
        final_stmt = (
            select(AgentSession)
            .where(AgentSession.id == session_obj.id)
            .options(selectinload(AgentSession.messages))
            .execution_options(populate_existing=True)
        )
        refreshed_res = await db.execute(final_stmt)
        return refreshed_res.scalar_one()

    async def get_session(
        self,
        db: AsyncSession,
        thread_id: str,
    ) -> AgentSession | None:
        """Fetch persistent agent session with all related messages."""
        stmt = (
            select(AgentSession)
            .where(AgentSession.thread_id == thread_id)
            .options(selectinload(AgentSession.messages))
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_sessions(
        self,
        db: AsyncSession,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[AgentSession]:
        """List persistent agent sessions, optionally filtered by user."""
        stmt = select(AgentSession).order_by(AgentSession.created_at.desc()).limit(limit)
        if user_id:
            stmt = stmt.where(AgentSession.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_messages(
        self,
        db: AsyncSession,
        thread_id: str,
    ) -> list[AgentMessage]:
        """Fetch all messages ordered chronologically for a session thread."""
        session_obj = await self.get_session(db, thread_id)
        if not session_obj:
            return []
        return list(session_obj.messages)

    async def delete_session(
        self,
        db: AsyncSession,
        thread_id: str,
    ) -> bool:
        """Delete an agent session and all associated messages."""
        session_obj = await self.get_session(db, thread_id)
        if not session_obj:
            return False
        await db.delete(session_obj)
        await db.commit()
        return True

    async def upsert_preference(
        self,
        db: AsyncSession,
        user_id: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source_session_id: str | None = None,
    ) -> TravelerMemoryProfile:
        """Learn or update a traveler preference fact in long-term memory."""
        stmt = select(TravelerMemoryProfile).where(
            TravelerMemoryProfile.user_id == user_id,
            TravelerMemoryProfile.preference_key == key,
        )
        result = await db.execute(stmt)
        pref = result.scalar_one_or_none()

        if pref:
            pref.preference_value = value
            pref.confidence = confidence
            if source_session_id:
                pref.source_session_id = source_session_id
        else:
            pref = TravelerMemoryProfile(
                user_id=user_id,
                preference_key=key,
                preference_value=value,
                confidence=confidence,
                source_session_id=source_session_id,
            )
            db.add(pref)

        await db.commit()
        await db.refresh(pref)
        logger.info(f"[Memory] Stored traveler preference for user {user_id}: {key}='{value}'")
        return pref

    async def get_traveler_profile(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> dict[str, Any]:
        """Retrieve aggregated key-value preferences learned for a traveler."""
        stmt = select(TravelerMemoryProfile).where(TravelerMemoryProfile.user_id == user_id)
        result = await db.execute(stmt)
        records = result.scalars().all()
        return {r.preference_key: r.preference_value for r in records}


# Singleton instance
postgres_memory_store = PostgresMemoryStore()
