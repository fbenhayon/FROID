# Git Marker Cleaner

## Classification

This artifact is archived as a **workspace skill**, not a custom agent.

Reason: it is an on-demand workflow with a bundled executable script. It does not require an autonomous persona, context isolation, or delegation to a separate subagent.

## Version decision

- Version 1: superseded and retired from the active implementation.
- Version 2: retained as the active implementation and hardened with diff3 display, atomic writes, UTF-8 BOM and line-ending preservation, read-error reporting, and exit codes.
- The original downloaded files in `C:\Users\Fabio\Downloads` were not deleted. They remain external backups.

## Operational caution

The resolver is interactive and does not guarantee semantic correctness. Choices that concatenate both sides can still produce invalid code. Review the resulting diff and run the affected project's checks after every resolution.

## Current location

`.claude/skills/git-marker-cleaner/`
