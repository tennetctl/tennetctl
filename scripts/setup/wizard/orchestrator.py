"""Setup wizard orchestrator.

Entry point for ``tennetctl setup``. Detects the current install phase,
skips completed phases, runs the remaining ones in order, and exits.

On any error the traceback is hidden from the user; a human-readable
banner is printed instead. The process exits non-zero.

On success the wizard exits 0.
"""

from __future__ import annotations

import importlib
import os
import sys

import asyncpg

_prompt = importlib.import_module("scripts.00_core._prompt")
_dsn_mod = importlib.import_module("scripts.00_core.dsn")
_errors = importlib.import_module("scripts.00_core.errors")
_paths = importlib.import_module("scripts.00_core._paths")
_state_mod = importlib.import_module("scripts.setup.wizard.state")
_bootstrap = importlib.import_module("scripts.setup.db_bootstrap.bootstrap")
_phase2 = importlib.import_module("scripts.setup.vault_init.phase2")
_phase3 = importlib.import_module("scripts.setup.first_admin.phase3")
_phase4 = importlib.import_module("scripts.setup.settings.phase4")

WizardError = _errors.WizardError


def run_wizard(argv: list[str]) -> int:
    """Parse *argv*, resolve the current phase, run the wizard.

    Returns an exit code (0 = success, non-zero = failure).
    """
    import asyncio  # noqa: PLC0415

    _paths.ensure_backend_on_syspath()

    opts = _parse_argv(argv)

    try:
        return asyncio.run(_run_async(opts))
    except WizardError as exc:
        _print_error_banner(exc)
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("\n  Setup aborted.\n")
        return 130


# ---------------------------------------------------------------------------
# Async body
# ---------------------------------------------------------------------------

async def _run_async(opts: object) -> int:
    env: str = opts.env or os.environ.get("TENNETCTL_ENV") or _prompt_env(opts.yes)  # type: ignore[union-attr]
    mode: str = opts.mode or "a"  # type: ignore[union-attr]
    yes_flag: bool = opts.yes  # type: ignore[union-attr]

    print("\ntennetctl setup")
    print("=" * 60)
    print(f"  Environment : {env}")
    print(f"  DB mode     : {'A (superuser bootstrap)' if mode == 'a' else 'B (pre-provisioned DSNs)'}")
    print()

    # ------------------------------------------------------------------ #
    # Phase 0 — detect current install state                             #
    # ------------------------------------------------------------------ #
    state = await _detect_state()

    if state.phase4_settings_seeded:
        print("  ✔ Install already complete. All phases detected. Nothing to do.")
        return 0

    if (
        state.phase1_db_bootstrapped
        and not yes_flag
        and not opts.resume  # type: ignore[union-attr]
        and not _any_phase_incomplete(state)
    ):
        # Should not happen (caught by phase4_settings_seeded above)
        pass

    # ------------------------------------------------------------------ #
    # Phase 1 — DB bootstrap + migrations                                #
    # ------------------------------------------------------------------ #
    admin_dsn: str | None = None
    write_dsn: str | None = None
    read_dsn: str | None = None

    if not state.phase1_db_bootstrapped:
        result = await _bootstrap.run_phase1(mode=mode, yes_flag=yes_flag)
        admin_dsn = result.admin_dsn
        write_dsn = result.write_dsn
        read_dsn = result.read_dsn
    elif not state.phase2_vault_initialized:
        # Phase 1 is done but Phase 2 has not completed.
        # Because Phase 2 is now fully transactional, any failure leaves the
        # DB clean (no partial vault state). We need the three DSNs to run
        # Phase 2. Try to recover them from env vars (Mode B) or require the
        # operator to re-run with MODE=a so the wizard re-bootstraps the roles.
        #
        # Mode A: Re-run Phase 1 to re-generate and re-set role passwords.
        #         This is safe because Phase 2 never stored them (vault is clean).
        # Mode B: The operator pre-provisioned the DSNs, so we re-run Phase 1
        #         in mode B which re-verifies the supplied DSNs.
        print("  [Phase 1] Phase 2 incomplete — re-running Phase 1 to obtain DSNs …")
        result = await _bootstrap.run_phase1(mode=mode, yes_flag=yes_flag)
        admin_dsn = result.admin_dsn
        write_dsn = result.write_dsn
        read_dsn = result.read_dsn
    else:
        print("  [Phase 1] ✔ Already complete — skipping.")
        # Phases 1 + 2 done — recover DSNs from vault
        admin_dsn, write_dsn, read_dsn = await _recover_dsns_from_vault(state)

    # ------------------------------------------------------------------ #
    # Phase 2 — vault init                                               #
    # ------------------------------------------------------------------ #
    if not state.phase2_vault_initialized:
        await _phase2.run_phase2(
            admin_dsn=admin_dsn,
            write_dsn=write_dsn,
            read_dsn=read_dsn,
        )
    else:
        print("  [Phase 2] ✔ Already complete — skipping.")

    # ------------------------------------------------------------------ #
    # Phase 3 — first admin                                              #
    # ------------------------------------------------------------------ #
    if not state.phase3_first_admin_created:
        await _phase3.run_phase3(admin_dsn=admin_dsn, yes_flag=yes_flag)
    else:
        print("  [Phase 3] ✔ Already complete — skipping.")

    # ------------------------------------------------------------------ #
    # Phase 4 — settings seed                                            #
    # ------------------------------------------------------------------ #
    if not state.phase4_settings_seeded:
        await _phase4.run_phase4(
            admin_dsn=admin_dsn,
            write_dsn=write_dsn,
            env=env,
            yes_flag=yes_flag,
        )
    else:
        print("  [Phase 4] ✔ Already complete — skipping.")

    print("  ✔ Install complete.")
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _detect_state():
    """Connect with the best available DSN and detect install state.

    Priority:
      1. $DATABASE_URL_ADMIN (admin/DDL role — most permissive, most reliable)
      2. $DATABASE_URL (write role — sufficient for read queries)
      3. $DATABASE_URL_SUPER (superuser — used on first run to detect existing state)

    Falls back to all-False (fresh install) if none connect.
    """
    dsn = (
        os.environ.get("DATABASE_URL_ADMIN")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("DATABASE_URL_SUPER")
    )
    if dsn is None:
        return _state_mod.InstallState(
            phase1_db_bootstrapped=False,
            phase2_vault_initialized=False,
            phase3_first_admin_created=False,
            phase4_settings_seeded=False,
            unseal_salt_b64=None,
        )
    try:
        conn = await asyncpg.connect(dsn)
        try:
            return await _state_mod.detect_install_state(conn)
        finally:
            await conn.close()
    except asyncpg.InvalidPasswordError as exc:
        # Auth failure means the DB is reachable but creds are wrong.
        # Surface this as a real error rather than masking it as "fresh install".
        raise _errors.Phase0Error(
            "AUTH_FAILED",
            f"Database authentication failed: {exc}. Check your DSN credentials.",
        ) from exc
    except (OSError, asyncpg.CannotConnectNowError, asyncpg.TooManyConnectionsError):
        # Connection-refused / unreachable — treat as fresh install so the
        # wizard can proceed to create the DB roles (Phase 1 handles this).
        return _state_mod.InstallState(
            phase1_db_bootstrapped=False,
            phase2_vault_initialized=False,
            phase3_first_admin_created=False,
            phase4_settings_seeded=False,
            unseal_salt_b64=None,
        )
    except Exception:
        # Unknown error — treat as fresh install (conservative).
        return _state_mod.InstallState(
            phase1_db_bootstrapped=False,
            phase2_vault_initialized=False,
            phase3_first_admin_created=False,
            phase4_settings_seeded=False,
            unseal_salt_b64=None,
        )


