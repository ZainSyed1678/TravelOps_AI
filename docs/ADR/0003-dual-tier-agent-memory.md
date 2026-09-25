# ADR 0003: Dual-Tier Redis Hot Cache & PostgreSQL Durable Conversation Memory

## Status
Accepted

## Context
Conversational AI agents in enterprise operations require:
1. **Low Latency**: Sub-10ms response times for active conversational state retrieval and token buffer management.
2. **Durability & ACID Guarantees**: Long-term storage of customer journey threads, operator interactions, and session metadata across days or months.
3. **Learned Personalization**: Dynamic extraction and persistence of passenger preferences (preferred airlines, seat types, cabin classes, meal preferences) across multi-turn sessions.

Single-tier architectures either suffer from volatile data loss (Redis-only) or excessive query latency and connection pool pressure (PostgreSQL-only).

## Decision
We implemented a **Dual-Tier Memory Service (`AgentMemoryService`)**:
1. **Hot Tier (Redis)**:
   - Stores active conversation token buffers and message lists keyed by `travelops:memory:{thread_id}:messages`.
   - Utilizes sliding TTL (default 24 hours) for fast retrieval during active user sessions.
   - Includes in-memory thread-safe dictionary fallback if Redis is unavailable.
2. **Durable Tier (PostgreSQL)**:
   - Persists normalized session records (`agent_sessions`) and message records (`agent_messages`) using SQLAlchemy 2.0 with Alembic schema migrations.
   - Maintains `traveler_memory_profiles` capturing structured traveler preferences updated asynchronously after each conversational session.
3. **Write-Through Synchronization**:
   - New messages are cached immediately in Redis and written asynchronously to PostgreSQL.
   - On cache miss, the durable store warms the Redis cache automatically.

## Consequences
### Positive
- Sub-5ms retrieval for active chat sessions.
- Zero message loss: durable history preserved across container restarts and Redis flush events.
- Learned passenger preferences persist permanently and personalize future flight ranking.

### Negative
- Requires maintaining dual persistence code paths and synchronization logic.
- Potential cache invalidation edge cases handled via atomic key management.
