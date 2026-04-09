## Planned: Org Invitations

**Severity if unbuilt:** HIGH (no way to onboard users to an org without direct DB access)
**Depends on:** notifications module (email delivery), org memberships (built)

## Problem

The only way to add a user to an org is `POST /v1/memberships/orgs` which
requires the user's UUID. There is no invite-by-email flow. New users have
no self-service path into an org.

## Scope when built

### DB tables (new sub-feature `10_invitations` under `03_iam`)

- `10_fct_invitations` — id, org_id, invited_by, status_id, expires_at, accepted_by, is_active, deleted_at, ...
- `07_dim_invitation_statuses` — pending, accepted, expired, revoked
- `20_dtl_attrs` — invitee_email, token_hash, role_code (owner/admin/member/viewer)

### Endpoints

```
POST   /v1/orgs/{org_id}/invitations          — create invitation (email, role)
GET    /v1/orgs/{org_id}/invitations          — list invitations (status filter, paginated)
GET    /v1/orgs/{org_id}/invitations/{id}     — get invitation
DELETE /v1/orgs/{org_id}/invitations/{id}     — revoke pending invitation

POST   /v1/invitations/accept                 — accept invitation (token in body)
POST   /v1/invitations/resend/{id}            — resend invitation email
```

### Invitation flow

1. Admin calls `POST /v1/orgs/{org_id}/invitations` with email + role.
2. Server generates 32-byte token (`secrets.token_urlsafe(32)`).
3. Token hash (BLAKE2b-256) stored in dtl_attrs. Raw token fired via email.
4. Link: `https://{dashboard}/accept-invite?token={raw_token}`
5. Recipient clicks link → `POST /v1/invitations/accept` with token.
6. Server validates hash + expiry, creates user if needed (or links existing),
   creates org membership, marks invitation accepted.
7. Audit events emitted at both creation and acceptance.

### Rules

- Invitations expire after 7 days (configurable via settings).
- Duplicate invitations to same email + org are rejected (pending one exists).
- Revoking an invitation soft-deletes it and marks status = revoked.
- Rate limit: max 20 pending invitations per org.

### Settings keys

```
iam.invitation_expiry_hours   default: 168 (7 days)
iam.max_pending_invitations   default: 20
```

## Not in scope here

- Workspace invitations (separate but same pattern)
- Bulk invite (CSV upload)
- Public join links (link without specific email)
