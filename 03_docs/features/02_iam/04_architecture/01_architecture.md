# IAM — Architecture

## Schema: `"02_iam"`

---

## Core Design: fct / dtl(EAV) / dim

Every entity follows a three-layer model:

```
dim_*          Lookup enumerations. Small, seeded, rarely changes.
               e.g. dim_user_statuses: active | inactive | suspended

fct_*          Pure identity record. UUID PK + FK references only.
               No names, no emails, no strings. Just keys and status.
               e.g. fct_users: id, status_id, account_type_id, is_super_admin

20_dtl_attrs   ONE generic EAV table for ALL entity descriptive data.
               key_text  — simple string values (email, name, slug, url)
               key_jsonb — complex structured values (settings, config, profile)
               Adding a new property to any entity = insert a row in dim_attr_defs
                           + insert a row in dtl_attrs. ZERO schema changes.
```

---

## All Tables (25 total)

### Dimensions (01–09)

**`01_dim_user_statuses`**
| id | code | label |
|----|------|-------|
| 1 | active | Active |
| 2 | inactive | Inactive |
| 3 | suspended | Suspended |
| 4 | pending_verification | Pending Verification |
| 5 | deleted | Deleted |

**`02_dim_org_statuses`**
| id | code | label |
|----|------|-------|
| 1 | active | Active |
| 2 | suspended | Suspended |
| 3 | deleted | Deleted |
| 4 | trialing | Trialing |

**`03_dim_account_types`**
| id | code | label |
|----|------|-------|
| 1 | human | Human User |
| 2 | service_account | Service Account |
| 3 | bot | Bot |

**`04_dim_auth_providers`**
| id | code | label |
|----|------|-------|
| 1 | local | Password |
| 2 | google | Google |
| 3 | github | GitHub |
| 4 | gitlab | GitLab |
| 5 | saml | SAML SSO |
| 6 | oidc | OIDC SSO |
| 7 | totp | Authenticator App |
| 8 | passkey | Passkey / WebAuthn |

**`05_dim_challenge_types`**
| id | code | label | ttl_seconds |
|----|------|-------|-------------|
| 1 | email_otp | Email OTP | 600 |
| 2 | sms_otp | SMS OTP | 600 |
| 3 | magic_link | Magic Link | 1800 |
| 4 | email_verify | Email Verification | 86400 |
| 5 | password_reset | Password Reset | 3600 |
| 6 | totp_enroll | TOTP Enrollment | 600 |

**`06_dim_entity_types`**
Shared catalog of all entity types in tennetctl. Used by EAV and audit.
| id | code | label | schema_name |
|----|------|-------|-------------|
| 1 | user | User | 02_iam |
| 2 | org | Organisation | 02_iam |
| 3 | workspace | Workspace | 02_iam |
| 4 | group | Group | 02_iam |
| 5 | identity | Identity Credential | 02_iam |
| 6 | session | Session | 02_iam |
| 7 | api_key | API Key | 02_iam |
| 8 | secret | Vault Secret | 07_vault |
| 9 | metric | Metric Series | 04_monitoring |
| ... | ... | ... (extended as modules are built) | ... |

**`07_dim_attr_defs`**
The catalog of every attribute key for every entity type.
This is what makes EAV safe — every key is defined and typed here.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | SMALLINT PK | |
| `entity_type_id` | SMALLINT FK → `06_dim_entity_types` | Which entity this attribute belongs to |
| `code` | TEXT | Machine key: `email`, `display_name`, `settings`, `github_org` |
| `label` | TEXT | Human label: `"Email Address"` |
| `value_type` | TEXT | `text` or `jsonb` — which column to use |
| `is_pii` | BOOL | If true: handle per GDPR (mask in logs, right-to-erase) |
| `is_encrypted` | BOOL | If true: value is AES-256-GCM encrypted before storage |
| `is_required` | BOOL | Enforced at service layer |
| `is_unique` | BOOL | Enforced by partial unique index on dtl_attrs |
| `description` | TEXT | What this attribute means |

