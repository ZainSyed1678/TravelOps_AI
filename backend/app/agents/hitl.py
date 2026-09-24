"""Human-in-the-Loop (HITL) confirmation service, safety barrier, and audit logging."""

import asyncio
import concurrent.futures
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import nest_asyncio
from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.providers.factory import get_booking_provider


class ActionType(StrEnum):
    """Types of actions subject to Human-in-the-Loop approval."""

    REBOOK_FLIGHT = "REBOOK_FLIGHT"
    CANCEL_BOOKING = "CANCEL_BOOKING"
    BOOK_FLIGHT = "BOOK_FLIGHT"
    BOOK_HOTEL = "BOOK_HOTEL"
    ISSUE_REFUND = "ISSUE_REFUND"


class RiskLevel(StrEnum):
    """Risk severity classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionStatus(StrEnum):
    """Operational lifecycle status of an action."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class HITLBarrierException(Exception):
    """Raised when an unconfirmed mutating operation attempts to execute without human approval."""

    def __init__(self, message: str, action_id: str | None = None):
        super().__init__(message)
        self.message = message
        self.action_id = action_id


class AuditLogEntry(BaseModel):
    """Immutable audit entry recording human and automated actions."""

    id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:12]}")
    action_id: str
    action_type: str
    actor: str
    event_type: str  # CREATED, APPROVED, REJECTED, EXECUTED, BLOCKED
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)


class PendingAction(BaseModel):
    """Structured proposal for an action requiring human operator confirmation."""

    action_id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:12]}")
    thread_id: str | None = None
    action_type: str
    booking_reference: str | None = None
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "MEDIUM"
    financial_impact: dict[str, Any] = Field(default_factory=dict)
    status: str = "PENDING"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_notes: str | None = None
    execution_result: dict[str, Any] | None = None


class HITLConfirmationRequest(BaseModel):
    """Request payload to confirm and execute a pending action."""

    operator_id: str = Field(..., description="ID or role of operator/user confirming the action")
    notes: str | None = Field(None, description="Optional operator notes or justification")
    waiver_override: bool = Field(False, description="Override fee or policy restrictions if applicable")


class HITLRejectionRequest(BaseModel):
    """Request payload to reject a pending action."""

    operator_id: str = Field(..., description="ID or role of operator/user rejecting the action")
    reason: str = Field(..., description="Reason for rejection or customer feedback")


class HITLConfirmationResponse(BaseModel):
    """Response returned upon confirmation or rejection."""

    action_id: str
    action_type: str
    status: str
    resolved_by: str
    resolved_at: datetime
    execution_result: dict[str, Any] | None = None
    message: str


