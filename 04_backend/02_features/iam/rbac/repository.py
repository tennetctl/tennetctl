"""RBAC repository — raw SQL for platform/org/workspace roles and permissions.

All reads go through v_* views; all writes go to raw fct_* / lnk_* tables.
conn = asyncpg connection (never pool).
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Permissions catalog
# ---------------------------------------------------------------------------

async def list_permissions(conn: object) -> list[dict]:
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT id, resource, action, description, is_active, created_at, updated_at
          FROM "03_iam"."10_fct_permissions"
         WHERE is_active = true
         ORDER BY resource, action
        """,
    )
    return [dict(r) for r in rows]


async def get_permission_by_id(conn: object, permission_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, resource, action, description, is_active, created_at, updated_at
          FROM "03_iam"."10_fct_permissions"
         WHERE id = $1
        """,
        permission_id,
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Platform roles
# ---------------------------------------------------------------------------

async def list_platform_roles(conn: object) -> list[dict]:
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT id, code, name, category_id, category_label, category_code,
               is_system, is_active, deleted_at, created_by, updated_by,
               created_at, updated_at
          FROM "03_iam".v_platform_roles
         WHERE deleted_at IS NULL
         ORDER BY name
        """,
    )
    return [dict(r) for r in rows]


async def get_platform_role(conn: object, role_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, code, name, category_id, category_label, category_code,
               is_system, is_active, deleted_at, created_by, updated_by,
               created_at, updated_at
          FROM "03_iam".v_platform_roles
         WHERE id = $1
        """,
        role_id,
    )
    return dict(row) if row else None


async def get_platform_role_by_code(conn: object, code: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id FROM "03_iam"."10_fct_platform_roles" WHERE code = $1
        """,
        code,
    )
    return dict(row) if row else None


async def insert_platform_role(
    conn: object,
    *,
    id: str,
    code: str,
    name: str,
    category_id: int,
    is_system: bool,
    actor_id: str,
) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."10_fct_platform_roles"
            (id, code, name, category_id, is_system, is_active,
             created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, true, $6, $6,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        id, code, name, category_id, is_system, actor_id,
    )


async def update_platform_role(
    conn: object,
    role_id: str,
    *,
    name: str | None = None,
    is_active: bool | None = None,
    actor_id: str,
) -> None:
    if name is not None:
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."10_fct_platform_roles"
               SET name = $2, updated_by = $3, updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            role_id, name, actor_id,
        )
    if is_active is not None:
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."10_fct_platform_roles"
               SET is_active = $2, updated_by = $3, updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            role_id, is_active, actor_id,
        )


async def soft_delete_platform_role(conn: object, role_id: str, *, actor_id: str) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."10_fct_platform_roles"
           SET deleted_at = CURRENT_TIMESTAMP,
               is_active  = false,
               updated_by = $2,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        role_id, actor_id,
    )


async def add_platform_role_permission(
    conn: object,
    *,
    id: str,
    platform_role_id: str,
    permission_id: str,
) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_platform_role_permissions"
            (id, platform_role_id, permission_id, created_at)
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
        """,
        id, platform_role_id, permission_id,
    )


async def remove_platform_role_permission(
    conn: object,
    *,
    platform_role_id: str,
    permission_id: str,
) -> bool:
    result = await conn.execute(  # type: ignore[union-attr]
        """
        DELETE FROM "03_iam"."40_lnk_platform_role_permissions"
         WHERE platform_role_id = $1 AND permission_id = $2
        """,
        platform_role_id, permission_id,
    )
    return result.split()[-1] != "0"


async def list_platform_role_permissions(conn: object, platform_role_id: str) -> list[dict]:
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT p.id, p.resource, p.action, p.description, p.is_active
          FROM "03_iam"."40_lnk_platform_role_permissions" lnk
          JOIN "03_iam"."10_fct_permissions" p ON p.id = lnk.permission_id
         WHERE lnk.platform_role_id = $1
         ORDER BY p.resource, p.action
        """,
        platform_role_id,
    )
    return [dict(r) for r in rows]


