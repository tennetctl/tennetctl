# T-Vault — Encrypted Secrets Management

## What this feature does

T-Vault is tennetctl's built-in secrets manager. It stores secrets, environment
variables, and application configs in Postgres — encrypted at rest with
AES-256-GCM envelope encryption. There is no `.env` file anywhere in a
tennetctl deployment: every runtime secret the app needs — including the
three database DSNs (admin, write, read) that were generated at install time
— lives in the vault.

The vault is **sealed at rest**: the Master Data Key (MDK) that protects
every secret is not accessible without an external trust anchor. tennetctl
supports four pluggable unseal backends, one of which is picked at install
time and cannot change without re-encrypting the MDK.

## Why it exists

Every production system needs secrets: database passwords, API keys, signing
keys, certificates. Most teams scatter these across `.env` files, CI variables,
and cloud-vendor secret managers. T-Vault centralises them with encryption,
versioning, scoped access, and a full audit trail — with zero external
dependencies beyond Postgres and (optionally) a cloud KMS for auto-unseal.

## Pluggable unseal backends

| Mode | Trust anchor | Unseal ergonomics | Status |
| --- | --- | --- | --- |
| `manual` | Operator's head / hardware token | Paste Root Unseal Key on every boot | BUILDING (v1) |
| `kms_azure` | Azure Key Vault (Workload Identity on AKS) | Auto-unseal on pod start | BUILDING (v1) |
| `kms_aws` | AWS KMS (IRSA on EKS) | Auto-unseal on pod start | PLANNED |
| `kms_gcp` | GCP Cloud KMS (Workload Identity on GKE) | Auto-unseal on pod start | PLANNED |

### Why auto-unseal matters for K8s

HashiCorp Vault's traditional "operator pastes a key on every boot" model is
hostile to ephemeral pods. HPA scale-ups, node failures, and rolling deploys
all require unattended restarts. The K8s-native answer is to delegate the
unseal decision to an external trust anchor (a cloud KMS key) that the pod
authenticates to using its workload identity — the pod never holds the
unseal key, only a proof of identity that the KMS exchanges for a one-shot
decryption.

Manual mode exists for local dev, the install ceremony itself, and single-VM
deployments where there is no workload identity provider. The cloud KMS
backends plug into the same interface, so switching from dev to prod is a
config choice at install time, not a code change.

### Security trade-off we accept

Auto-unseal means an attacker with runtime code execution on a pod (e.g. an
RCE in the app) gets the MDK in memory and can decrypt everything until the
pod dies. Manual mode has the same property *after* unseal, but the blast
radius is smaller: pod crash = attacker loses the MDK and must phish an
operator again. Auto-unseal keeps working across restarts, so the attacker
wins for as long as they can persist on the pod. This is an accepted
trade-off for K8s-native operation, because the alternative — no horizontal
scaling without a human in the loop — is operationally infeasible.

## Where the three DB DSNs live

At install time the wizard generates (or collects) three Postgres roles:

- `tennetctl_admin` — DDL only, used by migrations
- `tennetctl_write` — runtime app identity (SELECT/INSERT/UPDATE)
- `tennetctl_read` — read-only, used by reporting and read-scoped API keys

All three DSNs are written into the vault at install time under:

```text
tennetctl/db/admin_dsn
tennetctl/db/write_dsn
tennetctl/db/read_dsn
```

The **write DSN is supplied to the pod via the `$DATABASE_URL` env var** —
the one and only configuration variable a tennetctl process reads from its
environment. This is the boot handshake: the pod reads `$DATABASE_URL` to
reach Postgres, queries `v_vault` to pick its unseal backend, unseals
(manually or via KMS), then reads the other DSNs (and every other runtime
secret) from the vault. There is no config file, no drift check, and no
filesystem state involved.

Migrations need the admin DSN. When the operator runs `tennetctl migrate up`,
the CLI unseals the vault (via the same backend used by the app), reads
`admin_dsn`, runs the migrations, and exits. Admin creds never live on disk
outside the vault.

## Scope boundaries

**In scope:**

- Vault singleton + lifecycle (init at install time, seal/unseal thereafter)
- Pluggable `UnsealBackend` interface with four backends (two in v1,
  two PLANNED)
- AES-256-GCM envelope encryption at rest
- Project-scoped secret containers
- Per-project environments (dev / staging / prod)
- Secret versioning — every update creates a new version
- Scoped API keys for programmatic access
- Full audit trail on every read and write

**Out of scope (future):**

- IAM role-based access (RBAC integration — phase 2)
- Dynamic secrets (e.g. ephemeral DB credentials)
- Hardware Security Module (HSM) integration beyond cloud KMS
- Certificate lifecycle management
- Multi-region replication
- Shamir's Secret Sharing for threshold unseal

## Sub-features

See `feature.manifest.yaml` for the full list and build order, or
`01_sub_features.md` for the narrative.

## Dependencies

- Depends on: `01_sql_migrator` (the migration runner must exist before
  vault schema can be applied)
- Depended on by: `00_setup` (the install wizard calls vault init), `03_iam`
  (IAM reads its JWT signing key from the vault at runtime), and every
  later feature that needs runtime secrets
