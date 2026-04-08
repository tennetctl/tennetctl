"""Phase 3 — First admin user, default org, and default workspace.

Creates in a single transaction:
  1. The first admin user row + EAV attrs (username, email, password_hash)
  2. The default org ("tennetctl") + EAV attrs (name, slug, description)
  3. The default workspace ("tennetctl") + EAV attrs (name, slug, description)
  4. lnk_user_orgs (admin → org)
  5. lnk_user_workspaces (admin → workspace)
  6. system_meta.installed_at timestamp

All dim IDs resolved by code — no hardcoded IDENTITY values.
"""

from __future__ import annotations

import importlib

import asyncpg

_id_mod    = importlib.import_module("scripts.00_core._id")
_errors    = importlib.import_module("scripts.00_core.errors")
_prompt    = importlib.import_module("scripts.00_core._prompt")
_password  = importlib.import_module("04_backend.02_features.iam.auth.password")

Phase3Error = _errors.Phase3Error

_DEFAULT_ORG_NAME  = "tennetctl"
_DEFAULT_ORG_SLUG  = "tennetctl"
_DEFAULT_ORG_DESC  = "Default tenant organisation created at install time."
_DEFAULT_WS_NAME   = "tennetctl"
_DEFAULT_WS_SLUG   = "tennetctl"
_DEFAULT_WS_DESC   = "Default workspace created at install time."


async def run_phase3(*, admin_dsn: str, yes_flag: bool = False) -> None:
    print("\n── Phase 3 — First Admin ─────────────────────────────────")

    username = _prompt.ask("Admin username", yes_flag=yes_flag, default="admin")
    email    = _prompt.ask("Admin email",    yes_flag=yes_flag, default="admin@tennetctl.local")
    password = _prompt.ask("Admin password", yes_flag=yes_flag, default="ChangeMe123!", secret=True)

    password_hash = _password.hash_password(password)

    await _insert_first_admin(
        admin_dsn=admin_dsn,
        username=username,
        email=email,
        password_hash=password_hash,
    )
    print(f"  Created admin user '{username}'.")
    print("  ✔ Phase 3 complete.")


async def _fetch_dim_id(conn, table: str, code: str) -> int:
    """Resolve a dim table row's id by code."""
    row = await conn.fetchrow(f'SELECT id FROM "03_iam".{table} WHERE code = $1', code)
    if row is None:
        raise Phase3Error("DIM_NOT_FOUND", f"Dim row not found: {table}.code={code!r}")
    return row["id"]


async def _fetch_attr_id(conn, entity_code: str, attr_code: str) -> int:
    """Resolve attr_def_id by (entity_code, attr_code)."""
    row = await conn.fetchrow(
        """
        SELECT d.id
          FROM "03_iam"."07_dim_attr_defs" d
          JOIN "03_iam"."06_dim_entity_types" et ON d.entity_type_id = et.id
         WHERE et.code = $1 AND d.code = $2
        """,
        entity_code,
        attr_code,
    )
    if row is None:
        raise Phase3Error("ATTR_NOT_FOUND", f"Attr not found: entity={entity_code!r} attr={attr_code!r}")
    return row["id"]


