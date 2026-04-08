"""Tests for pure-EAV secret storage (Commit 3).

Unit tests — FakeConn that records SQL calls, no live DB needed.
Exercises insert_secret / fetch_secret_by_path EAV round-trip.

Run unit tests:
    uv run pytest tests/test_vault_secrets_eav.py -v
"""

from __future__ import annotations

import importlib

import pytest

_repo = importlib.import_module("04_backend.02_features.vault.setup.repository")

# ---------------------------------------------------------------------------
# Constants matching the seed data in 20260408_001_vault_bootstrap.sql
# ---------------------------------------------------------------------------

_SECRET_ENTITY_TYPE_ID = 2   # id of 'secret' in 06_dim_entity_types
_ATTR_DEFS = {
    "path":       16,
    "ciphertext": 17,
    "nonce":      18,
}

# ---------------------------------------------------------------------------
# FakeConn — simulates dim lookups and EAV round-trip for secrets
# ---------------------------------------------------------------------------


class _FakeConn:
    """Minimal connection double that honours the secret EAV attr_defs seed."""

    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple]] = []
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.fetch_calls: list[tuple[str, tuple]] = []
        # In-memory EAV store: (entity_type_id, entity_id, attr_def_id) → value
        self._attrs: dict[tuple, str] = {}
        # In-memory fct store: entity_id → {id, is_active, deleted_at}
        self._fct_rows: dict[str, dict] = {}
        # Override: if set, fetchrow on 06_dim_entity_types returns this id
        self._secret_et_id: int = _SECRET_ENTITY_TYPE_ID

    async def execute(self, sql: str, *args) -> str:
        self.execute_calls.append((sql, args))
        if "10_fct_secrets" in sql and "INSERT" in sql:
            entity_id = args[0]
            self._fct_rows[entity_id] = {
                "id":         entity_id,
                "is_active":  True,
                "deleted_at": None,
            }
        if "20_dtl_attrs" in sql and "INSERT" in sql:
            # args: entity_type_id, entity_id, attr_def_id, key_text
            et_id, entity_id, attr_def_id, value = args[0], args[1], args[2], args[3]
            self._attrs[(et_id, entity_id, attr_def_id)] = value
        return "INSERT 0 1"

    async def fetchrow(self, sql: str, *args) -> dict | None:
        self.fetchrow_calls.append((sql, args))
        if "06_dim_entity_types" in sql:
            return {"id": self._secret_et_id}
        if "10_fct_secrets" in sql:
            entity_id = args[0]
            return self._fct_rows.get(entity_id)
        if "20_dtl_attrs" in sql and "attr_def_id" in sql and "key_text" in sql:
            # Path lookup: WHERE attr_def_id=$1 AND key_text=$2
            attr_def_id, key_text = args[0], args[1]
            for (_, entity_id, ad_id), value in self._attrs.items():
                if ad_id == attr_def_id and value == key_text:
                    return {"entity_id": entity_id}
            return None
        return None

    async def fetch(self, sql: str, *args) -> list[dict]:
        self.fetch_calls.append((sql, args))
        if "07_dim_attr_defs" in sql:
            return [{"id": v, "code": k} for k, v in _ATTR_DEFS.items()]
        if "20_dtl_attrs" in sql and len(args) >= 2:
            entity_type_id, entity_id = args[0], args[1]
            return [
                {"attr_def_id": ad_id, "key_text": value}
                for (et_id, eid, ad_id), value in self._attrs.items()
                if et_id == entity_type_id and eid == entity_id
            ]
        return []


# ---------------------------------------------------------------------------
# Helper: seed an inactive fct row into FakeConn
# ---------------------------------------------------------------------------


def _seed_inactive_fct(conn: _FakeConn, entity_id: str) -> None:
    """Override the fct row for entity_id to have is_active=False."""
    conn._fct_rows[entity_id] = {
        "id":         entity_id,
        "is_active":  False,
        "deleted_at": None,
    }


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_secret_writes_fct_and_attrs() -> None:
    """insert_secret must write 1 fct row + 3 attr rows (path, ciphertext, nonce)."""
    conn = _FakeConn()
    await _repo.insert_secret(
        conn,
        id="secret-uuid-001",
        path="tennetctl/db/write_dsn",
        ciphertext="cipher-abc",
        nonce="nonce-xyz",
        created_by="user-uuid-001",
    )

    fct_inserts = [s for s, _ in conn.execute_calls if "10_fct_secrets" in s and "INSERT" in s]
    attr_inserts = [s for s, _ in conn.execute_calls if "20_dtl_attrs" in s and "INSERT" in s]

    assert len(fct_inserts) == 1, "Expected exactly 1 fct row insert"
    assert len(attr_inserts) == 3, "Expected exactly 3 attr rows (path, ciphertext, nonce)"


@pytest.mark.asyncio
async def test_fetch_secret_by_path_returns_dict() -> None:
    """fetch_secret_by_path must return dict with id, path, ciphertext, nonce."""
    conn = _FakeConn()
    secret_id = "secret-uuid-002"
    await _repo.insert_secret(
        conn,
        id=secret_id,
        path="tennetctl/jwt/secret",
        ciphertext="ct-jwt",
        nonce="nc-jwt",
        created_by=None,
    )

    result = await _repo.fetch_secret_by_path(conn, "tennetctl/jwt/secret")

    assert result is not None
    assert result["id"] == secret_id
    assert result["path"] == "tennetctl/jwt/secret"
    assert result["ciphertext"] == "ct-jwt"
    assert result["nonce"] == "nc-jwt"


@pytest.mark.asyncio
async def test_fetch_secret_by_path_returns_none_for_missing() -> None:
    """fetch_secret_by_path must return None when no matching path exists."""
    conn = _FakeConn()
    # No secrets inserted — path lookup in 20_dtl_attrs will find nothing.
    result = await _repo.fetch_secret_by_path(conn, "tennetctl/does/not/exist")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_secret_by_path_returns_none_for_inactive() -> None:
    """fetch_secret_by_path must return None when the fct row is is_active=FALSE."""
    conn = _FakeConn()
    secret_id = "secret-uuid-003"
    await _repo.insert_secret(
        conn,
        id=secret_id,
        path="tennetctl/db/read_dsn",
        ciphertext="ct-inactive",
        nonce="nc-inactive",
        created_by=None,
    )
    # Manually mark the fct row as inactive.
    _seed_inactive_fct(conn, secret_id)

    result = await _repo.fetch_secret_by_path(conn, "tennetctl/db/read_dsn")
    assert result is None
