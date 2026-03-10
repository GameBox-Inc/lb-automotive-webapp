"""
Request/Response logging middleware for security auditing.
Includes correlation IDs (callSid, requestId, traceId, etc.) in every log for end-to-end tracing.
"""
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from observability.tracing import get_trace_context, update_phase
from observability.tracing import PHASE_RESPONSE_SENT

logger = logging.getLogger(__name__)


def _log_extra(**kwargs):
    """Merge trace context with additional fields for logging."""
    extra = get_trace_context()
    extra.update(kwargs)
    return extra


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log API requests and responses for security auditing.
    Always logs Twilio webhook requests. Includes callSid, requestId, traceId, etc. in every log.
    """
    
    # Sensitive endpoints that should always be logged
    SENSITIVE_ENDPOINTS = [
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/verify-captcha",
        "/api/staff",
        "/api/staff/",
        "/api/settings",
        "/api/customers",
    ]
    
    # Twilio webhook - always log for IVR debugging
    TWILIO_WEBHOOK_PATH = "/api/twilio/webhook"
    
    # Methods that modify data
    MODIFY_METHODS = ["POST", "PUT", "PATCH", "DELETE"]
    
    def _should_log_request(self, request: Request) -> bool:
        return (
            request.url.path == self.TWILIO_WEBHOOK_PATH
            or any(request.url.path.startswith(ep) for ep in self.SENSITIVE_ENDPOINTS)
            or request.method in self.MODIFY_METHODS
        )
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        user_agent = request.headers.get("User-Agent", "unknown")
        is_sensitive = any(request.url.path.startswith(ep) for ep in self.SENSITIVE_ENDPOINTS)
        is_modify = request.method in self.MODIFY_METHODS
        
        if self._should_log_request(request):
            logger.info(
                f"API Request: {request.method} {request.url.path}",
                extra=_log_extra(
                    client_ip=client_ip,
                    user_agent=user_agent,
                    method=request.method,
                    path=request.url.path,
                    query_params=str(request.query_params),
                    is_sensitive=is_sensitive,
                )
            )
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            update_phase(PHASE_RESPONSE_SENT)
            
            if self._should_log_request(request):
                logger.info(
                    f"API Response: {request.method} {request.url.path} - {response.status_code}",
                    extra=_log_extra(
                        client_ip=client_ip,
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        process_time=process_time,
                        latencyMs=int(process_time * 1000),
                    )
                )
            
            if process_time > 2.0:
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} took {process_time:.2f}s",
                    extra=_log_extra(
                        client_ip=client_ip,
                        method=request.method,
                        path=request.url.path,
                        process_time=process_time,
                        latencyMs=int(process_time * 1000),
                    )
                )
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            update_phase("error")
            logger.error(
                f"API Error: {request.method} {request.url.path} - {type(e).__name__}",
                extra=_log_extra(
                    client_ip=client_ip,
                    method=request.method,
                    path=request.url.path,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    process_time=process_time,
                    latencyMs=int(process_time * 1000),
                ),
                exc_info=True
            )
            raise
