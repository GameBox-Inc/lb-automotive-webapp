"""
Request tracing and correlation IDs for end-to-end debugging.
Provides contextvars for callSid, requestId, traceId, sessionId, podName, routeName, latencyMs, phase.
"""
import os
import time
import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any

# Phase constants for IVR pipeline
PHASE_WEBHOOK_RECEIVED = "webhook_received"
PHASE_STT_STARTED = "stt_started"
PHASE_LLM_STARTED = "llm_started"
PHASE_LLM_COMPLETE = "llm_complete"
PHASE_TTS_READY = "tts_ready"

# Availability / scheduling phases
PHASE_AVAILABILITY_COMPUTE = "availability_compute"
PHASE_BOOKING_CREATE = "booking_create"
PHASE_RESPONSE_SENT = "response_sent"
PHASE_ERROR = "error"

_trace_context: ContextVar[Dict[str, Any]] = ContextVar(
    "trace_context",
    default={}
)


def _ensure_context() -> Dict[str, Any]:
    """Get or create trace context."""
    try:
        ctx = _trace_context.get()
    except LookupError:
        ctx = {}
        _trace_context.set(ctx)
    return ctx


def init_request_trace(
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    session_id: Optional[str] = None,
    route_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Initialize trace context for a new request. Call from middleware.
    Returns the context dict.
    """
    ctx = _ensure_context()
    ctx.clear()
    ctx["requestId"] = request_id or str(uuid.uuid4())
    ctx["traceId"] = trace_id or ctx["requestId"]
    ctx["sessionId"] = session_id or str(uuid.uuid4())[:8]
    ctx["podName"] = os.getenv("HOSTNAME", os.getenv("POD_NAME", "local"))
    ctx["routeName"] = route_name or ""
    ctx["callSid"] = ""
    ctx["accountSid"] = ""
    ctx["phase"] = ""
    ctx["latencyMs"] = 0
    ctx["_start_time"] = time.perf_counter()
    return ctx


def set_twilio_context(call_sid: str, account_sid: str = "") -> None:
    """Set Twilio correlation IDs. Call from webhook handler after parsing form."""
    ctx = _ensure_context()
    ctx["callSid"] = call_sid or ""
    ctx["accountSid"] = account_sid or ""


def update_phase(phase: str) -> None:
    """Update the current phase (e.g. webhook_received, llm_started, tts_ready)."""
    ctx = _ensure_context()
    ctx["phase"] = phase
    if "_start_time" in ctx:
        ctx["latencyMs"] = int((time.perf_counter() - ctx["_start_time"]) * 1000)


def get_trace_context() -> Dict[str, Any]:
    """
    Get current trace context for logging. Excludes internal keys.
    Returns a copy suitable for log extra=.
    """
    try:
        ctx = _trace_context.get()
    except LookupError:
        return {}
    out = {
        "callSid": ctx.get("callSid", ""),
        "accountSid": ctx.get("accountSid", ""),
        "requestId": ctx.get("requestId", ""),
        "traceId": ctx.get("traceId", ""),
        "sessionId": ctx.get("sessionId", ""),
        "podName": ctx.get("podName", ""),
        "routeName": ctx.get("routeName", ""),
        "latencyMs": ctx.get("latencyMs", 0),
        "phase": ctx.get("phase", ""),
    }
    return out


def get_trace_extra() -> Dict[str, Any]:
    """Alias for get_trace_context() for logger.info(..., extra=get_trace_extra())."""
    return get_trace_context()


def bind_trace_to_logger(logger_instance, **kwargs) -> Dict[str, Any]:
    """
    Merge trace context with additional kwargs for a log call.
    Usage: logger.info("msg", extra=bind_trace_to_logger(logger, key="value"))
    """
    extra = get_trace_context()
    extra.update(kwargs)
    return extra


def restore_trace_context(ctx: Dict[str, Any]) -> None:
    """
    Restore trace context from a dict (e.g. when passing to background tasks).
    Call at the start of a background task to propagate correlation IDs.
    """
    if not ctx:
        return
    c = _ensure_context()
    c.update({k: v for k, v in ctx.items() if not k.startswith("_")})
