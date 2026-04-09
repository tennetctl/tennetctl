## IAM — Sub-Features

V1 ships exactly two sub-features. Anything else is future work.

## 00_bootstrap

Schema sub-feature. Owns the `"03_iam"` schema and every table in it:
`10_fct_users`, `20_fct_sessions`, the IAM-side dim tables
(`06_dim_account_types`, `07_dim_auth_types`, `08_dim_session_statuses`),
the shared `06_dim_entity_types` + `07_dim_attr_defs` for EAV, and
`20_dtl_attrs`. Seeds the dim rows (`default_admin`, `default_user`,
`username_password`, the three attr_defs for `username` / `email` /
`password_hash`) in the same migration. One migration file:
`20260408_003_iam_bootstrap.sql` with `sequence: 3` and `depends_on: [2]`.

This sub-feature has **no backend code** — it is schema only. IAM's
repository and service layers live in `01_auth`.

## 01_auth

The only v1 auth sub-feature. Implements `POST /v1/auth/login`,
`POST /v1/auth/logout`, `GET /v1/auth/me`, the opaque session token
model, the session cookie middleware, and the Argon2id password
verification path. Five standard backend files
(`schemas.py`, `repository.py`, `service.py`, `routes.py`, `__init__.py`).

## Build order

```text
00_bootstrap   ← schema + dim seeds, must land before Phase 3 of install
01_auth        ← backend code, can be built in parallel with Phase 3
```

`00_bootstrap` is a hard prerequisite for `00_setup.03_first_admin`
because Phase 3 inserts directly into the tables this sub-feature
creates. `01_auth` is only needed at runtime, so it can be built
after install works end-to-end.
