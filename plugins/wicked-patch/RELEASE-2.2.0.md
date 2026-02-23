# Release wicked-patch v2.2.0

**Date**: 2026-02-23
**Component**: wicked-patch

## Summary

This release includes: 2 new feature(s), 3 bug fix(es).

## Changes

### Features

- feat: add TypeScript type definitions for wicked-search and wicked-workbench APIs (#59 #61) (017c4f0)
- feat: evidence-gated scenario testing with three-agent architecture (ff4fc7a)

### Bug Fixes

- fix: resolve scenario spec mismatches and add wicked-agentic scenarios (#62 #63) (4ab91cc)
- fix: resolve 3 UAT failures + address PR #57 review comments (#58) (9472da7)
- fix: rewrite wicked-patch scenarios to match actual CLI (#51) (#54) (a58b12d)

### Chores

- release: wicked-patch v2.1.1 (7f8868d)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-patch@wicked-garden
```
