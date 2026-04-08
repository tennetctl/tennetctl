## Planned: Block Secrets from CLI Flags

**Severity if unbuilt:** CRITICAL
**Affects:** `00_setup` wizard, not IAM runtime
**Depends on:** nothing (pure CLI change)

## Problem

`tennetctl setup` accepts `--root-unseal-key`, `--root-read-key`, and
`--admin-password` as CLI flags. Any value passed as a flag is recorded in
shell history (`~/.zsh_history`, `~/.bash_history`) and visible in
`ps aux` output while the process is running. A compromised machine leaks
all three secrets trivially.

## Fix when built

- Remove the `--root-unseal-key`, `--root-read-key`, and `--admin-password`
  flags from the CLI entirely.
- Accept these values only via:
  1. Interactive prompt (`rich.Prompt.ask(..., password=True)`) — already
     the default path; this fix makes it the *only* path.
  2. Environment variables (`TENNETCTL_ROOT_UNSEAL_KEY`, etc.) — document
     that the caller should set them in a subshell without history:
     `set +o history; export TENNETCTL_ROOT_UNSEAL_KEY=...; tennetctl setup`.
- If an env var is detected, print a one-time warning:
  "Secret loaded from env var — ensure shell history is disabled for this
  session."
- Location: `scripts/setup/wizard/cli.py` argument parser.
