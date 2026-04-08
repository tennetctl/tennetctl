# T-Vault — Architecture

## Schema layout

All tables live in the `"02_vault"` Postgres schema.
No cross-schema foreign keys. Cross-module data flows via events (R-002).

```text
02_vault
├── 01_dim_vault_statuses          sealed | unsealed
├── 02_dim_unseal_modes            manual | kms_azure | kms_aws | kms_gcp
├── 03_dim_secret_types            env_var | config | raw
├── 04_dim_secret_statuses         active | archived | deleted
├── 05_dim_api_key_permissions     read | read_write
├── 06_dim_entity_types            vault | project | environment | secret | api_key
├── 07_dim_attr_defs               EAV attribute registry
├── 08_dim_api_key_statuses        active | revoked
├── 10_fct_vault                   Singleton — holds wrapped MDK + per-mode key material
├── 11_fct_projects                Project identity (org_id, status_id)
├── 12_fct_environments            Environment identity (project_id, status_id)
├── 13_fct_secrets                 Secret identity (project_id, env_id, type_id, status_id)
├── 14_fct_secret_versions         Immutable version rows per secret mutation
├── 15_fct_api_keys                API key identity (project_id, env_id, permission_id, status_id)
├── 20_dtl_attrs                   EAV attribute values (all entities)
├── 30_adm_vault_config            Operator config (rotation intervals, key algo params)
└── 60_evt_vault_access            Append-only access log (every read + write)
```

Views (read layer):

```
v_vault            → singleton vault status
v_projects         → projects with EAV attrs resolved
v_environments     → environments with project name
v_secrets          → secrets with current version value decrypted (in app, not SQL)
v_api_keys         → API keys (key material excluded — hash only)
```

---

## Envelope encryption

Every mode follows the same **DEK-per-secret + MDK-wraps-DEK** envelope
scheme. The only thing that changes between modes is **how the MDK itself is
protected at rest** and how it gets decrypted on boot.

### Manual mode

```text
Operator provides:
  Root Unseal Key   (SHA-256, 64 hex chars) — provided at init and each unseal
  Root Read Key     (SHA-256, 64 hex chars) — provided at init only; stored as hash

At init:
  1. Generate MDK (Master Data Key) — random 32 bytes
  2. Encrypt MDK with Root Unseal Key → mdk_ciphertext (AES-256-GCM + mdk_nonce)
  3. Hash Root Unseal Key with BLAKE2b → unseal_key_hash (for verification)
  4. Hash Root Read Key with BLAKE2b  → read_key_hash  (for verification)
  5. Store mdk_ciphertext, mdk_nonce, unseal_key_hash, read_key_hash
     in 10_fct_vault (unseal_mode_id = 1)
  6. Root Unseal Key and Root Read Key are discarded — never stored

At unseal:
  1. Operator provides Root Unseal Key via POST /v1/vault/unseal
  2. Verify: BLAKE2b(provided_key) == unseal_key_hash
  3. Decrypt mdk_ciphertext with provided key → MDK (held in memory only)
  4. status_id → unsealed
```

### Cloud KMS modes (kms_azure, kms_aws, kms_gcp)

```text
Operator provides at install time:
  KMS key reference (Azure: vault URL + key name; AWS: KMS ARN; GCP: resource name)
  — the trust anchor for the MDK. No cryptographic material on disk.

At init:
  1. Generate MDK (Master Data Key) — random 32 bytes
  2. Call backend.wrap(mdk) — the cloud KMS wraps the MDK with its own key,
     returns wrapped_mdk (opaque ciphertext, base64url-encoded)
  3. Store wrapped_mdk + unseal_config (JSONB with KMS reference)
     in 10_fct_vault (unseal_mode_id = 2/3/4)

At unseal (automatic, every process boot):
  1. Pod authenticates to the cloud KMS via workload identity
     (AKS Workload Identity / EKS IRSA / GKE Workload Identity)
  2. Call backend.unwrap(wrapped_mdk) — cloud KMS decrypts, returns plaintext MDK
  3. Hold MDK in memory for the lifetime of the process
  4. status_id → unsealed
  No human involvement. No key material on disk. No key material in K8s Secrets.
```

### Per-secret operations (identical across all modes)

