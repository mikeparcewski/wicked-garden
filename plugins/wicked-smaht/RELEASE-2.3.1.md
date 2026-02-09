# Release wicked-smaht v2.3.1

**Date**: 2026-02-08
**Component**: wicked-smaht

## Summary

This release includes: 3 new feature(s).

## Changes

### Features

- feat(wicked-qe): integrate with wicked-scenarios for E2E scenario discovery and execution (6538a71)
- feat(wicked-mem): add PostToolUse nudge for MEMORY.md direct edits (a15db3f)
- feat: add wicked-scenarios plugin for E2E testing via markdown scenarios (c7d4422)

### Documentation

- docs: rewrite all 17 plugin READMEs with sell-first structure (c30ebec)

### Chores

- chore: add wicked-scenarios to marketplace catalog (74de311)
- chore: remove old release notes replaced by new versions (39955d9)
- release: bump 8 plugins - dynamic flow, friction fixes, batch release (49dfd00)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-smaht@wicked-garden
```
