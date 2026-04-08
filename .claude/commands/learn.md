---
description: Extract reusable patterns from this session, evaluate quality, decide global vs project scope, and save. Also evolves clustered instincts into commands/skills/agents.
---

# /learn

Extract the most valuable patterns from this session, evaluate them before saving, and evolve clusters of instincts into higher-order structures.

## Usage

```bash
/learn              # extract + evaluate + save patterns from this session
/learn evolve       # analyze instinct clusters → suggest commands/skills/agents
/learn evolve --generate   # also write the evolved files
```

---

## Mode: extract (default)

### Step 1 — Scan session for extractable patterns

Look for:
- **Error resolution patterns** — root cause + fix + reusability signal
- **Debugging techniques** — non-obvious steps, tool combinations
- **Workarounds** — library quirks, API limitations, version-specific fixes
- **Project conventions discovered** — architecture decisions, integration patterns, gotchas

Skip: trivial fixes (typos, syntax), one-off issues (API outages), anything already documented in CLAUDE.md or rules.

---

### Step 2 — Determine save scope

Ask: "Would this pattern be useful in a different project?"

- **Global** (`~/.claude/skills/learned/`): generic — bash compatibility, LLM behavior, debugging techniques, framework quirks
- **Local** (`.claude/skills/learned/`): project-specific — EAV quirks, router conventions, specific schema gotchas
- When in doubt: Global (moving Global→Local is easier than reverse)

---

### Step 3 — Quality gate

Before saving, run this checklist:

- [ ] Grep existing skills for content overlap — don't duplicate
- [ ] Check MEMORY.md (project + global) for overlap
- [ ] Could this be appended to an existing skill instead?
- [ ] Is this reusable, or a one-off fix?


Then pick a verdict:

| Verdict | Action |
| --- | --- |
| **Save** | Unique, specific, actionable → proceed |
| **Improve then Save** | Valuable but needs refinement → revise once, re-evaluate |
| **Absorb into [X]** | Append to existing skill → show diff, confirm |
| **Drop** | Trivial or redundant → explain and stop |

---

### Step 4 — Draft and save

Skill file format:

```markdown
---
name: pattern-name
description: "Under 130 characters — specific enough to match in future sessions"
origin: auto-extracted
---

# [Pattern Name]

**Extracted:** [date]
**Context:** [when this applies]

## Problem
[what it solves — be specific]

## Solution
[the pattern/technique — with code examples]

## When to Use
[trigger conditions]
```

Save to determined location. Present path + checklist results + 1-line rationale before saving. Confirm with user.

---

## Mode: evolve

Analyze instinct clusters and suggest (or generate) higher-order structures.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/continuous-learning-v2/scripts/instinct-cli.py" evolve [--generate]
```

### Evolution rules

**→ Command** when instincts describe a repeatable user-invoked workflow (2+ instincts with sequential steps)

**→ Skill** when instincts describe auto-triggered behaviors (style enforcement, error responses, pattern matching)

**→ Agent** when instincts describe a complex multi-step process that benefits from isolation

### Output format

```text
EVOLVE ANALYSIS — N instincts

COMMAND CANDIDATES
  /new-table  ← new-table-migration + update-schema + regenerate-types  [84% avg confidence]

SKILL CANDIDATES
  functional-patterns  ← prefer-functional + use-immutable + avoid-classes  [79% avg]

AGENT CANDIDATES
  debugger  ← debug-check-logs + debug-isolate + debug-reproduce + debug-verify  [82% avg]
```

With `--generate`: writes files to `~/.claude/homunculus/projects/<id>/evolved/`.
