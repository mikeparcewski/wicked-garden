# Release wicked-kanban v1.2.1

**Date**: 2026-02-24
**Component**: wicked-kanban

## Summary

This release includes: 3 bug fix(es).

## Changes

### Bug Fixes

- fix(crew,kanban): ensure crew sessions create and persist kanban initiative tracking (909a2fa)
- fix: restore CREW-CORE.md accidentally deleted in doc consolidation (2fef152)
- fix(wicked-smaht): context hook reads wrong input field, never fires (#65) (e4edd01)

### Documentation

- docs: standardize all 17 plugin READMEs to canonical template (0a57fe8)
- docs: rewrite README as ecosystem sales pitch (c6de8fd)

### Chores

- Compare 4 signal-routing architecture versions and add PDF export (#64) (8534871)
- chore: remove stale working documents from repo root (b871427)
- chore: remove stale tests/ and test-results/ directories (984bc0c)
- release: bump 16 plugins (c9322d0)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-kanban@wicked-garden
```
