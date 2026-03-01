# Release wicked-garden v1.3.2

**Date**: 2026-03-01
**Component**: wicked-garden

## Summary

This release includes: 1 new feature(s), 3 bug fix(es).

## Changes

### Features

- feat: add trigger phrases to agentic skills and split oversized refs (#121, #122) (28be533)

### Bug Fixes

- fix: replace glob refs with explicit links, fix escaped code fences (9c719f3)
- fix: include CP error messages in stop hook output, sanitize task subjects (f61c0d7)
- fix: resolve wg-check findings #117-#120 (65b1f46)

### Refactoring

- refactor: organize scenarios by domain and block native plan mode (22f6839)

### Chores

- Merge pull request #124 from mikeparcewski/feat/121-122-wg-check-enhancements (bfdb902)
- Merge pull request #123 from mikeparcewski/fix/117-120-wg-check-bugs (de17e2a)
- release: wicked-garden v1.3.1 (4e32282)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-garden@wicked-garden
```