async def assign_user_platform_role(
    conn: object,
    *,
    id: str,
    user_id: str,
    platform_role_id: str,
    granted_by: str,
) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_user_platform_roles"
            (id, user_id, platform_role_id, granted_by, granted_at, is_active)
        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, true)
        """,
        id, user_id, platform_role_id, granted_by,
    )


async def revoke_user_platform_role(
    conn: object,
    *,
    user_id: str,
    role_id: str,
) -> bool:
    result = await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."40_lnk_user_platform_roles"
           SET is_active = false
         WHERE user_id = $1 AND platform_role_id = $2 AND is_active = true
        """,
        user_id, role_id,
    )
    return result.split()[-1] != "0"


async def get_user_platform_role_assignment(
    conn: object,
    *,
    user_id: str,
    platform_role_id: str,
) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, user_id, platform_role_id, granted_by, granted_at, is_active
          FROM "03_iam"."40_lnk_user_platform_roles"
         WHERE user_id = $1 AND platform_role_id = $2
        """,
        user_id, platform_role_id,
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Org roles
# ---------------------------------------------------------------------------

async def list_org_roles(conn: object, org_id: str) -> list[dict]:
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT id, org_id, org_slug, code, name, category_id, category_label,
               category_code, is_system, is_active, deleted_at,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_org_roles
         WHERE org_id = $1
           AND deleted_at IS NULL
         ORDER BY name
        """,
        org_id,
    )
    return [dict(r) for r in rows]


async def get_org_role(conn: object, role_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, org_id, org_slug, code, name, category_id, category_label,
               category_code, is_system, is_active, deleted_at,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_org_roles
         WHERE id = $1
        """,
        role_id,
    )
    return dict(row) if row else None


async def insert_org_role(
    conn: object,
    *,
    id: str,
    org_id: str,
    code: str,
    name: str,
    category_id: int,
    is_system: bool,
    actor_id: str,
) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."10_fct_org_roles"
            (id, org_id, code, name, category_id, is_system, is_active,
             created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, true, $7, $7,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        id, org_id, code, name, category_id, is_system, actor_id,
    )


async def update_org_role(
    conn: object,
    role_id: str,
    *,
    name: str | None = None,
    is_active: bool | None = None,
    actor_id: str,
) -> None:
    if name is not None:
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."10_fct_org_roles"
               SET name = $2, updated_by = $3, updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            role_id, name, actor_id,
        )
    if is_active is not None:
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."10_fct_org_roles"
               SET is_active = $2, updated_by = $3, updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            role_id, is_active, actor_id,
        )


async def soft_delete_org_role(conn: object, role_id: str, *, actor_id: str) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."10_fct_org_roles"
           SET deleted_at = CURRENT_TIMESTAMP,
               is_active  = false,
               updated_by = $2,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        role_id, actor_id,
    )


async def add_org_role_permission(
    conn: object,
    *,
    id: str,
    org_role_id: str,
    permission_id: str,
) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_org_role_permissions"
            (id, org_role_id, permission_id, created_at)
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
        """,
        id, org_role_id, permission_id,
    )


async def remove_org_role_permission(
    conn: object,
    *,
    org_role_id: str,
    permission_id: str,
) -> bool:
    result = await conn.execute(  # type: ignore[union-attr]
        """
        DELETE FROM "03_iam"."40_lnk_org_role_permissions"
         WHERE org_role_id = $1 AND permission_id = $2
        """,
        org_role_id, permission_id,
    )
    return result.split()[-1] != "0"


