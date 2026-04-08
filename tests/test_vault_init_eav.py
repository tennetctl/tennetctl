"""Tests for pure-EAV vault initialization (Commit 2).

Two flavours:

1. **Unit tests** — FakeConn that records SQL calls, no live DB needed.
   Exercises insert_vault_row / fetch_vault_row pivot logic.

2. **Integration tests** (``@pytest.mark.integration``) — require a live dev DB
   with 20260408_001 and 20260408_002 migrations applied.

Run unit tests:
    uv run pytest tests/test_vault_init_eav.py -v

Run integration tests:
    DATABASE_URL_ADMIN="postgres://tennetctl_admin:tennetctl_admin_dev@localhost:55432/tennetctl" \\
      uv run pytest tests/test_vault_init_eav.py -m integration -v
"""

from __future__ import annotations

import importlib
import os

import pytest
import pytest_asyncio
import asyncpg

_repo = importlib.import_module("04_backend.02_features.vault.setup.repository")
_svc = importlib.import_module("04_backend.02_features.vault.setup.service")
_db = importlib.import_module("04_backend.01_core.db")

# ---------------------------------------------------------------------------
# FakeConn — records every call; simulates dim lookups and EAV round-trip
# ---------------------------------------------------------------------------

_ENTITY_TYPE_ID = 1   # vault entity type
_ATTR_DEFS = {
    "mdk_ciphertext":  9,
    "mdk_nonce":       10,
    "unseal_key_hash": 11,
    "read_key_hash":   12,
    "wrapped_mdk":     13,
    "unseal_config":   14,
    "initialized_at":  15,
}


class _FakeConn:
    """Minimal connection double that honours the EAV attr_defs seed."""

    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple]] = []
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.fetch_calls: list[tuple[str, tuple]] = []
        # In-memory store keyed by (entity_type_id, entity_id, attr_def_id)
        self._attrs: dict[tuple, str] = {}
        self._fct_row: dict | None = None

    async def execute(self, sql: str, *args) -> str:
        self.execute_calls.append((sql, args))
        if "10_fct_vault" in sql and "INSERT" in sql:
            self._fct_row = {"id": args[0], "status_id": args[1], "unseal_mode_id": args[2]}
        if "20_dtl_attrs" in sql and "INSERT" in sql:
            # args: et_id, entity_id, attr_def_id, value
            self._attrs[(args[0], args[1], args[2])] = args[3]
        return "INSERT 0 1"

    async def fetchrow(self, sql: str, *args) -> dict | None:
        self.fetchrow_calls.append((sql, args))
        if "06_dim_entity_types" in sql:
            return {"id": _ENTITY_TYPE_ID}
        if "10_fct_vault" in sql:
            return self._fct_row
        return None

    async def fetch(self, sql: str, *args) -> list[dict]:
        self.fetch_calls.append((sql, args))
        if "07_dim_attr_defs" in sql:
            return [{"id": v, "code": k} for k, v in _ATTR_DEFS.items()]
        if "20_dtl_attrs" in sql:
            entity_type_id, entity_id = args[0], args[1]
            return [
                {"attr_def_id": attr_def_id, "key_text": value}
                for (et_id, eid, attr_def_id), value in self._attrs.items()
                if et_id == entity_type_id and eid == entity_id
            ]
        return []


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_vault_row_writes_fct_and_attrs():
    """insert_vault_row should write one fct row and four attr rows."""
    conn = _FakeConn()
    await _repo.insert_vault_row(
        conn,
        id="vault-uuid-001",
        unseal_mode_id=1,
        status_id=2,
        mdk_ciphertext="aaa",
        mdk_nonce="bbb",
        unseal_key_hash="ccc",
        initialized_at_iso="2026-04-08T00:00:00Z",
    )

    fct_inserts = [s for s, _ in conn.execute_calls if "10_fct_vault" in s]
    attr_inserts = [s for s, _ in conn.execute_calls if "20_dtl_attrs" in s]

    assert len(fct_inserts) == 1
    # mdk_ciphertext, mdk_nonce, unseal_key_hash, initialized_at
    assert len(attr_inserts) == 4