async def _recover_dsns_from_vault(state) -> tuple[str, str, str]:
    """Re-derive the MDK and decrypt the three DSNs from the vault.

    Called when phases 1 and 2 are already done but we need the DSNs
    to run phases 3 and 4 (e.g. resuming an interrupted install).
    """
    # Any DSN that can read 02_vault.10_fct_secrets will do
    write_dsn_env = (
        os.environ.get("DATABASE_URL_ADMIN")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("DATABASE_URL_SUPER")
    )

    if not write_dsn_env:
        raise _errors.Phase0Error(
            "NO_WRITE_DSN",
            "Phases 1 and 2 are complete but no database DSN is set. "
            "Cannot recover vault secrets.",
            hint="Export the write-role DSN as $DATABASE_URL and re-run.",
        )

    # KDF input is the write DSN password — same as what Phase 2 used.
    # DATABASE_URL (write role) must be set here to recover.
    dsn_parts = _dsn_mod.parse_dsn(write_dsn_env)
    kdf_password: str = dsn_parts["password"]  # type: ignore[assignment]

    if not state.unseal_salt_b64:
        raise _errors.Phase0Error(
            "NO_UNSEAL_SALT",
            "Vault is initialised but system_meta.unseal_salt is NULL.",
        )

    import base64  # noqa: PLC0415
    salt_bytes = base64.urlsafe_b64decode(state.unseal_salt_b64)

    _kdf = importlib.import_module("scripts.setup.vault_init.kdf")
    _vault_service = importlib.import_module("04_backend.02_features.vault.setup.service")

    wrap_key = _kdf.derive_wrap_key(kdf_password, salt_bytes)

    conn = await asyncpg.connect(write_dsn_env)
    try:
        mdk = await _vault_service.unseal_vault(conn, wrap_key=wrap_key)
        admin_dsn = await _vault_service.get_secret(conn, mdk=mdk, path="tennetctl/db/admin_dsn")
        write_dsn = await _vault_service.get_secret(conn, mdk=mdk, path="tennetctl/db/write_dsn")
        read_dsn = await _vault_service.get_secret(conn, mdk=mdk, path="tennetctl/db/read_dsn")
    finally:
        await conn.close()

    return admin_dsn, write_dsn, read_dsn


def _any_phase_incomplete(state) -> bool:
    return not (
        state.phase1_db_bootstrapped
        and state.phase2_vault_initialized
        and state.phase3_first_admin_created
        and state.phase4_settings_seeded
    )


def _prompt_env(yes_flag: bool) -> str:
    return _prompt.ask(
        "Environment",
        default="dev",
        validate=lambda v: None if v in ("dev", "staging", "prod") else "Choose dev, staging, or prod.",
        yes_flag=yes_flag,
    )


def _print_error_banner(exc: Exception) -> None:
    sys.stderr.write(f"\n  ✗ Setup failed: {exc}\n\n")


# ---------------------------------------------------------------------------
# Argument parsing (mirrors scripts/setup/__main__.py but handles the full
# set of flags here so the orchestrator is self-contained)
# ---------------------------------------------------------------------------

def _parse_argv(argv: list[str]):
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(prog="tennetctl setup", add_help=False)
    parser.add_argument("--env", choices=("dev", "staging", "prod"), default=None)
    parser.add_argument("--mode", choices=("a", "b"), default=None)
    parser.add_argument("--unseal-mode", choices=("manual", "kms_azure"), default="manual")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    return parser.parse_args(argv)
