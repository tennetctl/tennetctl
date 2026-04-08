"""Install-state detection.

Reads Postgres to determine which setup phases have already completed.
All functions are read-only and idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstallState:
    """Snapshot of which setup phases have been completed."""
    phase1_db_bootstrapped: bool   # migrations 0-4 all applied
    phase2_vault_initialized: bool  # 10_fct_vault row with initialized_at set
    phase3_first_admin_created: bool  # system_meta.installed_at IS NOT NULL
    phase4_settings_seeded: bool   # (global, env) row in 10_fct_settings
    unseal_salt_b64: str | None    # base64url salt, present after phase 2


async def detect_install_state(conn: object) -> InstallState:
    """Query Postgres and return the current InstallState.

    Handles a fresh database gracefully: queries that fail because the
    schema doesn't exist yet return False for that phase.
    """
    phase1 = await _check_phase1(conn)
    phase2 = await _check_phase2(conn) if phase1 else False
    phase3 = await _check_phase3(conn) if phase1 else False
    phase4 = await _check_phase4(conn) if phase1 else False
    unseal_salt = await _fetch_unseal_salt(conn) if phase1 else None

    return InstallState(
        phase1_db_bootstrapped=phase1,
        phase2_vault_initialized=phase2,
        phase3_first_admin_created=phase3,
        phase4_settings_seeded=phase4,
        unseal_salt_b64=unseal_salt,
    )


async def _check_phase1(conn: object) -> bool:
    """Phase 1 complete when the highest applied migration sequence >= 4."""
    try:
        row = await conn.fetchrow(  # type: ignore[union-attr]
            'SELECT COALESCE(MAX(sequence), -1) AS max_seq '
            'FROM "00_schema_migrations".applied_migrations'
        )
        return row["max_seq"] >= 4
    except Exception as exc:
        msg = str(exc).lower()
        if "does not exist" in msg or "relation" in msg or "schema" in msg:
            return False
        raise


async def _check_phase2(conn: object) -> bool:
    """Phase 2 complete when v_vault shows a row with initialized_at set.

    Reads the view rather than 10_fct_vault directly because initialized_at
    was moved to EAV (20_dtl_attrs) and the view pivots it back.
    """
    try:
        row = await conn.fetchrow(  # type: ignore[union-attr]
            'SELECT EXISTS ('
            '  SELECT 1 FROM "02_vault"."v_vault" WHERE initialized_at IS NOT NULL'
            ') AS done'
        )
        return bool(row["done"])
    except Exception as exc:
        msg = str(exc).lower()
        if "does not exist" in msg or "relation" in msg:
            return False
        raise


async def _check_phase3(conn: object) -> bool:
    """Phase 3 complete when system_meta.installed_at IS NOT NULL."""
    try:
        row = await conn.fetchrow(  # type: ignore[union-attr]
            'SELECT installed_at IS NOT NULL AS done '
            'FROM "00_schema_migrations".system_meta WHERE id = 1'
        )
        return bool(row["done"]) if row else False
    except Exception as exc:
        msg = str(exc).lower()
        if "does not exist" in msg or "relation" in msg:
            return False
        raise


async def _check_phase4(conn: object) -> bool:
    """Phase 4 complete when (global, env) row exists in 10_fct_settings."""
    try:
        row = await conn.fetchrow(  # type: ignore[union-attr]
            'SELECT EXISTS ('
            '  SELECT 1 FROM "00_schema_migrations"."10_fct_settings" '
            "  WHERE scope = 'global' AND key = 'env'"
            ') AS done'
        )
        return bool(row["done"])
    except Exception as exc:
        msg = str(exc).lower()
        if "does not exist" in msg or "relation" in msg:
            return False
        raise


async def _fetch_unseal_salt(conn: object) -> str | None:
    """Return the base64url-encoded unseal salt, or None if not yet set."""
    try:
        row = await conn.fetchrow(  # type: ignore[union-attr]
            'SELECT unseal_salt FROM "00_schema_migrations".system_meta WHERE id = 1'
        )
        return row["unseal_salt"] if row else None
    except Exception as exc:
        msg = str(exc).lower()
        if "does not exist" in msg or "relation" in msg or "column" in msg:
            return None
        raise
