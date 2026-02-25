# Release wicked-crew v1.2.2

**Date**: 2026-02-25
**Component**: wicked-crew

## Summary

This release includes: 6 new feature(s), 2 bug fix(es).

## Changes

### Features

- feat(smaht): replace hook-based context injection with prompt-embedded dispatch packets (70d9877)
- feat(smaht): replace turn-based context warnings with content pressure tracking (f0aae53)
- feat: add wicked-scenarios format generation to 6 specialist plugins (09e94b9)
- feat(qe,scenarios): consolidate acceptance pipeline — QE owns testing, scenarios is thin CLI backend (7514e56)
- feat(kanban,scenarios): store evidence inline in kanban artifacts (c06924d)
- feat(scenarios): add report command, batch mode, and fix evidence path (b8101ed)

### Bug Fixes

- fix(smaht): prevent subagent context blowout with SubagentStart hook and budget enforcement (d24abb1)
- fix(kanban): remove TaskCompleted prompt hook that blocked combined updates (1a515bc)

### Chores

- release: wicked-smaht v4.2.0 (4e91bf0)
- release: wicked-scenarios v1.6.0, wicked-qe v1.3.0, wicked-product v1.2.1, wicked-engineering v1.2.1, wicked-platform v1.2.1, wicked-data v1.2.1, wicked-agentic v2.2.1 (df7f8da)
- release: wicked-scenarios v1.5.0 (4d5a7c6)
- release: wicked-smaht v4.1.0, wicked-scenarios v1.4.0 (dd2a368)
- release: wicked-crew v1.2.1, wicked-kanban v1.2.1 (c934ff2)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-crew@wicked-garden
```
