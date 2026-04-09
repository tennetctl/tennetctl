"""Tests for the pure-EAV audit service.

Two flavours of tests here:

1. **Unit tests** (no ``@pytest.mark.integration``): use a FakeConn that records
   every query + args, so the validation rules in ``emit()`` can be exercised
   without a live DB. These run in <1s in ``uv run pytest tests/test_audit_emit_eav.py``.

2. **Integration tests** (``@pytest.mark.integration``): require a live dev DB
   with all migrations applied. They verify the CHECK constraint, the round-trip
   through ``v_events``, and the EAV pivot. Run with
   ``uv run pytest tests/test_audit_emit_eav.py -m integration``.

The integration tests assume:
  - A fresh ``tennetctl setup`` has been run.
  - ``$DATABASE_URL`` points at the write DSN (or admin works too).
  - The admin user exists (created by the wizard).
"""

from __future__ import annotations

import importlib
import os

import asyncpg
import pytest
import pytest_asyncio

_audit = importlib.import_module("04_backend.02_features.audit.service")
_db = importlib.import_module("04_backend.01_core.db")


# ---------------------------------------------------------------------------
# Unit tests — validation rules only, no DB
# ---------------------------------------------------------------------------


class _FakeConn:
    """Minimal connection double that records execute calls."""

    def __init__(self) -> None:
        self.fetch_calls: list[tuple[str, tuple]] = []
        self.execute_calls: list[tuple[str, tuple]] = []
        self.fetchrow_calls: list[tuple[str, tuple]] = []

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        # Return canned dim rows so _load_dim_caches populates.
        if "01_dim_event_categories" in sql:
            return [
                {"id": 1, "code": "iam"},
                {"id": 2, "code": "vault"},
                {"id": 3, "code": "setup"},
            ]
        if "02_dim_event_outcomes" in sql:
            return [
                {"id": 1, "code": "success"},
                {"id": 2, "code": "failure"},
            ]
        if "03_dim_event_actions" in sql:
            return [
                {"id": 1, "code": "session.login"},
                {"id": 2, "code": "session.login_failed"},
                {"id": 99, "code": "unknown"},
            ]
        if "05_dim_attr_defs" in sql:
            return [
                {"id": 10, "code": "target_id"},
                {"id": 11, "code": "target_type"},
                {"id": 12, "code": "ip_address"},
                {"id": 13, "code": "user_agent"},
                {"id": 14, "code": "metadata"},
            ]
        return []

    async def fetchrow(self, sql, *args):
        self.fetchrow_calls.append((sql, args))
        if "04_dim_entity_types" in sql:
            return {"id": 1}
        return None

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))
        return "INSERT 0 1"


@pytest.fixture(autouse=True)
def _reset_audit_caches():
    """Clear module-level dim caches before every test so tests are isolated."""
    _audit._reset_caches_for_tests()
    yield
    _audit._reset_caches_for_tests()


@pytest.mark.asyncio
async def test_emit_raises_without_user_id_for_non_setup():
    """Non-setup events without user_id must raise ValueError immediately."""
    conn = _FakeConn()
    with pytest.raises(ValueError, match="user_id is required"):
        await _audit.emit(
            conn,
            category="iam",
            action="session.login",
            outcome="success",
            user_id=None,
            session_id="sess-123",
        )
    # Nothing should have been written to the DB.
    assert conn.execute_calls == []


@pytest.mark.asyncio
async def test_emit_raises_without_session_id_for_success():
    """Successful non-setup events without session_id must raise ValueError."""
    conn = _FakeConn()
    with pytest.raises(ValueError, match="session_id is required"):
        await _audit.emit(
            conn,
            category="iam",
            action="session.refresh",
            outcome="success",
            user_id="user-123",
            session_id=None,
        )
    assert conn.execute_calls == []


@pytest.mark.asyncio
async def test_emit_allows_null_session_for_failure_outcome():
    """Failed logins may have session_id=None."""
    conn = _FakeConn()
    await _audit.emit(
        conn,
        category="iam",
        action="session.login_failed",
        outcome="failure",
        user_id="user-123",
        session_id=None,
    )
    # One INSERT into 60_evt_events; no attr inserts because no context fields.
    insert_sqls = [c[0] for c in conn.execute_calls]
    assert any("60_evt_events" in s for s in insert_sqls)
    assert not any("20_dtl_attrs" in s for s in insert_sqls)


@pytest.mark.asyncio
async def test_emit_allows_null_user_and_session_for_setup():
    """Setup wizard events may have NULL user_id and session_id."""
    conn = _FakeConn()
    await _audit.emit(
        conn,
        category="setup",
        action="session.login",  # action code doesn't matter for setup
        outcome="success",
        user_id=None,
        session_id=None,
    )
    insert_sqls = [c[0] for c in conn.execute_calls]
    assert any("60_evt_events" in s for s in insert_sqls)


@pytest.mark.asyncio
async def test_emit_missing_required_kwarg_is_type_error():
    """Calling emit without user_id/session_id at all raises TypeError."""
    conn = _FakeConn()
    with pytest.raises(TypeError):
        await _audit.emit(  # type: ignore[call-arg]
            conn,
            category="iam",
            action="session.login",
            outcome="success",
            # user_id and session_id intentionally omitted
        )


