# Release wicked-kanban v0.11.0

**Date**: 2026-02-16
**Component**: wicked-kanban

## Summary

This release includes: 2 new feature(s), 2 bug fix(es).

## Changes

### Features

- feat: workbench dashboard skill refs, scenario rewrites, and cleanup (8e21970)
- feat: add categories, impact, content, and ide-url API verbs (030ffc6)

### Bug Fixes

- fix: kanban board isolation, MEMORY.md write blocking, and hook event corrections (afb3f87)
- fix: workbench proxy item_id path handling and traverse forwarding (077441a)

### Chores

- release: wicked-search v1.7.0, wicked-workbench v0.8.0 (be7cbea)
- release: batch bump 14 plugins to patch (7af7913)
- release: wicked-workbench v0.7.2 (ab35680)
- release: wicked-workbench v0.7.1, wicked-mem v0.8.1, wicked-kanban v0.10.1 (62adb4d)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-kanban@wicked-garden
```
