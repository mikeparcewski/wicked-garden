# Changelog

## [2.10.0] - 2026-03-22

### Features
- feat: `smaht:briefing` command — session briefing pulling from mem, kanban, crew, and git
- feat: `smaht/discovery` skill — contextual command suggestions discovered dynamically from cross-references
- feat: README rewrite — leads with memory moat demo, intent-based "Start Here" table

### Cleanup
- fix: removed 5 dead Python scripts (672 lines) — feedback.py, tool_usage_stats.py, migrate_capabilities.py, plugin_status.py
- fix: moved test_gate_enforcement.py to tests/crew/

## [2.9.1] - 2026-03-22

### Bug Fixes
- fix: correct 31 broken script paths in commands/agents (missing domain prefix)
- fix: remove 4 references to scripts that never existed (compliance_checker, a11y-check, evidence, bootstrap)
- fix: disambiguate trigger collisions across 12 skills (design-review/visual-review, product-management/synthesize/requirements-analysis, gh-cli/github-actions, deliberate/debugging, compliance/audit)
- fix: replace generic trigger phrases in policy and reporting skills
- fix: add quoted trigger phrases to wickedizer skill
- fix: second-person "your PATH" → "the system PATH" in agent-browser
- fix: broken script paths in 6 platform/qe commands (observability→platform, scenarios→qe)
- fix: stale counts in README (142 cmds, 79 skills, 8 specialists) and CLAUDE.md
- fix: dead multi-model:collaborate command in docs/advanced.md
- fix: wg-test stale skill invocations and script path
- fix: hardcoded ~/Projects paths in new-generator command → ${CLAUDE_PLUGIN_ROOT}

## [2.9.0] - 2026-03-22

### Quality Investments
- feat: jam refs — facilitation-patterns.md (persona archetypes by problem type) + synthesis-patterns.md (structure, techniques, examples)
- feat: product help rewritten as task-based navigation ("I want to..." groupings)
- feat: persona agent enriched with archetype behavior patterns and task-type adaptations

### Cleanup (Third Pass)
- fix: remove ghost design specialist from specialist.json (merged into product)
- fix: startah_adapter.py skill reference wicked-garden:multi-model → wicked-garden:smaht:collaborate
- fix: relocate 6 orphaned scenario directories to correct domain owners
- fix: CLAUDE.md overview "17 domain areas" → "14 domain areas"
- fix: wg-scaffold discovers domains dynamically from commands/ directory (no hardcoded list)
- fix: persona skill table updated to 8 specialists (design merged into product)

## [2.8.0] - 2026-03-22

### Domain Consolidation (17 → 14 domains)
- refactor: design → product (v2.7.0: 5 commands, 3 agents, 5 skills)
- refactor: scenarios → qe (v2.7.0: 6 commands, 1 agent, 1 skill)
- refactor: multi-model → smaht (collaborate command moved)
- refactor: patch → engineering (7 commands, 1 skill, 2 scripts + generators)
- refactor: observability → platform (7 commands, 1 skill, 4 scripts)

### Orphan Skill Triage (9 → 4 cross-cutting)
- delete: control-plane skill (documented removed architecture)
- move: readme-style-guide → .claude/ dev tools (internal tooling)
- reassign: agent-browser → qe, imagery → product, issue-reporting → crew
- keep: deliberate, wickedizer, integration-discovery, runtime-exec (cross-cutting)

### Documentation
- add: README "Start Here" section with 3 opinionated entry paths
- update: all cross-references, aliases, domain counts, help commands

## [2.7.0] - 2026-03-22

### Quality & Hygiene
- fix: 2 skills exceeding 200-line limit (trust-and-safety, kanban) — content moved to refs/
- fix: add trigger phrases to persona skill for reliable matching
- fix: disambiguate 5 skill collision pairs (accessibility, review, data analysis)
- fix: add "This skill should be used when" framing to 8 skills
- fix: remove redundant "When to Use" body sections from agentic skills
- fix: replace hardcoded paths in test files with `${CLAUDE_PLUGIN_ROOT}`
- fix: replace secret scanner flag in infra.md example

