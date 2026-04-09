"""SQL migration section splitter.

Splits a migration SQL file into its UP and DOWN sections by matching the
``-- UP ===`` and ``-- DOWN ===`` marker lines defined in the project's
migration convention.
"""

from __future__ import annotations

import importlib
import re

_errors = importlib.import_module("scripts.00_core.errors")
MigrationError = _errors.MigrationError

# Matches lines like "-- UP ===========..." (case-insensitive, flexible whitespace)
_UP_RE = re.compile(r"^--\s+UP\s*=+", re.MULTILINE | re.IGNORECASE)
_DOWN_RE = re.compile(r"^--\s+DOWN\s*=+", re.MULTILINE | re.IGNORECASE)


def split_up_down(sql_text: str) -> tuple[str, str]:
    """Split *sql_text* into ``(up_sql, down_sql)`` sections.

    Raises MigrationError if either section marker is absent.
    Returns the content between the UP marker and the DOWN marker as ``up_sql``,
    and everything after the DOWN marker as ``down_sql``.
    """
    up_match = _UP_RE.search(sql_text)
    if not up_match:
        raise MigrationError(
            "MISSING_UP_SECTION",
            "Migration file has no '-- UP ===...' marker.",
            hint="Add '-- UP ========' on its own line before the forward migration SQL.",
        )

    down_match = _DOWN_RE.search(sql_text)
    if not down_match:
        raise MigrationError(
            "MISSING_DOWN_SECTION",
            "Migration file has no '-- DOWN ===...' marker.",
            hint="Add '-- DOWN ========' on its own line before the rollback SQL.",
        )

    # UP content: from end of UP marker line to start of DOWN marker line
    up_start = sql_text.index("\n", up_match.start()) + 1
    down_start_line = down_match.start()
    up_sql = sql_text[up_start:down_start_line].strip()

    # DOWN content: from end of DOWN marker line to EOF
    down_start = sql_text.index("\n", down_match.start()) + 1
    down_sql = sql_text[down_start:].strip()

    return up_sql, down_sql
