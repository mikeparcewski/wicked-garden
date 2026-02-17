# Release wicked-search v2.0.0

**Date**: 2026-02-17
**Component**: wicked-search

## Summary

This release includes: 1 breaking change(s), 2 new feature(s).

## Changes

### Breaking Changes

- feat(wicked-search)!: v2.0 — single unified SQLite backend, remove legacy code (92fb403)

### Features

- feat(wicked-search): add unified SQLite query layer merging graph DB and JSONL index (14fc856)
- feat(wicked-kanban): add task lifecycle enrichment via TaskCompleted hooks (6916d59)

### Chores

- release: wicked-kanban v0.12.0 (d6fcf76)
- release: wicked-search v1.9.0 (0463d46)

## Upgrade Guide

This release contains breaking changes. Please review the breaking changes above and update your code accordingly.

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-search@wicked-garden
```
