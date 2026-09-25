"""Context variables for request tracing and distributed correlation."""

from contextvars import ContextVar

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id_ctx", default="")


def get_correlation_id() -> str:
    """Retrieve the active correlation ID for the current async task context."""
    return correlation_id_ctx.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the active correlation ID for the current async task context."""
    correlation_id_ctx.set(correlation_id)
