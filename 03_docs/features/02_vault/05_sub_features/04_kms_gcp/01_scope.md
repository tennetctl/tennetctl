# T-Vault GCP Cloud KMS Auto-Unseal — Scope

**Status: PLANNED** — not built in v1. This doc is a stub that fixes the
shape of the eventual implementation so build order, schema, and registry
wiring are already decided.

## What it will do

Implement the `UnsealBackend` protocol (defined in `01_setup`) for GCP
Cloud KMS. Wrap the MDK with a KMS key at install time; on every process
boot the pod calls `kms.decrypt` using its GKE Workload Identity and
auto-unseals with no human interaction. Same shape as `02_kms_azure` and
`03_kms_aws`, different cloud.

## Authentication

**GKE Workload Identity** is the production path. The K8s service account
is annotated with a GCP service account email; GKE's identity provider
projects a signed token into the pod; Google Cloud's auth library exchanges
it for short-lived GCP credentials.

The Google Cloud client library's default credential chain handles this
transparently — no code changes needed per environment.

## Crypto flow

```text
init(config={ project, location, key_ring, key }):
    mdk = os.urandom(32)
    client = kms_v1.KeyManagementServiceClient()
    key_name = client.crypto_key_path(
        config.project, config.location, config.key_ring, config.key
    )
    result = client.encrypt(name=key_name, plaintext=mdk)
    wrapped_mdk = base64url(result.ciphertext)
    → persist {
        unseal_mode_id = 4 (kms_gcp),
        wrapped_mdk,
        unseal_config: JSON({project, location, key_ring, key}),
        status_id = sealed
      }

unseal(vault_row, user_input=None):
    config = JSON.loads(vault_row.unseal_config)
    client = kms_v1.KeyManagementServiceClient()
    key_name = client.crypto_key_path(
        config.project, config.location, config.key_ring, config.key
    )
    result = client.decrypt(
        name=key_name,
        ciphertext=base64url_decode(vault_row.wrapped_mdk),
    )
    return result.plaintext

auto_unseal():
    return True
```

Cloud KMS `encrypt`/`decrypt` handle payloads up to 64KiB — more than
enough for a 32-byte MDK. Key rotation is handled transparently by GCP:
`decrypt` with the key resource name works regardless of which primary
version encrypted the ciphertext.

## unseal_config JSON shape

```json
{
  "project": "tennetctl-prod",
  "location": "europe-west1",
  "key_ring": "tennetctl-vault",
  "key": "mdk-wrapping"
}
```

## In scope (when built)

- `GcpKmsUnsealBackend` class implementing the `UnsealBackend` protocol
- Registration into `UNSEAL_BACKENDS["kms_gcp"]`
- Pydantic model for the GCP-specific config (project, location, key_ring, key)
- Install-time validation: encrypt + decrypt a test payload, verify round-trip
- GKE Workload Identity setup walkthrough for the install wizard
- Error taxonomy parallel to `02_kms_azure`

## Dependencies

- Depends on: `01_setup` (defines `UnsealBackend` protocol)
- Python deps: `google-cloud-kms`
