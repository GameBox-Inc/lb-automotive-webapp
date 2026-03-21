"""
Prometheus monitoring and metrics
"""
import functools
import re
from contextlib import contextmanager
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from time import time
from datetime import datetime
import logging
from pythonjsonlogger import jsonlogger

logger = logging.getLogger(__name__)

# Normalize dynamic path segments so http_requests_total does not explode in cardinality.
_UUID_SEGMENT = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def normalize_http_endpoint_label(request: Request) -> str:
    """
    Prefer the FastAPI/Starlette route template (e.g. /api/appointments/{id}).
    Otherwise collapse UUID and numeric path segments to {id}.
    """
    route = request.scope.get("route")
    if route is not None:
        path = getattr(route, "path", None)
        if path:
            return path
    path = request.url.path or "/"
    if path in ("/", ""):
        return "/"
    parts = path.split("/")
    out = []
    for seg in parts:
        if seg == "":
            out.append("")
            continue
        if _UUID_SEGMENT.match(seg):
            out.append("{id}")
        elif seg.isdigit():
            out.append("{id}")
        else:
            out.append(seg)
    return "/".join(out) if out else "/"


# HTTP Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Database Metrics
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['table', 'operation']
)

db_queries_total = Counter(
    'db_queries_total',
    'Total database queries',
    ['table', 'operation']
)

# Business Metrics
appointments_total = Counter(
    'appointments_total',
    'Total appointments',
    ['status', 'source']  # source: web, ivr
)

ivr_calls_total = Counter(
    'ivr_calls_total',
    'Total IVR calls',
    ['step', 'language']
)

# Concurrent Twilio IVR webhook requests in this process (for scaling on call load).
ivr_webhook_in_flight = Gauge(
    'ivr_webhook_in_flight',
    'Number of Twilio IVR webhook requests currently being handled in this worker process',
)


def track_ivr_webhook_inflight(func):
    """Decorator: increment ivr_webhook_in_flight for the duration of the webhook handler."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ivr_webhook_in_flight.inc()
        try:
            return func(*args, **kwargs)
        finally:
            ivr_webhook_in_flight.dec()

    return wrapper


@contextmanager
def ivr_webhook_inflight_cm():
    """Context manager variant for nested or non-decorator use."""
    ivr_webhook_in_flight.inc()
    try:
        yield
    finally:
        ivr_webhook_in_flight.dec()


# IVR TTS (Twilio Polly vs ElevenLabs + Play)
ivr_tts_requests_total = Counter(
    'ivr_tts_requests_total',
    'IVR TTS routing attempts',
    ['provider', 'result'],
)

ivr_tts_duration_seconds = Histogram(
    'ivr_tts_duration_seconds',
    'ElevenLabs TTS synthesis duration (seconds)',
    ['result'],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

active_users = Gauge(
    'active_users',
    'Currently active users'
)

# Application Metrics
app_info = Gauge(
    'app_info',
    'Application information',
    ['version']
)

async def track_request(request: Request, call_next):
    """Middleware to track HTTP requests"""
    start_time = time()
    
    # Process request
    response = await call_next(request)
    
    # Track metrics
    duration = time() - start_time
    endpoint = normalize_http_endpoint_label(request)
    method = request.method
    status = response.status_code
    
    http_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status=status
    ).inc()
    
    http_request_duration_seconds.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)
    
    return response

def track_db_query(table: str, operation: str):
    """Decorator to track database queries"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time()
            db_queries_total.labels(table=table, operation=operation).inc()
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time() - start_time
                db_query_duration_seconds.labels(
                    table=table,
                    operation=operation
                ).observe(duration)
        
        return wrapper
    return decorator

async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# Initialize app info
app_info.labels(version='1.0.0').set(1)

def setup_logging():
    """Configure structured logging with trace context (callSid, requestId, etc.) in every log."""
    from observability.trace_logging_filter import TraceContextFilter

    class CustomJsonFormatter(jsonlogger.JsonFormatter):
        TRACE_FIELDS = ("callSid", "accountSid", "requestId", "traceId", "sessionId", "podName", "routeName", "latencyMs", "phase")

        def add_fields(self, log_record, record, message_dict):
            super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
            log_record['timestamp'] = datetime.utcnow().isoformat()
            log_record['level'] = record.levelname
            log_record['logger'] = record.name
            for f in self.TRACE_FIELDS:
                if hasattr(record, f):
                    log_record[f] = getattr(record, f)

    handler = logging.StreamHandler()
    formatter = CustomJsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    handler.addFilter(TraceContextFilter())

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