Seeded attribute definitions:

| id | entity_type | code | value_type | pii | encrypted | required | unique |
|----|-------------|------|------------|-----|-----------|----------|--------|
| 1 | user | email | text | true | false | true | true |
| 2 | user | display_name | text | false | false | false | false |
| 3 | user | avatar_url | text | false | false | false | false |
| 4 | user | phone | text | true | true | false | false |
| 5 | user | settings | jsonb | false | false | false | false |
| 6 | user | email_verified_at | text | false | false | false | false |
| 7 | user | last_active_at | text | false | false | false | false |
| 10 | org | slug | text | false | false | true | true |
| 11 | org | display_name | text | false | false | true | false |
| 12 | org | settings | jsonb | false | false | false | false |
| 20 | workspace | slug | text | false | false | true | false |
| 21 | workspace | display_name | text | false | false | true | false |
| 22 | workspace | settings | jsonb | false | false | false | false |
| 30 | group | name | text | false | false | true | false |
| 31 | group | description | text | false | false | false | false |

Future attribute (no DB change needed — just add a row here + insert the value):
| 8 | user | department | text | false | false | false | false |
| 9 | user | employee_id | text | false | false | false | false |
| 13 | org | billing_email | text | true | false | false | false |
| 14 | org | github_org_name | text | false | false | false | false |

---

### Facts (10–19) — UUID PK + FK references only. No descriptive data.

**`10_fct_users`**
```
id              UUID     PK (uuid7)
status_id       SMALLINT FK → 01_dim_user_statuses
account_type_id SMALLINT FK → 03_dim_account_types
is_super_admin  BOOLEAN  NOT NULL DEFAULT false
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

**`11_fct_orgs`**
```
id          UUID     PK
status_id   SMALLINT FK → 02_dim_org_statuses
created_by  UUID     FK → 10_fct_users
created_at  TIMESTAMP
updated_at  TIMESTAMP
```

**`12_fct_workspaces`**
```
id          UUID     PK
org_id      UUID     FK → 11_fct_orgs ON DELETE CASCADE
is_active   BOOLEAN  NOT NULL DEFAULT true
created_by  UUID     FK → 10_fct_users
created_at  TIMESTAMP
updated_at  TIMESTAMP
```

**`13_fct_identities`**
One row per credential per user (password, Google, GitHub, TOTP, passkey, SAML).
```
id          UUID     PK
user_id     UUID     FK → 10_fct_users ON DELETE CASCADE
provider_id SMALLINT FK → 04_dim_auth_providers
is_active   BOOLEAN  NOT NULL DEFAULT true
last_used_at TIMESTAMP
created_at  TIMESTAMP
updated_at  TIMESTAMP
```
UNIQUE (user_id, provider_id) — one active credential per provider per user.

**`14_fct_auth_challenges`**
One row per outstanding challenge (OTP code, magic link token, password reset token).
```
id                UUID     PK
user_id           UUID     FK → 10_fct_users (NULLABLE — pre-signup flows)
challenge_type_id SMALLINT FK → 05_dim_challenge_types
expires_at        TIMESTAMP NOT NULL
consumed_at       TIMESTAMP          — NULL = pending
attempt_count     SMALLINT NOT NULL DEFAULT 0
created_at        TIMESTAMP
```

**`15_fct_sessions`**
One row per login. Family-based refresh token rotation.
```
id          UUID     PK
user_id     UUID     FK → 10_fct_users
org_id      UUID     FK → 11_fct_orgs (NULLABLE — platform sessions)
family_id   UUID     NOT NULL  — all rotated tokens in one login share a family
revoked_at  TIMESTAMP
expires_at  TIMESTAMP
created_at  TIMESTAMP
updated_at  TIMESTAMP
```

**`16_fct_api_keys`**
```
id          UUID     PK
org_id      UUID     FK → 11_fct_orgs  (NULLABLE — platform-level service keys)
user_id     UUID     FK → 10_fct_users (NULLABLE — org-level service keys)
is_active   BOOLEAN  NOT NULL DEFAULT true
expires_at  TIMESTAMP
last_used_at TIMESTAMP
created_by  UUID     FK → 10_fct_users
created_at  TIMESTAMP
updated_at  TIMESTAMP
```

**`17_fct_groups`**
Hierarchical groups within an org for RBAC.
```
id          UUID     PK
org_id      UUID     FK → 11_fct_orgs ON DELETE CASCADE
parent_id   UUID     FK → 17_fct_groups (NULLABLE — top-level groups)
is_active   BOOLEAN  NOT NULL DEFAULT true
created_by  UUID     FK → 10_fct_users
created_at  TIMESTAMP
updated_at  TIMESTAMP
```

---

### Detail — EAV (20–29)

**`20_dtl_attrs`** — THE single EAV table for all entity attributes.

```
entity_type_id  SMALLINT     FK → 06_dim_entity_types      — which entity type
entity_id       UUID         NOT NULL                        — FK to the fct table's id
attr_def_id     SMALLINT     FK → 07_dim_attr_defs          — which attribute key
key_text        TEXT                                         — value if value_type = 'text'
key_jsonb       JSONB                                        — value if value_type = 'jsonb'
created_at      TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP
updated_at      TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP

