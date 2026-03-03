# wicked-garden v1.10.0

## Summary

Enforces domain boundaries across the monoplugin. Crew commands no longer reach directly into kanban and smaht scripts — they delegate through proper command interfaces instead.

## What Changed

### New Commands

- **`/wicked-garden:kanban:initiative`** — Manage kanban initiatives (lookup, create, ensure-issues). Previously only available as a raw script call.
- **`/wicked-garden:smaht:context`** — Build structured context packages for subagent dispatches. Replaces direct `context_package.py` script calls from other domains.

### Bug Fixes

- **Cross-domain script coupling resolved** — `crew/start.md` was calling `kanban_initiative.py` directly; `crew/execute.md` and `crew/just-finish.md` were calling `smaht/context_package.py` directly. All now delegate through domain commands via Skill.
- **Broken variable fixed** — `{CREW_PLUGIN_ROOT}` (missing `$`) in `crew/execute.md` line 580 corrected to `${CLAUDE_PLUGIN_ROOT}`.
- **Wrong script path fixed** — `smaht/debug.md` referenced `scripts/context_package.py` instead of `scripts/smaht/context_package.py`.

### Cleanup

- Removed stale `RELEASE-1.7.1.md` and `RELEASE-1.8.0.md`.

## Upgrade Notes

No breaking changes. The new commands are additive. Existing crew workflows will now route through kanban and smaht domain commands instead of calling scripts directly — behavior is identical, but domain boundaries are properly enforced.
