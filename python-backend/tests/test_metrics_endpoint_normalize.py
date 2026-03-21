"""Low-cardinality HTTP metric path normalization."""
from unittest.mock import MagicMock

from observability.monitoring import normalize_http_endpoint_label


def test_normalize_uses_route_template_when_present():
    req = MagicMock()
    route = MagicMock()
    route.path = "/api/appointments/{appointment_id}"
    req.scope = {"route": route}
    req.url.path = "/api/appointments/real-uuid-here"
    assert normalize_http_endpoint_label(req) == "/api/appointments/{appointment_id}"


def test_normalize_collapses_uuid_segment():
    req = MagicMock()
    req.scope = {"route": None}
    uid = "550e8400-e29b-41d4-a716-446655440000"
    req.url.path = f"/api/foo/{uid}/bar"
    assert normalize_http_endpoint_label(req) == "/api/foo/{id}/bar"


def test_normalize_collapses_numeric_segment():
    req = MagicMock()
    req.scope = {"route": None}
    req.url.path = "/api/appointments/42/edit"
    assert normalize_http_endpoint_label(req) == "/api/appointments/{id}/edit"


def test_normalize_root():
    req = MagicMock()
    req.scope = {"route": None}
    req.url.path = "/"
    assert normalize_http_endpoint_label(req) == "/"
