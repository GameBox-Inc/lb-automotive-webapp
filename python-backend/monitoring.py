"""
Prometheus monitoring and metrics
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from time import time
import logging

logger = logging.getLogger(__name__)

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
    endpoint = request.url.path
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
