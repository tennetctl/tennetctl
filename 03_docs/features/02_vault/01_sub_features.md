# T-Vault — Sub-Features

Build order is strict. Each sub-feature depends on the ones before it.
Do not start a sub-feature until the previous one is merged.

## Tier 0: Foundation

### 00_bootstrap

Creates the `02_vault` Postgres schema and the three shared EAV tables
(`06_dim_entity_types`, `07_dim_attr_defs`, `20_dtl_attrs`) that every other
vault sub-feature depends on. No API, no backend code — schema only.

### 01_setup

Vault singleton, init/unseal/seal lifecycle, and the pluggable
`UnsealBackend` interface. Owns `10_fct_vault`, `01_dim_vault_statuses`,
`02_dim_unseal_modes`, and the three HTTP endpoints
(`/v1/vault/unseal`, `/v1/vault/seal`, `/v1/vault/status`).

Ships exactly one concrete backend implementation: `ManualUnsealBackend`,
where the operator provides a 64-hex-char Root Unseal Key on every boot.
This is the mode used for local dev, the install ceremony, and single-VM
deployments. Cloud backends plug into the same interface via their own
sub-features below.

## Tier 1: Unseal backends (plug into 01_setup's interface)

Every backend in this tier implements the `UnsealBackend` protocol defined
in `01_setup`. They add zero new schema — the per-backend metadata lives
in `10_fct_vault.unseal_config` (JSONB-as-text) which was created in `01_setup`.

### 02_kms_azure — BUILDING in v1

Azure Key Vault auto-unseal. The MDK is wrapped with an Azure Key Vault
wrapping key. Pods authenticate via Workload Identity on AKS (production)
or DefaultAzureCredential (local/CI). On boot the pod calls the Key Vault
`unwrapKey` operation and auto-unseals with zero human interaction. This is
the first K8s-native unseal backend and the one the install wizard steers
operators toward for cloud deployments.

### 03_kms_aws — PLANNED

AWS KMS auto-unseal via IRSA (EKS workload identity). Same shape as
`02_kms_azure`: wrap the MDK with a KMS key at install time, call `Decrypt`
on every boot. Will be built once tennetctl is deployed on EKS.

### 04_kms_gcp — PLANNED

GCP Cloud KMS auto-unseal via Workload Identity (GKE). Same shape again.
Will be built once tennetctl is deployed on GKE.

## Tier 2: Organisation

### 05_project

Vault projects group secrets by application or service. A project is the
top-level container — every secret belongs to a project. CRUD only; no
encryption at this tier. The `v_projects` view resolves status and materialises
EAV attributes (name, slug, description).

### 06_environment

Per-project environments: `development`, `staging`, `production`. An
environment scopes secrets so the same key (e.g. `DATABASE_URL`) can hold
different values in dev vs prod. CRUD only.

## Tier 3: Secrets

### 07_secret

Encrypted secret storage. Every secret is a key-value pair (e.g.
`DATABASE_URL = postgres://...`). The value is encrypted with a unique Data
Encryption Key (DEK), which is itself encrypted by the vault's Master Data Key
(MDK). Supports three secret types: `env_var`, `config`, `raw`. Includes
versioning — every update creates a new version; previous versions remain
readable until explicitly deleted.

### 08_api_key

Scoped API keys for programmatic secret access. Each API key is bound to a
project and optionally an environment. Permissions: `read` or `read_write`.
Keys are hashed at rest (BLAKE2b). The raw key is shown exactly once on
creation.
