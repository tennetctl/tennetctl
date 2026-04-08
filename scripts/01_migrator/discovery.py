"""Migration discovery.

Scans the repo for migration.yaml manifests and returns an ordered list
of MigrationEntry objects ready to be applied by the runner.

Discovery rules:
- Globs ``03_docs/features/*/05_sub_features/*/migration.yaml``.
- For each entry in the manifest, resolves the SQL file from
  ``09_sql_migrations/02_in_progress/`` first, then ``01_migrated/``.
- Sequences must be globally unique across all features/sub-features.
- The final list is sorted by sequence ascending.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import importlib

import yaml

_errors = importlib.import_module("scripts.00_core.errors")
MigrationError = _errors.MigrationError


@dataclass(frozen=True)
class MigrationEntry:
    sequence: int
    filename: str
    feature: str
    sub_feature: str
    description: str
    path: Path
    checksum: str  # SHA-256 hex of the file contents at discovery time
    reversible: bool
    depends_on: tuple[int, ...]


def _resolve_sql_file(sub_feature_dir: Path, filename: str) -> Path:
    """Return the absolute path to the SQL file, checking in_progress then migrated."""
    in_progress = sub_feature_dir / "09_sql_migrations" / "02_in_progress" / filename
    migrated = sub_feature_dir / "09_sql_migrations" / "01_migrated" / filename
    if in_progress.exists():
        return in_progress
    if migrated.exists():
        return migrated
    raise MigrationError(
        "MIGRATION_FILE_MISSING",
        f"SQL file {filename!r} not found in 02_in_progress/ or 01_migrated/ "
        f"under {sub_feature_dir}",
        hint="Check the file exists and the migration.yaml filename matches.",
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _parse_manifest(
    yaml_path: Path,
    feature: str,
    sub_feature: str,
    sub_feature_dir: Path,
) -> list[MigrationEntry]:
    """Parse one migration.yaml and return its MigrationEntry objects."""
    try:
        data: Any = yaml.safe_load(yaml_path.read_text())
    except yaml.YAMLError as exc:
        raise MigrationError(
            "INVALID_MIGRATION_YAML",
            f"Failed to parse {yaml_path}: {exc}",
        ) from exc

    entries: list[MigrationEntry] = []
    for item in data.get("migrations", []):
        filename: str = item["file"]
        sequence: int = int(item["sequence"])
        sql_path = _resolve_sql_file(sub_feature_dir, filename)
        entries.append(
            MigrationEntry(
                sequence=sequence,
                filename=filename,
                feature=feature,
                sub_feature=sub_feature,
                description=item.get("description", ""),
                path=sql_path,
                checksum=_sha256(sql_path),
                reversible=bool(item.get("reversible", True)),
                depends_on=tuple(int(d) for d in item.get("depends_on", [])),
            )
        )
    return entries


def discover_migrations(project_root: Path) -> list[MigrationEntry]:
    """Discover all migrations under *project_root* and return them sorted by sequence.

    Raises MigrationError if:
    - A yaml file references a missing SQL file.
    - Two migrations share the same sequence number.
    """
    docs_root = project_root / "03_docs" / "features"
    if not docs_root.is_dir():
        raise MigrationError(
            "DOCS_ROOT_MISSING",
            f"Expected docs root at {docs_root} — is project_root correct?",
        )

    all_entries: list[MigrationEntry] = []

    for yaml_path in sorted(docs_root.glob("*/05_sub_features/*/migration.yaml")):
        # Derive feature/sub_feature from directory structure
        # yaml_path = .../03_docs/features/02_vault/05_sub_features/01_setup/migration.yaml
        sub_feature_dir = yaml_path.parent
        feature = yaml_path.parts[-4]       # e.g. "02_vault"
        sub_feature = yaml_path.parts[-2]   # e.g. "01_setup"

        entries = _parse_manifest(yaml_path, feature, sub_feature, sub_feature_dir)
        all_entries.extend(entries)

    # Validate global sequence uniqueness
    seen: dict[int, str] = {}
    for entry in all_entries:
        if entry.sequence in seen:
            raise MigrationError(
                "DUPLICATE_SEQUENCE",
                f"Sequence {entry.sequence} is used by both "
                f"{seen[entry.sequence]} and {entry.filename}",
                hint="Each migration must have a globally unique three-digit NNN.",
            )
        seen[entry.sequence] = entry.filename

    return sorted(all_entries, key=lambda e: e.sequence)
