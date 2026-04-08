## Vault Init — Design

## File layout

```text
scripts/setup/vault_init/
├── __init__.py
├── entrypoint.py        — run_vault_init(opts, state) — only public fn
├── mode_prompts.py      — unseal-mode menu + per-mode config prompts
├── manual_config.py     — ManualUnsealConfig collection + validation
├── azure_config.py      — AzureKmsConfig collection + self-test
├── seeding.py           — DSN seeding via vault_secret_service
└── tests/
    ├── test_manual_config.py
    ├── test_azure_config.py
    ├── test_seeding.py
    └── test_idempotency.py
```

## Entrypoint

```python
# scripts/setup/vault_init/entrypoint.py

async def run_vault_init(opts: SetupOptions, state: InstallState) -> None:
    """Phase 2: init the vault and seed the three DB DSNs.

    Runs the entire phase inside a single admin Postgres connection so
    that the vault row write, the three secret writes, and the
    system_meta update all commit atomically. If any step fails, nothing
    is persisted.
    """

    async with asyncpg.connect(state.admin_dsn) as conn:
        await _preflight_check(conn)    # abort if vault already initialized

        state.unseal_mode = await mode_prompts.resolve_unseal_mode(opts)

        if state.unseal_mode == "manual":
            raw_config = await manual_config.collect(opts)
        elif state.unseal_mode == "kms_azure":
            raw_config = await azure_config.collect(opts)
            await azure_config.run_self_test(raw_config)
        else:
            raise Phase2Error(
                f"Unseal mode '{state.unseal_mode}' is not available in v1"
            )

        async with conn.transaction():
            # 1. Init vault — returns MDK in memory
            result = await vault_setup_service.init_vault(
                conn=conn,
                mode=state.unseal_mode,
                config=raw_config,
            )
            mdk: bytes = result["mdk"]

            try:
                # 2. Seed the three DSNs using the runtime secret service
                vault_state = VaultState(mdk=mdk)
                await seeding.seed_db_dsns(conn, vault_state, state)

                # 3. Update system_meta atomically with the vault row
                await conn.execute(
                    '''UPDATE "00_schema_migrations".system_meta
                       SET vault_initialized_at = $1,
                           unseal_mode          = $2,
                           updated_at           = CURRENT_TIMESTAMP
                       WHERE id = 1''',
                    result["initialized_at"],
                    state.unseal_mode,
                )
            finally:
                # Clear MDK from memory even if the transaction aborts
                vault_state.mdk = None
                mdk = b"\x00" * 32  # best-effort overwrite before GC
                del mdk

    # After the `async with conn.transaction()` commits:
    state.vault_initialized_at = result["initialized_at"]
    state.admin_dsn = None         # no longer needed — in the vault
    state.read_dsn  = None         # no longer needed — in the vault
    # state.write_dsn survives into Phase 4 for the one-time operator print-out
```

## Preflight check

```python
async def _preflight_check(conn) -> None:
    """Abort Phase 2 if the vault is already initialized.

    Three possible states:
      A. No row in 10_fct_vault  → proceed normally
      B. Row exists, initialized_at IS NOT NULL, all three DSN secrets
         exist in 14_fct_secret_versions → Phase 2 is already complete,
         skip via phase detection (should not have been called)
      C. Row exists, initialized_at IS NOT NULL, DSN secrets missing →
         partial state; refuse to continue
    """
    row = await conn.fetchrow(
        'SELECT initialized_at FROM "02_vault"."10_fct_vault"'
    )
    if row is None:
        return  # State A — proceed

    if row["initialized_at"] is None:
        # Row exists but init never finished — rare but possible if
        # init_vault crashed after INSERT but before the row was filled
        raise Phase2Error(
            "Vault row exists with initialized_at=NULL — partial init "
            "detected. Drop the row manually and re-run Phase 2."
        )

    # Vault claims to be initialized — verify DSNs exist
    dsn_count = await conn.fetchval('''
        SELECT COUNT(*)
        FROM "02_vault".v_secrets
        WHERE path IN ('tennetctl/db/admin_dsn',
                       'tennetctl/db/write_dsn',
                       'tennetctl/db/read_dsn')
    ''')

    if dsn_count == 3:
        # State B — already complete, should have been filtered out
        # by phase detection. Defensive abort.
        raise Phase2Error(
            "Phase 2 is already complete. If you need to re-seed DSNs, "
            "drop them from 13_fct_secrets manually first."
        )

    # State C
    raise Phase2Error(
        f"Vault is initialized but only {dsn_count}/3 DSN secrets are "
        "seeded. The install is in an inconsistent state — drop the "
        "vault row and all vault secrets, then re-run Phase 2."
    )
```

## Mode prompts

