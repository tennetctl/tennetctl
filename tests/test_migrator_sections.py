"""Unit tests for scripts/01_migrator/sections.py."""

import importlib
import pytest

_sections = importlib.import_module("scripts.01_migrator.sections")
split_up_down = _sections.split_up_down
MigrationError = importlib.import_module("scripts.00_core.errors").MigrationError


_SAMPLE_SQL = """\
-- =============================================================================
-- Some header
-- =============================================================================

-- UP =========================================================================

CREATE TABLE foo (id INT);

-- DOWN =======================================================================

DROP TABLE foo;
"""


def test_splits_normal_file():
    up, down = split_up_down(_SAMPLE_SQL)
    assert "CREATE TABLE foo" in up
    assert "DROP TABLE foo" in down


def test_up_does_not_contain_down_marker():
    up, _ = split_up_down(_SAMPLE_SQL)
    assert "-- DOWN" not in up


def test_down_does_not_contain_up_marker():
    _, down = split_up_down(_SAMPLE_SQL)
    assert "-- UP" not in down


def test_missing_up_raises():
    with pytest.raises(MigrationError) as exc_info:
        split_up_down("SELECT 1;\n-- DOWN ====\nDROP TABLE x;")
    assert exc_info.value.code == "MISSING_UP_SECTION"


def test_missing_down_raises():
    with pytest.raises(MigrationError) as exc_info:
        split_up_down("-- UP ====\nCREATE TABLE x (id INT);")
    assert exc_info.value.code == "MISSING_DOWN_SECTION"


def test_strips_whitespace():
    sql = "-- UP ===\n\n  CREATE TABLE t (id INT);\n\n-- DOWN ===\n\n  DROP TABLE t;\n"
    up, down = split_up_down(sql)
    assert up == "CREATE TABLE t (id INT);"
    assert down == "DROP TABLE t;"


def test_case_insensitive_markers():
    sql = "-- up ===\nCREATE TABLE t (id INT);\n-- down ===\nDROP TABLE t;"
    up, down = split_up_down(sql)
    assert "CREATE TABLE" in up
    assert "DROP TABLE" in down
