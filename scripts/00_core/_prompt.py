"""Minimal CLI prompt helpers.

Wraps sys.stdin/getpass so the wizard can be fully tested by
monkey-patching _input_fn and _getpass_fn.
"""

from __future__ import annotations

import getpass
import sys
from collections.abc import Callable

# Allow tests to inject answers without subprocess or pexpect
_input_fn: Callable[[str], str] = input
_getpass_fn: Callable[[str], str] = getpass.getpass


def ask(
    label: str,
    *,
    default: str | None = None,
    secret: bool = False,
    validate: Callable[[str], str | None] | None = None,
    yes_flag: bool = False,
) -> str:
    """Prompt the user for a value.

    Args:
        label:    Displayed prompt text (without trailing colon/space).
        default:  Value returned when the user presses Enter without input.
        secret:   Use getpass (hidden input) when True.
        validate: Called with the raw answer; return an error message string
                  to re-prompt, or None to accept.
        yes_flag: When True and a default is set, skip the prompt entirely
                  and return the default. Useful for non-interactive CI runs.
    """
    if yes_flag and default is not None:
        return default

    prompt = f"  {label}"
    if default is not None:
        prompt += f" [{default}]"
    prompt += ": "

    while True:
        try:
            raw = (_getpass_fn(prompt) if secret else _input_fn(prompt)).strip()
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\nAborted.\n")
            raise SystemExit(1)

        value = raw if raw else (default or "")

        if not value:
            sys.stderr.write("  This field is required.\n")
            continue

        if validate is not None:
            error = validate(value)
            if error:
                sys.stderr.write(f"  {error}\n")
                continue

        return value


def confirm(label: str, *, default: bool = True, yes_flag: bool = False) -> bool:
    """Prompt for a yes/no answer. Returns a bool."""
    if yes_flag:
        return default

    hint = "[Y/n]" if default else "[y/N]"
    prompt = f"  {label} {hint}: "

    while True:
        try:
            raw = _input_fn(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\nAborted.\n")
            raise SystemExit(1)

        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        sys.stderr.write("  Please answer y or n.\n")
