---
name: ralph-prompt
description: Craft a precise, iteration-safe Ralph Loop prompt for any task. Use before running /ralph-loop to ensure the prompt has clear success criteria, self-correction instructions, and an escape hatch.
origin: custom
---

# Ralph Prompt

Use this skill to generate a structured prompt and the exact `/ralph-loop:ralph-loop` command before starting any autonomous loop. A poorly written Ralph prompt leads to wasted iterations, infinite loops, or silent failures.

## When to Activate

Before any `/ralph-loop:ralph-loop` invocation — especially for multi-step tasks with testable outputs.

## How Ralph Works

Ralph writes the prompt to `.claude/.ralph-loop.local.md` and runs the task. When Claude tries to exit, the Stop hook feeds the same prompt back. Claude sees its previous work in files and git history, not in conversation context. The loop exits when Claude outputs a `<promise>` tag matching the `--completion-promise`, or when `--max-iterations` is hit.

**Critical constraints:**
- The prompt never changes between iterations — write it to survive being re-read many times
- Claude cannot remember conversation context across iterations — only files and git
- The promise tag uses exact string matching — no variations
- Never output the promise unless all stated conditions are genuinely, verifiably true

## Prompt Structure

Every Ralph prompt needs these sections:

**Context** — What exists, what stack, where to look first. Include the repo path and key file locations.

**Thinking Prefix** — For complex or ambiguous tasks, start with `"think step by step"` or `"think hard about"` before critical decisions. This triggers high-effort reasoning so Claude plans before acting, reducing wasted iterations.

**Task** — Numbered list of exactly what to build, fix, or change. Be specific — file paths, function names, exact behaviors.

**Self-Correction Loop** — For each iteration: run the verification command, if it fails read the error and fix the root cause, if it passes run the full test suite, if all green output the completion promise.

**Constraints** — Non-negotiables: patterns to follow, files not to touch, commit after each meaningful change, never redo already-committed work.

**Verification Command** — The single command that proves the task is done.

**Completion Criteria** — All conditions that must be TRUE before outputting the promise. Specific and verifiable.

**Escape Hatch** — If stuck for 3 iterations with no progress, write a `BLOCKED.md` explaining what was attempted, then output the promise to avoid infinite loops.

## Iteration Limits

| Task complexity | Recommended max-iterations |
|---|---|
| Simple bug fix | 5–10 |
| Single feature (1 endpoint, 1 page) | 15–20 |
| Multi-phase feature | 30–50 |
| Greenfield build | 50–100 |

Always set `--max-iterations`. Always set `--completion-promise`. Never run without both.

## Command Format

```
/ralph-loop:ralph-loop "{task description}" --completion-promise "TASK COMPLETE" --max-iterations 20
```

## Common Mistakes

- Vague tasks like "make auth work" — use specific file paths and function names
- No verification command — always include the exact command that proves doneness
- No escape hatch — always include the blocked-after-3-iterations fallback
- Testing against mocks only — integration tests must hit real dependencies
- Outputting the promise on partial completion — the promise means ALL criteria are verifiably true
