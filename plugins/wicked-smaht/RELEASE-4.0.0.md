# Release wicked-smaht v4.0.0

**Date**: 2026-02-24
**Component**: wicked-smaht

## Summary

This release includes: 1 breaking change(s), 14 new feature(s), 33 bug fix(es).

## Changes

### Breaking Changes

- feat(wicked-search)!: v2.0 — single unified SQLite backend, remove legacy code (92fb403)

### Features

- feat: add TypeScript type definitions for wicked-search and wicked-workbench APIs (#59 #61) (017c4f0)
- feat: evidence-gated scenario testing with three-agent architecture (ff4fc7a)
- feat: add AGENTS.md support for cross-tool compatibility (#47) (6eab8bf)
- feat(wicked-scenarios): add setup command and platform-aware tool installation (#20) (3daf8c8)
- feat(wicked-scenarios): add setup command and platform-aware tool installation (#18) (0c6d8b1)
- feat(wg-test): auto-file GitHub issues for scenario failures (2fa79e9)
- feat: resolve GitHub issues #7, #8, #9, #10 (#11) (303ab7b)
- feat: resolve frontend migration plugin features (#6) (60ffc00)
- feat(wicked-startah): add GitHub issue reporting skill, hooks, and command (63b9515)
- feat(wicked-search): add unified SQLite query layer merging graph DB and JSONL index (14fc856)
- feat(wicked-kanban): add task lifecycle enrichment via TaskCompleted hooks (6916d59)
- feat(wicked-search): add cross-category relationships to categories API (2e9d57b)
- feat(wicked-search): add /wicked-search:categories command (237a055)
- feat: workbench dashboard skill refs, scenario rewrites, and cleanup (8e21970)

### Bug Fixes

- fix: wicked-smaht context hook reads wrong input field, never fires (3f894d2)
- fix: resolve scenario spec mismatches and add wicked-agentic scenarios (#62 #63) (4ab91cc)
- fix: resolve 3 UAT failures + address PR #57 review comments (#58) (9472da7)
- fix: rewrite wicked-patch scenarios to match actual CLI (#51) (#54) (a58b12d)
- fix: address PR review feedback for risk assessment (#48) (cd965f4)
- fix: make remove_field always HIGH risk in plan assessment (#48) (82d8581)
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
- fix(wicked-search): fix graph domain, refs import, and categories performance (96286f8)
- fix: kanban board isolation, MEMORY.md write blocking, and hook event corrections (afb3f87)

### Documentation

- docs: standardize all 17 plugin READMEs to canonical template (0a57fe8)
- docs: rewrite README as ecosystem sales pitch (c6de8fd)

### Chores

- Fix intent-based-retrieval scenario to match actual implementation (8add625)
- chore: remove stale working documents from repo root (b871427)
- chore: remove stale tests/ and test-results/ directories (984bc0c)
- release: bump 16 plugins (c9322d0)
- release: wicked-patch v2.1.1 (7f8868d)
- Merge pull request #49 from mikeparcewski/fix/48-plan-command-cross-file-impact (755883b)
- release: bump 17 plugins (408ac5e)
- Merge pull request #42 from mikeparcewski/claude/wg-test-all-issues-X8oja (74d8328)
- chore: gitignore test artifact from wicked-workbench scenario (f5903d5)
- ensure teams are executed (f0cb1c6)
- Merge pull request #25 from mikeparcewski/claude/fix-wg-issues-15-16-17-XSnpD (b0b0093)
- merge: resolve conflicts with main (keep swimlane fix, consistent schema) (9f3b7c0)
- Merge pull request #14 from mikeparcewski/claude/resolve-github-issues-fbb4D (fe1dd5b)
- Merge pull request #13 from mikeparcewski/claude/resolve-github-issues-fbb4D (37bc975)
- release: bump 17 plugins (e1a205a)
- release: wicked-search v2.0.1 (b5883a0)
- release: wicked-startah v0.8.0 (2b7e538)
- release: wicked-search v2.0.0 (e07c996)
- release: wicked-kanban v0.12.0 (d6fcf76)
- release: wicked-search v1.9.0 (0463d46)
- chore: remove old release notes superseded by new versions (65e35e7)
- release: batch bump 17 plugins to minor (6ebcf34)
- release: wicked-search v1.7.0, wicked-workbench v0.8.0 (be7cbea)

## Upgrade Guide

This release contains breaking changes. Please review the breaking changes above and update your code accordingly.

## Installation

```bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install wicked-smaht@wicked-garden
```
