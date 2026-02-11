# Changelog

## [0.5.0] - 2026-02-10

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

## [0.4.1] - 2026-02-08

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

## [0.4.0] - 2026-02-07

### Features
- feat: dynamic crew flow, usage friction fixes, batch release tooling (311401b)

### Chores
- release: wicked-mem v0.3.2 (f46577e)

## [0.3.2] - 2026-02-06

### Features
- feat(wicked-mem): add TaskCompleted hook for memory capture prompt (531713c)
- feat(wicked-kanban): add TaskCompleted hook for reliable task sync (25057d3)
- feat(wicked-crew): replace hardcoded phases with flexible phases.json config (f8e7baa)

### Chores
- release: wicked-kanban v0.4.0 (4824f18)
- release: wicked-crew v0.8.0 (7f48928)
- release: bump 12 plugins - onboarding fixes, mem hooks, crew features (d819228)

## [0.3.1] - 2026-02-06

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

## [0.3.0] - 2026-02-06

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

## [0.2.10] - 2026-02-06

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

## [0.2.7] - 2026-02-03

### Added
- **System tag filtering**: Strip `<task-notification>`, `<system-reminder>`, `<command-message>` before signal detection
- **Feature flags**: `config.py` with environment variable overrides for gradual rollout
- **ReDoS protection**: 50KB content limit to prevent catastrophic backtracking

### Changed
- **Signal patterns**: Refined to avoid matching system status output
- `strip_system_tags()` function with comprehensive error handling
- `smart_sample()` now strips system tags before sampling
- `queue_signal()` skips content that is 100% system tags
- `prompt_submit.py` uses cleaned prompts for all operations

### Fixed
- Memory pollution from `<task-notification>` system messages
- False positives from words like "completed" in system tags

## [0.2.6] - 2026-02-01

### Changed
- **Console formatting**: Replaced markdown with `[Memory]` prefix format
  - SessionStart, prompt_submit, and pre_compact hooks updated
  - Output now displays cleanly in terminal without raw asterisks

## [0.2.5] - 2026-01-30

### Added
- **Cross-project search**: `recall --all-projects` searches ALL projects (like kanban)
- **`search-all` command**: Returns enriched results with match_type, project context
- Deduplication in recall to prevent duplicate results

### Changed
- `recall` now accepts `--all-projects` flag for global search
- Search results include project name and where match was found (title/tags/content)

## [0.2.4] - 2026-01-30

### Fixed
- `/wicked-mem:store` command now uses python3 directly (no external deps needed)
- Removed unnecessary uv dependency from store command

## [0.2.3] - 2025-01-27

### Changed
- Stop hook refactored to prompt-file architecture (`hooks/prompts/stop.md`)
- Removed `stop_extract.py` - learning extraction now handled by agent spawning
- Stop hook can now spawn `memory-learner` agent for rich context extraction

### Added
- `hooks/prompts/stop.md` - maintainable prompt file for Stop hook
- References shared `.claude/hooks/standards.md` for consistent behavior

## [0.2.2] - 2025-01-27

### Changed
- Minor hook script updates for consistency

## [0.1.6] - 2026-01-23

### Chores
- chore: marketplace validation and cleanup (3e350f1)
- initial check-in (98cb674)

