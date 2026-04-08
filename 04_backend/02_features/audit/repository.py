"""Audit repository — reads v_events. No writes (service.emit handles that)."""

from __future__ import annotations


async def list_events(
    conn: object,
    *,
    limit: int = 50,
    offset: int = 0,
    org_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    category: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
) -> tuple[list[dict], int]:
    """Return (page, total) from v_events with optional filters."""
    conditions = []
    params: list = [limit, offset]

    if org_id is not None:
        params.append(org_id)
        conditions.append(f"org_id = ${len(params)}")
    if user_id is not None:
        params.append(user_id)
        conditions.append(f"user_id = ${len(params)}")
    if session_id is not None:
        params.append(session_id)
        conditions.append(f"session_id = ${len(params)}")
    if category is not None:
        params.append(category)
        conditions.append(f"category = ${len(params)}")
    if action is not None:
        params.append(action)
        conditions.append(f"action = ${len(params)}")
    if outcome is not None:
        params.append(outcome)
        conditions.append(f"outcome = ${len(params)}")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await conn.fetch(  # type: ignore[union-attr]
        f"""
        SELECT id, org_id, workspace_id, user_id, session_id,
               category, action, outcome, actor_id,
               target_id, target_type, ip_address, user_agent,
               created_at
          FROM "04_audit".v_events
          {where}
         ORDER BY created_at DESC
         LIMIT $1 OFFSET $2
        """,
        *params,
    )

    # COUNT — re-number filter params from $1
    filter_params = params[2:]
    count_conditions = []
    if org_id is not None:
        count_conditions.append(f"org_id = ${len(count_conditions) + 1}")
    if user_id is not None:
        count_conditions.append(f"user_id = ${len(count_conditions) + 1}")
    if session_id is not None:
        count_conditions.append(f"session_id = ${len(count_conditions) + 1}")
    if category is not None:
        count_conditions.append(f"category = ${len(count_conditions) + 1}")
    if action is not None:
        count_conditions.append(f"action = ${len(count_conditions) + 1}")
    if outcome is not None:
        count_conditions.append(f"outcome = ${len(count_conditions) + 1}")
    count_where = ("WHERE " + " AND ".join(count_conditions)) if count_conditions else ""

    total = await conn.fetchval(  # type: ignore[union-attr]
        f'SELECT COUNT(*) FROM "04_audit".v_events {count_where}',
        *filter_params,
    )

    return [dict(r) for r in rows], int(total)


async def get_event(conn: object, event_id: str) -> dict | None:
    """Return a single audit event from v_events or None."""
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, org_id, workspace_id, user_id, session_id,
               category, action, outcome, actor_id,
               target_id, target_type, ip_address, user_agent,
               created_at
          FROM "04_audit".v_events
         WHERE id = $1
        """,
        event_id,
    )
    return dict(row) if row else None
