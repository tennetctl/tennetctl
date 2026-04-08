# T-Vault AWS KMS Auto-Unseal — Scope

**Status: PLANNED** — not built in v1. This doc is a stub that fixes the
shape of the eventual implementation so build order, schema, and registry
wiring are already decided.

## What it will do

Implement the `UnsealBackend` protocol (defined in `01_setup`) for AWS KMS.
Wrap the MDK with a KMS key at install time; on every process boot the pod
calls `kms:Decrypt` using its IRSA identity and auto-unseals with no human
interaction. Same shape as `02_kms_azure`, different cloud.

## Authentication

**IRSA (IAM Roles for Service Accounts)** is the production path on EKS.
The K8s service account is annotated with an IAM role ARN; the EKS pod
identity webhook projects a signed token into the pod; the AWS SDK's
default credential chain exchanges that token for short-lived AWS
credentials via `sts:AssumeRoleWithWebIdentity`.

Fallbacks in the credential chain:

1. Environment variables (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`)
   for CI or local dev
2. `~/.aws/credentials` profile for local dev
3. EC2 IMDS for non-EKS VM deployments
4. IRSA for EKS pods (production)

## Crypto flow

```text
init(config={ key_arn, region }):
    mdk = os.urandom(32)
    kms = boto3.client("kms", region_name=config.region)
    result = kms.encrypt(KeyId=config.key_arn, Plaintext=mdk)
    wrapped_mdk = base64url(result["CiphertextBlob"])
    → persist {
        unseal_mode_id = 3 (kms_aws),
        wrapped_mdk,
        unseal_config: JSON({key_arn, region}),
        status_id = sealed
      }

unseal(vault_row, user_input=None):
    config = JSON.loads(vault_row.unseal_config)
    kms = boto3.client("kms", region_name=config.region)
    result = kms.decrypt(
        KeyId=config.key_arn,
        CiphertextBlob=base64url_decode(vault_row.wrapped_mdk),
    )
    return result["Plaintext"]

auto_unseal():
    return True
```

Note: AWS KMS's `Encrypt`/`Decrypt` are used instead of `WrapKey`/`UnwrapKey`
because KMS's data-key model already provides envelope-style semantics for
payloads up to 4KB (the MDK is 32 bytes, well under the limit).

## unseal_config JSON shape

```json
{
  "key_arn": "arn:aws:kms:us-east-1:123456789012:key/abcd1234-...",
  "region": "us-east-1"
}
```

Unlike Azure, AWS KMS key versions are invisible — KMS handles rotation
transparently, and `Decrypt` with the key ARN always works regardless of
which version encrypted the ciphertext. No `key_version` field needed.

## In scope (when built)

- `AwsKmsUnsealBackend` class implementing the `UnsealBackend` protocol
- Registration into `UNSEAL_BACKENDS["kms_aws"]`
- Pydantic model for the AWS-specific config (key_arn, region)
- Install-time validation: encrypt + decrypt a test payload, verify round-trip
- IRSA setup walkthrough for the install wizard
- Error taxonomy parallel to `02_kms_azure`:
  `AwsKmsAuthError`, `AwsKmsPermissionError`, `AwsKmsKeyNotFoundError`,
  `AwsKmsNetworkError`, `AwsKmsWrappedMdkCorrupted`

## Out of scope

- KMS grants (we use resource-based IAM policies)
- KMS multi-Region keys in v1 (single-region is the happy path)
- External key stores (CloudHSM or XKS) — use software KMS for v1

## Dependencies

- Depends on: `01_setup` (defines `UnsealBackend` protocol)
- Python deps: `boto3`
