# Release wicked-garden v1.15.0

**Date**: 2026-03-04
**Component**: wicked-garden

## Summary

Simplifies storage modes from 4 (local-install, local-only, offline, remote) to 2 (local, remote). Fixes CP auto-start failure caused by missing `concurrently` binary.

## Changes

### Features

- Simplified storage modes: `local` (default, auto-starts CP with JSON fallback) and `remote` (team server)
- Legacy mode values (`local-install`, `local-only`, `offline`) are auto-mapped to `local` for backward compatibility

### Fixes

- Fixed CP auto-start: changed `pnpm run dev` to `pnpm run dev:backend` (the `dev` script requires `concurrently` which isn't in PATH as a local dep)
- Removed browser/dashboard auto-open on session start (local mode has no UI)

### Removed

- `local-only` mode (SQLite-only storage path)
- `offline` mode (replaced by local fallback in `local` mode)
- Browser viewer integration (`_open_browser_once`, `_viewer_already_opened`, `_mark_viewer_opened`)
- `_setup_local_only` and `_offline_storage_summary` bootstrap functions

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-garden@wicked-garden
```
