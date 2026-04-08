"""Unit tests for scripts/01_migrator/discovery.py."""

import importlib
import textwrap
from pathlib import Path

import pytest

_discovery = importlib.import_module("scripts.01_migrator.discovery")
discover_migrations = _discovery.discover_migrations
MigrationError = importlib.import_module("scripts.00_core.errors").MigrationError

_SQL_TEMPLATE = textwrap.dedent("""\
    -- UP =========================================================================

    CREATE TABLE {name} (id INT);

    -- DOWN =======================================================================

    DROP TABLE {name};
""")

_YAML_TEMPLATE = textwrap.dedent("""\
    feature: "{feature}"
    sub_feature: "{sub_feature}"
    migrations:
      - file: "{filename}"
        sequence: {sequence}
        description: "Test migration {sequence}"
        depends_on: []
        reversible: true
""")


def _make_migration(
    root: Path,
    feature: str,
    sub_feature: str,
    sequence: int,
    filename: str,
    table_name: str,
) -> None:
    sub_dir = (
        root / "03_docs" / "features" / feature / "05_sub_features" / sub_feature
    )
    sql_dir = sub_dir / "09_sql_migrations" / "02_in_progress"
    sql_dir.mkdir(parents=True, exist_ok=True)

    (sql_dir / filename).write_text(_SQL_TEMPLATE.format(name=table_name))
    (sub_dir / "migration.yaml").write_text(
        _YAML_TEMPLATE.format(
            feature=feature,
            sub_feature=sub_feature,
            filename=filename,
            sequence=sequence,
        )
    )


def test_discovers_migrations_in_sequence_order(tmp_path):
    _make_migration(tmp_path, "02_vault",   "00_bootstrap", 1, "001_vault.sql",   "vault_tbl")
    _make_migration(tmp_path, "01_migrator","00_bootstrap", 0, "000_schema.sql",  "schema_tbl")
    _make_migration(tmp_path, "03_iam",     "00_bootstrap", 3, "003_iam.sql",     "iam_tbl")

    entries = discover_migrations(tmp_path)

    assert [e.sequence for e in entries] == [0, 1, 3]
    assert entries[0].feature == "01_migrator"
    assert entries[1].feature == "02_vault"
    assert entries[2].feature == "03_iam"


def test_checksum_is_sha256_hex(tmp_path):
    _make_migration(tmp_path, "02_vault", "00_bootstrap", 1, "001.sql", "tbl")
    entries = discover_migrations(tmp_path)
    assert len(entries[0].checksum) == 64
    assert all(c in "0123456789abcdef" for c in entries[0].checksum)


def test_missing_sql_file_raises(tmp_path):
    sub_dir = (
        tmp_path / "03_docs" / "features" / "02_vault"
        / "05_sub_features" / "00_bootstrap"
    )
    sub_dir.mkdir(parents=True)
    (sub_dir / "migration.yaml").write_text(
        _YAML_TEMPLATE.format(
            feature="02_vault",
            sub_feature="00_bootstrap",
            filename="missing.sql",
            sequence=99,
        )
    )
    with pytest.raises(MigrationError) as exc_info:
        discover_migrations(tmp_path)
    assert exc_info.value.code == "MIGRATION_FILE_MISSING"


def test_duplicate_sequence_raises(tmp_path):
    _make_migration(tmp_path, "02_vault", "00_bootstrap", 5, "005a.sql", "tbl_a")
    _make_migration(tmp_path, "03_iam",   "00_bootstrap", 5, "005b.sql", "tbl_b")
    with pytest.raises(MigrationError) as exc_info:
        discover_migrations(tmp_path)
    assert exc_info.value.code == "DUPLICATE_SEQUENCE"


def test_resolves_from_migrated_dir(tmp_path):
    """SQL in 01_migrated/ is found even when 02_in_progress/ is absent."""
    feature = "02_vault"
    sub_feature = "00_bootstrap"
    filename = "001_migrated.sql"
    sub_dir = (
        tmp_path / "03_docs" / "features" / feature / "05_sub_features" / sub_feature
    )
    migrated_dir = sub_dir / "09_sql_migrations" / "01_migrated"
    migrated_dir.mkdir(parents=True)
    (migrated_dir / filename).write_text(_SQL_TEMPLATE.format(name="migrated_tbl"))
    (sub_dir / "migration.yaml").write_text(
        _YAML_TEMPLATE.format(
            feature=feature,
            sub_feature=sub_feature,
            filename=filename,
            sequence=1,
        )
    )
    entries = discover_migrations(tmp_path)
    assert len(entries) == 1
    assert entries[0].sequence == 1
