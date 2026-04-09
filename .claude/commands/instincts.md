---
description: Manage learned instincts — view status, export, import, promote to global, prune stale, and list projects.
---

# /instincts

Single command for all instinct lifecycle management.

## Usage

```bash
/instincts              # show status (default)
/instincts export       # export instincts to file
/instincts import <file-or-url>   # import from file or URL
/instincts promote      # promote project instincts to global
/instincts prune        # delete pending instincts older than 30 days
/instincts projects     # list all known projects + instinct counts
```

All subcommands run via:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/continuous-learning-v2/scripts/instinct-cli.py" <subcommand> [flags]
```

---

## status (default)

Show all instincts grouped by domain with confidence bars.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/continuous-learning-v2/scripts/instinct-cli.py" status
```

Output:

```
INSTINCT STATUS — 12 total
Project: my-app (a1b2c3d4e5f6)  |  Project: 8  |  Global: 4

PROJECT-SCOPED
  WORKFLOW (3)
    ███████░░░  70%  grep-before-edit    trigger: when modifying code

GLOBAL
  SECURITY (2)
    █████████░  85%  validate-user-input  trigger: when handling user input
```

---

## export

```bash
/instincts export
/instincts export --domain testing
/instincts export --min-confidence 0.7
/instincts export --scope project --output project-instincts.yaml
```

Flags: `--domain`, `--min-confidence`, `--scope project|global|all`, `--output <file>`

---

## import

```bash
/instincts import team-instincts.yaml
/instincts import https://github.com/org/repo/instincts.yaml
/instincts import team-instincts.yaml --dry-run
/instincts import team-instincts.yaml --scope global --force
```

Shows conflicts before writing. Higher-confidence import wins on ID collision.

Flags: `--dry-run`, `--force`, `--min-confidence`, `--scope project|global`

---

## promote

Promote project-scoped instincts to global (cross-project reuse).

```bash
/instincts promote                  # auto-detect candidates
/instincts promote grep-before-edit # promote one specific instinct
/instincts promote --dry-run
/instincts promote --force
```

Candidates: appear in 2+ projects and meet confidence threshold.

---

## prune

Delete pending instincts that were never reviewed or promoted.

```bash
/instincts prune                # delete instincts older than 30 days
/instincts prune --max-age 60
/instincts prune --dry-run
```

---

## projects

List all known projects with instinct counts and last-seen timestamps.

```bash
/instincts projects
```
