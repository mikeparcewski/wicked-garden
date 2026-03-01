# Changelog

## [1.3.2] - 2026-03-01

### Features
- feat: add trigger phrases to agentic skills and split oversized refs (#121, #122) (28be533)

### Bug Fixes
- fix: replace glob refs with explicit links, fix escaped code fences (9c719f3)
- fix: include CP error messages in stop hook output, sanitize task subjects (f61c0d7)
- fix: resolve wg-check findings #117-#120 (65b1f46)

### Refactoring
- refactor: organize scenarios by domain and block native plan mode (22f6839)

### Chores
- Merge pull request #124 from mikeparcewski/feat/121-122-wg-check-enhancements (bfdb902)
- Merge pull request #123 from mikeparcewski/fix/117-120-wg-check-bugs (de17e2a)
- release: wicked-garden v1.3.1 (4e32282)

## [1.3.1] - 2026-03-01

### Bug Fixes
- fix: restore dropped conversational trigger phrases in skill descriptions (b898932)
- fix: resolve wg-check --full findings (#109-#115) (8122e1f)

### Chores
- Merge pull request #116 from mikeparcewski/fix/wg-check-full-findings (16b45b5)
- release: wicked-garden v1.3.0 (51957d7)

## [1.3.0] - 2026-03-01

### Features
- feat: dynamic schema adaptation via manifest_detail() for unregistered sources (ae3b9f7)

### Chores
- Merge pull request #108 from mikeparcewski/feat/dynamic-schema-adaptation (db234ce)
- release: wicked-garden v1.2.1 (213edad)

## [1.2.1] - 2026-03-01

### Bug Fixes
- fix: correct wg-check smoke test comment about GET/POST verb classification (fc82d5b)
- fix: wg-check specialist.json schema + CP smoke test verb safety + crew:start wording (5e312b5)

### Chores
- Merge pull request #107 from mikeparcewski/fix/wg-check-and-crew-start (27f938a)
- release: wicked-garden v1.2.0 (b2e8d70)

## [1.2.0] - 2026-03-01

### Features
- feat: SM router enforcement + CP error detection (#98) (2797b19)

### Chores
- release: wicked-garden v1.1.0 (10d519f)

## [1.1.0] - 2026-02-28

### Breaking Changes
- feat(wicked-search)!: v2.0 — single unified SQLite backend, remove legacy code (92fb403)

### Features
- feat: auto-start bootstrap, manifest-driven CP client, and StorageManager migration (2275fd1)
- feat(wicked-garden): consolidate 18 plugins into unified wicked-garden plugin (8eb0566)
- feat(crew,jam,startah): resolve 6 open GitHub issues #75-80 (eb1c320)
- feat(wg-test): add --batch and --debug flags for parallel scenario execution (cd04d4b)
- feat(smaht): replace hook-based context injection with prompt-embedded dispatch packets (70d9877)
- feat(smaht): replace turn-based context warnings with content pressure tracking (f0aae53)
- feat: add wicked-scenarios format generation to 6 specialist plugins (09e94b9)
- feat(qe,scenarios): consolidate acceptance pipeline — QE owns testing, scenarios is thin CLI backend (7514e56)
- feat(kanban,scenarios): store evidence inline in kanban artifacts (c06924d)
- feat(scenarios): add report command, batch mode, and fix evidence path (b8101ed)
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
- feat: add categories, impact, content, and ide-url API verbs (030ffc6)
- feat: enrich plugin Data APIs with graph traversal, hotspots, multi-project isolation, and more (ba7cb5a)
- feat(kanban): add comment command for task annotations (37b4241)
- feat(search): add layer and type filtering for search results (338457e)
- feat(delivery): add cross-plugin data discovery for crew and mem (1d130d4)
- feat(crew): add artifacts API, include-status flag, and path validation (bace271)
- feat(delivery): setup command and configurable settings (b38164e)
- feat(delivery): configurable cost estimation and delta-triggered commentary (48d7267)
- feat(delivery,search): data gateway metrics and graph exposure (d95cb70)
- feat(workbench,kanban,mem,crew): data gateway write operations and specialist reviewer routing (7490f97)
- feat(jam,smaht): evidence-based decision lifecycle and cross-session memory (4ab158a)
- feat(wicked-smaht): add delegation and startah adapters, improve routing and hooks (a7185e5)
- feat: Plugin Data API v1.0.0 — wicked.json replaces catalog.json (95ebf21)
- feat(wicked-crew): dynamic archetype scoring, smaht integration, orchestrator-only execution (db86340)
- feat(wicked-crew): signal model v2 with confidence scoring, semantic detection, and feedback loop (279e54c)
- feat(wicked-crew): replace extension-based scoring with multi-dimensional risk analysis (2a7042b)
- feat(wicked-smaht): add tiered context management with HOT/FAST/SLOW routing (2bef5da)

### Bug Fixes
- fix: correct plugin install org from something-wicked to mikeparcewski (f3783a1)
- fix: address PR review feedback on phase enforcement (#85) (f07840f)
- fix: enforce test phase injection and checkpoint re-analysis (#85) (d2f4aae)
- fix: CP client Content-Type and domain prefix routing (be21bd5)
- fix: plugin.json author must be object not string (314a61c)
- fix: marketplace.json source must use ./ not . (f8e458c)
- fix(agentic,crew): resolve all 8 open GitHub issues #67-74 (608954c)
- fix(smaht): fix context injection format and broken adapters (757d1d8)
- fix(smaht): prevent subagent context blowout with SubagentStart hook and budget enforcement (d24abb1)
- fix(kanban): remove TaskCompleted prompt hook that blocked combined updates (1a515bc)
- fix(crew,kanban): ensure crew sessions create and persist kanban initiative tracking (909a2fa)
- fix: restore CREW-CORE.md accidentally deleted in doc consolidation (2fef152)
- fix(wicked-smaht): context hook reads wrong input field, never fires (#65) (e4edd01)
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
- fix: workbench proxy item_id path handling and traverse forwarding (077441a)
- fix: resolve 5 reported issues across workbench, mem, and kanban plugins (be46dab)
- fix: address review findings in plugin API enhancements (81dacde)

### Documentation
- docs: update README counts and structure for current state (764f10d)
- docs: update AGENTS.md for unified plugin references (c1bb48a)
- docs: standardize all 17 plugin READMEs to canonical template (0a57fe8)
- docs: rewrite README as ecosystem sales pitch (c6de8fd)
- docs: update READMEs, skills, and marketplace for plugin API enhancements (0c5093a)
- docs: align specialist configs, update READMEs with Data API and integration tables (201daf2)
- docs: explain multi-dimensional risk scoring in READMEs (ab6f9a6)
- docs: expand CLAUDE.md with architecture, patterns, and conventions (999707d)
- docs: fix README issues from 18-plugin specialist review (59d495b)
- docs: rewrite READMEs with differentiators and value-first openings (a89f1ff)

### Refactoring
- refactor: replace 12 domain api.py + adapters with generic CP proxy (5c1c1d7)
- refactor: housekeeping — scenarios, help commands, branding, stale paths (a2c1bc1)
- refactor: promote unified plugin to repo root, remove old plugins (9219d98)
- refactor: convert informal task prose to actual Task() dispatches across specialist agents (8da7b21)
- refactor(wicked-delivery): narrow scope to feature delivery tactics, migrate PMO agents to wicked-crew (32113de)
- refactor: consolidate caching into wicked-startah, remove wicked-cache plugin (1d0e938)
- refactor(wicked-workbench): replace catalog-based architecture with Plugin Data API gateway (c0af448)

### Chores
- Merge pull request #86 from mikeparcewski/fix/85-enforce-test-phase-injection (792da33)
- cleanup: dissolve startah/workbench domains, remove cache infra (18→16 domains) (62df101)
- cleanup: remove dead workbench code and stale references (27695cf)
- release: wicked-crew v1.3.0, wicked-jam v1.3.0, wicked-startah v0.12.0 (33cb5e4)
- release: wicked-observability v1.0.0, wicked-crew v1.2.3 (0e7f74b)
- release: wicked-smaht v4.3.1 (70f3e83)
- release: wicked-smaht v4.3.0, wicked-crew v1.2.2 (7ee6b25)
- release: wicked-smaht v4.2.0 (4e91bf0)
- release: wicked-scenarios v1.6.0, wicked-qe v1.3.0, wicked-product v1.2.1, wicked-engineering v1.2.1, wicked-platform v1.2.1, wicked-data v1.2.1, wicked-agentic v2.2.1 (df7f8da)
- release: wicked-scenarios v1.5.0 (4d5a7c6)
- release: wicked-smaht v4.1.0, wicked-scenarios v1.4.0 (dd2a368)
- release: wicked-crew v1.2.1, wicked-kanban v1.2.1 (c934ff2)
- Compare 4 signal-routing architecture versions and add PDF export (#64) (8534871)
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
- release: batch bump 14 plugins to patch (7af7913)
- release: wicked-workbench v0.7.2 (ab35680)
- release: wicked-workbench v0.7.1, wicked-mem v0.8.1, wicked-kanban v0.10.1 (62adb4d)
- release: wicked-crew v0.15.0, wicked-delivery v0.8.0, wicked-search v1.6.0, wicked-kanban v0.10.0 (59f7f71)
- release: wicked-crew v0.14.0, wicked-delivery v0.7.0, wicked-search v1.5.0, wicked-kanban v0.9.0 (0e06628)
- release: wicked-agentic v1.2.0, wicked-crew v0.13.0, wicked-data v0.4.0, wicked-delivery v0.6.1, wicked-engineering v0.8.0, wicked-jam v0.4.0, wicked-kanban v0.8.0, wicked-mem v0.7.0, wicked-patch v1.2.0, wicked-platform v0.3.0, wicked-product v0.3.0, wicked-qe v0.4.0, wicked-scenarios v0.3.0, wicked-search v1.4.0, wicked-smaht v2.7.0, wicked-startah v0.5.0, wicked-workbench v0.6.0 (5470682)
- release: wicked-delivery v0.6.0 (86413a5)
- chore: remove stale release notes from previous version (c0cdff9)
- release: wicked-delivery v0.5.0 (9b1872a)
- release: wicked-delivery v0.4.0, wicked-search v1.3.0 (8125a6c)
- release: wicked-workbench v0.5.0, wicked-kanban v0.7.0, wicked-mem v0.6.0, wicked-crew v0.12.0 (16eef1f)
- Merge pull request #2 from mikeparcewski/dependabot/uv/plugins/wicked-workbench/server/cryptography-46.0.5 (1489682)
- release: wicked-jam v0.3.0, wicked-smaht v2.6.0 (2b1245a)
- chore: CLAUDE.md conventions, search/patch fixes, data ontology command, test scaffolding (11aaf2d)
- release: wicked-crew v0.11.0 (12c7f1f)
- chore(deps): Bump cryptography in /plugins/wicked-workbench/server (62707ff)
- Merge remote-tracking branch 'origin/main' (f1f0e12)
- release: bump 18 plugins (bc1a9ed)
- Merge pull request #1 from arturl/main (6eefef4)
- Update plugins/wicked-engineering/commands/review.md (b9c8105)
- release: wicked-smaht v2.4.0, wicked-crew v0.9.2 (f05e63e)
- Add --focus tests to review command for LLM-generated test quality (6d729bb)
- review useless files (29b10d1)
- chore: normalize author to Mike Parcewski and fix repo URLs (ab8df47)

