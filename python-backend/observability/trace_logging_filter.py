"""
Logging filter that injects trace context (callSid, requestId, etc.) into every log record.
Ensures all logs have correlation IDs for debugging.
"""
import logging
from observability.tracing import get_trace_context


class TraceContextFilter(logging.Filter):
    """
    Adds callSid, accountSid, requestId, traceId, sessionId, podName, routeName, latencyMs, phase
    to every log record. Update latencyMs before each log by calling update_phase().
    """

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_trace_context()
        for key, value in ctx.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True
