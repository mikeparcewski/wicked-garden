# Release wicked-smaht v4.2.0

**Date**: 2026-02-25
**Component**: wicked-smaht

## Summary

This release includes: 5 new feature(s).

## Changes

### Features

- feat(smaht): replace turn-based context warnings with content pressure tracking (f0aae53)
- feat: add wicked-scenarios format generation to 6 specialist plugins (09e94b9)
- feat(qe,scenarios): consolidate acceptance pipeline — QE owns testing, scenarios is thin CLI backend (7514e56)
- feat(kanban,scenarios): store evidence inline in kanban artifacts (c06924d)
- feat(scenarios): add report command, batch mode, and fix evidence path (b8101ed)

### Chores

- release: wicked-scenarios v1.6.0, wicked-qe v1.3.0, wicked-product v1.2.1, wicked-engineering v1.2.1, wicked-platform v1.2.1, wicked-data v1.2.1, wicked-agentic v2.2.1 (df7f8da)
- release: wicked-scenarios v1.5.0 (4d5a7c6)
- release: wicked-smaht v4.1.0, wicked-scenarios v1.4.0 (dd2a368)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-smaht@wicked-garden
```
