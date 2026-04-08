---
description: Look up library docs via Context7, update project codemaps, and sync documentation with the codebase.
---

# /docs

Three modes: look up external docs, update architecture codemaps, sync project documentation.

## Usage

```bash
/docs <library> <question>     # look up library/framework docs
/docs codemaps                 # regenerate architecture codemaps
/docs update                   # sync docs from source-of-truth files
```

---

## Mode: lookup (default)

Look up current documentation for a library, framework, or API via Context7.

```bash
/docs next.js "how do I configure middleware?"
/docs fastapi "dependency injection patterns"
/docs prisma "upsert with relations"
```

**Process:**

1. Call `resolve-library-id` with the library name and question
2. Call `query-docs` with the resolved ID and question
3. Return a concise answer with relevant code examples
4. Note the library version if relevant

If Context7 is unavailable, answer from training data with a note that docs may be outdated.

---

## Mode: codemaps

Analyze codebase structure and generate token-lean architecture docs in `docs/CODEMAPS/`.

```bash
/docs codemaps
```

**Files generated:**

| File | Contents |
| --- | --- |
| `architecture.md` | System diagram, service boundaries, data flow |
| `backend.md` | API routes, middleware chain, service→repo mapping |
| `frontend.md` | Page tree, component hierarchy, state management |
| `data.md` | DB tables, relationships, migration history |
| `dependencies.md` | External services, integrations, shared libraries |

**Format** — token-lean, optimized for AI context:

```markdown
## Routes
POST /api/users → UserController.create → UserService.create → UserRepo.insert

## Key Files
src/services/user.ts (business logic, 120 lines)

## Dependencies
- PostgreSQL (primary store)
- Redis (session cache)
```

Each codemap should stay under 1000 tokens. Use ASCII diagrams over verbose prose.

**If codemaps already exist:** diff the changes. If >30% changed, show diff and ask before overwriting.

Add freshness header to each file: `<!-- Generated: YYYY-MM-DD | Files: N | ~N tokens -->`

---

## Mode: update

Sync documentation from source-of-truth files. Never manually edit generated sections.

```bash
/docs update
```

**Sources → generated docs:**

| Source | Generates |
| --- | --- |
| `package.json` / `pyproject.toml` scripts | Command reference table |
| `.env.example` | Environment variable docs |
| Route files / `openapi.yaml` | API endpoint reference |
| `Dockerfile` / `docker-compose.yml` | Infrastructure setup |

**Process:**

1. Read each source file
2. Extract scripts, env vars, routes, infrastructure
3. Update the relevant doc section (marked `<!-- AUTO-GENERATED -->`)
4. Preserve all hand-written prose outside those markers
5. Flag docs not modified in 90+ days as potentially stale

**Output:**

```text
Documentation Update
Updated:  docs/CONTRIBUTING.md (scripts table)
Updated:  docs/ENV.md (3 new variables)
Flagged:  docs/DEPLOY.md (142 days stale)
Skipped:  docs/API.md (no changes detected)
```

Only create new doc files if explicitly requested.
