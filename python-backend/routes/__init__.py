"""Routes package initialization."""
from . import auth_routes
from . import appointments
from . import services
from . import settings
from . import cases
from . import staff
from . import customers
from . import reports
from . import twilio

__all__ = [
    "auth_routes",
    "appointments",
    "services",
    "settings",
    "cases",
    "staff",
    "customers",
    "reports",
    "twilio",
]
