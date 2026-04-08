# T-Vault Azure KMS Auto-Unseal — Design

## File layout

```text
backend/02_features/vault/kms_azure/
├── __init__.py          — registers AzureKeyVaultUnsealBackend into UNSEAL_BACKENDS
├── schemas.py           — AzureKmsConfig (Pydantic v2)
├── backend.py           — AzureKeyVaultUnsealBackend implementation
└── tests/
    ├── test_init.py
    ├── test_unseal.py
    └── test_errors.py
```

This sub-feature is code-only — no schema, no migration, no HTTP routes.
It plugs into the vault lifecycle endpoints in `01_setup` via the backend
registry.

## AzureKmsConfig (Pydantic v2)

```python
# backend/02_features/vault/kms_azure/schemas.py

from pydantic import BaseModel, Field, HttpUrl

class AzureKmsConfig(BaseModel):
    """Install-time config for the Azure Key Vault unseal backend.
    Serialised to JSON and stored in 10_fct_vault.unseal_config."""

    vault_url: HttpUrl = Field(
        ...,
        description="Key Vault URL, e.g. https://tennetctl-kv.vault.azure.net/",
    )
    key_name: str = Field(
        ...,
        min_length=1,
        max_length=127,
        pattern=r"^[A-Za-z0-9-]+$",
        description="Name of the wrapping key in Key Vault.",
    )
    key_version: str = Field(
        ...,
        min_length=32,
        description=(
            "Pinned version of the wrapping key. Must be a concrete version "
            "identifier — 'latest' is not accepted, because key rotation "
            "without a config update would brick every pod."
        ),
    )
```

## AzureKeyVaultUnsealBackend

```python
# backend/02_features/vault/kms_azure/backend.py

import base64
import json
import os
from azure.identity import DefaultAzureCredential
from azure.keyvault.keys import KeyClient
from azure.keyvault.keys.crypto import CryptographyClient, KeyWrapAlgorithm

from backend.02_features.vault.setup.unseal_backend import UnsealBackend, InitResult
from .schemas import AzureKmsConfig

ALG = KeyWrapAlgorithm.rsa_oaep_256

class AzureKeyVaultUnsealBackend:
    code = "kms_azure"

    async def init(self, raw_config: dict) -> InitResult:
        cfg = AzureKmsConfig.model_validate(raw_config)
        mdk = os.urandom(32)

        cred = DefaultAzureCredential()
        kc = KeyClient(vault_url=str(cfg.vault_url), credential=cred)
        key = kc.get_key(cfg.key_name, cfg.key_version)
        crypto = CryptographyClient(key=key, credential=cred)

        wrap = crypto.wrap_key(ALG, mdk)
        wrapped_mdk_b64 = base64.urlsafe_b64encode(wrap.encrypted_key).decode()

        return InitResult(
            mdk=mdk,
            persistence={
                "unseal_mode_id": 2,          # kms_azure
                "wrapped_mdk":    wrapped_mdk_b64,
                "unseal_config":  cfg.model_dump_json(),
                # manual-mode columns stay NULL
                "mdk_ciphertext":  None,
                "mdk_nonce":       None,
                "unseal_key_hash": None,
                "read_key_hash":   None,
            },
        )

    async def unseal(self, vault_row: dict, user_input: str | None) -> bytes:
        if user_input is not None:
            raise ValueError(
                "AzureKeyVaultUnsealBackend does not accept user_input — "
                "this backend auto-unseals via workload identity"
            )

        cfg = AzureKmsConfig.model_validate_json(vault_row["unseal_config"])
        wrapped = base64.urlsafe_b64decode(vault_row["wrapped_mdk"])

        cred = DefaultAzureCredential()
        kc = KeyClient(vault_url=str(cfg.vault_url), credential=cred)
        key = kc.get_key(cfg.key_name, cfg.key_version)
        crypto = CryptographyClient(key=key, credential=cred)

        result = crypto.unwrap_key(ALG, wrapped)
        return result.key  # bytes

    def auto_unseal(self) -> bool:
        return True
```

## Error taxonomy

Every exception from the Azure SDK is caught and re-raised as one of these
tennetctl-specific errors so the install wizard and startup logs give
actionable output instead of a stack trace:

