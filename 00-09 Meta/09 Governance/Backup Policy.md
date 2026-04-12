---
type: governance
tags: [meta, governance]
last_reviewed: 2026-04-12
---

# Backup Policy

## Primary Sync: Git

The vault lives inside the Workflow Manager git repository. **Git is the source of truth.**

- **Obsidian Git plugin** handles auto-commit on a 10-minute interval.
- Push to the private GitHub remote regularly (at minimum: end of each work session).
- `.obsidian/workspace.json`, `graph.json`, `hotkeys.json`, and plugin `data.json` files are gitignored — they contain per-user state.
- Core config files (`app.json`, `core-plugins.json`, `community-plugins.json`, `appearance.json`, `daily-notes.json`) ARE committed so any team member gets shared defaults.

## What NOT to Use for Vault Sync

- **iCloud** — silent sync failures documented. Do not store the vault in an iCloud-synced folder.
- **Dropbox** — merge conflicts on .md files are messy. Not recommended.
- **Google Drive** — silent file rename issues. Not recommended for the vault folder itself.
- **OneDrive** — the repo is currently on OneDrive (Desktop path). This works because git is the actual sync mechanism, but be aware that OneDrive may create conflict copies if Obsidian and OneDrive sync collide. Monitor for `filename (1).md` duplicates.

## Secondary Backup

Consider adding a nightly tar/zip to S3, B2, or another off-site location. This is not set up yet — add it when the vault has 100+ notes.

## Version History

- **Git commit history** is the authoritative version record.
- **File Recovery** core plugin provides per-session snapshots (7-day rolling window).
- If you ever need to recover a deleted note, check `git log -- "path/to/note.md"` first.

## Obsidian Sync

Not currently used. Consider adding Obsidian Sync ($4-10/mo) only if:
- The team grows past 2 active editors and git friction becomes real.
- You need mobile sync without a git client on your phone.

## Disaster Recovery

If the vault is corrupted:
1. Check `git status` for uncommitted changes.
2. Stash or commit any salvageable work.
3. `git checkout -- .` to restore the last committed state.
4. If the `.obsidian/` config is broken, delete it and re-open Obsidian (it will regenerate defaults from the committed config files).
