---
name: git-marker-cleaner
description: "Use when scanning the FROID workspace for Git conflict markers or when a user explicitly requests a report of unresolved merge markers. The bundled cleaner may remove marker lines only after explicit confirmation."
---

# Git Marker Cleaner

Use the bundled `git_marker_cleaner.py` to scan a workspace for common Git conflict marker lines and, only after explicit confirmation, resolve them interactively.

## Workflow

1. Run a report-only scan first:

   `python .claude/skills/git-marker-cleaner/git_marker_cleaner.py <directory>`

2. Review every reported file and line before making changes.
3. Do not use `--clean` automatically.
4. If the user explicitly confirms removal, run:

   `python .claude/skills/git-marker-cleaner/git_marker_cleaner.py <directory> --clean`

5. Inspect the diff and run the affected project's tests or build checks.

## Important limitation

`--clean` opens an interactive resolver. It supports standard Git conflicts and displays the base section of diff3 conflicts without treating that base as a selectable version. It does not prove that the selected result is valid code. Concatenation can still produce invalid source code, so inspect the diff and run project checks afterward.

The scanner skips `.git`, `node_modules`, `__pycache__`, `venv`, `.venv`, `dist`, and `build` by default. Read errors are reported. Resolved files preserve UTF-8 BOM and line endings and are replaced atomically. Files using another encoding must be handled manually.

Exit codes are `0` for a clean scan, `1` when conflicts remain, and `2` for read or post-resolution errors.