```text
Per secret write:
  1. Generate DEK (Data Encryption Key) — random 32 bytes
  2. Encrypt secret value with DEK → value_ciphertext (AES-256-GCM)
  3. Encrypt DEK with MDK → dek_ciphertext (AES-256-GCM)
  4. Store value_ciphertext + dek_ciphertext in 14_fct_secret_versions

Per secret read:
  1. Load dek_ciphertext from 14_fct_secret_versions
  2. Decrypt DEK with MDK (in-memory)
  3. Decrypt value_ciphertext with DEK → plaintext
  4. Return plaintext; never log or persist

At seal:
  1. Clear MDK from memory
  2. status_id → sealed
  3. All subsequent secret reads return 503 VAULT_SEALED
  4. Next process boot: manual → waits for operator; KMS → auto-unseals
```

Nothing plaintext ever touches the database. If the database is stolen:

- **manual mode**: `mdk_ciphertext` is unreadable without the Root Unseal Key,
  which lives only in the operator's head / hardware token.
- **KMS modes**: `wrapped_mdk` is unreadable without the cloud KMS key, which
  is protected by IAM policy — the attacker needs both DB access *and*
  compromise of the cloud IAM layer, which is a much higher bar than DB-only.

---

## Service boundaries

```text
01_setup       ──owns──▶  10_fct_vault  (+ UnsealBackend protocol)
02_kms_azure   ──plugs──▶ UnsealBackend  (Azure Key Vault implementation)
03_kms_aws     ──plugs──▶ UnsealBackend  (AWS KMS, PLANNED)
04_kms_gcp     ──plugs──▶ UnsealBackend  (GCP KMS, PLANNED)
05_project     ──owns──▶  11_fct_projects
06_environment ──owns──▶  12_fct_environments  (depends on 11_fct_projects)
07_secret      ──owns──▶  13_fct_secrets
                           14_fct_secret_versions
08_api_key     ──owns──▶  15_fct_api_keys
```

All sub-features share `20_dtl_attrs` (owned by `00_bootstrap`). The three
KMS sub-features add zero new schema — they register themselves into the
`UNSEAL_BACKENDS` registry defined in `01_setup` and store their per-backend
metadata in the `unseal_config` JSONB column of `10_fct_vault`.

---

## Events emitted

All events are published to NATS JetStream subject `vault.*`.

| Subject                | Emitted by  | Consumed by |
| ---------------------- | ----------- | ----------- |
| `vault.initialized`    | 01_setup    | audit       |
| `vault.unsealed`       | 01_setup    | audit       |
| `vault.sealed`         | 01_setup    | audit       |
| `vault.secret.created` | 07_secret   | audit       |
| `vault.secret.accessed`| 07_secret   | audit       |
| `vault.secret.rotated` | 07_secret   | audit       |
| `vault.secret.deleted` | 07_secret   | audit       |
| `vault.api_key.created`| 08_api_key  | audit       |
| `vault.api_key.revoked`| 08_api_key  | audit       |

---

## Key invariants

1. `10_fct_vault` always has exactly one row after init.
2. MDK plaintext never exists in the database — only `mdk_ciphertext`.
3. Secret plaintext never exists in the database — only `value_ciphertext`.
4. The vault must be in `unsealed` status for any secret read or write. Otherwise return `503 VAULT_SEALED`.
5. Every secret mutation creates a new row in `14_fct_secret_versions` — existing versions are never mutated.
6. API keys are stored as BLAKE2b hashes only. Raw key shown exactly once at creation.

---

## Security properties

| Threat                    | Mitigation                                                                                                       |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| DB stolen at rest         | MDK + DEKs are ciphertext. Manual: needs Root Unseal Key. KMS: needs cloud IAM compromise.                       |
| Process memory dump       | MDK held in process memory only while unsealed. Cleared on seal or process exit.                                 |
| Pod compromise (RCE)      | Attacker gets MDK in memory. Manual: scoped to pod lifetime. KMS: scoped across restarts (accepted).             |
| SQL injection             | asyncpg parameterized queries; write role has no DDL.                                                            |
| Brute force on key hashes | BLAKE2b hashes are not reversible; keys are 256-bit.                                                             |
| Unauthorized API access   | All endpoints require a scoped API key or admin session.                                                         |
| Cross-tenant data leak    | org_id on all entity tables; RLS enforced at DB level.                                                           |
| Lost Root Unseal Key      | Manual mode: unrecoverable — secrets lost forever. KMS mode: tied to cloud KMS key lifecycle.                    |
| Cloud KMS key deleted     | KMS modes: vault becomes permanently sealed. Use cloud KMS's own deletion protections (scheduled deletion, IAM). |