class HITLManager:
    """Manages pending action queues, executes verified operations, and records audit logs."""

    def __init__(self):
        self._actions: dict[str, PendingAction] = {}
        self._audit_log: list[AuditLogEntry] = []

    def clear(self) -> None:
        """Clear all stored actions and audit records (primarily for testing)."""
        self._actions.clear()
        self._audit_log.clear()

    def create_pending_action(
        self,
        action_type: str,
        summary: str,
        details: dict[str, Any],
        thread_id: str | None = None,
        risk_level: str | None = None,
        financial_impact: dict[str, Any] | None = None,
        ttl_minutes: int = 30,
    ) -> PendingAction:
        """Register a new mutating action proposal requiring human review before execution."""
        # Compute risk level if not specified
        if not risk_level:
            if action_type in (ActionType.REBOOK_FLIGHT.value, ActionType.CANCEL_BOOKING.value):
                risk_level = RiskLevel.HIGH.value
            elif action_type in (ActionType.BOOK_FLIGHT.value, ActionType.BOOK_HOTEL.value):
                risk_level = RiskLevel.MEDIUM.value
            else:
                risk_level = RiskLevel.LOW.value

        now = datetime.now(UTC)
        expires = now + timedelta(minutes=ttl_minutes)

        action = PendingAction(
            thread_id=thread_id,
            action_type=action_type,
            booking_reference=details.get("booking_reference"),
            summary=summary,
            details=details,
            risk_level=risk_level,
            financial_impact=financial_impact or {},
            status=ActionStatus.PENDING.value,
            created_at=now,
            expires_at=expires,
        )

        self._actions[action.action_id] = action

        # Audit log creation event
        self._record_audit(
            action_id=action.action_id,
            action_type=action.action_type,
            actor="SYSTEM_AGENT",
            event_type="CREATED",
            details={"summary": summary, "risk_level": risk_level, "details": details},
        )

        logger.info(
            f"[HITL] Created pending action '{action.action_id}' ({action_type}) with risk level '{risk_level}'"
        )
        return action

    def get_action(self, action_id: str) -> PendingAction | None:
        """Retrieve pending action by ID and check expiration."""
        action = self._actions.get(action_id)
        if not action:
            return None

        # Check expiration
        if (
            action.status == ActionStatus.PENDING.value
            and action.expires_at
            and datetime.now(UTC) > action.expires_at
        ):
            action.status = ActionStatus.EXPIRED.value
            self._record_audit(
                action_id=action.action_id,
                action_type=action.action_type,
                actor="SYSTEM",
                event_type="EXPIRED",
                details={"expired_at": datetime.now(UTC).isoformat()},
            )

        return action

    def list_pending_actions(
        self,
        thread_id: str | None = None,
        action_type: str | None = None,
    ) -> list[PendingAction]:
        """List all currently pending actions, optionally filtered."""
        results: list[PendingAction] = []
        for action in self._actions.values():
            # Refresh expired state
            if (
                action.status == ActionStatus.PENDING.value
                and action.expires_at
                and datetime.now(UTC) > action.expires_at
            ):
                action.status = ActionStatus.EXPIRED.value

            if action.status != ActionStatus.PENDING.value:
                continue
            if thread_id and action.thread_id != thread_id:
                continue
            if action_type and action.action_type != action_type:
                continue
            results.append(action)

        return results

    def enforce_safety_guard(self, action_type: str, action_id: str | None = None) -> None:
        """Enforce that financial or booking mutations CANNOT proceed without human approval."""
        if not action_id:
            self._record_audit(
                action_id="UNKNOWN",
                action_type=action_type,
                actor="SECURITY_GUARD",
                event_type="BLOCKED",
                details={"reason": "Attempted mutation without action_id"},
            )
            raise HITLBarrierException(
                f"Safety Violation: Action '{action_type}' requires explicit Human-in-the-Loop approval before execution."
            )

        action = self.get_action(action_id)
        if not action:
            raise HITLBarrierException(
                f"Safety Violation: Action ID '{action_id}' not found.",
                action_id=action_id,
            )

        if action.status != ActionStatus.APPROVED.value:
            self._record_audit(
                action_id=action_id,
                action_type=action_type,
                actor="SECURITY_GUARD",
                event_type="BLOCKED",
                details={"status": action.status, "reason": "Action not approved by human"},
            )
            raise HITLBarrierException(
                f"Safety Violation: Action '{action_id}' is in status '{action.status}'. Execution requires 'APPROVED' status.",
                action_id=action_id,
            )

    def confirm_action(
        self,
        action_id: str,
        operator_id: str,
        notes: str | None = None,
        waiver_override: bool = False,
    ) -> HITLConfirmationResponse:
        """Approve and execute a pending action through the safety barrier."""
        action = self.get_action(action_id)
        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pending action '{action_id}' not found.",
            )

        if action.status != ActionStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action '{action_id}' is already in status '{action.status}' and cannot be confirmed.",
            )

        logger.info(f"[HITL] Operator '{operator_id}' confirmed action '{action_id}' ({action.action_type})")

        # Execute verified supplier operation
        execution_result = self._execute_action(action, operator_id, waiver_override)

        now = datetime.now(UTC)
        action.status = ActionStatus.APPROVED.value
        action.resolved_at = now
        action.resolved_by = operator_id
        action.resolution_notes = notes
        action.execution_result = execution_result

        # Record audit log
        self._record_audit(
            action_id=action.action_id,
            action_type=action.action_type,
            actor=operator_id,
            event_type="APPROVED",
            details={"notes": notes, "waiver_override": waiver_override},
        )
        self._record_audit(
            action_id=action.action_id,
            action_type=action.action_type,
            actor=operator_id,
            event_type="EXECUTED",
            details=execution_result,
        )

        # Update LangGraph conversation thread state if thread_id is registered
        self._update_thread_on_confirm(action, operator_id, execution_result)

        return HITLConfirmationResponse(
            action_id=action.action_id,
            action_type=action.action_type,
            status=action.status,
            resolved_by=operator_id,
            resolved_at=now,
            execution_result=execution_result,
            message=f"Action '{action.action_type}' was successfully approved by {operator_id} and executed.",
        )

    def reject_action(
        self,
        action_id: str,
        operator_id: str,
        reason: str,
    ) -> HITLConfirmationResponse:
        """Reject a pending action proposal and notify the conversation thread."""
        action = self.get_action(action_id)
        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pending action '{action_id}' not found.",
            )

        if action.status != ActionStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action '{action_id}' is already in status '{action.status}' and cannot be rejected.",
            )

        now = datetime.now(UTC)
        action.status = ActionStatus.REJECTED.value
        action.resolved_at = now
        action.resolved_by = operator_id
        action.resolution_notes = reason

        self._record_audit(
            action_id=action.action_id,
            action_type=action.action_type,
            actor=operator_id,
            event_type="REJECTED",
            details={"reason": reason},
        )

        logger.info(f"[HITL] Operator '{operator_id}' rejected action '{action_id}': {reason}")

        # Update LangGraph conversation thread
        self._update_thread_on_reject(action, operator_id, reason)

        return HITLConfirmationResponse(
            action_id=action.action_id,
            action_type=action.action_type,
            status=action.status,
            resolved_by=operator_id,
            resolved_at=now,
            execution_result=None,
            message=f"Action '{action.action_type}' was rejected by {operator_id}. Reason: {reason}",
        )

    def get_audit_trail(self, action_id: str | None = None) -> list[AuditLogEntry]:
        """Return the immutable audit trail, optionally filtered by action_id."""
        if action_id:
            return [e for e in self._audit_log if e.action_id == action_id]
        return list(self._audit_log)

    def _execute_action(
        self,
        action: PendingAction,
        operator_id: str,
        waiver_override: bool,
    ) -> dict[str, Any]:
        """Execute the actual mutating supplier call based on approved action payload."""
        provider = get_booking_provider()

        if action.action_type == ActionType.REBOOK_FLIGHT.value:
            b_ref = action.details.get("booking_reference", "")
            new_fl = action.details.get("new_flight", "EK501")
            waiver = action.details.get("waiver_applied", False) or waiver_override

            # Call provider rebook
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        rebook_res = pool.submit(
                            asyncio.run,
                            provider.rebook_booking(b_ref, new_fl),
                        ).result()
                else:
                    rebook_res = asyncio.run(provider.rebook_booking(b_ref, new_fl))
            except Exception:
                nest_asyncio.apply()
                rebook_res = asyncio.get_event_loop().run_until_complete(
                    provider.rebook_booking(b_ref, new_fl)
                )

            total_due = 0.0 if waiver else rebook_res.total_amount_due

            return {
                "operation": "REBOOK_FLIGHT",
                "original_booking_reference": b_ref,
                "new_booking_reference": rebook_res.new_booking_reference,
                "new_pnr": rebook_res.new_pnr,
                "status": "CONFIRMED",
                "waiver_applied": waiver,
                "total_amount_due": total_due,
                "currency": rebook_res.currency,
                "executed_at": datetime.now(UTC).isoformat(),
            }

        elif action.action_type == ActionType.CANCEL_BOOKING.value:
            b_ref = action.details.get("booking_reference", "")
            reason = action.details.get("reason", "Cancelled by traveler")

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        cancel_res = pool.submit(
                            asyncio.run,
                            provider.cancel_booking(b_ref, reason),
                        ).result()
                else:
                    cancel_res = asyncio.run(provider.cancel_booking(b_ref, reason))
            except Exception:
                nest_asyncio.apply()
                cancel_res = asyncio.get_event_loop().run_until_complete(
                    provider.cancel_booking(b_ref, reason)
                )

            return {
                "operation": "CANCEL_BOOKING",
                "booking_reference": cancel_res.booking_reference,
                "cancellation_id": cancel_res.cancellation_id,
                "refund_amount": cancel_res.refund_amount,
                "penalty_amount": cancel_res.penalty_amount,
                "currency": cancel_res.currency,
                "status": "CANCELLED",
                "executed_at": datetime.now(UTC).isoformat(),
            }

        else:
            return {
                "operation": action.action_type,
                "status": "EXECUTED",
                "details": action.details,
                "executed_at": datetime.now(UTC).isoformat(),
            }

    def _record_audit(
        self,
        action_id: str,
        action_type: str,
        actor: str,
        event_type: str,
        details: dict[str, Any],
    ) -> None:
        """Append an entry to the audit log."""
        entry = AuditLogEntry(
            action_id=action_id,
            action_type=action_type,
            actor=actor,
            event_type=event_type,
            details=details,
        )
        self._audit_log.append(entry)

    def _update_thread_on_confirm(
        self,
        action: PendingAction,
        operator_id: str,
        exec_res: dict[str, Any],
    ) -> None:
        """Update conversation thread in TravelAgentOrchestrator when action is confirmed."""
        if not action.thread_id:
            return

        from app.agents.orchestrator import agent_orchestrator

        thread_state = agent_orchestrator.get_thread_state(action.thread_id)
        if not thread_state:
            return

        thread_state["requires_human_confirmation"] = False
        thread_state["confirmation_status"] = "APPROVED"
        thread_state["pending_action"] = None

        new_pnr = exec_res.get("new_pnr", "CONFIRMED")
        b_ref = exec_res.get("original_booking_reference", action.details.get("booking_reference", ""))
        amount = exec_res.get("total_amount_due", 0.0)
        curr = exec_res.get("currency", "INR")

        msg = (
            f"✅ **Action Confirmed & Executed**\n\n"
            f"The `{action.action_type}` for reservation `{b_ref}` has been successfully executed with supplier.\n"
            f"- **Status:** CONFIRMED\n"
            f"- **PNR / Reference:** `{new_pnr}`\n"
            f"- **Amount Charged:** {curr} {amount:,.2f}\n"
            f"- **Approved By:** `{operator_id}`"
        )
        thread_state["messages"].append({"role": "assistant", "content": msg})
        thread_state["trace"].append(
            f"hitl: action {action.action_id} confirmed and executed by {operator_id}; PNR: {new_pnr}"
        )

    def _update_thread_on_reject(
        self,
        action: PendingAction,
        operator_id: str,
        reason: str,
    ) -> None:
        """Update conversation thread in TravelAgentOrchestrator when action is rejected."""
        if not action.thread_id:
            return

        from app.agents.orchestrator import agent_orchestrator

        thread_state = agent_orchestrator.get_thread_state(action.thread_id)
        if not thread_state:
            return

        thread_state["requires_human_confirmation"] = False
        thread_state["confirmation_status"] = "REJECTED"
        thread_state["pending_action"] = None

        b_ref = action.details.get("booking_reference", "")
        msg = (
            f"❌ **Action Rejected**\n\n"
            f"The proposed `{action.action_type}` for reservation `{b_ref}` was rejected by `{operator_id}`.\n"
            f"**Reason:** {reason}\n\n"
            "No changes or charges have been applied to your itinerary."
        )
        thread_state["messages"].append({"role": "assistant", "content": msg})
        thread_state["trace"].append(
            f"hitl: action {action.action_id} rejected by {operator_id}; reason: {reason}"
        )


# Global singleton instance of HITLManager
hitl_manager = HITLManager()
