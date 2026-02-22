# Release wicked-patch v2.1.1

**Date**: 2026-02-21
**Component**: wicked-patch

## Summary

This release includes: 1 new feature(s), 2 bug fix(es).

## Changes

### Features

- feat: add AGENTS.md support for cross-tool compatibility (#47) (6eab8bf)

### Bug Fixes

- fix: address PR review feedback for risk assessment (#48) (cd965f4)
- fix: make remove_field always HIGH risk in plan assessment (#48) (82d8581)

### Chores

- Merge pull request #49 from mikeparcewski/fix/48-plan-command-cross-file-impact (755883b)
- release: bump 17 plugins (408ac5e)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-patch@wicked-garden
```
