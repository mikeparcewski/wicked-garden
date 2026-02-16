# Release wicked-agentic v1.3.1

**Date**: 2026-02-16
**Component**: wicked-agentic

## Summary

This release includes: 2 bug fix(es).

## Changes

### Bug Fixes

- fix: workbench proxy item_id path handling and traverse forwarding (077441a)
- fix: resolve 5 reported issues across workbench, mem, and kanban plugins (be46dab)

### Documentation

- docs: update READMEs, skills, and marketplace for plugin API enhancements (0c5093a)

### Chores

- release: wicked-workbench v0.7.2 (ab35680)
- release: wicked-workbench v0.7.1, wicked-mem v0.8.1, wicked-kanban v0.10.1 (62adb4d)
- release: wicked-crew v0.15.0, wicked-delivery v0.8.0, wicked-search v1.6.0, wicked-kanban v0.10.0 (59f7f71)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-agentic@wicked-garden
```
