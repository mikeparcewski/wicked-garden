# Release wicked-mem v1.0.0

**Date**: 2026-02-19
**Component**: wicked-mem

## Summary

This release includes: 1 breaking change(s), 6 new feature(s), 1 bug fix(es).

## Changes

### Breaking Changes

- feat(wicked-search)!: v2.0 — single unified SQLite backend, remove legacy code (92fb403)

### Features

- feat: resolve frontend migration plugin features (#6) (60ffc00)
- feat(wicked-startah): add GitHub issue reporting skill, hooks, and command (63b9515)
- feat(wicked-search): add unified SQLite query layer merging graph DB and JSONL index (14fc856)
- feat(wicked-kanban): add task lifecycle enrichment via TaskCompleted hooks (6916d59)
- feat(wicked-search): add cross-category relationships to categories API (2e9d57b)
- feat(wicked-search): add /wicked-search:categories command (237a055)

### Bug Fixes

- fix(wicked-search): fix graph domain, refs import, and categories performance (96286f8)

### Chores

- release: wicked-search v2.0.1 (b5883a0)
- release: wicked-startah v0.8.0 (2b7e538)
- release: wicked-search v2.0.0 (e07c996)
- release: wicked-kanban v0.12.0 (d6fcf76)
- release: wicked-search v1.9.0 (0463d46)
- chore: remove old release notes superseded by new versions (65e35e7)
- release: batch bump 17 plugins to minor (6ebcf34)

## Upgrade Guide

This release contains breaking changes. Please review the breaking changes above and update your code accordingly.

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-mem@wicked-garden
```
