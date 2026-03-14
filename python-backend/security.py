"""
Security middleware and utilities for the application.
Implements protections against XSS, SQL injection, CSRF, and other attacks.
"""
import re
import html
import os
import json
import uuid as uuid_module
from typing import Any, Dict
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import time
from collections import defaultdict
from datetime import datetime, timedelta

import redis
from redis.exceptions import ConnectionError as RedisConnectionError

# Rate limiting storage (distributed via Redis if available)
REDIS_URL = os.getenv("REDIS_URL")
redis_client = None

if REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        print(f"Connected to Redis for rate limiting at {REDIS_URL}")
    except Exception as e:
        print(f"Failed to connect to Redis: {e}. Falling back to in-memory.")

rate_limit_storage = defaultdict(list)

# Allowed characters for different input types
ALPHANUMERIC_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.]+$')
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')
UUID_PATTERN = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')


# Load security patterns from external config
# This prevents specific detection logic from being exposed in source control
def load_security_config():
    config_path = os.path.join(os.path.dirname(__file__), 'security_config.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        # LOW-6: Fail fast if pattern lists are empty — empty lists give zero protection
        if not config.get("sql_injection_patterns") or not config.get("xss_patterns"):
            raise ValueError(
                "security_config.json is missing 'sql_injection_patterns' or 'xss_patterns'. "
                "The application cannot start without these security patterns."
            )
        return config
    except FileNotFoundError:
        raise FileNotFoundError(
            "security_config.json not found. This file must exist and contain "
            "'sql_injection_patterns' and 'xss_patterns' before the app can start. "
            "See python-backend/.env.example for setup instructions."
        )

_config = load_security_config()

# SQL injection keywords
SQL_INJECTION_PATTERNS = _config.get("sql_injection_patterns", [])

# XSS patterns
XSS_PATTERNS = _config.get("xss_patterns", [])


def sanitize_input(value: str, input_type: str = "text", max_length: int = None) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        value: Input string to sanitize
        input_type: Type of input (text, email, phone, uuid, alphanumeric)
        max_length: Maximum allowed length (None for no limit)
    
    Returns:
        Sanitized string
        
    Raises:
        HTTPException: If input is invalid or contains malicious patterns
    """
    if not isinstance(value, str):
        return value
    
    # Check length
    if max_length and len(value) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input exceeds maximum length of {max_length} characters"
        )
    
    # Check for SQL injection attempts
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input detected: SQL injection attempt"
            )
    
    # Check for XSS attempts
    for pattern in XSS_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input detected: XSS attempt"
            )
    
    # Type-specific validation
    if input_type == "email":
        if not EMAIL_PATTERN.match(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
    elif input_type == "phone":
        # Remove common phone formatting characters
        cleaned = re.sub(r'[\s\-\(\)]', '', value)
        if not PHONE_PATTERN.match(cleaned):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone number format"
            )
        return cleaned
    elif input_type == "uuid":
        try:
            # Accept any valid UUID format (with/without hyphens, braces, uppercase)
            normalized = str(uuid_module.UUID(value.strip()))
            return html.escape(normalized) if normalized else value
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid UUID format"
            )
    elif input_type == "alphanumeric":
        if not ALPHANUMERIC_PATTERN.match(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Input contains invalid characters"
            )
    
    # HTML escape for safe output
    return html.escape(value.strip())


def validate_appointment_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize appointment data."""
    if "customer_name" in data:
        # Use "text" so names with apostrophes (O'Brien), accents, etc. are allowed; SQL/XSS checks still apply
        data["customer_name"] = sanitize_input(data["customer_name"], "text")
    
    if "phone_number" in data:
        data["phone_number"] = sanitize_input(data["phone_number"], "phone")
    
    if "service_type" in data:
        data["service_type"] = sanitize_input(data["service_type"], "text")
    
    if "notes" in data and data["notes"]:
        data["notes"] = sanitize_input(data["notes"], "text")
        # Limit notes length
        if len(data["notes"]) > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Notes too long (max 1000 characters)"
            )

    if "service_id" in data and data["service_id"]:
        try:
            data["service_id"] = sanitize_input(str(data["service_id"]).strip(), "uuid")
        except HTTPException as e:
            if e.detail == "Invalid UUID format":
                data.pop("service_id", None)  # allow create to proceed with service_type only
            else:
                raise
    if "source" in data and data["source"]:
        data["source"] = sanitize_input(str(data["source"]).strip(), "text")[:50]

    return data


