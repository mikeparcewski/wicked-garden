# Release wicked-startah v0.12.0

**Date**: 2026-02-27
**Component**: wicked-startah

## Summary

This release includes: 8 new feature(s), 7 bug fix(es).

## Changes

### Features

- feat(crew,jam,startah): resolve 6 open GitHub issues #75-80 (eb1c320)
- feat(wg-test): add --batch and --debug flags for parallel scenario execution (cd04d4b)
- feat(smaht): replace hook-based context injection with prompt-embedded dispatch packets (70d9877)
- feat(smaht): replace turn-based context warnings with content pressure tracking (f0aae53)
- feat: add wicked-scenarios format generation to 6 specialist plugins (09e94b9)
- feat(qe,scenarios): consolidate acceptance pipeline — QE owns testing, scenarios is thin CLI backend (7514e56)
- feat(kanban,scenarios): store evidence inline in kanban artifacts (c06924d)
- feat(scenarios): add report command, batch mode, and fix evidence path (b8101ed)

### Bug Fixes

- fix(agentic,crew): resolve all 8 open GitHub issues #67-74 (608954c)
- fix(smaht): fix context injection format and broken adapters (757d1d8)
- fix(smaht): prevent subagent context blowout with SubagentStart hook and budget enforcement (d24abb1)
- fix(kanban): remove TaskCompleted prompt hook that blocked combined updates (1a515bc)
- fix(crew,kanban): ensure crew sessions create and persist kanban initiative tracking (909a2fa)
- fix: restore CREW-CORE.md accidentally deleted in doc consolidation (2fef152)
- fix(wicked-smaht): context hook reads wrong input field, never fires (#65) (e4edd01)

### Documentation

- docs: standardize all 17 plugin READMEs to canonical template (0a57fe8)
- docs: rewrite README as ecosystem sales pitch (c6de8fd)

### Chores

- release: wicked-observability v1.0.0, wicked-crew v1.2.3 (0e7f74b)
- release: wicked-smaht v4.3.1 (70f3e83)
- release: wicked-smaht v4.3.0, wicked-crew v1.2.2 (7ee6b25)
- release: wicked-smaht v4.2.0 (4e91bf0)
- release: wicked-scenarios v1.6.0, wicked-qe v1.3.0, wicked-product v1.2.1, wicked-engineering v1.2.1, wicked-platform v1.2.1, wicked-data v1.2.1, wicked-agentic v2.2.1 (df7f8da)
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
claude plugin install wicked-startah@wicked-garden
```
