# Release wicked-workbench v0.3.0

**Date**: 2026-02-09
**Component**: wicked-workbench

## Summary

This release includes: 1 new feature(s), 1 bug fix(es).

## Changes

### Features

- feat(wicked-workbench): add ACP-powered dynamic UI with React frontend (ba27700)

### Bug Fixes

- fix: resolve plugin structure issues across 6 plugins (ce3419f)

### Refactoring

- refactor: convert 29 commands from prose dispatch to Task() subagent calls (270b2cb)

### Chores

- release: bump all 18 plugins with changelogs and release notes (b0ec55d)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-workbench@wicked-garden
```
