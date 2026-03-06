"""
Request/Response logging middleware for security auditing.
"""
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log API requests and responses for security auditing.
    Logs authentication attempts, sensitive operations, and errors.
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
    
    # Methods that modify data
    MODIFY_METHODS = ["POST", "PUT", "PATCH", "DELETE"]
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract client information
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        
        # Extract user agent
        user_agent = request.headers.get("User-Agent", "unknown")
        
        # Check if this is a sensitive endpoint
        is_sensitive = any(request.url.path.startswith(endpoint) for endpoint in self.SENSITIVE_ENDPOINTS)
        is_modify = request.method in self.MODIFY_METHODS
        
        # Log request
        if is_sensitive or is_modify:
            logger.info(
                f"API Request: {request.method} {request.url.path}",
                extra={
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                    "is_sensitive": is_sensitive,
                }
            )
        
        # Process request
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Log response for sensitive operations
            if is_sensitive or is_modify:
                logger.info(
                    f"API Response: {request.method} {request.url.path} - {response.status_code}",
                    extra={
                        "client_ip": client_ip,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "process_time": process_time,
                    }
                )
            
            # Log slow requests
            if process_time > 2.0:
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} took {process_time:.2f}s",
                    extra={
                        "client_ip": client_ip,
                        "method": request.method,
                        "path": request.url.path,
                        "process_time": process_time,
                    }
                )
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            # Log errors
            logger.error(
                f"API Error: {request.method} {request.url.path} - {type(e).__name__}",
                extra={
                    "client_ip": client_ip,
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "process_time": process_time,
                },
                exc_info=True
            )
            raise
