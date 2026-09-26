"""Tool execution sandboxing, argument validation, and parameter confinement."""

import re
from typing import Any

from pydantic import BaseModel, Field

# Disallowed shell command and path traversal patterns
PATH_TRAVERSAL_PATTERN = re.compile(
    r"(\.\.[/\\]|[/\\]etc[/\\]|[/\\]sys[/\\]|[A-Za-z]:[/\\]Windows)", re.IGNORECASE
)
SHELL_METACHOICE_PATTERN = re.compile(
    r"([;&|`]|^\s*exec\b|^\s*bash\b|^\s*powershell\b|\$\(.*\))", re.IGNORECASE
)


class ToolSandboxResult(BaseModel):
    """Result of sandbox inspection for tool invocations."""

    is_allowed: bool = Field(..., description="Whether tool execution is permitted")
    reason: str | None = Field(None, description="Explanation if rejected")
    sanitized_parameters: dict[str, Any] = Field(
        default_factory=dict, description="Sanitized parameters"
    )


class ToolSandbox:
    """Sandbox environment isolating and restricting tool execution."""

    ALLOWED_TOOLS: frozenset[str] = frozenset(
        {
            "search_flights",
            "price_flight",
            "get_flight_status",
            "search_hotels",
            "get_hotel_details",
            "query_rag_policy",
            "query_knowledge_graph",
            "request_booking_confirmation",
            "execute_rebooking",
            "cancel_booking",
        }
    )

    def validate_tool_call(self, tool_name: str, parameters: dict[str, Any]) -> ToolSandboxResult:
        """Validate that the tool is registered and all parameters comply with sandbox boundaries."""
        if tool_name not in self.ALLOWED_TOOLS:
            return ToolSandboxResult(
                is_allowed=False,
                reason=f"Tool '{tool_name}' is not in the authorized sandbox whitelist.",
            )

        sanitized_params = dict(parameters)

        for key, value in parameters.items():
            if isinstance(value, str):
                # Check for path traversal
                if PATH_TRAVERSAL_PATTERN.search(value):
                    return ToolSandboxResult(
                        is_allowed=False,
                        reason=f"Parameter '{key}' contains suspicious path traversal sequence: '{value}'.",
                    )
                # Check for shell metacharacters
                if SHELL_METACHOICE_PATTERN.search(value):
                    return ToolSandboxResult(
                        is_allowed=False,
                        reason=f"Parameter '{key}' contains prohibited shell metacharacters.",
                    )
            elif isinstance(value, (int, float)):
                # Value bounds checks
                if key in ("passengers", "adults") and not (1 <= value <= 9):
                    return ToolSandboxResult(
                        is_allowed=False,
                        reason=f"Parameter '{key}' value {value} is out of allowable passenger bounds [1, 9].",
                    )
                if key in ("max_budget", "budget") and value < 0:
                    return ToolSandboxResult(
                        is_allowed=False,
                        reason=f"Budget parameter '{key}' cannot be negative.",
                    )

        return ToolSandboxResult(
            is_allowed=True,
            sanitized_parameters=sanitized_params,
        )


tool_sandbox = ToolSandbox()
