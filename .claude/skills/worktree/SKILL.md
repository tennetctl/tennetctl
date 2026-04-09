---
name: worktree
description: Manage ephemeral git worktrees for parallel feature sessions. Create, list, delete, and clean up worktrees. Every task gets its own worktree, deleted immediately after PR merge.
origin: custom
---

# Worktree — Parallel Session Management

Every task gets its own ephemeral worktree. Create before working, delete after PR merge. Never let worktrees accumulate.

## Commands

**Create for a new sub-feature build:**
`/worktree create 02_iam/02_user`

**Create for an enhancement:**
`/worktree create 02_iam/02_user enhance-rate-limiting`

**List all active worktrees:**
`/worktree list`

**Delete one after PR merge:**
`/worktree delete 02_user`

**Clean all whose remote branch is gone (merged):**
`/worktree clean`

## Naming Convention

| Operation | Branch | Directory |
|---|---|---|
| Build `02_iam/02_user` | `feat/02_iam-02_user` | `worktrees/02_user` |
| Enhance rate-limiting on user | `feat/02_iam-02_user-enhance-rate-limiting` | `worktrees/02_user-enhance-rate-limiting` |

## How Create Works

Parse input as `{module}/{sub_feature}` plus optional task slug. Branch off the project's integration branch. Create the worktree in `worktrees/{name}`. Print the directory, branch, and instructions for opening a new terminal pane.

## Lifecycle

1. **Create** — new worktree for the task
2. **Work** — open in new terminal pane, run `/build-sub-feature` or `/enhance-sub-feature`
3. **PR** — push and open PR targeting the integration branch
4. **Merge** — merge on GitHub
5. **Delete** — immediately remove the worktree and branch

Delete is mandatory after every merge. Stale worktrees cause old state to bleed into new work.

## Why Ephemeral

Reusing worktrees causes mixed commit histories that pollute PR diffs and risk two sessions colliding on shared files. Ephemeral worktrees give you a fresh directory, a clean branch, and zero collision every time.

## Recovery

If a worktree is stuck and won't remove normally, force-remove it and prune stale git internal references.
