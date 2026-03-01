# Release wicked-garden v1.3.3

**Date**: 2026-03-01
**Component**: wicked-garden

## Summary

This release includes: 3 bug fix(es).

## Changes

### Bug Fixes

- fix: update specialist names, add trigger phrases, remove redundant sections (#128, #129, #130) (fd0f29a)
- fix(crew): specialist discovery now parses unified specialists array (3992295)
- fix: resolve 3 critical bugs found by wg-test --all (#125) (595dcc3)

### Refactoring

- refactor: split 4 oversized agentic refs/ files into focused modules (#127) (0f90477)

### Chores

- Merge pull request #132 from mikeparcewski/feat/127-split-oversized-refs (69f6134)
- Merge pull request #131 from mikeparcewski/fix/128-130-skill-content-fixes (c77179d)
- Merge pull request #126 from mikeparcewski/claude/run-wg-tests-q9fco (cb04016)
- release: wicked-garden v1.3.2 (6506ee5)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-garden@wicked-garden
```