PK: (entity_type_id, entity_id, attr_def_id)
```

No surrogate UUID PK — the compound key (entity_type_id, entity_id, attr_def_id) is unique and meaningful. One row per attribute per entity.

Partial unique indexes enforce is_unique attributes (e.g., email):
```sql
CREATE UNIQUE INDEX uq_dtl_attrs_user_email
    ON "02_iam".20_dtl_attrs (key_text)
    WHERE entity_type_id = 1 AND attr_def_id = 1;  -- entity=user, attr=email
```

RLS: `entity_id` joins to `fct_orgs` / `fct_workspaces` to resolve `org_id` for row-level isolation.

**Operational detail tables** (security-critical schemas that are fixed by design):

**`21_dtl_identity_creds`** — credential material for `fct_identities`
```
identity_id       UUID PK → 13_fct_identities ON DELETE CASCADE
provider_user_id  TEXT         — external provider's user id (NULL for local/totp/passkey)
credential_data   JSONB NOT NULL DEFAULT '{}'
```
`credential_data` per provider:
- `local`: `{"password_hash": "argon2id:...", "history": [...]}`
- `google/github/gitlab`: `{"access_token_enc": "...", "raw_profile": {...}}`
- `totp`: `{"secret_enc": "...", "backup_codes_hash": [...]}`
- `passkey`: `{"credential_id": "...", "public_key": "...", "sign_count": 0, "transports": [...]}`
- `saml`: `{"attributes": {...}, "session_index": "..."}`

**`22_dtl_challenge_tokens`** — token material for `fct_auth_challenges`
```
challenge_id  UUID PK → 14_fct_auth_challenges ON DELETE CASCADE
token_hash    TEXT NOT NULL UNIQUE   — BLAKE2b of raw token/code
metadata      JSONB NOT NULL DEFAULT '{}'
```
`metadata` per type: `email_otp → {"email": "..."}`, `sms_otp → {"phone": "+1..."}`, `magic_link → {"redirect_url": "...", "email": "..."}`

**`23_dtl_session_tokens`** — token material for `fct_sessions`
```
session_id          UUID PK → 15_fct_sessions ON DELETE CASCADE
refresh_token_hash  TEXT NOT NULL UNIQUE   — BLAKE2b of raw refresh token
ip_address          INET
metadata            JSONB NOT NULL DEFAULT '{}'
```
`metadata`: `{"user_agent": "...", "device_name": "...", "country": "US"}`

**`24_dtl_api_key_data`** — key material for `fct_api_keys`
```
key_id      UUID PK → 16_fct_api_keys ON DELETE CASCADE
key_prefix  TEXT NOT NULL UNIQUE   — first 12 chars, for display
key_hash    TEXT NOT NULL UNIQUE   — BLAKE2b of full raw key
name        TEXT NOT NULL
scopes      JSONB NOT NULL DEFAULT '[]'   — ["users:read", "orgs:read"]
```

---

### Admin (30–39)

**`30_adm_roles`**
```
id           UUID     PK
org_id       UUID     FK → 11_fct_orgs (NULLABLE — platform built-in roles)
code         TEXT     NOT NULL
display_name TEXT     NOT NULL
is_system    BOOLEAN  NOT NULL DEFAULT false
permissions  JSONB    NOT NULL DEFAULT '[]'   — ["users:read", "workspaces:manage"]
created_at   TIMESTAMP
updated_at   TIMESTAMP
UNIQUE(org_id, code)
```

**`31_adm_org_auth_configs`**
```
id          UUID     PK
org_id      UUID     FK → 11_fct_orgs ON DELETE CASCADE
provider_id SMALLINT FK → 04_dim_auth_providers
is_active   BOOLEAN  NOT NULL DEFAULT false
created_by  UUID     FK → 10_fct_users
created_at  TIMESTAMP
updated_at  TIMESTAMP
UNIQUE(org_id, provider_id)
```
Config data (client_id, client_secret, redirect_uris, SAML metadata URL) stored in `20_dtl_attrs` as EAV rows under entity_type = `org_auth_config`.

---

### Links (40–59)

**`40_lnk_org_members`** — user membership in an org
```
id          UUID PK
org_id      UUID FK → 11_fct_orgs
user_id     UUID FK → 10_fct_users
role_id     UUID FK → 30_adm_roles
invited_by  UUID FK → 10_fct_users (NULLABLE)
joined_at   TIMESTAMP          — NULL = invite pending
created_at  TIMESTAMP
UNIQUE(org_id, user_id)
```

**`41_lnk_workspace_members`** — user membership in a workspace
```
id            UUID PK
org_id        UUID FK → 11_fct_orgs    (denormalised for RLS)
workspace_id  UUID FK → 12_fct_workspaces
user_id       UUID FK → 10_fct_users
role_id       UUID FK → 30_adm_roles (NULLABLE — NULL = inherit org role)
created_at    TIMESTAMP
UNIQUE(workspace_id, user_id)
```

**`42_lnk_group_members`** — user membership in a group
```
id          UUID PK
org_id      UUID FK (denormalised for RLS)
group_id    UUID FK → 17_fct_groups
user_id     UUID FK → 10_fct_users
created_at  TIMESTAMP
UNIQUE(group_id, user_id)
```

**`43_lnk_group_roles`** — roles assigned to a group
```
id          UUID PK
org_id      UUID FK (denormalised for RLS)
group_id    UUID FK → 17_fct_groups
role_id     UUID FK → 30_adm_roles
created_at  TIMESTAMP
UNIQUE(group_id, role_id)
```

---

### Events (60–79) — append-only

**`60_evt_login_attempts`**
```
id          UUID PK
user_id     UUID FK → 10_fct_users (NULLABLE — unknown user attempts)
org_id      UUID FK → 11_fct_orgs  (NULLABLE)
provider_id SMALLINT FK → 04_dim_auth_providers
outcome     TEXT NOT NULL   — success | invalid_credentials | locked | mfa_required | mfa_failed
ip_address  INET
metadata    JSONB NOT NULL DEFAULT '{}'   — user_agent, device, country
created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
```

---

## Table Count Summary

| Type | Count | Numbers |
|------|-------|---------|
| dim | 7 | 01–07 |
| fct | 8 | 10–17 |
| dtl EAV | 1 | 20 |
| dtl operational | 4 | 21–24 |
| adm | 2 | 30–31 |
| lnk | 4 | 40–43 |
| evt | 1 | 60 |
| **Total** | **27** | |

---

## How to Add a New Property — Zero Schema Changes

Example: add `department` to users.

```sql
-- Step 1: Add the attribute definition (new row in dim, no schema change)
INSERT INTO "02_iam".07_dim_attr_defs
    (id, entity_type_id, code, label, value_type, is_pii, is_encrypted, is_required, is_unique, description)
