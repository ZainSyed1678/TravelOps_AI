"""Redis-backed short-term session cache with resilient in-memory fallback."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings
from app.core.logging import logger

try:
    import redis

    _REDIS_CLIENT: redis.Redis | None = None
    _REDIS_AVAILABLE: bool | None = None
except ImportError:
    redis = None
    _REDIS_CLIENT = None
    _REDIS_AVAILABLE = False


class RedisSessionCache:
    """Fast, low-latency session caching for active conversational turns.

    Gracefully falls back to an in-memory dictionary cache with TTL tracking
    when Redis is offline or during hermetic tests.
    """

    def __init__(self, ttl_seconds: int | None = None):
        self.default_ttl = ttl_seconds or settings.REDIS_CACHE_TTL_SECONDS
        self._mem_cache: dict[str, dict[str, Any]] = {}
        self._mem_expiry: dict[str, datetime] = {}
        self._client: redis.Redis | None = None

    def _get_client(self) -> redis.Redis | None:
        """Connect to Redis lazily with reachability caching to prevent recurring timeouts."""
        global _REDIS_CLIENT, _REDIS_AVAILABLE

        if _REDIS_AVAILABLE is False:
            return None

        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT

        if not redis:
            _REDIS_AVAILABLE = False
            return None

        try:
            client = redis.from_url(
                settings.redis_url,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
                decode_responses=True,
            )
            client.ping()
            _REDIS_CLIENT = client
            _REDIS_AVAILABLE = True
            logger.info("Connected to Redis session cache successfully.")
            return _REDIS_CLIENT
        except Exception:
            _REDIS_AVAILABLE = False
            logger.info(
                "Redis daemon not reachable; initializing in-memory session cache fallback."
            )
            return None

    def get_session(self, thread_id: str) -> dict[str, Any] | None:
        """Retrieve cached agent state for thread_id."""
        client = self._get_client()
        if client:
            try:
                raw = client.get(f"travelops:session:{thread_id}")
                if raw:
                    return json.loads(raw)
                return None
            except Exception as e:
                logger.warning(f"Redis get_session failed, falling back to memory: {e}")

        # In-memory fallback
        if thread_id in self._mem_cache:
            exp = self._mem_expiry.get(thread_id)
            if exp and datetime.now(UTC) > exp:
                self.delete_session(thread_id)
                return None
            return self._mem_cache[thread_id]
        return None

    def set_session(
        self,
        thread_id: str,
        state: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        """Store agent state in hot cache with TTL."""
        ttl = ttl_seconds or self.default_ttl
        client = self._get_client()

        if client:
            try:
                serialized = json.dumps(state, default=str)
                client.setex(f"travelops:session:{thread_id}", ttl, serialized)
                return
            except Exception as e:
                logger.warning(f"Redis set_session failed, falling back to memory: {e}")

        # In-memory fallback
        self._mem_cache[thread_id] = state
        self._mem_expiry[thread_id] = datetime.now(UTC) + timedelta(seconds=ttl)

    def delete_session(self, thread_id: str) -> bool:
        """Evict session from hot cache."""
        deleted = False
        client = self._get_client()
        if client:
            try:
                res = client.delete(f"travelops:session:{thread_id}")
                deleted = bool(res)
            except Exception as e:
                logger.warning(f"Redis delete_session failed: {e}")

        if thread_id in self._mem_cache:
            self._mem_cache.pop(thread_id, None)
            self._mem_expiry.pop(thread_id, None)
            deleted = True

        return deleted

    def get_messages(self, thread_id: str) -> list[dict[str, Any]]:
        """Fetch messages array for active session."""
        session = self.get_session(thread_id)
        if session and "messages" in session:
            return session["messages"]
        return []

    def clear(self) -> None:
        """Clear cache state."""
        self._mem_cache.clear()
        self._mem_expiry.clear()
        client = self._get_client()
        if client:
            try:
                keys = client.keys("travelops:session:*")
                if keys:
                    client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis clear failed: {e}")


# Singleton instance
redis_session_cache = RedisSessionCache()
