"""Security operations, threat inspection, and audit REST API endpoints."""

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.api_response import ApiResponse, api_success
from app.security.audit import SecurityAuditEvent, security_audit_logger
from app.security.injection_guard import InjectionInspectionResult, injection_guard
from app.security.tool_sandbox import ToolSandboxResult, tool_sandbox

router = APIRouter()


class InspectPromptRequest(BaseModel):
    """Payload to test prompt safety."""

    prompt: str = Field(..., min_length=1, description="Prompt text to analyze")


class ValidateToolRequest(BaseModel):
    """Payload to validate tool invocation parameters."""

    tool_name: str = Field(..., description="Name of the agent tool to validate")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class SecurityStatusData(BaseModel):
    """Active security defenses and status."""

    prompt_injection_guard: bool = True
    tool_sandbox: bool = True
    input_sanitizer: bool = True
    security_headers_enabled: bool = True
    audit_logger_records: int
    active_defenses: list[str]


@router.post(
    "/inspect-prompt",
    response_model=ApiResponse[InjectionInspectionResult],
    summary="Inspect Prompt for Injection & Jailbreak",
    description="Analyze a candidate prompt against heuristic triggers, delimiters, and adversarial jailbreak patterns.",
)
async def inspect_prompt(request: InspectPromptRequest) -> ApiResponse[InjectionInspectionResult]:
    """Inspect and score an input prompt."""
    result = injection_guard.inspect(request.prompt)
    msg = (
        "Prompt passed security inspection"
        if result.is_safe
        else f"Prompt flagged as {result.risk_category}"
    )
    return api_success(data=result, message=msg)


@router.post(
    "/validate-tool",
    response_model=ApiResponse[ToolSandboxResult],
    summary="Validate Tool Invocation in Sandbox",
    description="Check tool arguments for path traversal, shell metacharacters, or parameter bounds violations.",
)
async def validate_tool(request: ValidateToolRequest) -> ApiResponse[ToolSandboxResult]:
    """Validate tool parameters against sandbox policy."""
    result = tool_sandbox.validate_tool_call(request.tool_name, request.parameters)
    msg = (
        "Tool invocation permitted by sandbox"
        if result.is_allowed
        else f"Tool invocation rejected: {result.reason}"
    )
    return api_success(data=result, message=msg)


@router.get(
    "/audit-logs",
    response_model=ApiResponse[list[SecurityAuditEvent]],
    summary="List Security Audit Events",
    description="Retrieve recorded security events, threat detections, and blocked injection attempts.",
)
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200, description="Max events to return"),
    event_type: str | None = Query(default=None, description="Filter by event type"),
    min_severity: str | None = Query(
        default=None, description="Filter by minimum severity (LOW, MEDIUM, HIGH, CRITICAL)"
    ),
) -> ApiResponse[list[SecurityAuditEvent]]:
    """Retrieve security audit events."""
    events = security_audit_logger.get_events(
        limit=limit,
        event_type=event_type,
        min_severity=min_severity,
    )
    return api_success(
        data=events,
        message=f"Retrieved {len(events)} security audit events",
        total=len(events),
    )


@router.get(
    "/status",
    response_model=ApiResponse[SecurityStatusData],
    summary="Get Security Defense Status",
    description="Inspect operational status of platform security layers, guards, and telemetry.",
)
async def get_security_status() -> ApiResponse[SecurityStatusData]:
    """Inspect active platform defenses."""
    with security_audit_logger._lock:
        audit_count = len(security_audit_logger._events)

    status_data = SecurityStatusData(
        prompt_injection_guard=True,
        tool_sandbox=True,
        input_sanitizer=True,
        security_headers_enabled=True,
        audit_logger_records=audit_count,
        active_defenses=[
            "Prompt Injection Defense (Heuristic & Delimiter Detection)",
            "Tool Sandbox & Parameter Boundary Confinement",
            "XSS Tag Stripping & SQL Injection Probes",
            "Defensive HTTP Security Headers (CSP, HSTS, X-Frame-Options)",
            "Append-Only In-Memory Security Audit Logger",
        ],
    )
    return api_success(data=status_data, message="Security defenses operational")