VALUES
    (8, 1, 'department', 'Department', 'text', false, false, false, false, 'User department for directory sync');

-- Step 2: Set the value for a user (new row in dtl_attrs, no schema change)
INSERT INTO "02_iam".20_dtl_attrs (entity_type_id, entity_id, attr_def_id, key_text)
VALUES (1, '018e...uuid...', 8, 'Engineering');

-- Done. No ALTER TABLE. No migration needed.
```

---

## Audit Module — Generic Event Architecture

The audit module (`"03_audit"`) follows the same fct/dtl-EAV pattern.

### `03_audit` Tables

**`01_dim_audit_actions`**
| id | code | label |
|----|------|-------|
| 1 | create | Created |
| 2 | update | Updated |
| 3 | delete | Deleted |
| 4 | read | Accessed |
| 5 | login | Logged In |
| 6 | logout | Logged Out |
| 7 | export | Exported |
| 8 | invite | Invited |
| 9 | revoke | Revoked |
| 10 | rotate | Rotated |

**`02_dim_audit_outcomes`**
| id | code | label |
|----|------|-------|
| 1 | success | Success |
| 2 | failure | Failed |
| 3 | denied | Permission Denied |
| 4 | partial | Partial |

**`03_dim_actor_types`**
| id | code | label |
|----|------|-------|
| 1 | user | Human User |
| 2 | service_account | Service Account |
| 3 | api_key | API Key |
| 4 | system | System |

**`10_fct_audit_events`** — pure identity record per event
```
id              UUID PK (uuid7)
actor_id        UUID    (NULLABLE — system events have no actor)
actor_type_id   SMALLINT FK → 03_dim_actor_types
org_id          UUID    FK → "02_iam".fct_orgs (NULLABLE — platform events)
action_id       SMALLINT FK → 01_dim_audit_actions
entity_type_id  SMALLINT FK → "02_iam".06_dim_entity_types
entity_id       UUID    NOT NULL
outcome_id      SMALLINT FK → 02_dim_audit_outcomes
created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
-- NO updated_at — audit events are immutable
```

Partitioned by month on `created_at` for retention management.

**`20_dtl_audit_attrs`** — key-value detail for every audit event

```
event_id    UUID FK → 10_fct_audit_events ON DELETE CASCADE
attr_key    TEXT NOT NULL        — free-form key (not FK — audit context is open-ended)
key_text    TEXT                 — simple string values
key_jsonb   JSONB                — complex structured values

