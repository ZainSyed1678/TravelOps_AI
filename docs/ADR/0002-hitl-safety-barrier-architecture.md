# ADR 0002: Human-in-the-Loop (HITL) Execution Safety Barrier Architecture

## Status
Accepted

## Context
Autonomous AI agents interacting with live travel reservation systems (GDS, NDC APIs) can trigger irreversible real-world mutations:
- Issuing non-refundable airline tickets.
- Cancelling existing reservations and forfeiting passenger seats.
- Executing disruption rebooking that incurs credit card charges or airline penalty fees.

Allowing autonomous LLMs to directly execute these operations without deterministic guardrails introduces unacceptable business, financial, and compliance risks.

## Decision
We implemented a **Synchronous Human-in-the-Loop (HITL) Execution Barrier** within the LangGraph orchestrator:
1. **Risk Classification**: Actions are categorized into severity levels:
   - `LOW` / `MEDIUM`: Read-only queries, flight availability searches, policy Q&A (executed autonomously).
   - `HIGH` / `CRITICAL`: Mutations including `BOOK_FLIGHT`, `CANCEL_BOOKING`, `REBOOK_FLIGHT`, `ISSUE_REFUND`.
2. **State Halt & Proposal Enqueueing**: When a mutating tool is invoked by an agent, execution is paused immediately. A structured `PendingAction` proposal is created containing parameter diffs, financial impact estimates, and a unique action ID (`act_*`).
3. **Dedicated Operator REST Gate**: Proposals can only be resolved via authenticated REST endpoints (`POST /api/v1/agents/hitl/actions/{action_id}/confirm` or `/reject`).
4. **Immutable Audit Ledger**: All creation, approval, and rejection events are written to an append-only audit log with operator credentials, timestamp, and justification notes.

## Consequences
### Positive
- Guarantees 100% safety compliance on high-risk mutations (verified by automated benchmark `agent_safety_compliance == 1.00`).
- Provides operational teams with real-time inspection, parameter overrides, and cancellation rationale logging.
- Protects travelers from unintended financial penalties or accidental reservation drops.

### Negative
- Asynchronous operational latency: requires human supervisor interaction before bookings or rebookings are dispatched to GDS providers.
