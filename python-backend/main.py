import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from database import init_db, seed_data, get_db_connection, DB_PATH
from routes import appointments, services, auth_routes, twilio_webhook, cases, staff, customers, settings, business_hours
from security import rate_limit_middleware, security_headers_middleware
from monitoring import setup_logging
from auth import get_current_admin_user
from logging_middleware import SecurityLoggingMiddleware
import traceback
import json

# Initialize Logging
setup_logging()


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


# Initialize FastAPI app
app = FastAPI(
    title="LB Automotive API",
    description="Python CORS server for LB Automotive Dashboard",
    version="1.0.0",
    lifespan=lifespan,
    # Security: Limit request body size to prevent DoS attacks
    # 10MB should be sufficient for most API requests
    max_request_size=10 * 1024 * 1024  # 10MB
)

# CORS configuration
origins_str = os.getenv("ALLOWED_ORIGINS")
if not origins_str:
    raise ValueError(
        "ALLOWED_ORIGINS environment variable is required. "
        "Set it to a comma-separated list of allowed origins (e.g., http://localhost:5173,https://example.com)"
    )
origins = [origin.strip() for origin in origins_str.split(",")]

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
    logger = logging.getLogger(__name__)
    logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        exc_info=True,
        extra={"path": request.url.path, "method": request.method}
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


# Security middlewares (order matters - logging should be first)
app.add_middleware(SecurityLoggingMiddleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

# Register routers
from routes import (
    auth_routes,
    appointments,
    services,
    settings,
    twilio_webhook,
    cases,
    staff,
    customers,
    reports,
    twilio_stream,
    ivr_routes,
    ivr_routes,
    business_hours,
    deployment_routes
)

# Include Routers
app.include_router(auth_routes.router)
app.include_router(appointments.router)
app.include_router(services.router)
app.include_router(settings.router)
app.include_router(twilio_webhook.router)
app.include_router(cases.router)
app.include_router(staff.router)
app.include_router(customers.router)
app.include_router(reports.router)
app.include_router(twilio_stream.router)
app.include_router(ivr_routes.router)
app.include_router(business_hours.router)
app.include_router(deployment_routes.router)


@app.get("/api/debug/db")
async def debug_db(current_user: dict = Depends(get_current_admin_user)):
    """
    Debug endpoint for database information.
    Requires admin authentication.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get schema for cases table
        cursor.execute("PRAGMA table_info(cases)")
        columns = [dict(row) for row in cursor.fetchall()]
        
        # Get count of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row["name"] for row in cursor.fetchall()]
        
        conn.close()
        
        # Return minimal information, no sensitive paths
        return {
            "db_exists": os.path.exists(DB_PATH),
            "tables": tables,
            "cases_schema": columns,
        }
    except Exception as e:
        # Don't expose traceback in production
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Debug endpoint error: {str(e)}", exc_info=True)
        return {"error": "Internal server error"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "LB Automotive API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """Deep health check endpoint."""
    status_data = {"status": "healthy", "components": {}}
    
    # Check database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