| Error class                    | When                                        | Action for operator                                                      |
| ------------------------------ | ------------------------------------------- | ------------------------------------------------------------------------ |
| `AzureKmsAuthError`            | No credential chain succeeds                | Configure Workload Identity on AKS, or `az login` locally                |
| `AzureKmsPermissionError`      | Auth works but `wrapKey`/`unwrapKey` denied | Grant the identity `Key Vault Crypto User` role on the key               |
| `AzureKmsKeyNotFoundError`     | `key_name` or `key_version` doesn't exist   | Verify `vault_url`, `key_name`, `key_version` in `unseal_config`         |
| `AzureKmsNetworkError`         | DNS/TLS/timeout to KV endpoint              | Check cluster egress, Key Vault private endpoint, NSG rules              |
| `AzureKmsWrappedMdkCorrupted`  | `unwrap_key` succeeds but returns wrong len | Key was rotated without updating `unseal_config`. Restore from backup.   |

The startup hook in `01_core/startup.py` catches `AzureKmsError` (the base
class) and crashes the pod loudly — Kubernetes's restart loop surfaces the
problem instead of the pod silently operating in a broken state.

## Install-time validation

Before the install wizard persists the initialized vault row, it runs a
self-test:

```text
1. Generate a random 32-byte test payload
2. wrap(test_payload)     — proves wrapKey permission
3. unwrap(wrapped)        — proves unwrapKey permission
4. assert unwrapped == test_payload — proves round-trip integrity
5. Discard all test data
```

If any step fails, the wizard aborts with the appropriate `AzureKms*Error`
and the operator fixes their Azure config before the vault is actually
initialized. **No partial state is ever written to 10_fct_vault.**

## AKS Workload Identity setup (operator runbook)

This is the production path. High-level steps the install wizard links to:

```text
# 1. Create a User-Assigned Managed Identity
az identity create --name tennetctl-vault-uami \
  --resource-group rg-tennetctl-prod --location westeurope

# 2. Grant it Key Vault Crypto User on the wrapping key
az role assignment create \
  --assignee <uami-principal-id> \
  --role "Key Vault Crypto User" \
  --scope /subscriptions/.../providers/Microsoft.KeyVault/vaults/tennetctl-kv

# 3. Federate the UAMI to the tennetctl pod's service account
az identity federated-credential create \
  --name tennetctl-vault-fic \
  --identity-name tennetctl-vault-uami \
  --resource-group rg-tennetctl-prod \
  --issuer <aks-oidc-issuer-url> \
  --subject system:serviceaccount:tennetctl:tennetctl-api

# 4. Annotate the K8s ServiceAccount
kubectl annotate serviceaccount tennetctl-api \
  azure.workload.identity/client-id=<uami-client-id> \
  -n tennetctl

# 5. Label the Pod spec
# spec.template.metadata.labels:
#   azure.workload.identity/use: "true"
```

After these five steps, the pod's `DefaultAzureCredential` picks up the
projected token automatically and the install can proceed.

## Testing strategy

- **Unit tests**: mock `DefaultAzureCredential`, `KeyClient`,
  `CryptographyClient` — verify the backend class dispatches to the right
  Azure SDK calls, serialises `unseal_config` correctly, and maps errors
  to the right `AzureKms*Error` classes.
- **Integration tests**: two modes.
  - **Local dev**: skip unless `TENNETCTL_AZURE_KV_INTEGRATION=1` is set
    in the env. When set, the test uses a real Azure KV instance
    (throwaway, in a dedicated test subscription) and a test key named
    `tennetctl-integration-test-<random>`. Teardown deletes the key.
  - **CI**: runs the same integration test against a long-lived test KV
    using a service-principal credential stored in GitHub Actions Secrets.
- Azurite does **not** support Key Vault crypto operations, so there is
  no offline emulator. Integration tests require real Azure or a mock.

## Security notes

- **No Azure credentials on disk, ever.** The install wizard uses whatever
  `DefaultAzureCredential` finds in the environment — typically `az login`
  or `AZURE_*` env vars for CI. Those credentials are never persisted
  anywhere — not to disk, not to `unseal_config`. On subsequent boots, the pod uses
  Workload Identity's projected SA token, which kubelet rotates.
- **The wrapping key never leaves Azure Key Vault.** We call `wrap`/`unwrap`
  remotely. The plaintext wrapping key is never in our process memory.
- **The MDK does live in process memory after unseal.** Same trade-off as
  manual mode — no way around this without HSM-backed computation of every
  per-secret decrypt, which would be prohibitively expensive per API call.
- **Key rotation is a deliberate ceremony, not a background job.** See
  the note in scope about `key_version` pinning. A future sub-feature will
  automate the rotation flow.
