"""tennetctl setup — entry point.

Delegates immediately to the orchestrator which owns all phase logic
and argument parsing.
"""

from __future__ import annotations

import importlib
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    _orchestrator = importlib.import_module("scripts.setup.wizard.orchestrator")
    return _orchestrator.run_wizard(list(argv or []))


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
