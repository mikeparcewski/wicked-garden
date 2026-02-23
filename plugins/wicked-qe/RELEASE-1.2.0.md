# Release wicked-qe v1.2.0

**Date**: 2026-02-23
**Component**: wicked-qe

## Summary

This release includes: 2 new feature(s), 4 bug fix(es).

## Changes

### Features

- feat: evidence-gated scenario testing with three-agent architecture (f3a9ed0)
- feat: add AGENTS.md support for cross-tool compatibility (#47) (6eab8bf)

### Bug Fixes

- fix: restore grouping title format and deduplication skip logic (2b554bb)
- fix: rewrite wicked-patch scenarios to match actual CLI (#51) (#54) (a58b12d)
- fix: address PR review feedback for risk assessment (#48) (cd965f4)
- fix: make remove_field always HIGH risk in plan assessment (#48) (82d8581)

### Chores

- release: wicked-patch v2.1.1 (7f8868d)
- Merge pull request #49 from mikeparcewski/fix/48-plan-command-cross-file-impact (755883b)
- release: bump 17 plugins (408ac5e)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-qe@wicked-garden
```
