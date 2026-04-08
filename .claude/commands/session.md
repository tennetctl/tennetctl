---
description: Manage work sessions — save state, resume from last session, list history, create checkpoints.
---

# /session

Save and restore work context across Claude Code sessions.

## Usage

```bash
/session save        # save current session state to file
/session resume      # load most recent session and orient
/session list        # list all saved sessions
/session checkpoint  # create a named checkpoint in git
```

---

## save

Capture everything that happened — what was built, what worked, what failed, what's next — and write it to `~/.claude/session-data/YYYY-MM-DD-HH-MM.md`.

Run before:

- Closing Claude Code at end of day
- Hitting context limits (save first, then start fresh)
- Handing off to a future session

**Process:**

1. Summarize what was accomplished this session
2. List files created or modified (with brief note on each)
3. Capture decisions made and why
4. Note blockers, open questions, and next steps
5. Record current branch, last commit, and any uncommitted changes
6. Write to `~/.claude/session-data/YYYY-MM-DD-HH-MM-<slug>.md`

---

## resume

Load the most recent session file and fully orient before doing any work.

```bash
/session resume                          # load most recent
/session resume ~/.claude/session-data/2026-04-01-build-iam.md   # load specific
```

**Process:**

1. Find the most recent file in `~/.claude/session-data/` (or use path from args)
2. Read it fully
3. Check current git status against the saved state
4. Summarize: what was done, what's in progress, what's next
5. Ask if ready to continue or if the plan has changed

---

## list

List saved sessions with metadata.

```bash
/session list
/session list --last 10
```

Reads `~/.claude/session-data/` and `~/.claude/sessions/` (legacy). Shows date, slug, branch, and a one-line summary.

---

## checkpoint

Create a named checkpoint — verify state, commit or stash, log it.

```bash
/session checkpoint              # auto-name from current work
/session checkpoint pre-refactor # named checkpoint
/session checkpoint verify       # verify existing checkpoints
/session checkpoint list         # list all checkpoints
```

**Process:**

1. Run quick verify (build + types) — stop and report if failing
2. Commit or stash current changes with the checkpoint name
3. Log to `.claude/checkpoints.log`:

```bash
echo "$(date +%Y-%m-%d-%H:%M) | $NAME | $(git rev-parse --short HEAD)" >> .claude/checkpoints.log
```

4. Confirm checkpoint created with hash