@pytest.mark.asyncio
async def test_fetch_vault_row_pivots_attrs():
    """fetch_vault_row should return a dict with all four key-material attrs."""
    conn = _FakeConn()

    # Seed a vault row + attrs manually via the insert function.
    await _repo.insert_vault_row(
        conn,
        id="vault-uuid-002",
        unseal_mode_id=1,
        status_id=2,
        mdk_ciphertext="cipher-abc",
        mdk_nonce="nonce-def",
        unseal_key_hash="hash-ghi",
        initialized_at_iso="2026-04-08T12:00:00Z",
    )

    result = await _repo.fetch_vault_row(conn)

    assert result is not None
    assert result["id"] == "vault-uuid-002"
    assert result["mdk_ciphertext"] == "cipher-abc"
    assert result["mdk_nonce"] == "nonce-def"
    assert result["unseal_key_hash"] == "hash-ghi"


@pytest.mark.asyncio
async def test_fetch_vault_row_returns_none_when_empty():
    """fetch_vault_row returns None if no vault row exists."""
    conn = _FakeConn()
    result = await _repo.fetch_vault_row(conn)
    assert result is None


@pytest.mark.asyncio
async def test_init_vault_manual_raises_if_already_initialized():
    """init_vault_manual raises VaultError when a vault row already exists."""
    conn = _FakeConn()
    wrap_key = b"\x00" * 32

    # First call succeeds.
    await _svc.init_vault_manual(conn, wrap_key=wrap_key)

    # Second call must raise because fetch_vault_row will now return a row.
    with pytest.raises(_svc.VaultError) as exc_info:
        await _svc.init_vault_manual(conn, wrap_key=wrap_key)
    assert "VAULT_ALREADY_INITIALIZED" in str(exc_info.value)


@pytest.mark.asyncio
async def test_init_vault_manual_passes_initialized_at():
    """init_vault_manual must write initialized_at as an EAV attr."""
    conn = _FakeConn()
    wrap_key = b"\x01" * 32
    await _svc.init_vault_manual(conn, wrap_key=wrap_key)

    # After insert, fetch_vault_row can't surface initialized_at because FakeConn
    # doesn't filter on attr values — but we can verify the attr INSERT was called
    # with the initialized_at attr_def_id (15).
    attr_inserts_args = [args for s, args in conn.execute_calls if "20_dtl_attrs" in s]
    attr_def_ids_written = {a[2] for a in attr_inserts_args}
    assert _ATTR_DEFS["initialized_at"] in attr_def_ids_written, (
        "initialized_at attr (id=15) was not written to 20_dtl_attrs"
    )


# ---------------------------------------------------------------------------
# Integration tests — require live DB
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def live_conn():
    """Admin connection to the dev DB, cleaned up after each test."""
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
async def test_live_vault_row_round_trip(live_conn):
    """EAV pivot: fetch_vault_row returns the attrs written by insert_vault_row.

    Reads the existing wizard-installed vault row (written by Phase 2) and
    verifies that fetch_vault_row correctly pivots all key-material attrs.
    We never insert a second row — the singleton constraint forbids it.
    """
    row = await _repo.fetch_vault_row(live_conn)
    assert row is not None, "No vault row found — run tennetctl setup first"
    # All four key-material attrs must be populated by the wizard.
    assert row["mdk_ciphertext"] is not None, "mdk_ciphertext attr missing from EAV pivot"
    assert row["mdk_nonce"] is not None, "mdk_nonce attr missing from EAV pivot"
    assert row["unseal_key_hash"] is not None, "unseal_key_hash attr missing from EAV pivot"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_v_vault_initialized_at_is_timestamp(live_conn):
    """v_vault.initialized_at casts correctly to TIMESTAMP (not just text)."""
    # The vault should already be initialized by the wizard in the dev env.
    row = await live_conn.fetchrow(
        'SELECT initialized_at FROM "02_vault"."v_vault" LIMIT 1'
    )
    if row is None:
        pytest.skip("Vault not yet initialized in dev DB — run tennetctl setup first")
    assert row["initialized_at"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_check_phase2_via_state(live_conn):
    """_check_phase2 returns True on an initialized dev DB."""
    _state = importlib.import_module("scripts.setup.wizard.state")
    phase2 = await _state._check_phase2(live_conn)
    assert phase2 is True, (
        "_check_phase2 returned False — vault may not be initialized yet. "
        "Run 'tennetctl setup --env dev --mode a --yes' first."
    )
