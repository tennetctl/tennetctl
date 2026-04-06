# 01_org — Design

The Org sub-feature implements a standard platform-level management pattern using a central identity table and descriptive attributes.

## Data Model
- **Table**: `02_iam.10_fct_orgs`
  - `id`: UUID v7 (Primary Key)
  - `slug`: Unique identifier for URLs/APIs.
  - `status_id`: Reference to `dim_org_statuses`.
  - `is_active`: Operational master switch.
  - `is_test`: Marker for seed/internal data.
- **View**: `02_iam.v_orgs`
  - Resolves `status_id` to code strings.
  - Calculates `is_deleted` flag from `deleted_at`.

## Service Logic
- **Creation**: Validates slug uniqueness across all non-deleted orgs. Initializes status to `trialing` or `active`.
- **Soft Deletion**: Updates `deleted_at` and changes status to `deleted`. This ensures the slug can be reused if a new org with the same name is created later, while preserving the history of the old UUID.
- **Audit**: All mutations (create, update, delete) emit a structured audit event.
