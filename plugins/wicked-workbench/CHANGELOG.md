# Changelog

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

## [0.9.0] - 2026-02-16

### Features
- feat: workbench dashboard skill refs, scenario rewrites, and cleanup (8e21970)

### Bug Fixes
- fix: kanban board isolation, MEMORY.md write blocking, and hook event corrections (afb3f87)

### Chores
- release: wicked-search v1.7.0, wicked-workbench v0.8.0 (be7cbea)

## [0.8.0] - 2026-02-16

### Features
- feat: add categories, impact, content, and ide-url API verbs (030ffc6)

### Chores
- release: batch bump 14 plugins to patch (7af7913)
- release: wicked-workbench v0.7.2 (ab35680)

## [0.7.2] - 2026-02-16

### Bug Fixes
- fix: workbench proxy item_id path handling and traverse forwarding (077441a)

### Chores
- release: wicked-workbench v0.7.1, wicked-mem v0.8.1, wicked-kanban v0.10.1 (62adb4d)

## [0.7.1] - 2026-02-16

### Bug Fixes
- fix: resolve 5 reported issues across workbench, mem, and kanban plugins (be46dab)

### Documentation
- docs: update READMEs, skills, and marketplace for plugin API enhancements (0c5093a)

### Chores
- release: wicked-crew v0.15.0, wicked-delivery v0.8.0, wicked-search v1.6.0, wicked-kanban v0.10.0 (59f7f71)

## [0.7.0] - 2026-02-15

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

## [0.6.0] - 2026-02-15

### Features
- feat(delivery): setup command and configurable settings (b38164e)
- feat(delivery): configurable cost estimation and delta-triggered commentary (48d7267)
- feat(delivery,search): data gateway metrics and graph exposure (d95cb70)

### Chores
- release: wicked-delivery v0.6.0 (86413a5)
- chore: remove stale release notes from previous version (c0cdff9)
- release: wicked-delivery v0.5.0 (9b1872a)
- release: wicked-delivery v0.4.0, wicked-search v1.3.0 (8125a6c)
- release: wicked-workbench v0.5.0, wicked-kanban v0.7.0, wicked-mem v0.6.0, wicked-crew v0.12.0 (16eef1f)

## [0.5.0] - 2026-02-14

### Features
- feat(workbench,kanban,mem,crew): data gateway write operations and specialist reviewer routing (7490f97)
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
- Merge pull request #2 from mikeparcewski/dependabot/uv/plugins/wicked-workbench/server/cryptography-46.0.5 (1489682)
- release: wicked-jam v0.3.0, wicked-smaht v2.6.0 (2b1245a)
- chore: CLAUDE.md conventions, search/patch fixes, data ontology command, test scaffolding (11aaf2d)
- release: wicked-crew v0.11.0 (12c7f1f)
- chore(deps): Bump cryptography in /plugins/wicked-workbench/server (62707ff)
- Merge remote-tracking branch 'origin/main' (f1f0e12)
- release: bump 18 plugins (bc1a9ed)
- Merge pull request #1 from arturl/main (6eefef4)
- Update plugins/wicked-engineering/commands/review.md (b9c8105)
- Add --focus tests to review command for LLM-generated test quality (6d729bb)

## [0.4.0] - 2026-02-10

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

## [0.3.0] - 2026-02-09

### Features
- feat(wicked-workbench): add ACP-powered dynamic UI with React frontend (ba27700)

### Bug Fixes
- fix: resolve plugin structure issues across 6 plugins (ce3419f)

### Refactoring
- refactor: convert 29 commands from prose dispatch to Task() subagent calls (270b2cb)

### Chores
- release: bump all 18 plugins with changelogs and release notes (b0ec55d)

## [0.2.3] - 2026-02-08

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
- release: bump all plugins for marketplace release (a660b40)
- chore: marketplace validation and cleanup (3e350f1)
- initial check-in (98cb674)

## [0.2.2] - 2026-02-06

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
- release: bump all plugins for marketplace release (a660b40)
- chore: marketplace validation and cleanup (3e350f1)
- initial check-in (98cb674)

All notable changes to wicked-workbench will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-28

### Added
- A2UI dashboard rendering from Claude Code generated JSON
- Plugin catalog discovery and aggregation
- MCP bridge for live data fetching from plugin servers
- Built-in demo catalogs when no plugins installed
- Health check endpoint at `/health`
- Dashboard skill with component mapping guidance

### Changed
- Simplified architecture: Claude Code generates A2UI, workbench renders
- Removed dependency on server-side Claude generation for main workflow

### Fixed
- Documentation clarified: API key only needed for optional `/api/generate` endpoint

## [0.1.0] - 2026-01-15

### Added
- Initial release
- FastAPI server with A2UI rendering
- Catalog loader for plugin component discovery
- MCP bridge for connecting to plugin data servers
- Basic HTML/JSON rendering output
