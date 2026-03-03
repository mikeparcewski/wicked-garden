# Release wicked-garden v1.11.0

**Date**: 2026-03-03
**Component**: wicked-garden

## Summary

This release includes: 1 new feature(s), 4 bug fix(es).

## Changes

### Features

- feat: resolve 10 enhancement issues (#153-#157, #165, #175, #179-#181) (579fa15)

### Bug Fixes

- fix: quote argument-hint YAML values in 34 command files (84fea1f)
- fix: resolve remaining open issues (#169-#171, #174, #178) (bd470da)
- fix: resolve 9 test-run bugs and migrate search to local-first (#158-#168) (c419303)
- fix(kanban): fix KanbanStore import shadowed by package __init__.py (0a9a0b4)

### Chores

- Merge pull request #183 from mikeparcewski/feat/resolve-enhancement-issues (00eddfb)
- Merge pull request #182 from mikeparcewski/fix/resolve-all-open-issues (4a98663)
- release: wicked-garden v1.10.1 (10bdb6b)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-garden@wicked-garden
```