### Chores
- chore: normalize git author metadata across commit history
- chore: remove tracked .DS_Store from repository

## [2.6.1] - 2026-03-21

### Bug Fixes
- fix: persona-agent color purple → magenta (valid value) (7ce7b15)
- fix: persona registry security — path traversal guard + cache dir permissions (38ff1c1)

### Documentation
- docs: update counts — 17 domains, 80 agents, 9 specialist roles, add persona domain (bc31ab0)

### Chores
- release: wicked-garden v2.6.0 — on-demand persona system (fd5ad9f)

## [2.6.0] - 2026-03-21

### Features
- feat: on-demand persona system with rich characteristics (b74985c)

### Chores
- release: wicked-garden v2.5.0 — crew quality gate enforcement + script-to-skill (c44a5a8)

## [2.5.0] - 2026-03-21

### Features
- feat: crew quality gate enforcement + script-to-skill conversion (0026743)

### Chores
- release: wicked-garden v2.4.0 — remove presentation domain (a8647ed)

## [2.4.0] - 2026-03-17

### Features
- feat: CLAUDE.md ↔ AGENTS.md sync + remove AGENTS.md write block (8847722)

### Removed
- remove: presentation skill domain (moved to separate repo)

### Bug Fixes
- fix: Windows compatibility — cross-platform Python resolution + TMPDIR fallback (9d36cf4)

### Chores
- release: wicked-garden v2.3.0 — Windows compatibility + Copilot CLI (61840d4)
- release: wicked-garden v2.2.0 — CLAUDE.md ↔ AGENTS.md sync (9d64122)

## [2.1.0] - 2026-03-15

