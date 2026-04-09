# Screenshots and Change Tracking

Every PR that changes the database, API, or UI must include visual documentation. This keeps the repo easy to navigate and makes code review faster.

---

## When Screenshots Are Required

| Change Type | Screenshot Required? | What to Capture |
|-------------|---------------------|-----------------|
| New UI page/component | Yes | Full page screenshot |
| UI modification | Yes | Before and after |
| New database table | Yes | Schema diagram or `\d+ table` output |
| Database schema change | Yes | Before and after `\d+ table` |
| New API endpoint | No (API contract YAML is sufficient) | — |
| Modified API response | Optional | Postman/curl response showing the change |

---

## How to Capture Screenshots

### UI Screenshots

1. Run the dev server: `npm run dev`
2. Navigate to the changed page
3. Take a full-page screenshot
4. Save as PNG in the PR (attach to PR body, do not commit to repo)

### Database Schema Screenshots

Use `psql` to capture the table structure:

```bash
# Connect to the database
docker compose exec postgres psql -U tennetctl -d tennetctl

# Show table structure
\d+ "02_iam"."11_fct_orgs"

# Show view definition
\d+ "02_iam".v_orgs

# List all tables in a schema
\dt+ "02_iam".*
```

Take a screenshot of the terminal output, or copy-paste into the PR as a code block.

### API Response Screenshots

Use `curl` or a tool like Postman:

```bash
# Example: capture a response
curl -s http://localhost:51734/api/v1/orgs | python -m json.tool
```

---

## Where Screenshots Go

### In PRs (Required)

Attach screenshots directly in the PR body under the `## Screenshots` section:

```markdown
## Screenshots

### Before
![Before - Org list page](screenshot-before.png)

### After
![After - Org list page with status column](screenshot-after.png)

### Database Schema
```
tennetctl=# \d+ "02_iam"."11_fct_orgs"
                           Table "02_iam.11_fct_orgs"
   Column    |            Type             |     Description
-------------+-----------------------------+---------------------
 id          | character varying(36)       | UUID v7 primary key
 status_id   | smallint                    | References dim_org_statuses
 is_active   | boolean                     | Whether org is active
 ...
```
```

### In Documentation (Optional)

For significant UI features, you may add screenshots to the sub-feature's `04_user_guide.md`:

```
03_docs/features/{module}/05_sub_features/{sub_feature}/screenshots/
├── 01_list_view.png
├── 02_create_form.png
└── 03_detail_page.png
```

Reference them in the user guide:

```markdown
## Creating an Organisation

![Create org form](screenshots/02_create_form.png)
```

---

## Change Tracking in Worklogs

Every enhancement updates the sub-feature's `08_worklog.md`:

```markdown
## 2026-04-06 — Enhancement: Add department attribute to users

### What changed
Added `department` as a new EAV attribute on users. The attribute appears
in the user detail view and can be set during user creation or profile update.

### Database changes
- New `dim_attr_defs` entry: `department` (id=8, entity_type=user)
- View `v_users` updated to materialize `department`
- No ALTER TABLE — property stored in `dtl_attrs`

### API changes
- `GET /v1/users/{id}` now includes `department` in response
- `PATCH /v1/users/{id}` accepts `department` field

### Screenshots
See PR #142 for before/after screenshots.
```

---

## PR Body Template

Use this template for every PR:

```markdown
## What this PR does
{2-3 sentences describing the change}

## Why
{Link to issue or motivation}

## Sub-feature
Module: {module}
Sub-feature: {nn}_{name}

## Database changes
- New dim entries: {list or "none"}
- New attr_defs: {list or "none"}
- New tables: {list or "none"}
- Modified views: {list or "none"}
- ALTER TABLE: {list or "none"}

## API changes
- New endpoints: {list or "none"}
- Modified endpoints: {list or "none"}

## Screenshots

### UI Changes (if any)
{Attach before/after screenshots}

### Database Changes (if any)
{Paste \d+ output or attach schema diagram}

## Testing
- [ ] pytest tests pass
- [ ] Robot Framework API tests pass
- [ ] Robot Framework E2E tests pass (if UI changed)
- [ ] Coverage at 80%+

## Checklist
- [ ] worklog.md updated
- [ ] API contract updated
- [ ] No file exceeds 500 lines
- [ ] Audit events emitted
- [ ] Properties in dtl_attrs, not fct_* columns
```

---

## Schema Diagram Guidelines

When adding new tables or relationships, create a simple diagram showing the relationships:

```
┌─────────────────────┐
│  11_fct_orgs        │
│  ─────────────────  │
│  id (PK)            │
│  status_id (FK)  ───┼──→  01_dim_org_statuses
│  is_active          │
│  deleted_at         │
│  created_at         │
└─────────┬───────────┘
          │
          │ entity_id
          ▼
┌─────────────────────┐
│  20_dtl_attrs       │
│  ─────────────────  │
│  entity_type_id     │
│  entity_id          │
│  attr_def_id (FK) ──┼──→  07_dim_attr_defs
│  key_text           │
│  key_jsonb          │
└─────────────────────┘
```

You can create these as ASCII art in markdown or use a tool like dbdiagram.io and attach the screenshot.

---

## Checklist — Screenshot Requirements

- [ ] UI changes: before and after screenshots attached to PR
- [ ] New tables: `\d+` output or schema diagram included
- [ ] Schema changes: before and after `\d+` output
- [ ] worklog.md updated with change description
- [ ] PR body follows the template above
