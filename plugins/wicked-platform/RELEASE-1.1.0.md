# Release wicked-platform v1.1.0

**Date**: 2026-02-21
**Component**: wicked-platform

## Summary

This release includes: 4 new feature(s), 25 bug fix(es).

## Changes

### Features

- feat(wicked-scenarios): add setup command and platform-aware tool installation (#20) (3daf8c8)
- feat(wicked-scenarios): add setup command and platform-aware tool installation (#18) (0c6d8b1)
- feat(wg-test): auto-file GitHub issues for scenario failures (2fa79e9)
- feat: resolve GitHub issues #7, #8, #9, #10 (#11) (303ab7b)

### Bug Fixes

- fix: resolve 5 wicked-patch UAT scenario failures (#39) (269bd26)
- fix: resolve cross-file reference linker (#44) (cde6cc2)
- fix: address review comments from Copilot and Gemini (#44) (044479b)
- fix: address review comments from Copilot and Gemini (#39) (aea27cd)
- fix: always run cross-language discovery and use narrower project prefix (#44) (1ee9600)
- fix: resolve cross-file reference linker storing short names instead of qualified IDs (#44) (964d01a)
- fix: resolve 5 wicked-patch UAT scenario failures (#39) (32f80ad)
- fix: resolve wicked-data date type and wicked-mem tag stats defects (#40, #41) (bfe5ae5)
- fix: override SKIP_PLUGIN_MARKETPLACE to enable plugin loading (be2e8f7)
- fix: resolve UAT failures across crew, data, jam, patch, search, workbench plugins (#38) (9eb2a28)
- fix: address PR #26 review comments from Gemini and Copilot (#27) (047f6b1)
- fix(wicked-search, wicked-scenarios): resolve scenario failures and add graceful degradation (#26) (5f7d918)
- fix: address engineering review findings across patch generators and smaht (422d000)
- fix: address PR #25 review comments across kanban, scenarios, smaht (b51d00c)
- fix(wicked-patch): resolve 8 cross-cutting bugs in patch generation (#21) (650d85f)
- fix(wicked-kanban): use swimlane field for task filtering in api.py (#24) (cf63d05)
- fix: resolve UAT scenario failures for smaht, kanban, startah (#15, #16, #17) (ecb8553)
- fix(wicked-smaht): serialize intent_type when saving turns to turns.jsonl (b41c005)
- fix: resolve UAT scenario failures for smaht, kanban, startah (#15, #16, #17) (567cae1)
- fix(wicked-workbench): call config.validate() at startup, clean up imports (9ddb28c)
- fix(wg-test): address PR #13 review comments on issue filing (f1886f3)
- fix: address PR #11 review findings — security, correctness, performance (#12) (9fda20e)
- fix: address PR #11 review findings — security, correctness, performance (caa62cb)
- fix: resolve UAT failures across 6 plugins (69417f6)
- fix(wicked-search): align lineage_paths schema — fix empty lineage API results (893d0d1)

### Chores

- Merge pull request #42 from mikeparcewski/claude/wg-test-all-issues-X8oja (74d8328)
- chore: gitignore test artifact from wicked-workbench scenario (f5903d5)
- ensure teams are executed (f0cb1c6)
- Merge pull request #25 from mikeparcewski/claude/fix-wg-issues-15-16-17-XSnpD (b0b0093)
- merge: resolve conflicts with main (keep swimlane fix, consistent schema) (9f3b7c0)
- Merge pull request #14 from mikeparcewski/claude/resolve-github-issues-fbb4D (fe1dd5b)
- Merge pull request #13 from mikeparcewski/claude/resolve-github-issues-fbb4D (37bc975)
- release: bump 17 plugins (e1a205a)

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-platform@wicked-garden
```
