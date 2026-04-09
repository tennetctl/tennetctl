"""Migration runner.

Applies pending migrations against a live Postgres connection.
Each migration executes inside its own transaction; on failure the
transaction is rolled back, the filename is printed, and the runner
raises MigrationError without touching subsequent migrations.

The runner is idempotent: re-running after a partial failure replays
only the un-applied sequences.
"""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass

_errors = importlib.import_module("scripts.00_core.errors")
MigrationError = _errors.MigrationError

# Type alias — avoids importing asyncpg at module level so tests can patch
Connection = object


@dataclass(frozen=True)
class AppliedResult:
    sequence: int
    filename: str
    execution_ms: int


async def load_applied_set(conn: object) -> set[int]:
    """Return the set of already-applied migration sequence numbers."""
    try:
        rows = await conn.fetch(  # type: ignore[union-attr]
            'SELECT sequence FROM "00_schema_migrations".applied_migrations'
        )
        return {row["sequence"] for row in rows}
    except Exception as exc:
        # Table doesn't exist yet (pre-bootstrap) — treat as empty set
        msg = str(exc).lower()
        if "does not exist" in msg or "relation" in msg:
            return set()
        raise


async def apply_pending(
    conn: object,
    entries: list,  # list[MigrationEntry] — avoid circular import
) -> list[AppliedResult]:
    """Apply all entries whose sequence is not in applied_migrations.

    Each migration runs in its own transaction. The applied_migrations
    INSERT is part of the same transaction so the record and the schema
    change are atomic.

    Returns the list of newly applied migrations in order.
    Raises MigrationError on the first failure (after rollback).
    """
    _sections = importlib.import_module("scripts.01_migrator.sections")
    split_up_down = _sections.split_up_down

    applied_set = await load_applied_set(conn)
    results: list[AppliedResult] = []

    for entry in entries:
        if entry.sequence in applied_set:
            continue

        sql_text = entry.path.read_text()
        try:
            up_sql, _ = split_up_down(sql_text)
        except Exception as exc:
            raise MigrationError(
                "SECTION_PARSE_ERROR",
                f"Cannot parse {entry.filename}: {exc}",
            ) from exc

        start = time.perf_counter()
        try:
            async with conn.transaction():  # type: ignore[union-attr]
                # asyncpg supports multi-statement DDL via the simple-query
                # protocol as long as there are no parameter placeholders
                await conn.execute(up_sql)  # type: ignore[union-attr]
                await conn.execute(  # type: ignore[union-attr]
                    """
                    INSERT INTO "00_schema_migrations".applied_migrations
                        (sequence, filename, feature, sub_feature, checksum, execution_ms)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (sequence) DO NOTHING
                    """,
                    entry.sequence,
                    entry.filename,
                    entry.feature,
                    entry.sub_feature,
                    entry.checksum,
                    0,  # updated below after timing
                )
        except Exception as exc:
            raise MigrationError(
                "MIGRATION_FAILED",
                f"Migration {entry.filename} failed: {exc}",
                hint="Fix the SQL error, then re-run. Already-applied migrations are skipped.",
            ) from exc

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Update execution_ms now that we have the real timing
        await conn.execute(  # type: ignore[union-attr]
            """
            UPDATE "00_schema_migrations".applied_migrations
               SET execution_ms = $1
             WHERE sequence = $2
            """,
            elapsed_ms,
            entry.sequence,
        )

        results.append(
            AppliedResult(
                sequence=entry.sequence,
                filename=entry.filename,
                execution_ms=elapsed_ms,
            )
        )
        print(f"  [{entry.sequence:03d}] Applied: {entry.filename} ({elapsed_ms}ms)")

    return results