async def assign_user_org_role(
    conn: object,
    *,
    id: str,
    user_id: str,
    org_id: str,
    org_role_id: str,
    granted_by: str,
) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_user_org_roles"
            (id, user_id, org_id, org_role_id, granted_by, granted_at, is_active)
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, true)
        """,
        id, user_id, org_id, org_role_id, granted_by,
    )


async def revoke_user_org_role(conn: object, assignment_id: str) -> bool:
    result = await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."40_lnk_user_org_roles"
           SET is_active = false
         WHERE id = $1 AND is_active = true
        """,
        assignment_id,
    )
    return result.split()[-1] != "0"


async def get_user_org_role_assignment(
    conn: object,
    *,
    user_id: str,
    org_id: str,
    org_role_id: str,
) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, user_id, org_id, org_role_id, granted_by, granted_at, is_active
          FROM "03_iam"."40_lnk_user_org_roles"
         WHERE user_id = $1 AND org_id = $2 AND org_role_id = $3
        """,
        user_id, org_id, org_role_id,
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Workspace roles
# ---------------------------------------------------------------------------

async def list_workspace_roles(conn: object, workspace_id: str) -> list[dict]:
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT id, org_id, workspace_id, code, name, category_id, category_label,
               category_code, is_system, is_active, deleted_at,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_workspace_roles
         WHERE workspace_id = $1
           AND deleted_at IS NULL
         ORDER BY name
        """,
        workspace_id,
    )
    return [dict(r) for r in rows]


async def get_workspace_role(conn: object, role_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, org_id, workspace_id, code, name, category_id, category_label,
               category_code, is_system, is_active, deleted_at,
               created_by, updated_by, created_at, updated_at
          FROM "03_iam".v_workspace_roles
         WHERE id = $1
        """,
        role_id,
    )
    return dict(row) if row else None


async def insert_workspace_role(
    conn: object,
    *,
    id: str,
    org_id: str,
    workspace_id: str,
    code: str,
    name: str,
    category_id: int,
    is_system: bool,
    actor_id: str,
) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."10_fct_workspace_roles"
            (id, org_id, workspace_id, code, name, category_id, is_system,
             is_active, created_by, updated_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, true, $8, $8,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        id, org_id, workspace_id, code, name, category_id, is_system, actor_id,
    )


async def update_workspace_role(
    conn: object,
    role_id: str,
    *,
    name: str | None = None,
    is_active: bool | None = None,
    actor_id: str,
) -> None:
    if name is not None:
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."10_fct_workspace_roles"
               SET name = $2, updated_by = $3, updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            role_id, name, actor_id,
        )
    if is_active is not None:
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "03_iam"."10_fct_workspace_roles"
               SET is_active = $2, updated_by = $3, updated_at = CURRENT_TIMESTAMP
             WHERE id = $1
            """,
            role_id, is_active, actor_id,
        )


async def soft_delete_workspace_role(conn: object, role_id: str, *, actor_id: str) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."10_fct_workspace_roles"
           SET deleted_at = CURRENT_TIMESTAMP,
               is_active  = false,
               updated_by = $2,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = $1
        """,
        role_id, actor_id,
    )


async def add_workspace_role_permission(
    conn: object,
    *,
    id: str,
    workspace_role_id: str,
    permission_id: str,
) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_workspace_role_permissions"
            (id, workspace_role_id, permission_id, created_at)
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
        """,
        id, workspace_role_id, permission_id,
    )


async def remove_workspace_role_permission(
    conn: object,
    *,
    workspace_role_id: str,
    permission_id: str,
) -> bool:
    result = await conn.execute(  # type: ignore[union-attr]
        """
        DELETE FROM "03_iam"."40_lnk_workspace_role_permissions"
         WHERE workspace_role_id = $1 AND permission_id = $2
        """,
        workspace_role_id, permission_id,
    )
    return result.split()[-1] != "0"


