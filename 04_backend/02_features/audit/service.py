"""Audit event service — append-only structured event log.

Every mutation (login, logout, refresh, user update, org/workspace change)
emits a row here. The INSERT is fire-and-forget within the same DB transaction
as the mutation. Audit failures never surface to the caller — they are logged
to stderr only. Programmer errors (missing required kwargs) DO propagate as
ValueError so they are caught in tests and development.

Mandatory scope columns (enforced at both the schema and service layer):
  * org_id, workspace_id, user_id, session_id

With two well-defined bypasses:
  1. category = 'setup'    → all scope may be NULL (wizard events)
  2. outcome  = 'failure'  → session_id may be NULL (failed logins)

The schema enforces this via chk_audit_events_user_session_scope. This module
enforces the same invariants in Python so missing kwargs fail with a clear
ValueError rather than an opaque DB CHECK violation.

Usage:
    await emit(
        conn,
        category="iam",
        action="session.login",
        outcome="success",
        user_id=user_id,
        session_id=session_id,
        org_id=org_id,
        workspace_id=workspace_id,
        target_id=session_id,
        target_type="iam_session",
        ip_address=ip,
        user_agent=ua,
    )
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from typing import Any

_id_mod = importlib.import_module("scripts.00_core._id")

# ---------------------------------------------------------------------------
# Dim ID caches
# Populated on first call from the DB, under an asyncio lock so concurrent
# boot-time emits don't race.
# ---------------------------------------------------------------------------
_category_ids: dict[str, int] | None = None
_outcome_ids: dict[str, int] | None = None
_action_ids: dict[str, int] | None = None
_attr_ids: dict[str, int] | None = None
_audit_event_entity_type_id: int | None = None
_cache_lock = asyncio.Lock()


async def _load_dim_caches(conn: object) -> None:
    """Populate all dim caches in one pass. Idempotent and concurrency-safe."""
    global _category_ids, _outcome_ids, _action_ids, _attr_ids
    global _audit_event_entity_type_id

    if _category_ids is not None:
        return

    async with _cache_lock:
        if _category_ids is not None:
            return

        cat_rows = await conn.fetch(  # type: ignore[union-attr]
            'SELECT id, code FROM "04_audit"."01_dim_event_categories"'
        )
        out_rows = await conn.fetch(  # type: ignore[union-attr]
            'SELECT id, code FROM "04_audit"."02_dim_event_outcomes"'
        )
        act_rows = await conn.fetch(  # type: ignore[union-attr]
            'SELECT id, code FROM "04_audit"."03_dim_event_actions"'
        )
        et_row = await conn.fetchrow(  # type: ignore[union-attr]
            'SELECT id FROM "04_audit"."04_dim_entity_types" WHERE code = $1',
            "audit_event",
        )
        attr_rows = await conn.fetch(  # type: ignore[union-attr]
            'SELECT id, code FROM "04_audit"."05_dim_attr_defs" '
            'WHERE entity_type_id = $1',
            et_row["id"],
        )

        _category_ids = {r["code"]: r["id"] for r in cat_rows}
        _outcome_ids = {r["code"]: r["id"] for r in out_rows}
        _action_ids = {r["code"]: r["id"] for r in act_rows}
        _attr_ids = {r["code"]: r["id"] for r in attr_rows}
        _audit_event_entity_type_id = et_row["id"]


def _reset_caches_for_tests() -> None:
    """Clear all module-level caches. Called from tests only."""
    global _category_ids, _outcome_ids, _action_ids, _attr_ids
    global _audit_event_entity_type_id
    _category_ids = None
    _outcome_ids = None
    _action_ids = None
    _attr_ids = None
    _audit_event_entity_type_id = None


async def emit(
    conn: object,
    *,
    category: str,
    action: str,
    outcome: str,
    user_id: str | None,
    session_id: str | None,
    org_id: str | None = None,
    workspace_id: str | None = None,
    actor_id: str | None = None,
    target_id: str | None = None,
    target_type: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one audit event row.

    ``user_id`` and ``session_id`` are declared as required keyword-only
    arguments without defaults so forgetting them raises ``TypeError`` at
    call time — this catches programmer errors immediately.

    Validation rules (raise ``ValueError`` before touching the DB):
      * Non-setup events require ``user_id``.
      * Non-setup non-failure events require ``session_id``.

    DB failures are swallowed and logged to stderr — audit writes must
    never abort the caller's transaction.

    Args:
        conn:          The caller's asyncpg connection (join their transaction).
        category:      Dim code in ``01_dim_event_categories``. Unknown codes
                       fall back to ``iam``.
        action:        Dim code in ``03_dim_event_actions``. Unknown codes
                       fall back to ``unknown``.
        outcome:       Dim code in ``02_dim_event_outcomes`` — ``success`` or ``failure``.
        user_id:       Authenticated principal. NULL only for ``category='setup'``.
        session_id:    Session the action was performed under. NULL only for
                       setup events or events with ``outcome='failure'``.
        org_id:        Tenant scope. NULL for non-tenanted events.
        workspace_id:  Workspace scope. NULL for non-workspace-scoped events.
        actor_id:      Row-author convention. Defaults to ``user_id``.
        target_id:     Resource being acted on. Stored as EAV attr.
        target_type:   Entity-type code of the target. Stored as EAV attr.
        ip_address:    Stored as EAV attr.
        user_agent:    Stored as EAV attr.
        metadata:      Freeform JSON. MUST NOT contain secrets or tokens.

    Raises:
        ValueError: If required scope columns are missing for the event type.
                    Programmer errors propagate so callers notice.
    """
    # Validate mandatory scope BEFORE any DB work. These are programmer errors
    # that must propagate — missing user_id on a non-setup event is a bug.
    if category != "setup":
        if user_id is None:
            raise ValueError(
                f"audit.emit: user_id is required for non-setup events "
                f"(category={category!r}, action={action!r}). "
                "Pass user_id explicitly — see feedback_audit_scope_mandatory.md."
            )
        if outcome != "failure" and session_id is None:
            raise ValueError(
                f"audit.emit: session_id is required for non-setup successful events "
                f"(category={category!r}, action={action!r}). "
                "Pass session_id explicitly — see feedback_audit_scope_mandatory.md."
            )

    # Default actor_id → user_id when the row-author happens to be the principal.
    effective_actor = actor_id if actor_id is not None else user_id

    try:
        await _load_dim_caches(conn)

        assert _category_ids is not None  # for type-checker
        assert _outcome_ids is not None
        assert _action_ids is not None
        assert _attr_ids is not None
        assert _audit_event_entity_type_id is not None

        category_id = _category_ids.get(category) or _category_ids.get("iam")
        outcome_id = _outcome_ids.get(outcome) or _outcome_ids.get("success")
        action_id = _action_ids.get(action) or _action_ids.get("unknown")

        if category_id is None or outcome_id is None or action_id is None:
            sys.stderr.write(
                f"[audit] emit skipped — dim caches missing rows "
                f"(category={category!r}, action={action!r}, outcome={outcome!r})\n"
            )
            return

        event_id = _id_mod.uuid7()

        await conn.execute(  # type: ignore[union-attr]
            """
            INSERT INTO "04_audit"."60_evt_events"
                (id, org_id, workspace_id, user_id, session_id,
                 category_id, action_id, outcome_id, created_by, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP)
            """,
            event_id,
            org_id,
            workspace_id,
            user_id,
            session_id,
            category_id,
            action_id,
            outcome_id,
            effective_actor,
        )

        # One EAV row per non-null context attribute.
        attr_values: list[tuple[str, str, Any, str]] = []
        # Tuple shape: (attr_code, column_name, value, column_name_for_insert)
        if target_id is not None:
            attr_values.append(("target_id", "key_text", target_id, "key_text"))
        if target_type is not None:
            attr_values.append(("target_type", "key_text", target_type, "key_text"))
        if ip_address is not None:
            attr_values.append(("ip_address", "key_text", ip_address, "key_text"))
        if user_agent is not None:
            attr_values.append(("user_agent", "key_text", user_agent, "key_text"))
        if metadata is not None:
            attr_values.append(("metadata", "key_jsonb", metadata, "key_jsonb"))

        for attr_code, _, value, column in attr_values:
            attr_def_id = _attr_ids.get(attr_code)
            if attr_def_id is None:
                sys.stderr.write(
                    f"[audit] unknown attr_def code={attr_code!r} — skipping\n"
                )
                continue
            attr_row_id = _id_mod.uuid7()
            if column == "key_text":
                await conn.execute(  # type: ignore[union-attr]
                    """
                    INSERT INTO "04_audit"."20_dtl_attrs"
                        (id, entity_type_id, entity_id, attr_def_id, key_text)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    attr_row_id,
                    _audit_event_entity_type_id,
                    event_id,
                    attr_def_id,
                    value,
                )
            else:  # key_jsonb — pass dict directly, asyncpg handles JSONB encode.
                await conn.execute(  # type: ignore[union-attr]
                    """
                    INSERT INTO "04_audit"."20_dtl_attrs"
                        (id, entity_type_id, entity_id, attr_def_id, key_jsonb)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    attr_row_id,
                    _audit_event_entity_type_id,
                    event_id,
                    attr_def_id,
                    value,
                )

    except ValueError:
        # Programmer errors propagate.
        raise
    except Exception as exc:
        # DB / runtime failures are swallowed so the caller's tx survives.
        sys.stderr.write(
            f"[audit] emit failed for action={action!r}: {exc}\n"
        )
