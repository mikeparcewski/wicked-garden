# Release wicked-crew v0.11.0

**Date**: 2026-02-10
**Component**: wicked-crew

## Summary

This release includes: 1 new feature(s).

## Changes

### Features

- feat(wicked-crew): signal model v2 with confidence scoring, semantic detection, and feedback loop (279e54c)

### Documentation

- docs: explain multi-dimensional risk scoring in READMEs (ab6f9a6)
- docs: expand CLAUDE.md with architecture, patterns, and conventions (999707d)

### Chores

- Merge remote-tracking branch 'origin/main' (f1f0e12)
- release: bump 18 plugins (bc1a9ed)
- Merge pull request #1 from arturl/main (6eefef4)
- Update plugins/wicked-engineering/commands/review.md (b9c8105)
- Add --focus tests to review command for LLM-generated test quality (6d729bb)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-crew@wicked-garden
```