```python
# scripts/setup/vault_init/mode_prompts.py

MODE_OPTIONS = [
    ("manual",    "Manual unseal (operator pastes key on every boot)", True),
    ("kms_azure", "Azure Key Vault auto-unseal",                        True),
    ("kms_aws",   "AWS KMS auto-unseal — PLANNED",                      False),
    ("kms_gcp",   "GCP KMS auto-unseal — PLANNED",                      False),
]

async def resolve_unseal_mode(opts: SetupOptions) -> str:
    if opts.unseal_mode is not None:
        _assert_mode_available(opts.unseal_mode)
        return opts.unseal_mode

    # Interactive menu
    for i, (code, label, enabled) in enumerate(MODE_OPTIONS, start=1):
        marker = " " if enabled else "*"
        print(f"  {i}){marker} {label}")

    while True:
        choice = Prompt.ask("Select [1-4]")
        try:
            idx = int(choice) - 1
            code, _, enabled = MODE_OPTIONS[idx]
        except (ValueError, IndexError):
            continue
        if not enabled:
            print("  That mode is not available in v1. Pick 1 or 2.")
            continue
        return code

def _assert_mode_available(code: str) -> None:
    for c, _, enabled in MODE_OPTIONS:
        if c == code:
            if not enabled:
                raise Phase2Error(
                    f"Unseal mode '{code}' is PLANNED and not available in v1"
                )
            return
    raise Phase2Error(f"Unknown unseal mode: {code}")
```

## Manual config collection

```python
# scripts/setup/vault_init/manual_config.py

import re

HEX_64 = re.compile(r"^[0-9a-f]{64}$")

async def collect(opts: SetupOptions) -> dict:
    unseal_key = resolve(
        opts.root_unseal_key,
        "TENNETCTL_SETUP_ROOT_UNSEAL_KEY",
        "Root Unseal Key (64 hex chars)",
        secret=True,
        validator=_validate_hex,
    )

    # Confirmation prompt only if interactive (flag already implies
    # the operator has the key somewhere scripted)
    if opts.root_unseal_key is None and sys.stdin.isatty():
        again = Prompt.ask("Confirm Root Unseal Key", password=True)
        if again != unseal_key:
            raise Phase2Error("Root Unseal Key confirmation did not match")

    read_key = resolve(
        opts.root_read_key,
        "TENNETCTL_SETUP_ROOT_READ_KEY",
        "Root Read Key (64 hex chars)",
        secret=True,
        validator=_validate_hex,
    )

    if opts.root_read_key is None and sys.stdin.isatty():
        again = Prompt.ask("Confirm Root Read Key", password=True)
        if again != read_key:
            raise Phase2Error("Root Read Key confirmation did not match")

    if unseal_key == read_key:
        raise Phase2Error("Root Unseal Key and Root Read Key must differ")

    return {"unseal_key": unseal_key, "read_key": read_key}

def _validate_hex(v: str) -> str:
    v = v.strip().lower()
    if not HEX_64.match(v):
        raise ValueError("must be exactly 64 lowercase hex characters")
    return v
```

## Azure config + self-test

```python
# scripts/setup/vault_init/azure_config.py

import os
from urllib.parse import urlparse

async def collect(opts: SetupOptions) -> dict:
    vault_url = resolve(
        opts.azure_vault_url,
        "TENNETCTL_SETUP_AZURE_VAULT_URL",
        "Azure Key Vault URL",
        validator=_validate_vault_url,
    )
    key_name = resolve(
        opts.azure_key_name,
        "TENNETCTL_SETUP_AZURE_KEY_NAME",
        "Wrapping key name",
        validator=_validate_key_name,
    )
    key_version = resolve(
        opts.azure_key_version,
        "TENNETCTL_SETUP_AZURE_KEY_VERSION",
        "Wrapping key version (pinned)",
        validator=_validate_key_version,
    )
    return {
        "vault_url":   vault_url,
        "key_name":    key_name,
        "key_version": key_version,
    }

def _validate_vault_url(v: str) -> str:
    parsed = urlparse(v)
    if parsed.scheme != "https":
        raise ValueError("must be https://")
    if not parsed.hostname or not parsed.hostname.endswith(".vault.azure.net"):
        raise ValueError("must end with .vault.azure.net")
    return v if v.endswith("/") else v + "/"

def _validate_key_name(v: str) -> str:
    import re
    if not re.match(r"^[A-Za-z0-9-]{1,127}$", v):
        raise ValueError("must match ^[A-Za-z0-9-]{1,127}$")
    return v

def _validate_key_version(v: str) -> str:
    v = v.strip()
    if v == "" or v.lower() == "latest":
        raise ValueError(
            "'latest' is not accepted — pin a concrete version id"
        )
    if len(v) < 32:
        raise ValueError("key version id must be at least 32 characters")
    return v

async def run_self_test(raw_config: dict) -> None:
    """Wrap + unwrap a random 32-byte payload via the Azure KMS backend
    to prove the operator's config actually works. Runs BEFORE any
    vault row is written, so a failure leaves zero persisted state."""

    from backend.02_features.vault.kms_azure.backend import (
        AzureKeyVaultUnsealBackend,
    )

    backend = AzureKeyVaultUnsealBackend()
    test_payload = os.urandom(32)

    try:
        wrap_result = await backend._wrap_for_self_test(
            config=raw_config, payload=test_payload,
        )
        unwrapped = await backend._unwrap_for_self_test(
            config=raw_config, wrapped=wrap_result,
        )
    except AzureKmsError as e:
        raise Phase2Error(
            f"Azure KMS self-test failed: {e}\n"
            f"See 02_vault/05_sub_features/02_kms_azure/02_design.md "
            f"for the runbook."
        ) from e

    if unwrapped != test_payload:
        raise Phase2Error(
            "Azure KMS self-test: wrap/unwrap did not round-trip. "
            "Your key may be corrupt or the wrong algorithm is configured."
        )
```

