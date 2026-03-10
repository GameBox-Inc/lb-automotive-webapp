"""
Request tracing middleware. Sets correlation IDs for every request.
Must run first (outermost) so trace context is available to all downstream code.
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from observability.tracing import init_request_trace, update_phase, get_trace_context, PHASE_RESPONSE_SENT


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Injects requestId, traceId, sessionId, podName, routeName into contextvars.
    Downstream code (webhook, logging) can add callSid, accountSid, phase.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-Id") or request.headers.get("X-Twilio-Request-Id", "")
        trace_id = request.headers.get("X-Trace-Id", "")
        if not request_id:
            import uuid
            request_id = str(uuid.uuid4())
        if not trace_id:
            trace_id = request_id

        init_request_trace(
            request_id=request_id,
            trace_id=trace_id,
            route_name=request.url.path,
        )
        request.state.trace = get_trace_context()

        response = await call_next(request)
        update_phase(PHASE_RESPONSE_SENT)
        return response
