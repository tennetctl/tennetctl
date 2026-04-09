"""tennetctl — top-level CLI dispatcher.

Routes subcommands to their feature packages. Kept intentionally small: each
sub-command owns its own argument parsing.
"""

from __future__ import annotations

import importlib
import sys


def main() -> int:
    # Ensure project root is on sys.path so importlib can find
    # both scripts.* and 04_backend.* packages.
    _paths = importlib.import_module("scripts.00_core._paths")
    _paths.ensure_backend_on_syspath()

    argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        _print_usage()
        return 0

    cmd, *rest = argv

    if cmd == "setup":
        _orchestrator = importlib.import_module("scripts.setup.wizard.orchestrator")
        return _orchestrator.run_wizard(rest)

    if cmd == "migrate":
        _migrate = importlib.import_module("scripts.01_migrator.__main__")
        return _migrate.main(rest)

    if cmd == "admin":
        return _dispatch_admin(rest)

    sys.stderr.write(f"tennetctl: unknown command {cmd!r}\n\n")
    _print_usage()
    return 2


def _dispatch_admin(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(
            "usage: tennetctl admin <subcommand> [options]\n"
            "\n"
            "subcommands:\n"
            "  reset-password   Reset a user's password\n"
        )
        return 0
    sub, *rest = argv
    if sub == "reset-password":
        _reset_pw = importlib.import_module("scripts.admin.reset_password")
        return _reset_pw.run(rest)
    sys.stderr.write(f"tennetctl admin: unknown subcommand {sub!r}\n")
    return 2


def _print_usage() -> None:
    sys.stdout.write(
        "usage: tennetctl <command> [options]\n"
        "\n"
        "commands:\n"
        "  setup    First-run install wizard\n"
        "  migrate  Manage database migrations\n"
        "  admin    Administrative operations\n"
        "\n"
        "Run 'tennetctl <command> --help' for command-specific options.\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
