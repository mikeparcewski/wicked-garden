# Changelog

## [1.1.0] - 2026-02-21

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

## [1.0.0] - 2026-02-19

### Breaking Changes
- feat(wicked-search)!: v2.0 — single unified SQLite backend, remove legacy code (92fb403)

### Features
- feat: resolve frontend migration plugin features (#6) (60ffc00)
- feat(wicked-startah): add GitHub issue reporting skill, hooks, and command (63b9515)
- feat(wicked-search): add unified SQLite query layer merging graph DB and JSONL index (14fc856)
- feat(wicked-kanban): add task lifecycle enrichment via TaskCompleted hooks (6916d59)
- feat(wicked-search): add cross-category relationships to categories API (2e9d57b)
- feat(wicked-search): add /wicked-search:categories command (237a055)

### Bug Fixes
- fix(wicked-search): fix graph domain, refs import, and categories performance (96286f8)

### Chores
- release: wicked-search v2.0.1 (b5883a0)
- release: wicked-startah v0.8.0 (2b7e538)
- release: wicked-search v2.0.0 (e07c996)
- release: wicked-kanban v0.12.0 (d6fcf76)
- release: wicked-search v1.9.0 (0463d46)
- chore: remove old release notes superseded by new versions (65e35e7)
- release: batch bump 17 plugins to minor (6ebcf34)

## [0.6.0] - 2026-02-16

### Features
- feat: workbench dashboard skill refs, scenario rewrites, and cleanup (8e21970)
- feat: add categories, impact, content, and ide-url API verbs (030ffc6)

### Bug Fixes
- fix: kanban board isolation, MEMORY.md write blocking, and hook event corrections (afb3f87)

### Chores
- release: wicked-search v1.7.0, wicked-workbench v0.8.0 (be7cbea)
- release: batch bump 14 plugins to patch (7af7913)

## [0.5.1] - 2026-02-16

### Bug Fixes
- fix: workbench proxy item_id path handling and traverse forwarding (077441a)
- fix: resolve 5 reported issues across workbench, mem, and kanban plugins (be46dab)

### Documentation
- docs: update READMEs, skills, and marketplace for plugin API enhancements (0c5093a)

### Chores
- release: wicked-workbench v0.7.2 (ab35680)
- release: wicked-workbench v0.7.1, wicked-mem v0.8.1, wicked-kanban v0.10.1 (62adb4d)
- release: wicked-crew v0.15.0, wicked-delivery v0.8.0, wicked-search v1.6.0, wicked-kanban v0.10.0 (59f7f71)

## [0.5.0] - 2026-02-15

### Features
- feat: enrich plugin Data APIs with graph traversal, hotspots, multi-project isolation, and more (ba7cb5a)
- feat(kanban): add comment command for task annotations (37b4241)
- feat(search): add layer and type filtering for search results (338457e)
- feat(delivery): add cross-plugin data discovery for crew and mem (1d130d4)
- feat(crew): add artifacts API, include-status flag, and path validation (bace271)

### Bug Fixes
- fix: address review findings in plugin API enhancements (81dacde)

### Chores
- release: wicked-crew v0.14.0, wicked-delivery v0.7.0, wicked-search v1.5.0, wicked-kanban v0.9.0 (0e06628)
- release: wicked-agentic v1.2.0, wicked-crew v0.13.0, wicked-data v0.4.0, wicked-delivery v0.6.1, wicked-engineering v0.8.0, wicked-jam v0.4.0, wicked-kanban v0.8.0, wicked-mem v0.7.0, wicked-patch v1.2.0, wicked-platform v0.3.0, wicked-product v0.3.0, wicked-qe v0.4.0, wicked-scenarios v0.3.0, wicked-search v1.4.0, wicked-smaht v2.7.0, wicked-startah v0.5.0, wicked-workbench v0.6.0 (5470682)

## [0.4.0] - 2026-02-15

### Features
- feat(delivery): setup command and configurable settings (b38164e)
- feat(delivery): configurable cost estimation and delta-triggered commentary (48d7267)
- feat(delivery,search): data gateway metrics and graph exposure (d95cb70)
- feat(workbench,kanban,mem,crew): data gateway write operations and specialist reviewer routing (7490f97)

### Chores
- release: wicked-delivery v0.6.0 (86413a5)
- chore: remove stale release notes from previous version (c0cdff9)
- release: wicked-delivery v0.5.0 (9b1872a)
- release: wicked-delivery v0.4.0, wicked-search v1.3.0 (8125a6c)
- release: wicked-workbench v0.5.0, wicked-kanban v0.7.0, wicked-mem v0.6.0, wicked-crew v0.12.0 (16eef1f)
- Merge pull request #2 from mikeparcewski/dependabot/uv/plugins/wicked-workbench/server/cryptography-46.0.5 (1489682)
- release: wicked-jam v0.3.0, wicked-smaht v2.6.0 (2b1245a)
- chore(deps): Bump cryptography in /plugins/wicked-workbench/server (62707ff)

## [0.3.0] - 2026-02-14

### Features
- feat(jam,smaht): evidence-based decision lifecycle and cross-session memory (4ab158a)
- feat(wicked-smaht): add delegation and startah adapters, improve routing and hooks (a7185e5)
- feat: Plugin Data API v1.0.0 — wicked.json replaces catalog.json (95ebf21)
- feat(wicked-crew): dynamic archetype scoring, smaht integration, orchestrator-only execution (db86340)
- feat(wicked-crew): signal model v2 with confidence scoring, semantic detection, and feedback loop (279e54c)

### Documentation
- docs: align specialist configs, update READMEs with Data API and integration tables (201daf2)
- docs: explain multi-dimensional risk scoring in READMEs (ab6f9a6)
- docs: expand CLAUDE.md with architecture, patterns, and conventions (999707d)

### Refactoring
- refactor: convert informal task prose to actual Task() dispatches across specialist agents (8da7b21)
- refactor(wicked-delivery): narrow scope to feature delivery tactics, migrate PMO agents to wicked-crew (32113de)
- refactor: consolidate caching into wicked-startah, remove wicked-cache plugin (1d0e938)
- refactor(wicked-workbench): replace catalog-based architecture with Plugin Data API gateway (c0af448)

### Chores
- chore: CLAUDE.md conventions, search/patch fixes, data ontology command, test scaffolding (11aaf2d)
- release: wicked-crew v0.11.0 (12c7f1f)
- Merge remote-tracking branch 'origin/main' (f1f0e12)
- release: bump 18 plugins (bc1a9ed)
- Merge pull request #1 from arturl/main (6eefef4)
- Update plugins/wicked-engineering/commands/review.md (b9c8105)
- Add --focus tests to review command for LLM-generated test quality (6d729bb)

## [0.2.0] - 2026-02-10

### Features
- feat(wicked-crew): replace extension-based scoring with multi-dimensional risk analysis (2a7042b)
- feat(wicked-smaht): add tiered context management with HOT/FAST/SLOW routing (2bef5da)

### Documentation
- docs: fix README issues from 18-plugin specialist review (59d495b)
- docs: rewrite READMEs with differentiators and value-first openings (a89f1ff)

### Chores
- release: wicked-smaht v2.4.0, wicked-crew v0.9.2 (f05e63e)
- review useless files (29b10d1)
- chore: normalize author to Mike Parcewski and fix repo URLs (ab8df47)

## [0.1.11] - 2026-02-08

### Features
- feat(wicked-qe): integrate with wicked-scenarios for E2E scenario discovery and execution (6538a71)
- feat(wicked-mem): add PostToolUse nudge for MEMORY.md direct edits (a15db3f)
- feat: add wicked-scenarios plugin for E2E testing via markdown scenarios (c7d4422)
- feat: dynamic crew flow, usage friction fixes, batch release tooling (311401b)
- feat(wicked-mem): add TaskCompleted hook for memory capture prompt (531713c)
- feat(wicked-kanban): add TaskCompleted hook for reliable task sync (25057d3)
- feat(wicked-crew): replace hardcoded phases with flexible phases.json config (f8e7baa)
- feat(wicked-crew): enforce sign-off verification in approve gate (ade44e2)
- feat(wicked-crew): add phase sign-off priority chain (cec0e13)
- feat(wicked-crew): add task lifecycle tracking to all crew agents (6254613)
- feat(wicked-patch): v1.0.0 - language-agnostic code generation (5e24b0b)
- feat(wicked-search): v1.0.0 - reasoning capabilities and index quality (4a1e6b3)
- feat: update existing plugins with enhanced capabilities (6ae5cfc)
- feat: add specialist plugins for domain expertise (4682037)
- feat(wicked-startah): add runtime-exec skill for Python/Node execution (55b1393)
- feat(wicked-search): add extensible parser/linker system with form binding support (ab18b36)
- feat(wicked-kanban): enhance TodoWrite hook for rich traceability (85d55c5)

### Bug Fixes
- fix(wicked-crew): enforce phase documentation and non-skippable review (d64a673)
- fix(wicked-mem): enforce memory storage with directive hook prompts (8703418)
- fix: resolve onboarding issues - ghost plugins, code defects, structure (d16c293)
- fix(wicked-mem,wicked-crew): memory filtering and task lifecycle improvements (c014f92)
- fix(hooks): update Stop hooks to use required JSON response format (6e1c236)
- fix(wicked-kanban): fix UI bugs and add security hardening (9ccbcd4)

### Documentation
- docs: rewrite all 17 plugin READMEs with sell-first structure (c30ebec)
- docs: standardize command prefixes and improve plugin READMEs (5129e89)

### Refactoring
- refactor: remove deprecated plugins consolidated into specialist plugins (a32a81f)

### Chores
- chore: add wicked-scenarios to marketplace catalog (74de311)
- chore: remove old release notes replaced by new versions (39955d9)
- release: bump 8 plugins - dynamic flow, friction fixes, batch release (49dfd00)
- release: wicked-mem v0.3.2 (f46577e)
- release: wicked-kanban v0.4.0 (4824f18)
- release: wicked-crew v0.8.0 (7f48928)
- release: bump 12 plugins - onboarding fixes, mem hooks, crew features (d819228)
- release: wicked-mem v0.3.0, wicked-kanban v0.3.10, wicked-crew v0.6.1 (044f1d2)
- chore: fix stale plugin names in scaffold and update hook standards (e6bfe62)
- chore: clean up repo garbage and auto-prune old release notes (eea12a8)
- release: bump all plugins, automate release pipeline, extract QE (769c540)
- chore: add wicked-patch to marketplace (62befa4)
- version updates (36c7444)
- chore: update plugin .gitignore files and crew hook script (7f263a2)
- chore: update dev tools and scaffolding templates (df55616)
- lots of stuff (278d71f)

## [0.1.10] - 2026-02-06

### Features
- feat(wicked-patch): v1.0.0 - language-agnostic code generation (5e24b0b)
- feat(wicked-search): v1.0.0 - reasoning capabilities and index quality (4a1e6b3)
- feat: update existing plugins with enhanced capabilities (6ae5cfc)
- feat: add specialist plugins for domain expertise (4682037)
- feat(wicked-startah): add runtime-exec skill for Python/Node execution (55b1393)
- feat(wicked-search): add extensible parser/linker system with form binding support (ab18b36)
- feat(wicked-kanban): enhance TodoWrite hook for rich traceability (85d55c5)

### Bug Fixes
- fix(wicked-mem,wicked-crew): memory filtering and task lifecycle improvements (c014f92)
- fix(hooks): update Stop hooks to use required JSON response format (6e1c236)
- fix(wicked-kanban): fix UI bugs and add security hardening (9ccbcd4)

### Documentation
- docs: standardize command prefixes and improve plugin READMEs (5129e89)

### Refactoring
- refactor: remove deprecated plugins consolidated into specialist plugins (a32a81f)

### Chores
- chore: add wicked-patch to marketplace (62befa4)
- version updates (36c7444)
- chore: update plugin .gitignore files and crew hook script (7f263a2)
- chore: update dev tools and scaffolding templates (df55616)
- lots of stuff (278d71f)

## [0.1.8] - 2025-01-27

### Changed
- Removed hooks.json (no hooks needed)

## [0.1.3] - 2026-01-23

### Chores
- chore: marketplace validation and cleanup (3e350f1)
- initial check-in (98cb674)