## DSN seeding

```python
# scripts/setup/vault_init/seeding.py

async def seed_db_dsns(
    conn,
    vault_state: VaultState,
    state: InstallState,
) -> None:
    """Write the three DSNs into the vault as secret_type='raw'.

    Uses vault_secret_service.create_secret — the SAME function the
    runtime /v1/secrets endpoint uses. No special install-time writer.
    """
    from backend.02_features.vault.secret import service as vault_secret_service

    await vault_secret_service.create_secret(
        conn=conn, vault_state=vault_state,
        path="tennetctl/db/admin_dsn",
        value=state.admin_dsn,
        secret_type="raw",
        actor_id=SYSTEM_INSTALLER_ACTOR_ID,
    )
    await vault_secret_service.create_secret(
        conn=conn, vault_state=vault_state,
        path="tennetctl/db/write_dsn",
        value=state.write_dsn,
        secret_type="raw",
        actor_id=SYSTEM_INSTALLER_ACTOR_ID,
    )
    await vault_secret_service.create_secret(
        conn=conn, vault_state=vault_state,
        path="tennetctl/db/read_dsn",
        value=state.read_dsn,
        secret_type="raw",
        actor_id=SYSTEM_INSTALLER_ACTOR_ID,
    )
```

`SYSTEM_INSTALLER_ACTOR_ID` is a well-known zero UUID constant
(`00000000-0000-0000-0000-000000000000`) reserved for install-time
writes. The audit log uses it to distinguish install-time seeding
from any subsequent operator action. The first admin row created
in Phase 3 takes over as the actor for all subsequent writes.

## Testing strategy

- **Unit tests** for validators (`_validate_hex`, `_validate_vault_url`,
  `_validate_key_name`, `_validate_key_version`) that assert the
  error messages and that good inputs round-trip unchanged.
- **Unit tests** for `manual_config.collect` using a fake `Prompt`
  that parametrises match/mismatch on the confirmation prompt and
  equal/unequal root keys.
- **Unit tests** for `resolve_unseal_mode` that assert selecting a
  disabled mode via flag raises, selecting a disabled mode in
  interactive mode loops back to the prompt, and selecting an
  enabled mode returns the right code.
- **Integration tests** for the full Phase 2 run against a disposable
  Postgres that has Phase 1 already applied, using the fake
  `AzureKeyVaultUnsealBackend` test double (selected via the env var
  `TENNETCTL_UNSEAL_BACKEND_FAKE=1`) to avoid hitting real Azure.
  Asserts that:
    - `10_fct_vault` row exists with the right per-mode columns
    - `13_fct_secrets` contains exactly three rows at the expected paths
    - round-tripping each secret yields the exact DSN strings passed in
    - `system_meta.vault_initialized_at` and `system_meta.unseal_mode`
      are set in the same transaction
- **Idempotency tests** that run Phase 2, kill the process between
  the vault row write and the DSN seeding (via a test hook that
  raises mid-transaction), and assert that:
    - the partial vault row was rolled back (transaction aborted)
    - re-running the wizard picks up cleanly in the same phase
- **Self-test failure tests** for Azure mode that inject a fake
  backend which returns a corrupted unwrap and assert that Phase 2
  aborts BEFORE any vault row is written.

## Security notes

- The MDK lives in process memory only for the duration of the Phase 2
  transaction. The `finally` block clears both `VaultState.mdk` and
  the local `mdk` variable before the function returns. Python does
  not zeroise memory deterministically, but dropping references lets
  the GC reclaim the buffer at the next collection.
- The three DSNs are encrypted per-secret via the normal DEK-per-secret
  envelope pattern (see `02_vault/04_architecture/01_architecture.md`).
  The wizard never writes them anywhere else — not to logs, not to
  audit output, not to Phase 2 return values.
- Azure KMS mode does a full wrap/unwrap round-trip **before** writing
  any vault state. A self-test failure leaves zero persisted state,
  so the operator can fix their Azure config and re-run without any
  cleanup.
- The `SYSTEM_INSTALLER_ACTOR_ID` is recorded on the three DSN secret
  rows so that the audit log shows which user (or the installer)
  wrote each secret. No operator identity is known at install time,
  which is why the installer uses a well-known zero UUID rather than
  impersonating the first admin (who doesn't exist yet).
- The self-test's random test payload is discarded in `finally`. It
  never touches the DB or any persistent store.
