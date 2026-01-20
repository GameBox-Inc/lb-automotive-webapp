import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, seed_data
from routes import appointments, services, auth_routes, twilio_webhook
from security import rate_limit_middleware, security_headers_middleware

# Initialize FastAPI app
app = FastAPI(
    title="LB Automotive API",
    description="Python CORS server for LB Automotive Dashboard",
    version="1.0.0"
)

# CORS configuration
origins_str = os.getenv("ALLOWED_ORIGINS", "*")
if origins_str == "*":
    origins = ["*"]
else:
    origins = [origin.strip() for origin in origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

# Security middlewares
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
    twilio_stream
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


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    print("Initializing database...")
    init_db()
    seed_data()
    print("Application started successfully!")


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
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
