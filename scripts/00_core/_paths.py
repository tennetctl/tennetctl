"""Project root resolution and sys.path bootstrap.

Called once from scripts/cli.py main() so that all importlib-based
imports of backend packages resolve correctly regardless of how the
CLI was invoked (uv run, direct python, installed wheel).
"""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    """Return the repository root (the directory containing pyproject.toml)."""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Cannot locate project root (no pyproject.toml found up the tree)")


def ensure_backend_on_syspath() -> None:
    """Add project root to sys.path so that importlib.import_module('04_backend...')
    and importlib.import_module('scripts...') work from any working directory."""
    root = str(project_root())
    if root not in sys.path:
        sys.path.insert(0, root)
