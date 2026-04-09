# T-Vault Setup — Scope

## What it does

Establishes the vault singleton and defines the pluggable `UnsealBackend`
interface that every mode (manual, kms_azure, kms_aws, kms_gcp) implements.
Owns the `10_fct_vault` row, the `01_dim_vault_statuses` and
`02_dim_unseal_modes` dim tables, and the four lifecycle API endpoints.

Implements **one** concrete backend in this sub-feature: `manual`. The cloud
KMS backends live in their own sub-features (`02_kms_azure`, `03_kms_aws`,
`04_kms_gcp`) and plug into the same interface.

## The UnsealBackend interface

Every unseal backend implements the same Python protocol:

```python
class UnsealBackend(Protocol):
    code: str  # "manual" | "kms_azure" | "kms_aws" | "kms_gcp"

    async def init(self, config: dict) -> InitResult:
        """Initialize the vault under this backend.

        Returns the MDK (plaintext, in memory) plus whatever must be persisted
        to 10_fct_vault. Called exactly once, by the install wizard.
        """

    async def unseal(self, vault_row: dict, user_input: str | None) -> bytes:
        """Return the MDK as plaintext bytes.

        `user_input` is the Root Unseal Key in manual mode, unused in KMS modes.
        Called on every process boot (after the first).
        Raises VaultSealedError if unsealing fails.
        """

    def auto_unseal(self) -> bool:
        """True if this backend can unseal without user input (all KMS modes).
        False for manual mode. Drives startup behaviour: True → unseal on boot,
        False → start in sealed HTTP mode and wait for POST /v1/vault/unseal.
        """
```

The `01_setup` sub-feature defines the protocol and implements only the
`ManualUnsealBackend` class. Adding a cloud KMS backend means adding a new
class that implements the same protocol — no changes to this sub-feature's
code or schema.

## In scope

- `POST /v1/vault/init` — not exposed over HTTP in v1. Init happens only during
  the `00_setup` install wizard, which calls the service layer directly.
  The HTTP route is reserved for future re-init flows and returns 405 in v1.
- `POST /v1/vault/unseal` — manual mode only. Accepts the Root Unseal Key,
  decrypts the MDK, transitions the vault to `unsealed`. In KMS modes this
  endpoint returns 409 `AUTO_UNSEAL_ACTIVE` because the vault auto-unseals on
  boot.
- `POST /v1/vault/seal` — clears the MDK from memory, transitions to `sealed`.
  Works in all modes. KMS modes will re-auto-unseal on the next process boot;
  manual mode will wait for another `POST /v1/vault/unseal`.
- `GET /v1/vault/status` — returns `{ status, unseal_mode, auto_unseal }`.
  Never returns key material.
- Create `01_dim_vault_statuses` dim (sealed, unsealed) — seeded at migration
  time.
- Create `02_dim_unseal_modes` dim (manual, kms_azure, kms_aws, kms_gcp) —
  seeded at migration time.
- Create `10_fct_vault` singleton fact table with pluggable key-material
  columns (see migration SQL for the per-mode CHECK constraint).
- Create `v_vault` read view that exposes status + unseal mode but no key
  material.
- Implement `ManualUnsealBackend`: Root Unseal Key (64 hex chars) + Root Read
  Key (64 hex chars), AES-256-GCM envelope encryption of the MDK, BLAKE2b
  hash of both root keys for verification.
- Boot-time dispatch: on every process start, read `10_fct_vault.unseal_mode_id`,
  look up the backend class, call `auto_unseal()` — if True, call `unseal()`
  automatically; if False, enter sealed HTTP mode.

## Out of scope

- The Azure Key Vault backend — that is `02_kms_azure`
- The AWS KMS backend — that is `03_kms_aws` (PLANNED)
- The GCP KMS backend — that is `04_kms_gcp` (PLANNED)
- Multi-key unseal (Shamir's Secret Sharing) — not in phase 1
- Root key rotation — future enhancement
- WebUI for unseal — future
- Any project, environment, or secret management
- IAM/RBAC integration — v1 uses a simple operator session; RBAC is future

## Acceptance criteria

### Interface

- [ ] `UnsealBackend` protocol defined with `init`, `unseal`, `auto_unseal`
- [ ] `ManualUnsealBackend` class implements the protocol
- [ ] Backend dispatch on boot reads `10_fct_vault.unseal_mode_id` and
      instantiates the right class

### Manual mode behaviour

- [ ] Install wizard calls `ManualUnsealBackend.init()` with two operator-
      provided 64-hex-char keys; MDK generated and persisted with AES-256-GCM
- [ ] Install wizard rejects keys that are not exactly 64 lowercase hex chars
- [ ] Install wizard rejects the call if `unseal_key == read_key`
- [ ] On process boot in manual mode, HTTP server starts in sealed mode;
      only `/v1/vault/status`, `/v1/vault/unseal`, `/v1/vault/seal`, and
      `/healthz` respond
- [ ] `POST /v1/vault/unseal` with the correct key transitions to unsealed
      and all other endpoints become responsive
- [ ] `POST /v1/vault/unseal` with wrong key returns 403 `WRONG_UNSEAL_KEY`
- [ ] `POST /v1/vault/seal` clears the MDK and transitions back to sealed
- [ ] Re-calling `POST /v1/vault/unseal` when already unsealed returns 409

### KMS mode behaviour (verified via test doubles)

- [ ] With a fake `auto_unseal() = True` backend, the HTTP server starts
      fully operational (not sealed) after `unseal()` runs at boot
- [ ] `POST /v1/vault/unseal` in a KMS mode returns 409 `AUTO_UNSEAL_ACTIVE`
- [ ] `POST /v1/vault/seal` in a KMS mode succeeds; subsequent process boot
      re-auto-unseals without operator action

### Status and DB

- [ ] `GET /v1/vault/status` returns `{ status, unseal_mode, auto_unseal,
      initialized_at }` and never leaks ciphertext or hashes
- [ ] `v_vault` view excludes all key material columns
- [ ] Migration round-trips: UP → DOWN → UP cleanly
- [ ] `10_fct_vault` CHECK constraint rejects any row where manual-mode columns
      and KMS-mode columns are both populated or both NULL after init

## Dependencies

- Depends on: `00_bootstrap` (schema and EAV tables must exist)
- Depended on by: `02_kms_azure`, `03_kms_aws`, `04_kms_gcp` (all implement
  the `UnsealBackend` protocol defined here), and all later secret-management
  sub-features (must be unsealed before any secret ops)
