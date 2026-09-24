"""System-wide Redis cache manager with in-memory fallback, semantic tags, and TTL invalidation."""

import fnmatch
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

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


class CacheStats(BaseModel):
    """Real-time cache performance and cardinality statistics."""

    backend: str = Field(..., description="Active cache engine: 'redis' or 'in_memory'")
    hits: int = Field(default=0, description="Total cache read hits")
    misses: int = Field(default=0, description="Total cache read misses")
    writes: int = Field(default=0, description="Total cache writes")
    deletes: int = Field(default=0, description="Total keys deleted")
    hit_rate: float = Field(default=0.0, description="Hit ratio (hits / (hits + misses))")
    keys_count: int = Field(default=0, description="Estimated total cached keys")


class CacheManager:
    """Production cache manager supporting namespace partitioning, TTL, and tag-based invalidation."""

    def __init__(self, default_ttl_seconds: int = 300, namespace: str = "travelops"):
        self.default_ttl = default_ttl_seconds
        self.namespace = namespace
        self._mem_store: dict[str, str] = {}
        self._mem_expiry: dict[str, datetime] = {}
        self._mem_tags: dict[str, set[str]] = {}  # tag -> set of keys
        self._hits = 0
        self._misses = 0
        self._writes = 0
        self._deletes = 0

    def _get_client(self) -> Any | None:
        """Connect to Redis lazily with reachability caching."""
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
            logger.info("Connected to Redis cache manager successfully.")
            return _REDIS_CLIENT
        except Exception:
            _REDIS_AVAILABLE = False
            logger.info("Redis not reachable; using in-memory fallback cache engine.")
            return None

    def _format_key(self, key: str, namespace: str | None = None) -> str:
        """Format fully qualified cache key."""
        ns = namespace or self.namespace
        return f"{ns}:{key}"

    def get(self, key: str, namespace: str | None = None) -> Any | None:
        """Retrieve and deserialize value from cache."""
        full_key = self._format_key(key, namespace)
        client = self._get_client()

        if client is not None:
            try:
                raw = client.get(full_key)
                if raw is not None:
                    self._hits += 1
                    return json.loads(raw)
                self._misses += 1
                return None
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        # In-memory fallback
        now = datetime.now(UTC)
        if full_key in self._mem_store:
            expiry = self._mem_expiry.get(full_key)
            if expiry and expiry < now:
                # Expired
                self._mem_store.pop(full_key, None)
                self._mem_expiry.pop(full_key, None)
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(self._mem_store[full_key])

        self._misses += 1
        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        namespace: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """Serialize and persist value with TTL and optional semantic invalidation tags."""
        full_key = self._format_key(key, namespace)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        serialized = json.dumps(value, default=str)
        client = self._get_client()

        if client is not None:
            try:
                if ttl > 0:
                    client.setex(full_key, ttl, serialized)
                else:
                    client.set(full_key, serialized)

                if tags:
                    for tag in tags:
                        tag_key = f"{self.namespace}:tag:{tag}"
                        client.sadd(tag_key, full_key)
                        if ttl > 0:
                            client.expire(tag_key, ttl + 3600)

                self._writes += 1
                return True
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")

        # In-memory fallback
        self._mem_store[full_key] = serialized
        if ttl > 0:
            self._mem_expiry[full_key] = datetime.now(UTC) + timedelta(seconds=ttl)
        else:
            self._mem_expiry.pop(full_key, None)

        if tags:
            for tag in tags:
                if tag not in self._mem_tags:
                    self._mem_tags[tag] = set()
                self._mem_tags[tag].add(full_key)

        self._writes += 1
        return True

    def delete(self, key: str, namespace: str | None = None) -> bool:
        """Remove a single key from cache."""
        full_key = self._format_key(key, namespace)
        client = self._get_client()

        if client is not None:
            try:
                client.delete(full_key)
                self._deletes += 1
                return True
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")

        # In-memory fallback
        self._mem_store.pop(full_key, None)
        self._mem_expiry.pop(full_key, None)
        self._deletes += 1
        return True

    def invalidate_prefix(self, prefix: str, namespace: str | None = None) -> int:
        """Invalidate all keys matching a prefix or pattern."""
        full_prefix = self._format_key(prefix, namespace)
        pattern = f"{full_prefix}*"
        client = self._get_client()
        count = 0

        if client is not None:
            try:
                keys = list(client.scan_iter(match=pattern))
                if keys:
                    count = client.delete(*keys)
                    self._deletes += count
                return count
            except Exception as e:
                logger.warning(f"Redis invalidate_prefix failed: {e}")

        # In-memory fallback
        matching_keys = [k for k in self._mem_store if fnmatch.fnmatch(k, pattern)]
        for k in matching_keys:
            self._mem_store.pop(k, None)
            self._mem_expiry.pop(k, None)
            count += 1
        self._deletes += count
        return count

    def invalidate_tag(self, tag: str) -> int:
        """Invalidate all keys tagged with a given semantic label."""
        tag_key = f"{self.namespace}:tag:{tag}"
        client = self._get_client()
        count = 0

        if client is not None:
            try:
                keys = list(client.smembers(tag_key))
                if keys:
                    count = client.delete(*keys)
                    self._deletes += count
                client.delete(tag_key)
                return count
            except Exception as e:
                logger.warning(f"Redis invalidate_tag failed: {e}")

        # In-memory fallback
        keys_to_delete = self._mem_tags.pop(tag, set())
        for k in keys_to_delete:
            if k in self._mem_store:
                self._mem_store.pop(k, None)
                self._mem_expiry.pop(k, None)
                count += 1
        self._deletes += count
        return count

    def flush(self, namespace: str | None = None) -> int:
        """Flush all keys in namespace or clear the entire cache."""
        ns = namespace or self.namespace
        return self.invalidate_prefix("", namespace=ns)

    def get_stats(self) -> CacheStats:
        """Compute hit rate, miss count, and total key cardinality."""
        client = self._get_client()
        total_requests = self._hits + self._misses
        hit_rate = round(self._hits / total_requests, 4) if total_requests > 0 else 0.0

        if client is not None:
            try:
                keys_count = client.dbsize()
                return CacheStats(
                    backend="redis",
                    hits=self._hits,
                    misses=self._misses,
                    writes=self._writes,
                    deletes=self._deletes,
                    hit_rate=hit_rate,
                    keys_count=keys_count,
                )
            except Exception:
                pass

        # In-memory clean up expired keys before returning count
        now = datetime.now(UTC)
        expired = [k for k, exp in self._mem_expiry.items() if exp < now]
        for k in expired:
            self._mem_store.pop(k, None)
            self._mem_expiry.pop(k, None)

        return CacheStats(
            backend="in_memory",
            hits=self._hits,
            misses=self._misses,
            writes=self._writes,
            deletes=self._deletes,
            hit_rate=hit_rate,
            keys_count=len(self._mem_store),
        )


cache_manager = CacheManager()


def hash_key(*args: Any, **kwargs: Any) -> str:
    """Create a deterministic SHA-256 fingerprint for arbitrary Python parameters."""
    raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
