# Changelog

## [0.8.0] - 2026-02-15

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

## [0.7.0] - 2026-02-14

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

## [0.6.0] - 2026-02-10

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

## [0.5.1] - 2026-02-08

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

## [0.5.0] - 2026-02-07

### Features
- feat: dynamic crew flow, usage friction fixes, batch release tooling (311401b)
- feat(wicked-mem): add TaskCompleted hook for memory capture prompt (531713c)

### Chores
- release: wicked-mem v0.3.2 (f46577e)
- release: wicked-kanban v0.4.0 (4824f18)

## [0.4.0] - 2026-02-06

### Features
- feat(wicked-kanban): add TaskCompleted hook for reliable task sync (25057d3)
- feat(wicked-crew): replace hardcoded phases with flexible phases.json config (f8e7baa)

### Chores
- release: wicked-crew v0.8.0 (7f48928)
- release: bump 12 plugins - onboarding fixes, mem hooks, crew features (d819228)

## [0.3.11] - 2026-02-06

### Features
- feat(wicked-crew): enforce sign-off verification in approve gate (ade44e2)
- feat(wicked-crew): add phase sign-off priority chain (cec0e13)
- feat(wicked-crew): add task lifecycle tracking to all crew agents (6254613)

### Bug Fixes
- fix(wicked-crew): enforce phase documentation and non-skippable review (d64a673)
- fix(wicked-mem): enforce memory storage with directive hook prompts (8703418)
- fix: resolve onboarding issues - ghost plugins, code defects, structure (d16c293)

### Chores
- release: wicked-mem v0.3.0, wicked-kanban v0.3.10, wicked-crew v0.6.1 (044f1d2)

## [0.3.10] - 2026-02-06

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
- chore: fix stale plugin names in scaffold and update hook standards (e6bfe62)
- chore: clean up repo garbage and auto-prune old release notes (eea12a8)
- release: bump all plugins, automate release pipeline, extract QE (769c540)
- chore: add wicked-patch to marketplace (62befa4)
- version updates (36c7444)
- chore: update plugin .gitignore files and crew hook script (7f263a2)
- chore: update dev tools and scaffolding templates (df55616)
- lots of stuff (278d71f)

## [0.3.9] - 2026-02-06

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

## [0.3.5] - 2026-02-01

### Changed
- **SessionStart hook**: Compact single-line format for board status
  - Changed from multi-line markdown to `[Kanban] Project:todo/wip/done` format
  - Shows up to 3 projects on one line with `+N more` indicator
  - Current project marked with `*` prefix

## [0.3.4] - 2026-02-01

### Changed
- **SessionStart hook**: Now shows board status on session start
  - Lists projects with task counts by swimlane (todo/in progress/done)
  - Marks current project based on repo path
  - Shows up to 5 projects with "... and N more" for larger boards

## [0.3.3] - 2026-01-30

### Fixed
- Initiative default status changed from "active" to "planning" (matches expected workflow)

### Added
- `add-project-comment` CLI command for project-level comments (stored in activity log)

## [0.3.2] - 2026-01-30

### Changed
- Cross-platform hook support: hooks now detect uv/python3 automatically
- Commands updated to list multiple package manager options (uv, poetry, venv, python3)

### Added
- `hooks/scripts/run_python.sh` - cross-platform Python runner helper

## [0.3.1] - 2025-01-27

### Changed
- Stop hook refactored to prompt-file architecture (`hooks/prompts/stop.md`)
- Stop hook now updates task statuses, logs work, and links commits automatically

### Added
- `hooks/prompts/stop.md` - maintainable prompt file for Stop hook
- References shared `.claude/hooks/standards.md` for consistent behavior

## [0.3.0] - 2025-01-27

### Changed
- Stop hook converted to prompt type for Haiku evaluation
- Removed noop Python stop_hook.py
- Removed frontend (wicked-workbench provides UI)

### Fixed
- Hook output no longer spams system reminders

## [0.1.4] - 2026-01-23

### Chores
- chore: marketplace validation and cleanup (3e350f1)
- initial check-in (98cb674)

