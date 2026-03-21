import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from database import init_db, seed_data, DatabaseContextManager
from security import rate_limit_middleware, security_headers_middleware
from observability import setup_logging
from auth import get_current_admin_user
from observability import SecurityLoggingMiddleware
from observability.request_tracing_middleware import RequestTracingMiddleware
import traceback
import json

# Initialize Logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    print("Initializing database...")
    init_db()
    seed_data()
    print("Application started successfully!")
    yield
    # Shutdown (if needed)



# MED-7: Hide API documentation in non-development environments.
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
DOCS_URL = "/docs" if ENVIRONMENT == "development" else None
REDOC_URL = "/redoc" if ENVIRONMENT == "development" else None

# Initialize FastAPI app
app = FastAPI(
    title="LB Automotive API",
    description="Python CORS server for LB Automotive Dashboard",
    version="1.0.0",
    lifespan=lifespan,
    # MED-7: docs_url/redoc_url are None in production (set by ENVIRONMENT above)
    docs_url=DOCS_URL,
    redoc_url=REDOC_URL,
    # Security: Limit request body size to prevent DoS attacks
    # 10MB should be sufficient for most API requests
    max_request_size=10 * 1024 * 1024  # 10MB
)

if DOCS_URL is None:
    logger.info("Swagger UI disabled (ENVIRONMENT != development). Set ENVIRONMENT=development to enable.")

# CORS configuration
origins_str = os.getenv("ALLOWED_ORIGINS")
if not origins_str:
    raise ValueError(
        "ALLOWED_ORIGINS environment variable is required. "
        "Set it to a comma-separated list of allowed origins (e.g., http://localhost:5173,https://example.com)"
    )
origins = [origin.strip() for origin in origins_str.split(",")]

# MED-8: Warn if ngrok origins are present in non-dev environments
if ENVIRONMENT != "development":
    for origin in origins:
        if "ngrok" in origin:
            logger.warning(
                f"SECURITY WARNING: ngrok origin '{origin}' found in ALLOWED_ORIGINS "
                "in a non-development environment. Remove it from ALLOWED_ORIGINS."
            )

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

# Global exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to prevent information leakage."""
    from observability.tracing import get_trace_context
    logger = logging.getLogger(__name__)
    extra = get_trace_context()
    extra.update({"path": request.url.path, "method": request.method})
    logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        exc_info=True,
        extra=extra
    )
    
    # Return generic error message to client
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with user-friendly messages."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []))
        message = error.get("msg", "Invalid input")
        errors.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": errors}
    )


# Observability: Prometheus request tracking (before security so all requests are counted)
from observability.monitoring import track_request, metrics_endpoint
app.add_middleware(SecurityLoggingMiddleware)
app.add_middleware(RequestTracingMiddleware)
app.middleware("http")(track_request)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

# Register routers
from routes import (
    auth_routes,
    appointments,
    services,
    settings,
    cases,
    staff,
    customers,
    reports,
    business_hours,
    deployment_routes,
    reminders,
)
from routes.twilio import webhook_router, stream_router, analytics_router, sms_router, tts_audio_router

# Include Routers
app.include_router(auth_routes.router)
app.include_router(appointments.router)
app.include_router(services.router)
app.include_router(settings.router)
app.include_router(tts_audio_router)
app.include_router(webhook_router)
app.include_router(sms_router)
app.include_router(cases.router)
app.include_router(staff.router)
app.include_router(customers.router)
app.include_router(reports.router)
app.include_router(stream_router)
app.include_router(analytics_router)
app.include_router(business_hours.router)
app.include_router(deployment_routes.router)
app.include_router(reminders.router)

# Static audio for IVR (thinking sound, etc.) — served at /audio/*
_audio_dir = Path(__file__).resolve().parent / "static" / "audio"
if _audio_dir.exists():
    app.mount("/audio", StaticFiles(directory=str(_audio_dir)), name="audio")


@app.get("/api/debug/db")
async def debug_db(current_user: dict = Depends(get_current_admin_user)):
    """
    Debug endpoint for database information (PostgreSQL).
    Requires admin authentication. Returns minimal schema info only.
    """
    try:
        with DatabaseContextManager(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            tables = [row["table_name"] for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'cases'
                ORDER BY ordinal_position
                """
            )
            columns = [dict(row) for row in cursor.fetchall()]
        return {"tables": tables, "cases_schema": columns}
    except Exception as e:
        logger.error(f"Debug endpoint error: {str(e)}", exc_info=True)
        return {"error": "Internal server error"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "LB Automotive API",
        "version": "1.0.0",
        "build_tag": os.getenv("BUILD_TAG", "local-dev"),
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready"
    }


@app.get("/ready")
async def ready_check():
    """Lightweight readiness: 200 when the process is up. Use for K8s readinessProbe so rollout can complete even if DB is temporarily unreachable."""
    return {"status": "ready"}


@app.get("/health")
async def health_check():
    """Deep health check endpoint."""
    status_data = {"status": "healthy", "components": {}}
    
    # Check database
    try:
        with DatabaseContextManager(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
        status_data["components"]["database"] = "healthy"
    except Exception as e:
        status_data["status"] = "degraded"
        status_data["components"]["database"] = "unhealthy"
        # Log error but don't expose details to client
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Database health check failed: {str(e)}", exc_info=True)
    
    # Check Redis if configured
    try:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            import redis
            redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1)
            redis_client.ping()
            status_data["components"]["redis"] = "healthy"
        else:
            status_data["components"]["redis"] = "not_configured"
    except Exception as e:
        status_data["status"] = "degraded"
        status_data["components"]["redis"] = "unhealthy"
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Redis health check failed: {str(e)}")
    
    if status_data["status"] != "healthy":
        from fastapi import Response
        return Response(content=json.dumps(status_data), status_code=503, media_type="application/json")
        
    return status_data


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint for scraping."""
    return await metrics_endpoint()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
