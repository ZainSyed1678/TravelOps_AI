"""Security audit logging and event tracking for threat detection."""

import hashlib
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.context import get_correlation_id
from app.core.logging import logger


class SecurityAuditEvent(BaseModel):
    """Normalized security audit event entry."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: str = Field(..., description="Classification of security event")
    severity: str = Field(..., description="Severity level: LOW, MEDIUM, HIGH, CRITICAL")
    client_ip: str = Field(default="127.0.0.1")
    correlation_id: str = Field(default="")
    details: dict[str, Any] = Field(default_factory=dict)
    payload_hash: str = Field(default="", description="SHA-256 hash of payload")


class SecurityAuditLogger:
    """Thread-safe in-memory security audit log recorder."""

    def __init__(self, max_records: int = 1000) -> None:
        self.max_records = max_records
        self._events: list[SecurityAuditEvent] = []
        self._lock = threading.Lock()

    def record_event(
        self,
        event_type: str,
        severity: str,
        details: dict[str, Any] | None = None,
        raw_payload: str | None = None,
        client_ip: str = "127.0.0.1",
        correlation_id: str | None = None,
    ) -> SecurityAuditEvent:
        """Record and store a security event."""
        cid = correlation_id or get_correlation_id() or ""
        p_hash = ""
        if raw_payload:
            p_hash = hashlib.sha256(raw_payload.encode("utf-8", errors="ignore")).hexdigest()

        event = SecurityAuditEvent(
            event_type=event_type,
            severity=severity,
            client_ip=client_ip,
            correlation_id=cid,
            details=details or {},
            payload_hash=p_hash,
        )

        with self._lock:
            self._events.append(event)
            if len(self._events) > self.max_records:
                self._events.pop(0)

        log_fn = logger.error if severity in ("HIGH", "CRITICAL") else logger.warning
        log_fn(
            f"SECURITY AUDIT: [{severity}] {event_type} - {details} (cid={cid}, hash={p_hash[:8]}...)"
        )
        return event

    def get_events(
        self,
        limit: int = 50,
        event_type: str | None = None,
        min_severity: str | None = None,
    ) -> list[SecurityAuditEvent]:
        """Retrieve recorded security audit events with optional filtering."""
        severity_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        min_level = severity_order.get(min_severity.upper(), 0) if min_severity else 0

        with self._lock:
            filtered = list(self._events)

        if event_type:
            filtered = [e for e in filtered if e.event_type.lower() == event_type.lower()]

        if min_level > 0:
            filtered = [e for e in filtered if severity_order.get(e.severity, 0) >= min_level]

        return filtered[-limit:][::-1]

    def clear(self) -> None:
        """Clear audit log buffer (useful for testing)."""
        with self._lock:
            self._events.clear()


security_audit_logger = SecurityAuditLogger()
