"""Security headers and HTTP defense middleware."""

from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.context import get_correlation_id
from app.core.exceptions import ProblemDetail
from app.security.audit import security_audit_logger
from app.security.sanitizer import check_sql_injection


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces defensive HTTP response headers and sanitizes incoming query strings."""

    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check query parameters for SQL injection attempts
        query_string = str(request.url.query)
        if query_string:
            is_suspicious, pattern = check_sql_injection(query_string)
            if is_suspicious:
                cid = getattr(request.state, "correlation_id", get_correlation_id() or "")
                client_ip = request.client.host if request.client else "127.0.0.1"

                security_audit_logger.record_event(
                    event_type="SQL_INJECTION_PROBE_BLOCKED",
                    severity="HIGH",
                    details={"path": request.url.path, "query": query_string, "pattern": pattern},
                    raw_payload=query_string,
                    client_ip=client_ip,
                    correlation_id=cid,
                )

                problem = ProblemDetail(
                    type="https://travelops.ai/errors/security-violation",
                    title="Malicious Input Detected",
                    status=status.HTTP_400_BAD_REQUEST,
                    detail="Request rejected due to potentially malicious query parameters.",
                    instance=request.url.path,
                    correlation_id=cid,
                )
                headers = dict(self.SECURITY_HEADERS)
                headers["X-Correlation-ID"] = cid
                headers["X-Request-ID"] = cid
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content=problem.model_dump(exclude_none=True),
                    media_type="application/problem+json",
                    headers=headers,
                )

        response = await call_next(request)

        # Inject defensive security headers
        for header, val in self.SECURITY_HEADERS.items():
            response.headers[header] = val

        return response