async def _insert_first_admin(
    *,
    admin_dsn: str,
    username: str,
    email: str,
    password_hash: str,
) -> None:
    conn = await asyncpg.connect(admin_dsn)
    try:
        # Check idempotency — skip if already installed.
        meta = await conn.fetchrow(
            'SELECT installed_at FROM "00_schema_migrations".system_meta WHERE id = 1'
        )
        if meta and meta["installed_at"] is not None:
            print("  [Phase 3] Already complete — skipping (installed_at is set).")
            return

        async with conn.transaction():
            # --- Resolve dim IDs by code ---
            account_type_id = await _fetch_dim_id(conn, '"06_dim_account_types"', "default_admin")
            auth_type_id    = await _fetch_dim_id(conn, '"07_dim_auth_types"',    "username_password")
            org_status_id   = await _fetch_dim_id(conn, '"01_dim_org_statuses"',  "active")
            ws_status_id    = await _fetch_dim_id(conn, '"02_dim_workspace_statuses"', "active")

            # --- Resolve attr_def IDs by code ---
            user_username_attr = await _fetch_attr_id(conn, "iam_user", "username")
            user_email_attr    = await _fetch_attr_id(conn, "iam_user", "email")
            user_pw_attr       = await _fetch_attr_id(conn, "iam_user", "password_hash")
            user_et_id_row     = await conn.fetchrow(
                'SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = $1', "iam_user"
            )
            user_et_id = user_et_id_row["id"]

            org_name_attr = await _fetch_attr_id(conn, "iam_org", "name")
            org_slug_attr = await _fetch_attr_id(conn, "iam_org", "slug")
            org_desc_attr = await _fetch_attr_id(conn, "iam_org", "description")
            org_et_id_row = await conn.fetchrow(
                'SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = $1', "iam_org"
            )
            org_et_id = org_et_id_row["id"]

            ws_name_attr = await _fetch_attr_id(conn, "iam_workspace", "name")
            ws_slug_attr = await _fetch_attr_id(conn, "iam_workspace", "slug")
            ws_desc_attr = await _fetch_attr_id(conn, "iam_workspace", "description")
            ws_et_id_row = await conn.fetchrow(
                'SELECT id FROM "03_iam"."06_dim_entity_types" WHERE code = $1', "iam_workspace"
            )
            ws_et_id = ws_et_id_row["id"]

            user_id = _id_mod.uuid7()
            org_id  = _id_mod.uuid7()
            ws_id   = _id_mod.uuid7()

            # 1. Insert user (reflexive created_by — FK is DEFERRABLE)
            await conn.execute(
                """
                INSERT INTO "03_iam"."10_fct_users"
                    (id, account_type_id, auth_type_id,
                     is_active, is_test, created_by, updated_by, created_at, updated_at)
                VALUES ($1, $2, $3, TRUE, FALSE, $1, $1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                user_id, account_type_id, auth_type_id,
            )

            # 2. Insert user EAV attrs
            for attr_id, value in (
                (user_username_attr, username),
                (user_email_attr,    email),
                (user_pw_attr,       password_hash),
            ):
                await conn.execute(
                    """
                    INSERT INTO "03_iam"."20_dtl_attrs"
                        (id, entity_type_id, entity_id, attr_def_id,
                         key_text, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    _id_mod.uuid7(), user_et_id, user_id, attr_id, value,
                )

            # 3. Insert org
            await conn.execute(
                """
                INSERT INTO "03_iam"."10_fct_orgs"
                    (id, status_id, is_active, is_test,
                     created_by, updated_by, created_at, updated_at)
                VALUES ($1, $2, TRUE, FALSE, $3, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                org_id, org_status_id, user_id,
            )

            # 4. Insert org EAV attrs
            for attr_id, value in (
                (org_name_attr, _DEFAULT_ORG_NAME),
                (org_slug_attr, _DEFAULT_ORG_SLUG),
                (org_desc_attr, _DEFAULT_ORG_DESC),
            ):
                await conn.execute(
                    """
                    INSERT INTO "03_iam"."20_dtl_attrs"
                        (id, entity_type_id, entity_id, attr_def_id,
                         key_text, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    _id_mod.uuid7(), org_et_id, org_id, attr_id, value,
                )

            # 5. Insert workspace
            await conn.execute(
                """
                INSERT INTO "03_iam"."10_fct_workspaces"
                    (id, org_id, status_id, is_active, is_test,
                     created_by, updated_by, created_at, updated_at)
                VALUES ($1, $2, $3, TRUE, FALSE, $4, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                ws_id, org_id, ws_status_id, user_id,
            )

            # 6. Insert workspace EAV attrs
            for attr_id, value in (
                (ws_name_attr, _DEFAULT_WS_NAME),
                (ws_slug_attr, _DEFAULT_WS_SLUG),
                (ws_desc_attr, _DEFAULT_WS_DESC),
            ):
                await conn.execute(
                    """
                    INSERT INTO "03_iam"."20_dtl_attrs"
                        (id, entity_type_id, entity_id, attr_def_id,
                         key_text, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    _id_mod.uuid7(), ws_et_id, ws_id, attr_id, value,
                )

            # 7. Insert lnk_user_orgs
            await conn.execute(
                """
                INSERT INTO "03_iam"."40_lnk_user_orgs"
                    (id, org_id, user_id, created_by, created_at)
                VALUES ($1, $2, $3, $3, CURRENT_TIMESTAMP)
                """,
                _id_mod.uuid7(), org_id, user_id,
            )

            # 8. Insert lnk_user_workspaces
            await conn.execute(
                """
                INSERT INTO "03_iam"."40_lnk_user_workspaces"
                    (id, org_id, workspace_id, user_id, created_by, created_at)
                VALUES ($1, $2, $3, $4, $4, CURRENT_TIMESTAMP)
                """,
                _id_mod.uuid7(), org_id, ws_id, user_id,
            )

            # 9. Mark install complete
            await conn.execute(
                """
                UPDATE "00_schema_migrations".system_meta
                   SET installed_at           = CURRENT_TIMESTAMP,
                       installer_version      = '0.1.0',
                       first_admin_username   = $1,
                       first_admin_created_at = CURRENT_TIMESTAMP,
                       install_id             = $2,
                       updated_at             = CURRENT_TIMESTAMP
                 WHERE id = 1
                """,
                username, _id_mod.uuid7(),
            )
    finally:
        await conn.close()
