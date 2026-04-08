"""Wizard error hierarchy.

All errors carry a machine-readable `code` (SCREAMING_SNAKE_CASE) so
callers can pattern-match without parsing message strings.
"""

from __future__ import annotations


class WizardError(Exception):
    """Base for all tennetctl wizard errors."""

    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint

    def __str__(self) -> str:
        base = f"[{self.code}] {self.args[0]}"
        if self.hint:
            base += f"\n  Hint: {self.hint}"
        return base


class Phase0Error(WizardError):
    """Raised during phase detection / preflight."""


class Phase1Error(WizardError):
    """Raised during DB bootstrap (role creation, migrations)."""


class Phase2Error(WizardError):
    """Raised during vault initialisation."""


class Phase3Error(WizardError):
    """Raised during first admin creation."""


class Phase4Error(WizardError):
    """Raised during settings seed."""


class MigrationError(WizardError):
    """Raised by the migration runner."""


class VaultError(WizardError):
    """Raised by vault service operations."""


class AbortedByUser(WizardError):
    """User pressed Ctrl-C or answered 'no' to a required confirmation."""

    def __init__(self) -> None:
        super().__init__("ABORTED_BY_USER", "Setup aborted by user.")