PK: (event_id, attr_key)
```

Example rows for a "user updated email" event:
```
(event_id_1, "before_email",  "old@example.com",  NULL)
(event_id_1, "after_email",   "new@example.com",  NULL)
(event_id_1, "ip_address",    "203.0.113.1",      NULL)
(event_id_1, "user_agent",    "Mozilla/5.0...",   NULL)
(event_id_1, "before_state",  NULL, {"email": "old@example.com", "display_name": "Alice"})
(event_id_1, "after_state",   NULL, {"email": "new@example.com", "display_name": "Alice"})
(event_id_1, "session_id",    "018e...uuid...",   NULL)
```

Any module emitting an audit event can add any keys it needs. No schema change required. The `fct_audit_events` record gives you who/what/when/outcome for fast filtering. The `dtl_audit_attrs` rows give you the full context for drill-down.

### Querying Audit

```sql
-- Find all events for a user in the last 24h
SELECT e.id, e.created_at, a.code AS action, o.code AS outcome
FROM "03_audit".10_fct_audit_events e
JOIN "03_audit".01_dim_audit_actions a ON a.id = e.action_id
JOIN "03_audit".02_dim_audit_outcomes o ON o.id = e.outcome_id
WHERE e.actor_id = $1
  AND e.created_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
ORDER BY e.created_at DESC;

-- Get full detail for one event
SELECT attr_key, key_text, key_jsonb
FROM "03_audit".20_dtl_audit_attrs
WHERE event_id = $1
ORDER BY attr_key;
```
