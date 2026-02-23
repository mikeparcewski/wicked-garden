# Release wicked-startah v0.11.0

**Date**: 2026-02-23
**Component**: wicked-startah

## Summary

This release includes: 3 new feature(s), 5 bug fix(es).

## Changes

### Features

- feat: add TypeScript type definitions for wicked-search and wicked-workbench APIs (#59 #61) (017c4f0)
- feat: evidence-gated scenario testing with three-agent architecture (ff4fc7a)
- feat: add AGENTS.md support for cross-tool compatibility (#47) (6eab8bf)

### Bug Fixes

- fix: resolve scenario spec mismatches and add wicked-agentic scenarios (#62 #63) (4ab91cc)
- fix: resolve 3 UAT failures + address PR #57 review comments (#58) (9472da7)
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
claude plugin install wicked-startah@wicked-garden
```
