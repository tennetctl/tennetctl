## Vault Init — Scope

## What it does

Phase 2 of the install wizard. Initializes the vault singleton, wraps the
Master Data Key with the operator's chosen unseal backend, and seeds the
three DB DSNs held in wizard memory into the vault as the very first
secrets. At the end of Phase 2 the vault row exists with `status = sealed`
and `vault_initialized_at = now()`, and the vault contains the three
DSNs the runtime will need on every subsequent boot.

This is the phase that resolves the install chicken-and-egg: the wizard
holds the DSNs in memory, writes them into the vault, and then can safely
forget them because the next boot will read them back out via the vault.

## Unseal mode prompt

```text
How will the vault unseal itself on pod restart?

  1) manual      — I will paste the Root Unseal Key on every boot.
                   Good for local dev and single-VM deployments.

  2) kms_azure   — Pods auto-unseal via Azure Key Vault.
                   Requires: AKS + Workload Identity + a KV wrapping key.

  3) kms_aws     — PLANNED (not available in v1)
  4) kms_gcp     — PLANNED (not available in v1)

Select [1/2]:
```

Options 3 and 4 print "PLANNED — not available in v1" and refuse
selection. The wizard will not let the operator pick an unseal mode
whose backend is not yet implemented.

## Mode-specific config capture

### Manual mode

Prompts:

```text
Root Unseal Key — 64 hex chars (this is what you'll paste on every boot):
Root Read Key   — 64 hex chars (held as hash only, used for future ops):
```

Validation:

- Each key must match `^[0-9a-f]{64}$` (lowercase hex, exactly 64 chars)
- The two keys must not be equal
- Both must be confirmed with a second paste to catch typos

The wizard does **not** generate the keys for the operator by default —
keys must come from outside (`openssl rand -hex 32`, hardware token, or
similar). This is intentional: wizard-generated keys the operator hasn't
stored independently are the number one way manual mode becomes an
unrecoverable vault.

**Exception: `--generate-keys` flag.** When this flag is passed, the
wizard generates both keys with `secrets.token_bytes(32)`, displays them
once in the terminal, and demands the operator confirm they have been
written down before continuing. The keys are never written to disk by
the wizard — only the hashes are persisted. Use this flag only in
environments where generating keys externally is not practical (local dev,
CI bootstrap). Do not use it in production without a documented key
backup procedure.

### Azure KMS mode

Prompts:

```text
Azure Key Vault URL  (e.g. https://kv-tennetctl.vault.azure.net/):
Wrapping key name    (the key in Key Vault to wrap our MDK):
Wrapping key version (pinned version id — 'latest' is not accepted):
```

Validation:

- `vault_url` is a valid HTTPS URL ending with `.vault.azure.net/`
- `key_name` matches `^[A-Za-z0-9-]{1,127}$`
- `key_version` is at least 32 characters (Azure KV key version ids are
  32-char hex)
- Before persisting anything, the wizard runs the self-test described
  in `02_vault/05_sub_features/02_kms_azure/02_design.md#install-time-validation`
  (wrap a random 32-byte payload and unwrap it) to prove the operator's
  Azure config actually works

Any Azure error — auth, permission, key not found, network — is caught
and re-raised as `Phase2Error` with a link to the Azure runbook section.

## Vault init call

The wizard calls the vault service layer **directly**, not via HTTP:

```python
# Not HTTP — direct Python import
from backend.02_features.vault.setup import service as vault_setup_service

result = await vault_setup_service.init_vault(
    conn    = admin_conn,        # asyncpg connection as tennetctl_admin
    mode    = state.unseal_mode,
    config  = mode_specific_config,
)
# result = { "status": "sealed", "unseal_mode": ..., "initialized_at": ..., "mdk": <bytes> }
```

This is the only place in the entire codebase where `init_vault` is
callable — the `POST /v1/vault/init` HTTP endpoint is deliberately
reserved (returns 405 in v1). The wizard has an admin Postgres
connection and the MDK in memory, both of which are exactly what
`init_vault` needs.

## DSN seeding

Once the MDK is in memory, Phase 2 opens a short-lived
`VaultState(mdk=...)` and calls the runtime `vault_secret_service` —
the **same** code path the runtime uses to create a secret — to seed
the three DSNs:

```python
from backend.02_features.vault.secret import service as vault_secret_service

vault_state = VaultState(mdk=result["mdk"])

await vault_secret_service.create_secret(
    conn        = admin_conn,
    vault_state = vault_state,
    path        = "tennetctl/db/admin_dsn",
    value       = state.admin_dsn,
    secret_type = "raw",
)
await vault_secret_service.create_secret(
    conn        = admin_conn,
    vault_state = vault_state,
    path        = "tennetctl/db/write_dsn",
    value       = state.write_dsn,
    secret_type = "raw",
)
await vault_secret_service.create_secret(
    conn        = admin_conn,
    vault_state = vault_state,
    path        = "tennetctl/db/read_dsn",
    value       = state.read_dsn,
    secret_type = "raw",
)
```

After the three writes succeed:

1. The MDK is cleared from `vault_state` (and from the wizard's local
   variable).
2. `state.admin_dsn` / `state.read_dsn` are cleared — only `state.write_dsn`
   survives into Phase 4 where it is printed once for the operator to
   capture before being zeroed.
3. `system_meta.vault_initialized_at` is updated to `now()` and
   `system_meta.unseal_mode` is set to the mode code.

## In scope

- Unseal mode prompt with the full option menu (manual + kms_azure
  enabled; kms_aws + kms_gcp shown but disabled)