async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware to prevent abuse.
    Limits requests per IP address using Redis if available.
    """
    # Trust X-Forwarded-For if available (behind Traefik/Ngrok)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host
        
    current_time = time.time()
    
    # Configure rate limits
    SHORT_WINDOW = 60  # 1 minute
    # MED-2: Reverted from debug value of 5000. 120 req/min per IP for general endpoints.
    # Auth endpoints have stricter per-route limiting via CAPTCHA + Redis.
    SHORT_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    
    if redis_client:
        try:
            # Redis-based distributed rate limiting
            key = f"rate_limit:{client_ip}"
            pipeline = redis_client.pipeline()
            # Remove old entries
            pipeline.zremrangebyscore(key, 0, current_time - SHORT_WINDOW)
            # Add current request
            pipeline.zadd(key, {str(current_time): current_time})
            # Count entries
            pipeline.zcard(key)
            # Set expiry on the whole set
            pipeline.expire(key, SHORT_WINDOW + 10)
            
            results = pipeline.execute()
            request_count = results[2]
            
            if request_count > SHORT_LIMIT:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Please try again later."}
                )
            
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(SHORT_LIMIT)
            response.headers["X-RateLimit-Remaining"] = str(max(0, SHORT_LIMIT - request_count))
            response.headers["X-RateLimit-Reset"] = str(int(current_time + SHORT_WINDOW))
            return response
            
        except (RedisConnectionError, Exception) as e:
            print(f"Redis rate limit error: {e}. Falling back to in-memory.")
            # Fallback to logic below
            
    # In-memory Fallback
    # Clean old entries
    rate_limit_storage[client_ip] = [
        timestamp for timestamp in rate_limit_storage[client_ip]
        if current_time - timestamp < SHORT_WINDOW
    ]
    
    if len(rate_limit_storage[client_ip]) >= SHORT_LIMIT:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many requests. Please try again later."}
        )
    
    rate_limit_storage[client_ip].append(current_time)
    response = await call_next(request)
    return response


async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # XSS Protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Strict Transport Security (HSTS)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Content Security Policy
    # Note: 'unsafe-inline' and 'unsafe-eval' are required for Vite/React development
    # In production, consider using nonces or hashes for inline scripts
    csp_policy = os.getenv("CSP_POLICY", "strict")  # 'strict' or 'development'
    
    if csp_policy == "strict":
        # Strict CSP for production (requires nonces for inline scripts)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
    else:
        # Development CSP (allows inline scripts for Vite HMR)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';"
        )
    
    # Referrer Policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions Policy
    response.headers["Permissions-Policy"] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )
    
    return response


def validate_sql_params(params: tuple) -> tuple:
    """
    Validate SQL parameters before execution.
    This is a defense-in-depth measure alongside parameterized queries.
    """
    validated = []
    for param in params:
        if isinstance(param, str):
            # Check for SQL injection patterns
            for pattern in SQL_INJECTION_PATTERNS:
                if re.search(pattern, param, re.IGNORECASE):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid parameter detected"
                    )
        validated.append(param)
    return tuple(validated)


# CSRF Token management (for session-based auth if needed)
csrf_tokens = {}

def generate_csrf_token(session_id: str) -> str:
    """Generate CSRF token for a session."""
    import secrets
    token = secrets.token_urlsafe(32)
    csrf_tokens[session_id] = {
        "token": token,
        "created_at": datetime.now()
    }
    return token


def validate_csrf_token(session_id: str, token: str) -> bool:
    """Validate CSRF token."""
    if session_id not in csrf_tokens:
        return False
    
    stored = csrf_tokens[session_id]
    
    # Check if token is expired (1 hour)
    if datetime.now() - stored["created_at"] > timedelta(hours=1):
        del csrf_tokens[session_id]
        return False
    
    return stored["token"] == token
