# Release wicked-agentic v2.2.1

**Date**: 2026-02-25
**Component**: wicked-agentic

## Summary

This release includes: 4 new feature(s), 5 bug fix(es).

## Changes

### Features

- feat: add wicked-scenarios format generation to 6 specialist plugins (09e94b9)
- feat(qe,scenarios): consolidate acceptance pipeline — QE owns testing, scenarios is thin CLI backend (7514e56)
- feat(kanban,scenarios): store evidence inline in kanban artifacts (c06924d)
- feat(scenarios): add report command, batch mode, and fix evidence path (b8101ed)

### Bug Fixes

- fix(smaht): prevent subagent context blowout with SubagentStart hook and budget enforcement (d24abb1)
- fix(kanban): remove TaskCompleted prompt hook that blocked combined updates (1a515bc)
- fix(crew,kanban): ensure crew sessions create and persist kanban initiative tracking (909a2fa)
- fix: restore CREW-CORE.md accidentally deleted in doc consolidation (2fef152)
- fix(wicked-smaht): context hook reads wrong input field, never fires (#65) (e4edd01)

### Documentation

- docs: standardize all 17 plugin READMEs to canonical template (0a57fe8)
- docs: rewrite README as ecosystem sales pitch (c6de8fd)

### Chores

- release: wicked-scenarios v1.5.0 (4d5a7c6)
- release: wicked-smaht v4.1.0, wicked-scenarios v1.4.0 (dd2a368)
- release: wicked-crew v1.2.1, wicked-kanban v1.2.1 (c934ff2)
- Compare 4 signal-routing architecture versions and add PDF export (#64) (8534871)
- chore: remove stale working documents from repo root (b871427)
- chore: remove stale tests/ and test-results/ directories (984bc0c)
- release: bump 16 plugins (c9322d0)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-agentic@wicked-garden
```
