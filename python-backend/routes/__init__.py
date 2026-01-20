"""Routes package initialization."""
from  . import auth_routes
from . import appointments
from . import services
from . import settings
from . import twilio_webhook
from . import cases
from . import staff
from . import customers
from . import reports
from . import twilio_stream

__all__ = [
    "auth_routes",
    "appointments",
    "services",
    "settings",
    "twilio_webhook",
    "cases",
    "staff",
    "customers",
    "reports",
    "twilio_stream"
]