- Per-mode config capture with validation
- Calling `vault_setup_service.init_vault` via direct Python import
- For KMS modes: running the backend's install-time self-test before
  persisting any state
- Creating a transient `VaultState` with the freshly-generated MDK
- Seeding the three DB DSNs via the same `vault_secret_service` the
  runtime uses — no special-case writer
- Clearing the MDK and the admin/read DSNs from memory after seeding
- Updating `system_meta.vault_initialized_at` and `system_meta.unseal_mode`
  in the same transaction as the DSN writes
- Seeding the JWT signing key into Vault at `iam/jwt_signing_key` (256-bit
  random, generated by the wizard — this is not a key the operator supplies)
- `--generate-keys` flag for manual mode: wizard generates both root keys,
  displays them once, and requires the operator to confirm before continuing
- Phase idempotency: if the vault row exists but the DSNs are not
  seeded yet, Phase 2 resumes at the seeding step without regenerating
  the MDK

## Out of scope

- Generating root keys for manual mode without `--generate-keys`
  (operator's responsibility by default)
- Creating Azure Key Vault resources, granting RBAC, configuring
  AKS Workload Identity (those are Terraform / `az cli` steps; the
  wizard only consumes an already-configured Key Vault)
- Rotating the unseal backend after install (future "rotate unseal"
  ceremony)
- Rotating the MDK (future)
- Exposing the MDK to anything outside `VaultState`
- Seeding any secrets other than the three DB DSNs (later features
  add their own bootstrap secrets as they land)

## Acceptance criteria

### Unseal mode selection

- [ ] Mode prompt lists all four options with "PLANNED" markers on
      kms_aws and kms_gcp
- [ ] Selecting kms_aws or kms_gcp re-prompts with an explicit
      "not available in v1" message
- [ ] Selecting manual or kms_azure proceeds to mode-specific config
- [ ] `--unseal-mode` flag bypasses the prompt
- [ ] `--unseal-mode kms_aws` or `kms_gcp` exits non-zero with the
      "not available" message

### Manual mode

- [ ] Both root keys are prompted with echo suppressed
- [ ] Keys are validated against `^[0-9a-f]{64}$`
- [ ] Equal keys are rejected with "root keys must not be identical"
- [ ] Each key is prompted twice and the two entries must match
- [ ] `--root-unseal-key` / `--root-read-key` flags bypass the prompts
      but still run validation
- [ ] `--generate-keys` generates both keys with `secrets.token_bytes(32)`,
      displays them in the terminal, and requires the operator to type
      "I have saved these keys" before continuing
- [ ] `--generate-keys` and `--root-unseal-key` are mutually exclusive;
      passing both exits non-zero with a clear error

### Azure KMS mode

- [ ] All three Azure config values are prompted or flagged
- [ ] `vault_url` is validated as an HTTPS URL ending in `.vault.azure.net/`
- [ ] `key_version` is validated as ≥32 chars
- [ ] `key_version` equal to "latest" is rejected with an explicit
      "pin a concrete version" message
- [ ] Pre-init self-test wraps and unwraps a random payload and
      compares — any mismatch aborts without writing the vault row
- [ ] Azure auth/permission/network errors surface as specific
      `Phase2Error` subclasses with links to the runbook

### Vault init

- [ ] Phase 2 aborts if a vault row already exists with
      `initialized_at IS NOT NULL` — operator must resume explicitly
- [ ] On successful init, `10_fct_vault` has exactly one row with
      `status_id = sealed` and `unseal_mode_id` matching the selected
      mode
- [ ] For manual mode, `mdk_ciphertext`, `mdk_nonce`, `unseal_key_hash`,
      `read_key_hash` are populated and the four KMS columns are NULL
- [ ] For kms_azure mode, `wrapped_mdk` and `unseal_config` are populated
      and the four manual columns are NULL

### DSN seeding

- [ ] Three secrets exist at `tennetctl/db/admin_dsn`,
      `tennetctl/db/write_dsn`, `tennetctl/db/read_dsn`
- [ ] Each DSN round-trips: decrypting the secret yields the exact
      DSN the wizard held in memory
- [ ] After seeding, `state.admin_dsn` and `state.read_dsn` are `None`
- [ ] `state.write_dsn` is still populated (for Phase 4 DB settings write)
- [ ] A secret exists at `iam/jwt_signing_key` containing 256 random bytes
      (hex-encoded). Round-trip: decrypt yields the original bytes.
- [ ] The wizard's `VaultState.mdk` is `None` after seeding

### system_meta update

- [ ] `vault_initialized_at` matches the `10_fct_vault.initialized_at`
      column within the same transaction
- [ ] `unseal_mode` column contains the selected mode code

### Idempotency

- [ ] Re-running Phase 2 with a fully-initialized vault row and three
      seeded DSNs is a no-op (skips straight to Phase 3)
- [ ] Re-running Phase 2 with a vault row but missing DSN secrets
      aborts with "vault is initialized but DSNs are not seeded —
      drop the vault row manually and re-run"

## Dependencies

- Depends on: `02_vault.01_setup` (`init_vault` service function and
  `ManualUnsealBackend`)
- Depends on: `02_vault.02_kms_azure` (`AzureKeyVaultUnsealBackend`,
  only when unseal mode = kms_azure)
- Depends on: `02_vault.07_secret` (`vault_secret_service.create_secret`
  and the `13_fct_secrets` / `14_fct_secret_versions` tables)
- Depends on: `01_db_bootstrap` (three verified DSNs in `InstallState`)
- Depended on by: `03_first_admin` (admin row is the last write; Phase 3
  assumes the vault is sealed but seeded), `00_wizard` orchestration
