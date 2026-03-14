"""
Tests for RLS session variable logic (_set_rls_session_vars).

Verifies that get_db_connection() sets the correct Postgres session variables
(app.service_request, app.current_user_id, app.is_admin, app.staff_id) based on
current_user_context and service_request_context. Does not require a real
Postgres with RLS; uses a mock connection to assert the SET commands issued.
"""
import pytest
from unittest.mock import MagicMock

from database import (
    _set_rls_session_vars,
    current_user_context,
    service_request_context,
)


@pytest.fixture
def mock_conn():
    """Connection mock that records cursor.execute() calls."""
    conn = MagicMock()
    cursor = MagicMock()
    executed = []

    def record_execute(sql, params=None):
        executed.append((sql, params))

    cursor.execute.side_effect = record_execute
    conn.cursor.return_value = cursor
    conn.executed = executed
    return conn


def test_set_rls_vars_when_service_request(mock_conn):
    """When service_request_context is True, SET app.service_request = 'true' and clear user vars."""
    token = service_request_context.set(True)
    try:
        _set_rls_session_vars(mock_conn)
    finally:
        service_request_context.reset(token)

    executed = mock_conn.executed
    assert any("app.service_request = 'true'" in (e[0] or "") for e in executed)
    assert any("app.is_admin = 'false'" in (e[0] or "") for e in executed)
    assert any("app.current_user_id = ''" in (e[0] or "") for e in executed)
    assert any("app.staff_id = ''" in (e[0] or "") for e in executed)


def test_set_rls_vars_when_user_authenticated(mock_conn):
    """When current_user_context has a user, SET app.current_user_id, app.is_admin, app.staff_id."""
    user = {
        "id": "user-123",
        "is_admin": True,
        "staff_id": "staff-456",
    }
    token = current_user_context.set(user)
    try:
        _set_rls_session_vars(mock_conn)
    finally:
        current_user_context.reset(token)

    executed = mock_conn.executed
    assert any("app.service_request = 'false'" in (e[0] or "") for e in executed)
    assert any("app.current_user_id" in (e[0] or "") and e[1] == ("user-123",) for e in executed)
    assert any("app.is_admin" in (e[0] or "") and e[1] == ("true",) for e in executed)
    assert any("app.staff_id" in (e[0] or "") and e[1] == ("staff-456",) for e in executed)


def test_set_rls_vars_when_user_non_admin_no_staff(mock_conn):
    """When user is not admin and has no staff_id, app.is_admin and app.staff_id are false/empty."""
    user = {"id": "cust-1", "is_admin": False, "staff_id": None}
    token = current_user_context.set(user)
    try:
        _set_rls_session_vars(mock_conn)
    finally:
        current_user_context.reset(token)

    executed = mock_conn.executed
    assert any("app.is_admin" in (e[0] or "") and e[1] == ("false",) for e in executed)
    assert any("app.staff_id" in (e[0] or "") and e[1] == ("",) for e in executed)
    assert any("app.current_user_id" in (e[0] or "") and e[1] == ("cust-1",) for e in executed)


def test_set_rls_vars_when_no_user_no_service(mock_conn):
    """When neither service nor user context, SET app.service_request = 'false' and empty user vars."""
    _set_rls_session_vars(mock_conn)

    executed = mock_conn.executed
    assert any("app.service_request = 'false'" in (e[0] or "") for e in executed)
    assert any("app.is_admin = 'false'" in (e[0] or "") for e in executed)
    assert any("app.current_user_id = ''" in (e[0] or "") for e in executed)
    assert any("app.staff_id = ''" in (e[0] or "") for e in executed)


def test_set_rls_vars_service_takes_precedence(mock_conn):
    """When both service_request and user are set, service_request wins (no user vars)."""
    tok_s = service_request_context.set(True)
    tok_u = current_user_context.set({"id": "user-1", "is_admin": True})
    try:
        _set_rls_session_vars(mock_conn)
    finally:
        service_request_context.reset(tok_s)
        current_user_context.reset(tok_u)

    executed = mock_conn.executed
    assert any("app.service_request = 'true'" in (e[0] or "") for e in executed)
    assert any("app.current_user_id = ''" in (e[0] or "") for e in executed)
