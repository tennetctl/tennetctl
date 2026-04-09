## Planned: Lazy Argon2id Re-hash on Login

**Severity if unbuilt:** HIGH (blocks safe parameter upgrades)
**Depends on:** `backend/01_core/password.py`

## Problem

Argon2id parameters (memory cost, time cost, parallelism) are encoded in
the PHC string stored in the DB. `argon2-cffi` reads the per-row parameters
on every verify, so existing hashes remain valid after a parameter change.
But there is no mechanism to upgrade old hashes to the new parameters —
users who haven't logged in since a parameter upgrade keep their old
(potentially weaker) hashes indefinitely.

## Fix when built

After a successful `verify_password(stored_hash, plaintext)` in
`service.login`, check whether the stored hash was produced with the current
parameters:

```python
from argon2 import PasswordHasher
_ph = PasswordHasher(...)  # current params

if _ph.check_needs_rehash(stored_hash):
    new_hash = hash_password(plaintext)
    await repo.update_password_hash(conn, user.id, new_hash)
    # plaintext is still in scope here — re-hash is the only time this
    # is safe to do. Drop reference immediately after.
```

`argon2-cffi` exposes `check_needs_rehash()` for exactly this purpose.

### Repository change

Add `update_password_hash(conn, user_id, new_hash)` to
`backend/02_features/iam/auth/repository.py`. Updates the `password_hash`
EAV row. Does NOT emit an audit event (this is an invisible infrastructure
upgrade, not a user-initiated password change).