async def assign_user_workspace_role(
    conn: object,
    *,
    id: str,
    user_id: str,
    org_id: str,
    workspace_id: str,
    workspace_role_id: str,
    granted_by: str,
) -> None:
    await conn.execute(  # type: ignore[union-attr]
        """
        INSERT INTO "03_iam"."40_lnk_user_workspace_roles"
            (id, user_id, org_id, workspace_id, workspace_role_id,
             granted_by, granted_at, is_active)
        VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP, true)
        """,
        id, user_id, org_id, workspace_id, workspace_role_id, granted_by,
    )


async def revoke_user_workspace_role(conn: object, assignment_id: str) -> bool:
    result = await conn.execute(  # type: ignore[union-attr]
        """
        UPDATE "03_iam"."40_lnk_user_workspace_roles"
           SET is_active = false
         WHERE id = $1 AND is_active = true
        """,
        assignment_id,
    )
    return result.split()[-1] != "0"


async def get_user_workspace_role_assignment(
    conn: object,
    *,
    user_id: str,
    workspace_id: str,
    workspace_role_id: str,
) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, user_id, org_id, workspace_id, workspace_role_id,
               granted_by, granted_at, is_active
          FROM "03_iam"."40_lnk_user_workspace_roles"
         WHERE user_id = $1 AND workspace_id = $2 AND workspace_role_id = $3
        """,
        user_id, workspace_id, workspace_role_id,
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Dim helpers
# ---------------------------------------------------------------------------

async def get_role_category_id(conn: object, category_code: str) -> int | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id FROM "03_iam"."06_dim_categories"
         WHERE category_type = 'role' AND code = $1
        """,
        category_code,
    )
    return int(row["id"]) if row else None


async def get_user_by_id(conn: object, user_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, is_active, deleted_at FROM "03_iam"."10_fct_users"
         WHERE id = $1
        """,
        user_id,
    )
    return dict(row) if row else None


async def get_org_by_id(conn: object, org_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, is_active FROM "03_iam"."10_fct_orgs"
         WHERE id = $1
        """,
        org_id,
    )
    return dict(row) if row else None