### Features
- feat: capability-based dynamic tool routing for agents (#307) (#308) (818bad7)
- feat: wicked-garden v2.0.0 — Skills 2.0 foundations (#306) (d95b3a1)

### Bug Fixes
- fix: mark gate tasks completed after orchestrator returns (#309) (#310) (31d5f29)

## [2.0.0] - 2026-03-15

### BREAKING CHANGES
- Agent model tiers: 4 agents now use haiku (memory-recaller, memory-archivist, memory-learner, continuous-quality-monitor), 5 agents now use opus (execution-orchestrator, value-orchestrator, solution-architect, system-designer, safety-reviewer). Users on fixed model budgets should review.
- All 79 agents now have `allowed-tools` restrictions. Agents can only use explicitly listed tools. Previously agents had unrestricted tool access.

### Features
- feat: Skills 2.0 foundations — model tiers, allowed-tools, invocation control, portability (e288c1e)
- Agent model tiers: haiku for utility agents (75% cost reduction), opus for high-stakes reasoning (architecture, security, gate decisions)
- `allowed-tools` frontmatter on all 79 agents — explicit tool restrictions per agent role
- `user-invocable: false` on 6 background skills (smaht, control-plane, runtime-exec, integration-discovery, issue-reporting, observability)
- `disable-model-invocation: true` on 3 user-only skills (crew/workflow, kanban, presentation — presentation later moved to separate repo in v2.4.0)
- `portability: portable` on 25 cross-platform skills (works on Codex, Gemini CLI, OpenCode, pi-mono)
- wg-check updated with 3 new validation sections: agent Skills 2.0 compliance, skill portability compliance, invocation control audit

### Bug Fixes
- fix: remove leftover YAML list items in agent frontmatter (3fe2e1e)

### Architecture Decisions (council-validated)
- Commands stay as commands (context:fork cannot dispatch subagents — runtime verified)
- refs/ rename rejected (unanimous council verdict — Codex, Gemini, Claude)
- Agents stay as separate files (routing stability, no split prompt authority)
- context:fork reserved for new skills that genuinely benefit from isolation

### Migration from v1.x
- **No action required** for most users — all commands work identically
- If you rely on agents having unrestricted tool access, review the new `allowed-tools` assignments
- If you pin model tiers, note that 4 agents moved to haiku and 5 to opus
- v1.49.3 remains available: `claude plugins add mikeparcewski/wicked-garden@v1.49.3`

## [1.49.3] - 2026-03-10

### Chores
- perf: strip assistant turns from agent descriptions, reducing tokens by 66% (c6092bb)
- release: wicked-garden v1.49.2 (69d6bcf)

## [1.49.2] - 2026-03-10

### Bug Fixes
- fix: enforce required deliverables as blockers in phase approval (3a733d9)
- fix: split 7 oversized refs files, fix marketplace version drift (c5eb7c6)

### Chores
- release: wicked-garden v1.49.1 (340257b)

## [1.49.1] - 2026-03-09

### Chores
- perf: trim agent examples to 1 each, reducing description tokens by 45% (bcf6dc5)
- release: wicked-garden v1.49.0 (2bceeba)

## [1.49.0] - 2026-03-09

### Bug Fixes
- fix: resolve GitHub issues #301-#304 (5488ffe)

## [1.48.0] - 2026-03-09

### Features
- feat: inject wicked-garden hints into project CLAUDE.md during setup (0d646f9)

### Documentation
- docs: split README into lean sales page + detailed docs/ directory (13f9ffa)

## [1.47.0] - 2026-03-09

### Features
- feat: presentation skill maintenance, visual QA, and consistency (#300) (90b59ca)

### Bug Fixes
- fix: update old wicked-{domain} specialist references to short names (f754b88)

### Chores
- chore: fix validator warnings — marketplace version, CLAUDE.md roles (30ec563)
- release: wicked-garden v1.45.0 (0f6ecda)

## [1.45.0] - 2026-03-09

### Features
- feat: audit agents and strip specialist.json to lean manifest (#297, #298) (ab71c9c)

### Chores
- release: wicked-garden v1.44.0 (e21e8a0)

## [1.44.0] - 2026-03-09

### Features
- feat: unified adapter registry with within-call deduplication and timing metrics (#295)
  - New `AdapterRegistry` class consolidates duplicated `_load_adapters()` from fast/slow path assemblers
  - `timed_query` coroutine adds per-adapter timing, cache hit/miss tracking, and failure counting
  - `CACHE_BYPASS` constant for adapters requiring always-fresh queries (mem adapter)
  - Orchestrator metrics extended with `adapter_timings` for observability
  - 52 new unit tests covering all acceptance criteria

### Bug Fixes
- fix: stale "search" fallback in ADAPTER_RULES replaced with valid adapter names

### Chores
- chore: fix marketplace.json persona count (48 → 54)
- chore: fix hooks.json script count (5 → 7)
- chore: close #294 (post_tool.py refactor — already well-structured) and #296 (specialist simplification — misdiagnosed problem)
- chore: create #297 (audit orphaned agents) and #298 (clarify specialist.json role) as replacements

## [1.43.1] - 2026-03-08

### Chores
- chore: flatten schemas/ directory and add README (19e1ec0)
- release: wicked-garden v1.43.0 (7f123b2)

## [1.43.0] - 2026-03-08

### Features
- feat: product-first test phase and evidence packages for review (#291, #292) (cec3cfe)

### Chores
- release: wicked-garden v1.42.1 (f6c7e5e)

## [1.42.1] - 2026-03-08

### Bug Fixes
- fix: remove dead code in OpenAI provider and use provider-agnostic examples (8649812)

### Chores
- chore: consolidate thin refs, clean frontmatter, fix script paths (bb056e4)
- release: wicked-garden v1.42.0 (75d87c3)

## [1.42.0] - 2026-03-08

### Features
- feat: add OpenAI, Stability AI, and Replicate providers to imagery skill (d173440)
- feat: add imagery skill domain with review/create/alter sub-skills (ae6793c)

### Bug Fixes
- fix: make imagery review skill tool-agnostic (480f094)

### Chores
- release: wicked-garden v1.41.0 (e635090)

## [1.41.0] - 2026-03-08

### Features
- feat: add design specialist to discovery and ux/product signal routing (#290) (2e23d3d)

## [1.40.0] - 2026-03-07

### Features
- feat: rename resolve skill to deliberate — name now matches behavior (reflection/deliberation, not fixing) (#288)
- feat: auto-route low-complexity changes (score <= 2) to just-finish mode (#289)
- feat: enhance issue-reporting with research, duplicate detection, and SMART criteria enforcement (#287)

### Improvements
- refactor: consolidate standalone CLI skills (codex-cli, gemini-cli, opencode-cli, pi-mono-cli) into multi-model (#285)
- docs: comprehensive README update — accurate component counts (142/86/75), new features documented (#286)

### Stats
- 142 commands, 86 agents, 75 skills, 51 specialist personas
- Net reduction: ~1000 lines removed via skill consolidation

## [1.39.0] - 2026-03-07

### Features
- feat: full testing pyramid for QE — 6-layer test execution (unit, integration, visual, security, scenario, regression) with parallel dispatch and test requirement matrix (639ece1)
- feat: _run.py smart script wrapper — auto-help on argparse errors, rolled out to all 60 command files
- feat: change_type_detector.py — classify files as UI/API/both/unknown for deterministic QE routing
- feat: test_task_factory.py — auto-create evidence-gated test tasks with dependency wiring
- feat: validate_test_evidence() — artifact validation for UI screenshots and API payloads
- feat: QE nudges now suggest full testing pyramid based on change type (not just acceptance tests)

### Tests
- 82 new tests across test_change_type_detector.py, test_test_task_factory.py, test_evidence_validation.py

## [1.38.0] - 2026-03-07

### Features
- feat: project-scoped storage — isolate state per working directory (029f3f2)

### Chores
- release: wicked-garden v1.37.0 (6823090)

## [1.37.0] - 2026-03-07

### Features
- feat: fix GH#284, GH#283, GH#282, add resolve integration and phase_manager advance (d15e3ee)

### Chores
- release: wicked-garden v1.36.0 (bb2f433)

## [1.36.0] - 2026-03-07

### Features
- feat: add resolve skill and fix GH#280, GH#281, GH#283 (bb605a7)

### Chores
- chore: update README component counts (141 commands, 79 skills) (2e91a60)
- release: wicked-garden v1.35.2 (d7c18fc)

## [1.35.2] - 2026-03-07

### Bug Fixes
- fix: close setup gate bypass from stale session state across sessions (270a827)
- fix: harden setup gate and skip optional tools during setup (acf22f0)

### Chores
- release: wicked-garden v1.35.1 (286a1fa)

## [1.35.1] - 2026-03-07

### Bug Fixes
- fix: setup gate bypassed by stale session state across sessions (4c51226)

## [1.35.0] - 2026-03-07

### Features
- feat: add /wicked-garden:reset command for selective state reset (3a17dee)

### Bug Fixes
- fix: eliminate stale cp.py, SM_LOCAL_ROOT, and has_plugin references in skills (02366dc)

### Documentation
- docs: fix README counts and add reset command reference (35c9c32)

### Chores
- release: wicked-garden v1.34.0 (4a9679a)

## [1.34.0] - 2026-03-07

### Features
- feat: centralized prereq-doctor for tool detection, install, and error diagnosis (fb76f87)

## [1.33.0] - 2026-03-06

### Bug Fixes
- fix: eliminate stale CP references across 29 files, add rationalization checker (7767cb7)

### Refactoring
- refactor: rename ai-collaboration → multi-model, retire ai-conversation (2f6a407)

### Chores
- release: wicked-garden v1.32.0 (333bec7)

## [1.32.0] - 2026-03-06

### Features
- feat: refactor context assembly — delegate prompt_submit to smaht v2 orchestrator (84806c3)

## [1.31.0] - 2026-03-06

### Features
- feat: expand QE across the full lifecycle (closes #277, closes #278, closes #279) (237f597)

### Bug Fixes
- fix: quality check fixes — invalid agent color, non-standard trigger phrases (5ad3748)

### Documentation
- docs: update README for v1.30 — CP elimination, design domain, expanded QE (8f6feaf)

### Chores
- release: wicked-garden v1.30.0 (f96b818)

## [1.30.0] - 2026-03-06

### Features
- feat: eliminate control plane — skill-owned data with integration-discovery routing (closes #273) (78410fb)
- feat: expand QE across the full lifecycle (closes #271) (773f78b)

### Chores
- release: wicked-garden v1.29.0 (d0427ff)

## [1.29.0] - 2026-03-06

### Features
- feat: expand QE across the full lifecycle — idea to operating (#271)
  - New agent: requirements-quality-analyst (clarify phase quality gate)
  - New agent: testability-reviewer (design phase testability review)
  - New agent: continuous-quality-monitor (build phase quality signals)
  - New agent: production-quality-engineer (post-deploy quality monitoring)
  - specialist.json: QE now enhances clarify and design phases, 3 new personas (86 total agents)
  - smart_decisioning.py: new "quality" signal category with 20 keywords
  - phases.json: wicked-qe added to clarify and design phase specialists
  - New acceptance test scenario: scenarios/qe/qe-lifecycle-expansion.md

## [1.28.0] - 2026-03-06

### Bug Fixes
- fix: suppress CP warning noise at normal log levels (closes #276) (00ebf82)

## [1.27.0] - 2026-03-06

### Features
- feat: kanban scoped boards for domain workflows (#269) (dce2f4a)

## [1.26.0] - 2026-03-06

### Features
- feat: enforce gate execution (#274) and add text-as-code signals (#275) (4839b2d)

## [1.25.0] - 2026-03-06

### Features
- feat: close issues #260, #262 — observability expansion + CLI consolidation (252bd28)

## [1.24.0] - 2026-03-06

### Features
- feat: close issues #266, #272 — create design domain with 5 skills (69aa39f)

## [1.23.0] - 2026-03-05

### Features
- feat: close issues #261, #270 — jam workflow integration (e598d6e)
- feat: update wg-release with quality gate, update wg-issue with ralph-loop (56baaf3)
- feat: bundle marketplace plugins in project settings (776abfd)
- feat: close issues #259, #264 — CLI discovery and integration improvements (7f11882)
- feat: close issues #265, #267, #268 — UX polish and discoverability (175b910)

### Chores
- release: wicked-garden v1.22.0 (e6b4547)

## [1.22.0] - 2026-03-05

### Features
- feat: flatten single-skill directories, update README counts, add freshness check (3973dfa)

### Chores
- release: wicked-garden v1.21.0 (09c8332)

## [1.21.0] - 2026-03-05

### Features
- feat: close issues #252, #258 — worktree isolation, library knowledge base, smart naming (96dabd3)

## [1.20.0] - 2026-03-05

### Features
- feat: add search directory watcher hook integration — auto-detect stale indexes at session start (#249)
- feat: add HTTP source type for external plugin indexing with auth-scoped fetch (#250)
- feat: add jam transcript thinking field — expose per-persona deliberation via CLI (#256)

### Tests
- test: 52 new tests across watcher integration, external HTTP indexing, and jam thinking field

## [1.19.2] - 2026-03-05

### Bug Fixes
- fix: resolve crew issues #251, #253, #255 (76fcc23)

### Chores
- release: wicked-garden v1.19.1 (0267b2c)

## [1.19.1] - 2026-03-05

### Features
- feat: add presentation skill with full deck creation capabilities (6f832ce)

### Refactoring
- refactor: polish presentation skill per reviewer recommendations (ee1ea70)

## [1.19.0] - 2026-03-05

### Features
- feat: add presentation skill — full-featured deck creation in pptx and html formats with style learning, design registry, and four creation modes

### Refactoring
- refactor: rename ppt-maker skill to presentation, align with library conventions
- refactor: rename references/ to refs/ in presentation skill directory
- refactor: convert all CLI command syntax to natural language invocations
- refactor: update 8 storage namespaces from ppt-maker:* to presentation:*
- refactor: remove client-specific example data from presentation skill docs

### Chores
- release: wicked-garden v1.18.0 (9b6d4db)

## [1.18.0] - 2026-03-05

### Features
- feat: add default skill validation mode to wg-test using skill-creator (#257) (215693f)
- feat: add operational logging and observability commands (94ec07d)

### Chores
- release: wicked-garden v1.17.10 (8f5e2e5)

## [1.17.10] - 2026-03-05

### Bug Fixes
- fix: resolve issues #241-#248, add QE test type taxonomy (b1dc057)
- fix: resolve issues #240-#248, add gate reviewer policy, release v1.17.9 (828ea04)

## [1.17.9] - 2026-03-04

### Bug Fixes
- fix: update old wicked-{domain}: refs to wicked-garden:{domain}: in scenarios (e9bdb0b)
- fix: improve skill description trigger phrases and formatting (#236, #237, #238) (3de0ffc)
- fix: front-load mandatory indexing in smaht:onboard command (#234) (57b1765)

### Chores
- release: wicked-garden v1.17.8 (2ce7900)
- release: wicked-garden v1.17.7 (c06a29a)

## [1.17.6] - 2026-03-04

### Bug Fixes
- fix: resolve search:index adapter issues (#229-#233) (9be0aa3)

### Chores
- release: wicked-garden v1.17.5 (3acae02)

## [1.17.5] - 2026-03-04

### Bug Fixes
- fix: wire lineage derivation and service map into search index command (ea7cac0)

### Chores
- release: wicked-garden v1.17.4 (656ebfd)

## [1.17.4] - 2026-03-04

### Bug Fixes
- fix: restore aggressive memory capture lost during plugin unification (5fd21c0)
- fix: smaht onboard now triggers deep linking (lineage + service-map) (14c08e4)

## [1.17.3] - 2026-03-04

### Chores
- release: wicked-garden v1.17.2 (aed5a85)

## [1.17.2] - 2026-03-04

### Bug Fixes
- fix: resolve 14 GitHub issues across search, smaht, crew, and infrastructure (022df1b)

### Chores
- release: wicked-garden v1.17.1 (3a30ffc)

## [1.17.1] - 2026-03-04

### Bug Fixes
- fix: O(1) import resolution and progress reporting in search linker (cba23f4)

### Chores
- release: wicked-garden v1.17.0 (ddc1dc2)

## [1.17.0] - 2026-03-04

### Bug Fixes
- fix: strengthen lifecycle enforcement across 6 areas (2458c48)

## [1.16.0] - 2026-03-04

### Bug Fixes
- fix: resolve remaining skill review findings (round 2) (b12790b)
- fix: resolve skill review findings (9e875f2)

## [1.15.2] - 2026-03-04

### Bug Fixes
- fix: move phases.json to .claude-plugin/ where plugin config belongs (7e275aa)

## [1.15.1] - 2026-03-04

### Refactoring
- refactor: replace file-based release notes with GitHub releases (0a5a470)

### Chores
- release: wicked-garden v1.15.0 (266e070)

## [1.15.0] - 2026-03-04

### Chores
- release: wicked-garden v1.14.0 (74918f7)

## [1.14.0] - 2026-03-04

### Features
- feat: resolve remaining gaps in #198, #200, #202 issue implementations (0626882)

## [1.13.0] - 2026-03-04

### Features
- feat: memory auto-extraction via MemoryPromoter in Stop hook (#198)
- feat: QE trio delegation for scenario testing with --no-qe flag (#199)
- feat: normalized scoring model with 8 dimensions and 5 routing lanes (#201)
- feat: QE evidence enforcement with SHA-256 checksums and INCONCLUSIVE verdicts (#202)
- feat: complexity pre-flight gate in crew:start with --quick/--force flags (#203)

### Bug Fixes
- fix: context inflation via session state dedup and pressure-scaled budgets (#200)
- fix: reversibility inversion in smart_decisioning scoring (Codex review)
- fix: context_hash field missing from SessionState (Codex review)
- fix: onboarding bypass on HOT path dedup (Codex review)
- fix: crew hint guard checking wrong session field (Codex review)

## [1.12.1] - 2026-03-04

### Chores
- release: wicked-garden v1.12.0 (daa429e)

## [1.12.0] - 2026-03-03

### Bug Fixes
- fix: scope crew projects by workspace to prevent cross-session bleed (598e30d)

### Chores
- release: wicked-garden v1.11.2 (c6cda0e)

## [1.11.2] - 2026-03-03

### Bug Fixes
- fix: resolve 19 open issues across search, kanban, crew, patch, smaht, agentic, observability, and scenarios (5ee4935)
- fix: resolve Codex review findings for cp-uuid-integration (#153-#157) (60256ee)

### Chores
- release: wicked-garden v1.11.1 (0082b50)

## [1.11.0] - 2026-03-03

### Features
- feat: resolve 10 enhancement issues (#153-#157, #165, #175, #179-#181) (579fa15)

### Bug Fixes
- fix: quote argument-hint YAML values in 34 command files (84fea1f)
- fix: resolve remaining open issues (#169-#171, #174, #178) (bd470da)
- fix: resolve 9 test-run bugs and migrate search to local-first (#158-#168) (c419303)
- fix(kanban): fix KanbanStore import shadowed by package __init__.py (0a9a0b4)

### Chores
- Merge pull request #183 from mikeparcewski/feat/resolve-enhancement-issues (00eddfb)
- Merge pull request #182 from mikeparcewski/fix/resolve-all-open-issues (4a98663)
- release: wicked-garden v1.10.1 (10bdb6b)

## [1.10.1] - 2026-03-03

### Bug Fixes
- fix: add `integrity-check` subcommand to `unified_search.py` with `--repair` flag for FTS5 index corruption (#158)
- fix: add general Python symbol extraction fallback via tree-sitter AST in `python_adapter.py` (#159)
- fix: support multi-specialist array format `{"specialists": [...]}` in `health_probe.py` (#161)
- fix: remove false-positive "scoring" keyword from infrastructure-framework archetype (#162)
- fix: update stale model ID to `anthropic/claude-sonnet-4-6` in jam scenario (#163)
- fix: rewrite 3 smaht scenarios with executable bash steps calling CLI scripts directly (#165)
- fix: migrate all 18 search commands to local-first routing with CP as optional enhancement (#166)
- fix: route kanban comments through local `kanban.py add-comment` instead of CP (#167)
- fix: accept specialist role values (not just category keys) in `specialist_discovery.py` validation (#168)
- fix(kanban): fix KanbanStore import shadowed by package `__init__.py` (0a9a0b4)

### Documentation
- docs: update README and CLAUDE.md with current component counts (125 commands, 79 agents, 71 skills, 48 personas)
- docs: update plugin.json and marketplace.json descriptions with correct persona count

## [1.10.0] - 2026-03-02

### Features
- feat(kanban): add initiative command for crew-kanban integration (08b0b99)
- feat(smaht): add context command for structured context package building (08b0b99)

### Bug Fixes
- fix(crew): resolve cross-domain script coupling — crew no longer calls kanban/smaht scripts directly (08b0b99)
- fix(crew): fix broken `{CREW_PLUGIN_ROOT}` variable in execute.md (08b0b99)
- fix(smaht): fix wrong path for context_package.py in debug.md (08b0b99)

### Chores
- chore: remove stale RELEASE-1.7.1.md and RELEASE-1.8.0.md (025aee2)

## [1.9.0] - 2026-03-02

### Bug Fixes
- fix: resolve 4 post-test-run issues (c17d4de)
- fix(setup): update session state on mid-session mode switch (1e1e011)
- fix(search): restore 8 scripts dropped during plugin consolidation (bb0711d)

### Chores
- release: wicked-garden v1.8.0 (ef45879)

## [1.8.0] - 2026-03-02

### Features
- feat: add local-only SQLite storage mode as default (475bc98)

### Chores
- release: wicked-garden v1.7.1 (3e5e129)

## [1.7.1] - 2026-03-02

### Features
- feat: implement hub-and-spoke CP project UUID integration (#153-#157) (4f8f76e)

### Chores
- release: wicked-garden v1.7.0 (0a4b6e3)

## [1.7.0] - 2026-03-02

### Features
- feat: write traces to control plane and improve onboarding re-detection (c3a0599)

### Chores
- release: wicked-garden v1.6.2 (47a035d)

## [1.6.2] - 2026-03-02

### Bug Fixes
- fix: use plain text questions when AskUserQuestion is broken in dangerous mode (8f77b01)

## [1.6.1] - 2026-03-02

### Bug Fixes
- fix: allow user responses through setup gate during setup flow (22614e0)

### Chores
- release: wicked-garden v1.6.0 (b3ce4a7)

## [1.6.0] - 2026-03-02

### Features
- feat: rewrite setup flow with batched questions and answer verification (64c8294)

### Chores
- release: wicked-garden v1.5.2 (f17cfce)

## [1.5.2] - 2026-03-02

### Bug Fixes
- fix: setup enforcement gate now actually blocks prompts (a891858)

## [1.5.1] - 2026-03-02

### Bug Fixes
- fix: SessionStart hook was using `systemMessage` (user-visible warning) instead of `hookSpecificOutput.additionalContext` (model context injection) — setup directive was never reaching Claude (6d5c3d0)
- fix: add UserPromptSubmit setup gate that blocks all prompts with `decision: "block"` until `setup_complete` is true — enforces first-run setup instead of relying on advisory context
- fix: restructure session briefing into user-facing status block showing connection mode, CP status, onboarding state, and active crew/kanban work

## [1.5.0] - 2026-03-02

### Features
- feat: consolidate setup/onboarding into single interactive wizard (6c908ff)
  - `/wicked-garden:setup` is now the single entry point for getting started
  - Auto-detects what's needed: CP config, onboarding, or both
  - Interactive questions via AskUserQuestion (local/remote/offline, full/quick/skip onboarding)
  - `--reconfigure` flag to reset and re-run everything
- feat: auto-clone wicked-control-plane from git on first use
  - Bootstrap clones `github.com/mikeparcewski/wicked-control-plane` into plugin cache
  - Auto-installs dependencies and starts CP when mode is local-install
  - Saves resolved path to config for faster subsequent sessions
- feat: setup hint in every session briefing for discoverability

### Bug Fixes
- fix: resolve issues #145-#148 — split refs, add triggers, fix H1, add observability skill (bd4d7e1)
- fix: replace all `wicked-viewer` / `~/Projects` paths with `~/.claude/plugins/cache/wicked-control-plane`

### Refactoring
- refactor: delete `commands/welcome.md` — consolidated into `commands/setup.md`
- refactor: bootstrap directives unified to always point at `/wicked-garden:setup`

## [1.4.0] - 2026-03-01

### Features
- feat: use CP FTS5 search verb for memory recall (#136) (6e2be5d)

### Bug Fixes
- fix: rewrite 31 scenarios to outcome-based criteria across 7 domains (33c207e)
- fix: align memory with CP schema + standardize skill descriptions (e994f46)
- fix: StorageManager CP fallback + local text search + wg-test CP preflight (#133, #134) (c125b7c)

### Refactoring
- refactor: migrate search domain from unified_search.py to control plane (895e018)

## [1.3.3] - 2026-03-01

### Bug Fixes
- fix: update specialist names, add trigger phrases, remove redundant sections (#128, #129, #130) (fd0f29a)
- fix(crew): specialist discovery now parses unified specialists array (3992295)
- fix: resolve 3 critical bugs found by wg-test --all (#125) (595dcc3)

### Refactoring
- refactor: split 4 oversized agentic refs/ files into focused modules (#127) (0f90477)

### Chores
- Merge pull request #132 from mikeparcewski/feat/127-split-oversized-refs (69f6134)
- Merge pull request #131 from mikeparcewski/fix/128-130-skill-content-fixes (c77179d)
- Merge pull request #126 from mikeparcewski/claude/run-wg-tests-q9fco (cb04016)
- release: wicked-garden v1.3.2 (6506ee5)

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