@pytest.mark.asyncio
async def test_emit_happy_path_writes_scope_and_attrs():
    """A fully populated emit writes one evt row + N attr rows."""
    conn = _FakeConn()
    await _audit.emit(
        conn,
        category="iam",
        action="session.login",
        outcome="success",
        user_id="user-abc",
        session_id="sess-xyz",
        org_id="org-123",
        workspace_id="ws-456",
        target_id="sess-xyz",
        target_type="iam_session",
        ip_address="10.0.0.1",
        user_agent="test-agent/1.0",
        metadata={"key": "value"},
    )

    insert_sqls = [(s, args) for s, args in conn.execute_calls]
    evt_inserts = [x for x in insert_sqls if "60_evt_events" in x[0]]
    attr_inserts = [x for x in insert_sqls if "20_dtl_attrs" in x[0]]

    assert len(evt_inserts) == 1
    # target_id, target_type, ip_address, user_agent, metadata → 5 attrs
    assert len(attr_inserts) == 5

    # Inspect the evt INSERT bound values: (id, org, ws, user, sess, cat, act, out, actor)
    evt_args = evt_inserts[0][1]
    assert evt_args[1] == "org-123"       # org_id
    assert evt_args[2] == "ws-456"        # workspace_id
    assert evt_args[3] == "user-abc"      # user_id
    assert evt_args[4] == "sess-xyz"      # session_id
    # created_by defaults to user_id when actor_id is not provided
    assert evt_args[8] == "user-abc"


@pytest.mark.asyncio
async def test_emit_actor_id_overrides_user_id_for_created_by():
    """Explicit actor_id takes precedence over user_id for the created_by column."""
    conn = _FakeConn()
    await _audit.emit(
        conn,
        category="iam",
        action="session.login",
        outcome="success",
        user_id="user-abc",
        session_id="sess-xyz",
        actor_id="impersonator-def",
    )
    evt_inserts = [a for s, a in conn.execute_calls if "60_evt_events" in s]
    assert len(evt_inserts) == 1
    assert evt_inserts[0][8] == "impersonator-def"  # created_by


@pytest.mark.asyncio
async def test_emit_db_failure_does_not_propagate():
    """DB errors during the INSERT are swallowed; caller's tx survives."""

    class _BoomConn(_FakeConn):
        async def execute(self, sql, *args):
            raise RuntimeError("DB unavailable")

    conn = _BoomConn()
    # Must not raise.
    await _audit.emit(
        conn,
        category="iam",
        action="session.login",
        outcome="success",
        user_id="user-abc",
        session_id="sess-xyz",
    )


# ---------------------------------------------------------------------------
# Integration tests — require a live DB with migrations applied
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def live_conn():
    """Acquire an admin connection to the dev DB with JSONB codec registered."""
    dsn = os.environ.get("DATABASE_URL_ADMIN") or os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("$DATABASE_URL_ADMIN or $DATABASE_URL not set")
    conn = await asyncpg.connect(dsn)
    await _db.register_jsonb_codec(conn)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_emit_setup_event(live_conn):
    """Setup events with NULL user_id/session_id are accepted by the CHECK."""
    _audit._reset_caches_for_tests()
    async with live_conn.transaction():
        await _audit.emit(
            live_conn,
            category="setup",
            action="setup.phase_complete",
            outcome="success",
            user_id=None,
            session_id=None,
            metadata={"phase": "test"},
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_emit_iam_event_requires_scope(live_conn):
    """Non-setup events bypass attempts are blocked by the CHECK constraint."""
    _audit._reset_caches_for_tests()
    # Python-level validation catches this before the DB does.
    with pytest.raises(ValueError):
        await _audit.emit(
            live_conn,
            category="iam",
            action="session.login",
            outcome="success",
            user_id=None,  # illegal for non-setup
            session_id="any-session",
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_v_events_pivots_attrs(live_conn):
    """Write an event with all context fields; read it back via v_events."""
    _audit._reset_caches_for_tests()
    test_marker = "audit-eav-test-marker-9f8e7d6c"
    async with live_conn.transaction():
        await _audit.emit(
            live_conn,
            category="setup",
            action="setup.phase_complete",
            outcome="success",
            user_id=None,
            session_id=None,
            target_id="fake-target",
            target_type="iam_user",
            ip_address="127.0.0.1",
            user_agent=test_marker,
            metadata={"round_trip": True},
        )
    row = await live_conn.fetchrow(
        """
        SELECT category, action, outcome, target_id, target_type,
               ip_address, user_agent, metadata
          FROM "04_audit".v_events
         WHERE user_agent = $1
         ORDER BY created_at DESC
         LIMIT 1
        """,
        test_marker,
    )
    assert row is not None, f"event with marker {test_marker} not found in v_events"
    assert row["category"] == "setup"
    assert row["action"] == "setup.phase_complete"
    assert row["outcome"] == "success"
    assert row["target_id"] == "fake-target"
    assert row["target_type"] == "iam_user"
    assert row["ip_address"] == "127.0.0.1"
    assert row["user_agent"] == test_marker
    # asyncpg returns JSONB as a python dict
    assert row["metadata"] == {"round_trip": True}