async def get_workspace_by_id(conn: object, workspace_id: str) -> dict | None:
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT id, org_id, is_active FROM "03_iam"."10_fct_workspaces"
         WHERE id = $1
        """,
        workspace_id,
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Runtime RBAC check
# ---------------------------------------------------------------------------

async def check_user_has_permission(
    conn: object,
    *,
    user_id: str,
    resource: str,
    action: str,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> bool:
    """Return True if user has the given permission in any of the three tiers.

    Checks:
    1. Platform roles → grants everywhere.
    2. Org roles → only if org_id matches.
    3. Workspace roles → only if workspace_id matches.
    """
    # 1. Platform tier
    row = await conn.fetchrow(  # type: ignore[union-attr]
        """
        SELECT 1
          FROM "03_iam"."40_lnk_user_platform_roles"   upr
          JOIN "03_iam"."10_fct_platform_roles"         r   ON r.id  = upr.platform_role_id
          JOIN "03_iam"."40_lnk_platform_role_permissions" rp ON rp.platform_role_id = r.id
          JOIN "03_iam"."10_fct_permissions"            p   ON p.id  = rp.permission_id
         WHERE upr.user_id    = $1
           AND p.resource     = $2
           AND p.action       = $3
           AND upr.is_active  = true
           AND r.is_active    = true
           AND p.is_active    = true
         LIMIT 1
        """,
        user_id, resource, action,
    )
    if row:
        return True

    # 2. Org tier (only if org_id provided)
    if org_id:
        row = await conn.fetchrow(  # type: ignore[union-attr]
            """
            SELECT 1
              FROM "03_iam"."40_lnk_user_org_roles"       uor
              JOIN "03_iam"."10_fct_org_roles"             r   ON r.id  = uor.org_role_id
              JOIN "03_iam"."40_lnk_org_role_permissions"  rp  ON rp.org_role_id = r.id
              JOIN "03_iam"."10_fct_permissions"           p   ON p.id  = rp.permission_id
             WHERE uor.user_id   = $1
               AND uor.org_id    = $2
               AND p.resource    = $3
               AND p.action      = $4
               AND uor.is_active = true
               AND r.is_active   = true
               AND p.is_active   = true
             LIMIT 1
            """,
            user_id, org_id, resource, action,
        )
        if row:
            return True

    # 3. Workspace tier (only if workspace_id provided)
    if workspace_id:
        row = await conn.fetchrow(  # type: ignore[union-attr]
            """
            SELECT 1
              FROM "03_iam"."40_lnk_user_workspace_roles"         uwr
              JOIN "03_iam"."10_fct_workspace_roles"               r   ON r.id  = uwr.workspace_role_id
              JOIN "03_iam"."40_lnk_workspace_role_permissions"    rp  ON rp.workspace_role_id = r.id
              JOIN "03_iam"."10_fct_permissions"                   p   ON p.id  = rp.permission_id
             WHERE uwr.user_id      = $1
               AND uwr.workspace_id = $2
               AND p.resource       = $3
               AND p.action         = $4
               AND uwr.is_active    = true
               AND r.is_active      = true
               AND p.is_active      = true
             LIMIT 1
            """,
            user_id, workspace_id, resource, action,
        )
        if row:
            return True

    return False


async def get_effective_permissions(
    conn: object,
    *,
    user_id: str,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> list[dict]:
    """Return all distinct (resource, action) pairs the user holds.

    Collects permissions from all three tiers, deduplicated.
    org_id and workspace_id narrow the search to include tier-scoped results.
    """
    rows = await conn.fetch(  # type: ignore[union-attr]
        """
        -- Platform permissions (always included)
        SELECT DISTINCT p.resource, p.action, 'platform' AS tier
          FROM "03_iam"."40_lnk_user_platform_roles"      upr
          JOIN "03_iam"."10_fct_platform_roles"            r   ON r.id  = upr.platform_role_id
          JOIN "03_iam"."40_lnk_platform_role_permissions" rp  ON rp.platform_role_id = r.id
          JOIN "03_iam"."10_fct_permissions"               p   ON p.id  = rp.permission_id
         WHERE upr.user_id   = $1
           AND upr.is_active = true
           AND r.is_active   = true
           AND p.is_active   = true

        UNION

        -- Org permissions (if org_id provided)
        SELECT DISTINCT p.resource, p.action, 'org' AS tier
          FROM "03_iam"."40_lnk_user_org_roles"       uor
          JOIN "03_iam"."10_fct_org_roles"             r   ON r.id  = uor.org_role_id
          JOIN "03_iam"."40_lnk_org_role_permissions"  rp  ON rp.org_role_id = r.id
          JOIN "03_iam"."10_fct_permissions"           p   ON p.id  = rp.permission_id
         WHERE uor.user_id   = $1
           AND ($2::text IS NULL OR uor.org_id = $2)
           AND uor.is_active = true
           AND r.is_active   = true
           AND p.is_active   = true

        UNION

        -- Workspace permissions (if workspace_id provided)
        SELECT DISTINCT p.resource, p.action, 'workspace' AS tier
          FROM "03_iam"."40_lnk_user_workspace_roles"         uwr
          JOIN "03_iam"."10_fct_workspace_roles"               r   ON r.id  = uwr.workspace_role_id
          JOIN "03_iam"."40_lnk_workspace_role_permissions"    rp  ON rp.workspace_role_id = r.id
          JOIN "03_iam"."10_fct_permissions"                   p   ON p.id  = rp.permission_id
         WHERE uwr.user_id      = $1
           AND ($3::text IS NULL OR uwr.workspace_id = $3)
           AND uwr.is_active    = true
           AND r.is_active      = true
           AND p.is_active      = true

        ORDER BY resource, action
        """,
        user_id, org_id, workspace_id,
    )
    return [dict(r) for r in rows]
