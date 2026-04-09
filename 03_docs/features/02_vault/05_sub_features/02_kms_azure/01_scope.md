# T-Vault Azure KMS Auto-Unseal — Scope

## What it does

Implements the `UnsealBackend` protocol (defined in `01_setup`) for Azure
Key Vault. The MDK is wrapped with an Azure Key Vault wrapping key at install
time; on every process boot the pod calls `unwrapKey` using its Azure identity
and auto-unseals the vault with no human interaction.

This is the first K8s-native unseal backend and the one the install wizard
steers operators toward for AKS deployments.

## Authentication chain

Uses the Azure SDK's `DefaultAzureCredential` chain, which tries each method
in order and falls through to the next on failure:

1. **Environment variables** — `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
   `AZURE_CLIENT_SECRET` (service principal). Used by CI.
2. **Workload Identity** — `AZURE_FEDERATED_TOKEN_FILE` projected by the
   AKS admission webhook. Used by production pods on AKS. This is the
   recommended production path.
3. **Managed Identity** — IMDS endpoint on the VM. Used by non-AKS VM
   deployments.
4. **Azure CLI** — `az login` credentials. Used by local developers.

The pod never holds a static credential. On AKS the projected SA token is
short-lived and auto-rotated by kubelet.

## Crypto flow

```text
init(config={
    vault_url:   "https://tennetctl-kv.vault.azure.net/",
    key_name:    "tennetctl-mdk-wrapping",
    key_version: "abc123..." | "latest"
}):
    mdk = os.urandom(32)
    cred = DefaultAzureCredential()
    client = KeyClient(vault_url=config.vault_url, credential=cred)
    crypto = CryptographyClient(
        key=client.get_key(config.key_name, config.key_version),
        credential=cred,
    )
    wrap_result = crypto.wrap_key(KeyWrapAlgorithm.rsa_oaep_256, mdk)
    wrapped_mdk = base64url(wrap_result.encrypted_key)
    → persist {
        unseal_mode_id = 2 (kms_azure),
        wrapped_mdk:    wrapped_mdk,
        unseal_config:  JSON.dumps(config),
        status_id = sealed
      }
    → return mdk (held in memory for the rest of install)

unseal(vault_row, user_input=None):
    config = JSON.loads(vault_row.unseal_config)
    cred = DefaultAzureCredential()
    client = KeyClient(vault_url=config.vault_url, credential=cred)
    crypto = CryptographyClient(
        key=client.get_key(config.key_name, config.key_version),
        credential=cred,
    )
    unwrap_result = crypto.unwrap_key(
        KeyWrapAlgorithm.rsa_oaep_256,
        base64url_decode(vault_row.wrapped_mdk),
    )
    return unwrap_result.key   # plaintext MDK bytes

auto_unseal():
    return True
```

## unseal_config JSON shape

Stored as TEXT in `10_fct_vault.unseal_config`:

```json
{
  "vault_url": "https://tennetctl-kv.vault.azure.net/",
  "key_name": "tennetctl-mdk-wrapping",
  "key_version": "abc123def456..."
}
```

### Why pin `key_version`

Azure Key Vault keys support versioning. If `key_version` is `"latest"` and
an operator rotates the key, the next pod boot will try to unwrap the old
ciphertext with the new key and fail. Pinning the version is mandatory —
the install wizard reads the current version from Key Vault at install
time and pins it. Key rotation becomes a deliberate, multi-step ceremony
(unwrap with old version → wrap with new version → update `unseal_config`
→ deploy) rather than an accidental pod crash loop.

## In scope

- `AzureKeyVaultUnsealBackend` class implementing the `UnsealBackend` protocol
- Registration into `UNSEAL_BACKENDS["kms_azure"]` registry from `01_setup`
- Pydantic model for the Azure-specific config (vault_url, key_name, key_version)
- Install-time validation: connect to the specified vault, verify the key
  exists, verify the pod identity has `wrapKey` + `unwrapKey` permission
  on the key (call `wrapKey` on a test 32-byte payload, then `unwrapKey` it)
- Install wizard prompt flow: vault URL → key name → show available versions
  → operator picks one (default: current)
- Boot-time `unseal()` implementation with clear error messages on auth
  failure, network failure, key-not-found, permission-denied
- Integration test using Azurite + a fake Key Vault emulator, OR a real
  Azure KV instance with a throwaway key (decided by whether Azurite
  supports Key Vault crypto ops — if not, real Azure required)
- Documentation: AKS Workload Identity setup walkthrough (create UAMI,
  federate to SA, annotate the pod spec)

## Out of scope

- Key rotation CLI command (tracked separately as a future enhancement)
- Multi-region Key Vault replication
- Support for HSM-backed keys beyond what Azure KV already offers (v1
  uses software-backed keys; HSM-backed is a config change the operator
  can make on the Azure side without tennetctl code changes)
- Shamir secret sharing across multiple KV keys (future if needed)
- Support for Key Vault certificates (we use keys, not certs)

## Acceptance criteria

- [ ] `AzureKeyVaultUnsealBackend` class implements `UnsealBackend` protocol
- [ ] `auto_unseal()` returns `True`
- [ ] `init()` generates an MDK, wraps it with the configured KV key, and
      returns a persistence payload with `wrapped_mdk` + `unseal_config`
- [ ] `init()` fails loud if the KV connection fails, the key doesn't exist,
      or the pod identity lacks `wrapKey` permission
- [ ] `unseal()` reads `unseal_config` from the vault row, connects to Azure
      KV, and returns the plaintext MDK
- [ ] `unseal()` fails loud on auth failure with an error message that
      distinguishes "pod has no identity" vs "identity has no KV access"
- [ ] `unseal()` fails loud on `wrapped_mdk` that cannot be decrypted (key
      rotated without updating unseal_config — tells the operator what to do)
- [ ] Backend is registered in `UNSEAL_BACKENDS["kms_azure"]` at import time
- [ ] Integration test: install → seal → unseal → decrypt a secret round-trips
      cleanly using a real or emulated Azure KV
- [ ] Docs: AKS Workload Identity setup walkthrough with concrete `az` commands

## Dependencies

- Depends on: `01_setup` (defines the `UnsealBackend` protocol and owns
  `10_fct_vault`)
- Depended on by: any deployment that wants K8s-native auto-unseal on AKS
- Python deps: `azure-identity`, `azure-keyvault-keys`
