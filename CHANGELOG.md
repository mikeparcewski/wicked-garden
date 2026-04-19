# Changelog

## [6.2.0] - 2026-04-19

### Features
- feat(crew): ops bundle — HMAC dispatch-log + log retention + pre-flip monitoring (#513) (8e8bd5f)
- feat(crew): hardening + tests — yolo guardrails + BLEND test tighten + 6-phase traversal (#512) (c883271)
- feat(crew): storage + DX bundle — reviewer-context, atomic conditions, amendments.jsonl, explain skill (#511) (9ed1cdc)
- feat(crew): review machinery correctness — blind reviewer, multi-reviewer invariant, re-eval skill contract (#510) (3c6c1e4)
- feat(crew): AC-11 CI benchmark lane — enforce 2x p95 SLO on gate-result load (#509) (7c84b93)

### Bug Fixes
- fix(crew): CLI parity bundle — honest stubs, deliverables from config, mode-3 default, status field parity (closes #492, #493, #494, #498, #499) (#508) (d260649)

### Documentation
- docs(propose-process): rubric doc drift — yolo-at-full-rigor + phases.primary + tasks.phase (closes #495, #496, #497) (#507) (dab62f9)

### Chores
- Closes #479, #471: gate-result ingestion security hardening (floor) (#501) (90c5b2c)
- release: wicked-garden v6.1.0 — mode-3 formal crew execution + issue sweep (903be9c)

## [6.1.0] - 2026-04-19

### Features
- feat(drift,session): WE runs rules + SessionState telemetry producers (#459) (#489) (2bdcfa9)
- feat(crew): enforce augment cap in _run_checkpoint_reanalysis (AC-9) (#487) (595f541)
- feat(crew): convergence lifecycle scenario + agent codification (#491) (9205575)
- feat(crew): mode-3 phase-executor + gate dispatch + #466 legacy audit (#472) (500cb75)
- feat: wire SessionState + build-phase guard hook + R3/R5 AST heuristics (#462) (#469) (e600d96)
- feat(#461): wire process_memory facilitator_context + retro auto-populate (#463) (3ceacf1)
- feat(platform): autonomous session-close guard pipeline (#456) (4084664)
- feat(delivery): persistent process memory + kaizen backlog (#454) (7658fb9)
- feat(qe): semantic reviewer — spec-to-code alignment verification (#455) (9d5c114)
- feat(crew): artifact convergence lifecycle with stall detection (#453) (ead6a63)
- feat(delivery): cross-session quality telemetry + drift detection (#452) (d123b0b)
- feat(crew): persistent contrarian agent + challenge gate (#442) (#451) (e2ad031)
- feat(product): scored spec quality rubric + clarify-gate enforcement (#450) (0175fda)
- feat(skills): add context: fork to heavy workflow skills (#332) (#449) (4418eb1)
- feat(qe): coverage tracker + wicked.coverage.changed emit (#424) (#427) (8c0098c)
- feat(platform): wire security + compliance bus emits via agent prompts (#426) (aa012e0)
- feat(delivery): wire rollout + experiment bus emits via agent prompts (#425) (cac3f6b)
- feat(jam): bus emit points + synthesis-trigger consumer (#409) (#419) (e22eeea)
- feat(qe): scenario scaffold consumer on build->test-strategy (#410) (#418) (1f1b307)
- feat(bus): close #407 emit gaps + #414 consumer budget enforcement (#421) (fb11e50)
- feat(bus): platform + qe emit points (#412) (#420) (76aac32)
- feat(smaht): pull-model context assembly — replace push briefings with on-demand pulls (80e024f)

### Bug Fixes
- fix(scenarios): refresh 05-qe-gate for v6 approval-check ordering (#490) (63bb67c)
- fix(propose-process): auto-insert challenge phase at complexity >= 4 (#486) (4c011d0)
- fix(scenarios): align artifact-state-machine assertions with CLI output shape (#485) (36228a9)
- fix: match actual approve-blocked message in phase-boundary-reeval Case 2 (#484) (fec0a6c)
- fix(crew): schema validator for facilitator plan JSON (closes #430) (#436) (74b5030)
- fix(release): bump plugin.json + marketplace.json to 5.1.0 (4f454ea)

### Tests
- test(crew): add challenge-gate-enforcement acceptance scenario (#458) (#488) (3bd59ff)

### Chores
- release: v6.0.1 — flatten nested skill paths so they register (#441) (b8b0a59)
- release: v6.0.0 — promote out of beta (#440) (1706a53)
- release: v6.0.0-beta.5 — fix skill registration (#439) (a35d9be)
- release: v6.0.0-beta.4 — autonomy mechanism + #332 partial (#438) (e7a68a3)
- release: wicked-garden v6.0.0-beta.3 — v6 reliability drop (#437) (3d0da5a)
- release: wicked-garden v6.0.0-beta.2 — v6 cutover fixes (7bddb8d)
- chore(v6): cleanup — delete signal_library, rubric v1.1 tightening, phase_manager fix (7d9465a)
- release: v6.0.0-beta.1 — facilitator replaces rule engine (#429) (f09264f)
- release: wicked-garden v5.2.0 — complete wicked-bus phase-2 (f3ea192)
- release: wicked-garden v5.1.0 — round out bus integration phase-2 (388dcf1)
- release: v5.0.0 — retire kanban domain, migrate to native TaskCreate metadata (#417) (75faaeb)
- release: wicked-garden v4.10.0 — pull-model context assembly (22da8ae)

## [6.0.1] - 2026-04-18

**Flatten skill paths so they actually register.** Claude Code's skill auto-discovery scans `skills/` for subdirectories containing `SKILL.md` — it does NOT recurse into sub-subdirectories. Skills at `skills/<domain>/<name>/SKILL.md` (two levels deep) never registered as model-invocable. The prior repo convention of nesting skills by domain was documentation-only; nobody had tried to invoke them via `Skill()` so the registration gap was invisible until v6.0 shipped `adopt-legacy` as a nested new skill.

### Fixed

Moved 5 skills from nested to flat paths so they actually register:

| Old | New | Registered As |
|---|---|---|
| `skills/crew/adopt-legacy/` | `skills/adopt-legacy/` | `wicked-garden:adopt-legacy` |
| `skills/crew/propose-process/` | `skills/propose-process/` | `wicked-garden:propose-process` |
| `skills/crew/workflow/` | `skills/workflow/` | `wicked-garden:workflow` |
| `skills/qe/acceptance-testing/` | `skills/acceptance-testing/` | `wicked-garden:acceptance-testing` |
| `skills/search/unified-search/` | `skills/unified-search/` | `wicked-garden:unified-search` |

All references throughout the codebase updated — commands, hooks, scripts, CHANGELOG, process-plans.

### Impact

- These 5 skills are now Skill()-invocable for the first time.
- The 3 that carry `context: fork` (workflow, acceptance-testing, unified-search) can actually fork now.
- `/wicked-garden:crew:start` routes to `wicked-garden:propose-process` (was Unknown skill).
- `/wicked-garden:crew:adopt-legacy` becomes usable for beta.3 project upgrades.

## [6.0.0] - 2026-04-18

**v6.0 production release.** Promotes beta.5 out of pre-release. The v6
autonomy mechanism + issue #332 context:fork shipped cleanly at the code
level (66/66 unit tests, 10/10 facilitator measurement scenarios, validator
selftests all green). Skill-registration behavior on the build machine
showed intermittent issues that appeared to be local install-state, not
packaging — promoting to 6.0 and expecting fresh installs to pick up all
5 newly-registering skills. If the skill-registration issue reproduces on
a clean install, a 6.0.1 patch will follow.

**Everything from beta.4 + beta.5 ships:**
- v6 autonomy mechanism (shift-left phase-boundary gates, bidirectional
  re-eval, codified reviewer matrix, JSONL addendum log, adopt-legacy skill)
- Issue #332 partial — `context: fork` on 3 heavy skills (crew:workflow,
  qe:acceptance-testing, search:unified-search)
- Breaking change — `CREW_GATE_ENFORCEMENT=legacy` deleted
- Skill-frontmatter cleanup — removed `disable-model-invocation: false`
  from 5 SKILL.md files that appeared to suppress registration

## [6.0.0-beta.5] - 2026-04-18

**Skill-registration fix.** Beta.4 shipped 5 SKILL.md files with
`disable-model-invocation: false` in frontmatter. Empirically that key —
at any value including `false` — suppresses model-invocability (Claude Code
appears to treat presence-of-key as opt-out). Removed the line from:
- `skills/adopt-legacy/SKILL.md`
- `skills/propose-process/SKILL.md`
- `skills/workflow/SKILL.md`
- `skills/acceptance-testing/SKILL.md`
- `skills/unified-search/SKILL.md`

`skills/persona/SKILL.md` retains `disable-model-invocation: true` (intentional — user-only).

After this release:
- `Skill(skill="wicked-garden:adopt-legacy")` becomes invokable
- `Skill(skill="wicked-garden:propose-process")` becomes invokable (was unknown throughout the v6 rebuild)
- `context: fork` on the 3 edited skills can finally activate on Skill() dispatch
- Total invocable skill count should go up by 5 post-reload

## [6.0.0-beta.4] - 2026-04-18

**v6.0 autonomy mechanism + issue #332 partial** — shift-left phase-boundary
gates, bidirectional re-eval with prune + re-tier-down, codified reviewer
matrix, JSONL addendum log, and the adopt-legacy skill. Also ships partial
delivery of issue #332 (3 of 6 heavy skills got `context: fork`).

**Still beta** because runtime behavior has not been validated in a live Claude
Code session — the plugin cache on the build machine runs an older version, so
all testing in this release cycle was via direct Python invocation (66/66 unit
tests, 10/10 measurement scenarios, validator selftests, canary dogfood).
Hook firing, phase-start gate dispatch, JSON addendum validation at approve
time, and `context: fork` forking behavior need live-runtime verification on
first post-install session.

**Breaking change**: `CREW_GATE_ENFORCEMENT=legacy` is deleted (D3 — no backward
compat flag in 6.0). There is no env-var escape hatch. Use
`/wicked-garden:adopt-legacy` to upgrade projects started on beta.3.

### Issue #332 partial delivery

Originally scoped for 6 heavy skills; actually ships fork on 3:
- ✓ `skills/workflow/SKILL.md` — `context: fork` applied
- ✓ `skills/acceptance-testing/SKILL.md` — `context: fork` applied
- ✓ `skills/unified-search/SKILL.md` — `context: fork` applied
- ✗ `qe:automate` — deferred; thin skill wrapper was dead code (command took precedence). Would need command body moved into skill body to actually fork.
- ✗ `crew:just-finish` — deferred; same structural pattern.
- ✗ `engineering:debug` / `jam:brainstorm` — dropped from scope by clarify-phase triage (conversational + inline-consumed).

3 stale `TODO (Issue #332): When Claude Code supports context: fork` blocks cleared from `skills/workflow`, `skills/unified-search`, `skills/acceptance-testing` — the feature is supported and documented in the official Claude Code skills docs.

### Post-build fixes (from plugin-validator pass)

- `skills/propose-process/SKILL.md` trimmed 233 → 197 lines (re-eval section extracted to `refs/re-evaluation.md`).
- `scripts/_session.py` — `phase_start_gate_due` added as a declared dataclass field (was a transient attr, silently dropped by `asdict()` serialization — AC-11 was broken in bytecode).
- `scripts/crew/phase_manager.py` — 6 dead `GATE_ENFORCEMENT_MODE == "legacy"` branches deleted (R1 dead code + D3 contradiction from the 4-variable-hardcoded-strict constant left behind).
- Deleted the 2 dead-wrapper SKILL.md files (`skills/qe/automate/SKILL.md`, `skills/crew/just-finish/SKILL.md`) that added no content their co-located commands didn't already have.
- `.claude-plugin/components.json` skills count corrected to 88 (66 pre-existing + 1 new adopt-legacy; 2 new edits retained but wrappers removed).

### Added

- **Shift-left phase-boundary gates** — every phase now has a named gate
  (`requirements-quality`, `design-quality`, `testability`, `code-quality`,
  `evidence-quality`, `final-audit`). Phase advance is blocked until the gate
  reviewer renders a non-REJECT verdict. Gate reviewer assignment is read from
  `.claude-plugin/gate-policy.json` at approve time by `_resolve_gate_reviewer()`
  in `phase_manager.py` — not from rubric prose.
- **Bidirectional re-eval loop** — `_run_checkpoint_reanalysis` now supports all
  three mutation directions (`prune`, `augment`, `re_tier`). Prune and re-tier UP
  auto-apply. Re-tier DOWN auto-applies only when tier is rubric-set and ≥2
  HIGH/MEDIUM factors are disproven; deferred for confirmation when tier was
  user-overridden (`rigor_override` in project state).
- **Phase-start heuristic gate** (`scripts/crew/phase_start_gate.py`) — fires
  before the first specialist engages on each phase; emits a `systemMessage`
  directive when task-completion count or evidence file mtimes changed since
  `last_reeval_ts`. Fail-open: missing chain data returns no-op with warning.
- **JSONL addendum log** — re-eval output is appended to
  `phases/{phase}/reeval-log.jsonl` (one JSON record per line, D8).
  `validate_reeval_addendum.py` validates each line; approve is blocked until a
  conformant addendum exists (fail-closed).
- **`gate-policy.json`** (`.claude-plugin/gate-policy.json`) — codified Gate ×
  Rigor reviewer matrix (D1, D4). Carries dispatch semantics per entry: mode
  (`sequential`, `parallel`, `council`, `self-check`) and fallback agent.
- **`adopt-legacy` skill + script** (`scripts/crew/adopt_legacy.py`,
  `skills/adopt-legacy/`) — detects three beta.3 legacy markers (missing
  `phase_plan_mode`, markdown re-eval addendums, legacy bypass env-var
  references) and transforms them in-place. Idempotent. Dry-run by default.
- **Acceptance scenarios** (`scenarios/crew/phase-boundary-reeval.md`) — five
  deterministic acceptance cases covering AC-5, AC-8, AC-9, AC-6, AC-7.
- **`audit_skip_log.py`** (`scripts/crew/audit_skip_log.py`) — scans all phase
  directories for unresolved `skip-reeval-log.json` entries. Final-audit gate
  returns CONDITIONAL until all entries are marked resolved.
- **`--skip-reeval`** flag on `phase_manager.py approve` — per-invocation
  emergency bypass requiring a mandatory `--reason` string. Writes to
  `phases/{phase}/skip-reeval-log.json`. No env-var or config default may set it
  implicitly (AC-15).

### Changed

- **`skills/propose-process/SKILL.md`** — new `## Phase-boundary gates`
  section lists all 6 gate names; new `## Re-evaluation mode (bidirectional, v6)`
  section describes the phase-start heuristic + phase-end full re-eval state
  machine; `## Interaction mode` updated to note D7 bidirectional rules.
- **`skills/propose-process/refs/gate-policy.md`** — rewritten as
  human-readable description of `gate-policy.json` (documentation only; not read
  by code).
- **`skills/propose-process/refs/plan-template.md`** — task chain table
  updated to surface per-phase gate names.
- **`skills/propose-process/refs/output-schema.md`** — gate-finding task
  metadata documented (`verdict`, `min_score`, `score` keys).
- **`commands/crew/migrate-gates.md`** — rewrites the beta-era migration guide
  to point at `adopt-legacy` instead of the now-deleted env-var bypass.

### Breaking Changes

- `CREW_GATE_ENFORCEMENT=legacy` environment variable is **deleted**. Any script,
  alias, or CI job that sets it must be updated. Projects relying on the legacy
  bypass must run `/wicked-garden:adopt-legacy` before upgrading.
- Phase approve is now fail-closed on missing re-eval addendum. Beta.3 projects
  that never ran a phase-end re-eval will be blocked at the first approve call.
  Recovery: run `--skip-reeval --reason "<justification>"` once per phase to
  unblock and log the bypass for final-audit review.

## [6.0.0-beta.3] - 2026-04-18

**v6 reliability drop** — bundles #430 (shipped in beta.2.1 via #436) plus
four reliability hardening items surfaced during the first live v6 dogfoods.
Focus: the v6 happy path should work without surprise in a fresh install
session.

### Added

- **Critical-skill smoke test (#434)** — `hooks/scripts/bootstrap.py` now
  checks that `skills/propose-process/SKILL.md` exists on disk at session
  start. When present, emits a `[Skills]` briefing note telling Claude how to
  handle "Unknown skill" errors (run `/reload-plugins`). When missing, flags
  the plugin install as incomplete. Turns a cryptic class of errors into a
  diagnostic path.
- **Emission verifier (#432)** — new `scripts/crew/verify_chain_emission.py`
  + Step 8.5 in `commands/crew/start.md`. After the task chain is emitted,
  compares native task count (filtered by chain_id) against the plan's
  `tasks[]`. Mismatches are surfaced with missing-title hints, not silently
  ignored.
- **Current-chain helper (#431)** — new `scripts/crew/current_chain.py` reads
  native tasks by `metadata.chain_id`, summarizes counts by status, and
  discovers evidence manifests under `phases/*/evidence/`. Wired into the
  facilitator re-eval directive in `hooks/scripts/prompt_submit.py` so the
  re-eval call has real data instead of prose "figure it out."

### Changed

- **Brain storage hardening (#433)** — `commands/crew/start.md` Step 10 now
  retries once, writes a `.pending-brain-store.json` sentinel on failure, and
  surfaces a WARNING to the user instead of failing silently. Added a new
  Step 0.5 to `commands/crew/execute.md` that flushes the sentinel on the
  next crew invocation when the brain becomes reachable.

### Fixed

- Diagnostic for the v6 plugin-cache-stale gotcha that bit the first two live
  `crew:start` invocations. Not a registry query (hooks can't do that) — just
  a filesystem check that turns silence into an actionable hint.

## [6.0.0-beta.2] - 2026-04-18

**v6 cutover fixes** surfaced during the first live dogfood of `crew:start`
→ `crew:execute` → `crew:approve`. Three enforcement paths in
`phase_manager.py` still looked for v5-era artifacts and would either block
the facilitator's minimal-rigor fast path or silently override its phase
plan. All three now defer to the facilitator when `phase_plan_mode ==
"facilitator"`. See issue #435.

### Fixed

- `phase_manager._check_phase_deliverables`: when `phase_plan_mode ==
  "facilitator"` and `process-plan.md` + parseable `process-plan.json` are
  present, treat them as satisfying `phases.json` `required_deliverables`.
  Unblocks approve without stub `complexity.md` / `acceptance-criteria.md`
  files or `--override-deliverables`. Legacy projects still enforced.
- `phase_manager._check_gate_run`: when `rigor_tier == "minimal"` and
  `status.md` contains a `signoff:` block with `result: approved` (or
  `conditional`), treat the gate as run. Minimal rigor is explicitly
  fast-pass per the facilitator rubric; this removes the need for
  `--override-gate` on every approve call.
- `phase_manager.validate_phase_plan`: when `phase_plan_mode ==
  "facilitator"`, skip complexity-driven injection of test-strategy/test
  phases. The facilitator's explicit phase list is authoritative; checkpoint
  re-analysis no longer silently expands a 3-phase minimal plan into 5.

### Manifests

- `.claude-plugin/components.json` counts corrected to disk reality:
  `commands: 147` (was 154), `skills: 87` (was 89). Domain list unchanged.
- `plugin.json` + `marketplace.json` bumped to `6.0.0-beta.2`.

## [6.0.0-beta.1] - 2026-04-18

**v6 is the rebuild**: the v5 keyword-based rule engine that drove crew
decisioning (`scripts/crew/smart_decisioning.py`, ~2,430 LOC) and the
push-model tiered context-assembly orchestrator (`scripts/smaht/v2/`, 11
files, ~2,950 LOC) are gone. In their place, a single progressive-disclosure
rubric — the `wicked-garden:propose-process` facilitator — reads the
work, scores 9 factors, picks specialists by reading agent frontmatter
directly, selects phases, sets rigor tier, and emits a full task chain. Context
assembly shifts from "push a briefing every turn" to "subagents pull what they
need via wicked-brain + wicked-garden:search."

### Breaking

- `/wicked-garden:crew:start` now invokes the facilitator rubric. Output shape
  differs from v5: no `signals_detected`, no `archetypes`, no `routing_lane` —
  replaced with `factors`, `specialists`, `phases`, `rigor_tier`, `complexity`.
  The command writes `process-plan.md` (markdown) + `process-plan.json` (raw)
  to the project directory.
- `WG_FACILITATOR` environment variable removed. v5 ran under
  `WG_FACILITATOR=legacy`; v6 has no legacy path. If you need v5 behavior,
  pin the `5.2.0` tag.
- `--quick` and `--no-auto-finish` flags on `crew:start` removed. These were
  v5 conflations of two orthogonal axes (phase plan and interaction mode).
  Use `--rigor=minimal` for a lighter phase plan, `--yolo` to skip user
  prompts, or both.
- `scripts/smaht/v2/orchestrator.py gather` / `route` CLI removed. Replaced by
  `/wicked-garden:smaht:smaht` (thin brain + search shim) and direct
  `wicked-brain:search` / `wicked-brain:query` invocations.
- `HOT/FAST/SLOW/SYNTHESIZE` context-assembly tiers no longer exist. Intent
  classification is a tiny inline heuristic in `prompt_submit.py` that only
  fires for the synthesize skill path.
- `HistoryCondenser` ticket-rail (current_task, decisions, file_scope,
  active_constraints, open_questions) removed. Session working state is now
  the facilitator's `process-plan.md` + `SessionState` (simple key/value) +
  native in-progress tasks.
- `/wicked-garden:smaht:debug` output shape changed — no more HOT/FAST/SLOW
  routing log; shows SessionState + last N bus events + active crew project.
- `detect_swarm_trigger()` relocated from `scripts/crew/smart_decisioning.py`
  to `scripts/crew/swarm_trigger.py`. Same public signature; the import
  changes.

### Added

- **Facilitator rubric** — `wicked-garden:propose-process` skill, the v6
  decision-making surface. Tier-1/2/3 progressive disclosure. 9 factors,
  phase catalog in refs/, plan template in refs/. Gate 1: 10 canonical
  scenarios measuring 10/10 PASS on quality output. Gate 3: wired into
  `crew:start` + async re-evaluate on `TaskCompleted` for facilitator-owned
  tasks.
- **`scripts/crew/swarm_trigger.py`** — standalone stdlib module carrying the
  v5 swarm-trigger detector forward. Extracted verbatim; public API unchanged.
- **`scripts/mem/session_fact_extractor.py`** — stdlib session-fact extractor
  reading native Claude tasks
  (`${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/{session_id}/*.json`). Replaces the
  v5 `FactExtractor` pipeline. Emission shape on wicked-bus is unchanged, so
  wicked-brain auto-memorize is unaffected.

### Removed

- `scripts/crew/smart_decisioning.py` (~2,430 LOC) — the v5 rule engine
- `scripts/smaht/v2/` (11 files, ~2,950 LOC) — adapter_registry,
  budget_enforcer, context_pressure, fact_extractor, fast_path,
  history_condenser, lane_tracker, orchestrator, router, slow_path, __init__
- 7 test files totaling ~2,580 LOC (adapter_registry, assembler_registry,
  orchestrator_metrics, prompt_submit_refactor, prompt_submit_routing,
  hot_continuation_accumulation, hot_path_fast_exit)
- 11 scenario files exercising v5 behavior
- 12 specialist agents merged/deleted/demoted across Gates 1-2 (net roster
  81 -> 69 agents)
- Total removal: ~17k lines

### Why beta

Measurement evidence to date is: (a) Gate 1's 10 canonical scenarios (10/10
PASS against rubric targets), (b) Gate 4 Phase 1's 3 smoke inputs (3/3 PASS,
all beating legacy in at least one dimension), (c) internal dogfooding on
the v6 branch. Live-run evidence on novel inputs is limited. The rubric may
need a v1.1 tightening once real users exercise it. If you need the v5
behavior for production work, pin to `5.2.0` — it's a drop-in replacement.

### Migration

- **Active crew projects** that predate v6: `crew:execute` and `crew:just-finish`
  now invoke the facilitator in `re-evaluate` mode at checkpoints. Projects
  without a `process-plan.json` on disk will trigger a fresh `propose` invocation
  on the next checkpoint.
- **Scripts calling `smart_decisioning.py --json`**: migrate to the
  `wicked-garden:propose-process` skill. The output schema is documented
  in `skills/propose-process/refs/output-schema.md`.
- **Code referencing `smaht/v2/` modules**: migrate to pull-model. For session
  state, use `scripts/_session.py::SessionState`. For session facts, use
  `scripts/mem/session_fact_extractor.py`. For context, invoke
  `wicked-brain:search` directly.

## [5.2.0] - 2026-04-18

### Features
- **feat(platform): security + compliance bus emits (#422, #426)** — `wicked.security.finding_raised`, `wicked.compliance.passed`, `wicked.compliance.failed` wired via agent-prompt directives (jam pattern) in `security-engineer.md`, `compliance-officer.md`, and `auditor.md`. No Python infrastructure required; directives fail-open via `|| true`, restate Tier 1/2 payload rules with explicit NEVER-list (finding text, remediation, source, audit contents, PII).
- **feat(delivery): rollout + experiment bus emits (#423, #425)** — `wicked.rollout.decided` and `wicked.experiment.concluded` wired via agent-prompt directives in `rollout-manager.md` and `experiment-designer.md`. Revives scope deferred from #412 (delivery has no Python scripts; prompt directives are the right lever).
- **feat(qe): coverage tracker + `wicked.coverage.changed` emit (#424, #427)** — new `scripts/qe/coverage_tracker.py` (stdlib-only, ~535 lines): parses Cobertura XML and coverage.py JSON reports, scans standard paths (`coverage.xml`, `coverage.json`, `htmlcov/coverage.xml`, `reports/coverage.*`, `.coverage/coverage.xml`), persists last reading in `DomainStore("wicked-qe")` coverage collection, emits `wicked.coverage.changed` with `{before_pct, after_pct, delta, chain_id}` when `|delta| > 1e-9`. Emit-before-store ordering so transient bus failures don't lose the delta. Path-traversal guarded. Wired into `scripts/qe/registry_store.py` post-`scenario.run` — zero new command surface. CLI flags: `--project-id`, `--chain-id`, `--json`, `--selftest`.

### Closed Issues
- #422 (platform security + compliance emits)
- #423 (delivery rollout + experiment emits)
- #424 (QE coverage tracker)

### Bus Integration State (epic #404)

**All deferred items from v5.1.0 are now shipped.** The wicked-bus phase-2 work originally scoped in #404 is complete:
- 18 core events in the catalog
- All wired: crew (7), jam (5 incl. synthesis_ready), qe (3 incl. coverage.changed), platform (3), delivery (2)
- 6/8 consumers registered (crew:auto-advance, smaht:brain-{consolidated,config-updated,initialized}, qe:scenario-scaffold, jam:synthesis-trigger)
- Budget enforcement active; health-probe Check 6 surfaces `registered/max`

No deferred items remain. #404 can close.

## [5.1.0] - 2026-04-18

### Features
- **feat(bus): finish phase-1 crew emit points (#407, #421)** — `wicked.rework.triggered` now fires alongside `wicked.gate.blocked` on REJECT with an iteration counter persisted to `phases/{phase}/rework-iterations.json`. `wicked.project.completed` fires on final-phase approval with `duration_secs`, `final_phase`, `chain_id`.
- **feat(bus): consumer budget enforcement (#414, #421)** — `scripts/_bus.py` now loads and counts `_bus_consumers.json` at registration time, logging an error above `max_consumers`. `health_probe.py` Check 6 surfaces registered/max and flags a warning when over budget.
- **feat(bus): platform + qe emit points (#412, #420)** — `wicked.scenario.run` wired in `scripts/qe/registry_store.py` with `result` derived from registry `completeness.missing` and `coverage_delta` from `captured_count / required_count`. Platform security/compliance and `coverage.changed` deferred — those paths live in agent/command markdown, no Python call site exists in v5.1.0.
- **feat(qe): scenario scaffold consumer (#410, #418)** — new `qe:scenario-scaffold` consumer fires on `wicked.phase.transitioned` when build completes (`phase_to ∈ {test-strategy, review}`). Writes an idempotent scaffold at `scripts/qe/scenarios/{project_id}/scenarios-scaffold.md` with Happy Path / Edge Cases / Error Conditions stubs. Path-traversal guarded; atomic `.tmp` + `replace` write. Wired into `/wicked-garden:qe:scenarios` poll-on-invoke.
- **feat(jam): bus emit points + synthesis-trigger consumer (#409, #419)** — 4 emits wired via `agents/jam/facilitator.md` + `agents/jam/council.md` prompt directives: `session.started`, `persona.contributed` (Round 1 only), `session.synthesized`, `council.voted`. New `jam:synthesis-trigger` consumer (`scripts/jam/_bus_consumers.py`) emits `wicked.session.synthesis_ready` when all Round 1 personas contribute or after 120 s timeout. `wicked.session.synthesis_ready` added to `BUS_EVENT_MAP` and catalog doc.

### Closed Issues
- #406 (event catalog doc — already shipped in 4.x)
- #407 (crew emit points — completed in this release)
- #408 (kanban rework consumer — obsolete under v5.0.0's reviewer-agent-emits-direct model)
- #409 (jam emit + synthesis)
- #410 (QE scaffold consumer)
- #411 (brain → smaht consumers — already shipped in 4.x)
- #412 (platform + qe emit points — scenario.run shipped; others deferred, no call sites)
- #413 (auto-advance with audit trail — already shipped in 4.x)
- #414 (consumer budget enforcement)

### Consumer Registry
6/8 consumers registered after this release:
- `crew:auto-advance`, `smaht:brain-consolidated`, `smaht:brain-config-updated`, `smaht:brain-initialized`, `qe:scenario-scaffold`, `jam:synthesis-trigger`

### Deferred for Future Releases
- Platform security-finding and compliance events (#412) — need a Python persistence path before they have anywhere to emit from
- QE `coverage.changed` event — needs a coverage tracker in `scripts/qe/`
- Delivery emit points — `scripts/delivery/` doesn't exist; delivery is currently agent/command-only

## [5.0.0] - 2026-04-17

### Breaking Changes
- **Remove the `kanban` domain entirely.** Commands under `/wicked-garden:kanban:*`, the `wicked-kanban` DomainStore, and all kanban scripts/skills/scenarios are deleted. Task tracking now uses Claude Code's native `TaskCreate` / `TaskUpdate` with enriched `metadata`.

### Features
- feat(hooks): metadata contract + PreToolUse validator for native tasks — new `scripts/_event_schema.py` defines the event envelope (`chain_id`, `event_type`, `source_agent`, `phase`, gate-finding `verdict`/`score`). Validator in `hooks/scripts/pre_tool.py` is env-gated by `WG_TASK_METADATA={off,warn,strict}` (warn by default; mirrors `CREW_GATE_ENFORCEMENT=legacy`).
- feat(hooks): SubagentStart reads `metadata.event_type` from `${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/{session_id}/*.json` for procedure-bundle injection (R1-R6 for coding-tasks, Gate Finding Protocol for gate-findings, etc.). No sidecar storage.

### Removed
- `scripts/kanban/` (1,727 lines — KanbanStore, initiatives, migrations).
- `commands/kanban/` (7 slash commands: `board-status`, `new-task`, `comment`, `initiative`, `name-session`, `start-api`, `help`).
- `skills/kanban/` (10 skill files and refs).
- `scenarios/kanban/` (10 acceptance scenarios).
- `hooks/scripts/post_tool.py` TaskCreate/TaskUpdate/TodoWrite sync handler (~220 lines).
- `_create_rework_task` in `scripts/crew/_bus_consumers.py` — gate REJECT no longer writes a kanban task; the reviewer agent emits `TaskCreate(metadata={event_type: "gate-finding", verdict: "REJECT", …})` directly.
- `kanban_board` and `kanban_sync` fields from `SessionState`.
- `kanban_initiative` / `kanban_initiative_id` fields from crew `ProjectState` (old `project.json` values fall through to `extras` on load — no migration needed).
- `wicked-kanban` entry from `DOMAIN_MCP_PATTERNS`, `SOURCE_PRIORITY`, `_DOMAIN_QUERIES`, and `_bus_consumers.json`.

### Migration notes
- Consumers of `/wicked-garden:kanban:new-task` etc. should switch to `TaskCreate(subject="…", metadata={"event_type":"task", "chain_id":"{project}.root", "source_agent":"{name}"})`.
- Ops integrations (Jira/Linear channel descriptions in `plugin.json._future_channels`) now point at native tasks instead of the kanban domain.

## [4.10.0] - 2026-04-16

### Chores
- release: wicked-garden v4.9.0 — bus-based fact promotion + mem cleanup (15b1da8)

## [4.9.0] - 2026-04-15

### Features
- feat(smaht,mem): bus-based fact promotion + wicked-garden:mem cleanup (8bb0272)

### Chores
- release: wicked-garden v4.8.1 — bootstrap fix for brain loose-skill detection (4579d83)

## [4.8.1] - 2026-04-14

### Bug Fixes
- fix(bootstrap): detect wicked-brain loose-skill installs (a4948c2)

### Chores
- release: wicked-garden v4.8.0 — wicked-bus integration (9e0dc90)

## [4.8.0] - 2026-04-12

### Features
- feat: wicked-bus integration — emit events, poll-on-invoke consumers, auto-advance (71b8f27)

### Chores
- release: wicked-garden v4.7.0 — scoring dimensions, gate persistence, test suite cleanup (18f5b5e)

## [4.7.0] - 2026-04-12

### Features
- feat(crew): add scope_effort, integration_surface, state_complexity dimensions + greenfield archetype (2476d08)

### Chores
- chore: add brain/worktree gitignore entries, remove CP health check from wg-test (5493bfa)
- release: wicked-garden v4.6.0 — brain port resolution, mem passthroughs, library cleanup (06aaf12)

## [4.6.0] - 2026-04-11

### Features
- feat(patch): auto-discover brain port from project brain configs (b756271)
- feat(patch): wire brain symbols/dependents API for plan command (4234718)
- feat: make wicked-brain mandatory — boot gate, prompt gate, adapter warning (f9d8573)

### Bug Fixes
- fix: clean stale wicked-search references, dead code, and review findings (ed25602)
- fix(patch): add scripts/ root to sys.path so _brain_port is importable (658a7de)
- fix(patch): fetch up to 10 symbols results to find file_path-backed entry (380486b)

### Refactoring
- refactor(mem): convert commands to thin passthroughs to wicked-brain skills (9f59c5d)
- refactor: rename all legacy plugin names to wicked-garden:{domain} (46dfa75)
- refactor: rename all wicked-search refs to wicked-garden:search (bcefad6)
- refactor: centralize brain port resolution via _brain_port.py (c373079)
- refactor(patch): remove wicked-search dependency, require --db explicitly (9bc9e99)
- refactor: remove wicked-search, clean stale references, relocate tests (d854e3a)

## [4.5.0] - 2026-04-10

### Refactoring
- refactor: simplify event queue code — remove dead branches, reduce I/O (7c099a6)

### Chores
- release: wicked-garden v4.4.0 — kanban event queue, chain causality, procedure injection (cf6d09c)

## [4.4.0] - 2026-04-10

### Features
- feat(kanban): dual-purpose event queue with chain causality tracking (aee44a8)

### Chores
- release: wicked-garden v4.3.0 — bulletproof standards, review tiers, swarm, provenance (ddd9e22)

## [4.3.0] - 2026-04-10

### Features
- feat: bulletproof standards, review tiers, swarm detection, provenance awareness (1011561)

### Chores
- release: wicked-garden v4.2.3 — centralized tool-discovery via SubagentStart hook (4ef539c)

## [4.2.3] - 2026-04-10

### Features
- feat(hooks): centralized tool-discovery injection via SubagentStart hook (41b8dca)

### Refactoring
- refactor(agents): replace hardcoded tool references with generic discovery (6445458)

### Chores
- Revert "refactor(agents): replace hardcoded tool references with generic discovery" (694a27f)
- release: wicked-garden v4.2.2 — agents discover tools instead of hardcoding (640931d)

## [4.2.2] - 2026-04-09

### Bug Fixes
- fix(qe): teach agents to discover tools instead of hardcoding them (9cb0de1)

### Chores
- release: wicked-garden v4.2.1 — non-skippable test phase (e236829)

## [4.2.1] - 2026-04-09

### Bug Fixes
- fix(crew): make test phase non-skippable, remove lazy skip paths (0a6d0e6)

### Chores
- release: wicked-garden v4.2.0 — aggressive QE testing with two-pass strategy (c465007)

## [4.2.0] - 2026-04-09

### Features
- feat(qe): aggressive two-pass testing with mandatory positive+negative scenarios (2243446)

### Bug Fixes
- fix: cross-platform python resolution, path corrections, refs trimming (b94bb0d)

### Chores
- chore(search): add graph-analysis ref extracted from unified-search SKILL.md (0fc084f)
- release: wicked-garden v4.1.0 — smaht synthesize pipeline improvements (8a3b1c9)

## [4.1.0] - 2026-04-08

### Features
- feat(smaht): thread orchestrator output into synthesize directive for SLOW-path prompts (#393) (c37aaf3)

### Bug Fixes
- fix(smaht): tighten synthesize gate + add scope validation step (#391) (#392) (ff8da7f)

### Chores
- release: wicked-garden v4.0.4 — kanban fixes, scenario cleanup, refs trimming (5180834)

## [4.0.4] - 2026-04-08

### Bug Fixes
- fix(kanban,crew): get-task returns comments + composite ID handling; README false positive (d690c72)
- fix(scenarios): update stale crew acceptance test scenarios (7788c96)

### Tests
- test(scenarios): align 3 stale acceptance scenarios with smaht v2 synthesis path (#389) (fb4051f)
- test(scenarios): align 3 stale acceptance scenarios with smaht v2 synthesis path (f10dd25)

### Chores
- chore: trim refs/ files to ≤300 lines (23 files) (#390) (cbb00b6)
- release: wicked-garden v4.0.3 — kanban KanbanStore routing + skill fixes (ecd93a9)

## [4.0.3] - 2026-04-08

### Bug Fixes
- fix(kanban): route hook task ops through KanbanStore (#381, #382, #383) (#388) (490cfe6)
- fix(kanban): remove dead 'doing' swimlane from domain_adapter boost_fn (#385) (#386) (6cd8863)
- fix(kanban): use _python.sh shim in _trigger_mem_write (#384) (#387) (c98efcb)

### Documentation
- docs: update CLAUDE.md and README for brain-first architecture and smaht v2 pipeline (9da1d3d)

### Tests
- test(smaht): add end-to-end scenario for synthesize skill slow-path (#375) (#380) (0c52366)

### Chores
- release: wicked-garden v4.0.2 — smaht pipeline hardening + docs overhaul (99ff94c)

## [4.0.2] - 2026-04-08

### Features
- feat: agentic context synthesis — complexity-gated smaht exploration (b8dcf31)
- feat: automatic brain lifecycle — setup pipeline + incremental reindex + full bootstrap (72e02b5)
- feat: wicked-brain as unified knowledge layer (v4.0.0) (#372) (a76a29b)
- feat: brain dependency check, crew graph-mode requirements, wicked-search plugin scaffold (ba0a6ca)
- feat: two-tier agent-level gate enforcement for crew workflows (#364-#370) (da3d71b)
- feat: graph-based requirements — filesystem-as-graph for atomic, traceable requirement nodes (bb8bcbf)
- feat: auto-generate search tags on mem:store for better keyword recall (d872dbb)
- feat: add 3-tier memory with auto-consolidation (0a9985f)
- feat: add Operate phase to crew workflow for SDLC feedback loop (f965e1d)
- feat: wire consensus protocol into crew gate decisions for high-complexity work (d262cde)
- feat: search/memory/knowledge scoring, knowledge graph, impact analysis, council consensus (83072c9)
- feat(crew): workflow hardening — traceability, artifact states, verification, project isolation (c05df50)

### Bug Fixes
- fix: warn on unknown TaskUpdate status and log sync exceptions (#378, #379) (0d78f34)
- fix(smaht): domain adapter intermittently fails fast-path timeout (#374) (2ecb046)
- fix(smaht): filter unnamed tasks.created events from briefings (#373) (4d8a6dd)
- fix: stop false-positive onboarding directive when brain has indexed content (b1773df)
- fix: smarter FTS5 fallback and strip table rows, CLI flag lists (2983a31)
- fix: strip chunk-IDs, table separators; penalize empty snippets (de14b66)
- fix: improve brain FTS5 keyword extraction and source priority (a1b60a5)
- fix: strip orphan file-path values from brain FTS snippets (ec00fd7)
- fix: correct ASCII logo to spell wicked-garden with hyphen (94278be)
- fix: resolve all validation issues from plugin review + skill review (41657aa)
- fix: sync marketplace.json version to 3.8.0 (329e02b)
- fix: sync marketplace.json version to 3.4.1 (699ba3e)
- fix: 3 bugs found by E2E scenario execution (d09257e)

### Documentation
- docs: add ASCII art logo to README (04d092e)
- docs: update plugin description and README for marketplace submission (e40bb2d)

### Tests
- test: add E2E scenarios for all v3.4.0 modules (10 new, 2 updated) (5d735cd)

### Refactoring
- refactor: simplify new code from #359, #360, #361 (64361d1)

### Chores
- release: wicked-garden v4.0.1 — automatic brain lifecycle (3162006)
- release: wicked-garden v3.8.0 — two-tier gate enforcement (40fc85c)
- release: wicked-garden v3.6.1 — auto-generate search tags for better recall (b5f96d1)
- release: wicked-garden v3.6.0 — consensus gates, operate phase, 3-tier memory (783a960)
- Merge branch 'feat/360-tiered-memory' (51bf311)
- merge: resolve conflicts between consensus gates (#361) and operate phase (#359) (6099e13)
- release: wicked-garden v3.5.0 — comprehensive documentation update (248cf6e)
- release: wicked-garden v3.4.1 — E2E scenarios + bug fixes (90f1ea0)
- release: wicked-garden v3.4.0 — cross-phase intelligence and workflow hardening (796c32e)

## [3.3.0] - 2026-04-03

### Features
- feat: hook upgrades (SubagentStart/Stop, PermissionRequest, Notification) + TODOs (dd0815d)
- feat: plugin manifest modernization + agent budgets for all 80 agents (f6f83ee)
- feat: smaht:learn tracking, PostToolUse profiling, agent trigger analysis (50b0ff4)

### Documentation
- docs: add LSP server integration TODO to plugin.json (#347) (8d2831d)

## [3.2.0] - 2026-04-03

### Features
- feat: OneDrive path fix, CI pipeline, cross-version memory, search hardening (ce2c7e6)
- feat: brainstorm fast convergence, plugin discoverability hints, turn progress (7581f3c)
- feat: large-read delegation warnings + subagent permission failure detection (6ccf6c5)
- feat: PreCompact WIP persistence + post-compaction recovery + plugin cleanup (0c2eecb)
- feat: onboarding memories — granular storage + active consumption (51405de)
- feat: wire all event consumers — mem recall, smaht adapter, jam per-round events (0660a78)
- feat: wire first event consumers — briefing reads events, crew emits rich events (dae8d77)
- feat: unified event log — EventStore with FTS5, DomainStore auto-emit, cross-domain queries (c34a164)
- feat: session briefing, contextual discovery, dead code removal (a2df3d6)
- feat: jam refs, task-based product help, enriched persona agent (174d7fc)

### Bug Fixes
- fix: correct 31 broken script paths, remove 4 missing script refs (fdf44b5)
- fix: disambiguate trigger collisions across 12 skills (f07832c)
- fix: fourth cleanup — broken script paths, stale counts, dead command refs (6fb6b57)
- fix: third cleanup pass — ghost specialist, stale refs, orphaned scenarios (8da557e)
- fix: skill quality improvements — deduplicate triggers, enforce line limits, remove hardcoded paths (407f272)

### Documentation
- docs: update all docs for v3.0 — domain counts, specialist table, event log (0b1cdd8)
- docs: README split into two stories — what you do vs what the plugin does (b202123)
- docs: README Start Here — add testing, persona; drop commodity features (550d427)
- docs: add smaht:onboard and smaht:briefing to README Start Here (d409dba)
- docs: README reposition — crew as hero, memory as compound interest (dde6995)
- docs: rewrite README to lead with memory moat, not command counts (4e6d53c)
- docs: update README, CLAUDE.md, workflow skill for v2.5-2.6 features (d62c16a)

### Refactoring
- refactor: consolidate multi-model, patch, observability into parent domains (15 → 14) (49823a8)
- refactor: consolidate design → product, scenarios → qe (17 → 15 domains) (f82aab3)

### Chores
- release: wicked-garden v3.1.0 — onboarding rework, README reposition, doc updates (abaaa05)
- release: wicked-garden v3.0.1 — event log consumers fully wired (a2d25a3)
- release: wicked-garden v2.10.0 — session briefing, contextual discovery, README rewrite (f5194ef)
- release: wicked-garden v2.9.1 — script path fixes + trigger disambiguation (aa733ba)
- release: wicked-garden v2.9.0 — quality investments + third cleanup pass (5baaea8)
- release: wicked-garden v2.8.0 — domain consolidation (17 → 14) (79a9ad8)
- release: wicked-garden v2.7.0 — skill quality + security hygiene (0c24de2)
- release: wicked-garden v2.6.1 — security fixes + doc updates (a7fe039)

## [3.1.0] - 2026-03-23

### Features
- feat: onboarding stores granular memories (one per fact, not monolithic summaries)
- feat: onboarding memories actively consumed by smaht context assembly (0.15 relevance boost)
- feat: crew:start and crew:execute explicitly recall onboarding memories for archetype analysis
- feat: README repositioned — crew as hero, two-table structure (what you do / what plugin does)

### Documentation
- docs: all docs updated for v3.0 (14 domains, 8 specialists, event log coverage)
- docs: architecture.md — added EventStore section
- docs: advanced.md — added Event Log section with query examples
- docs: crew-workflow.md — removed ghost design specialist, fixed signal routing

## [3.0.1] - 2026-03-23

### Event Log Consumers
- feat: `mem:recall` supplements results with cross-domain event context
- feat: smaht `events_adapter` — queries event log on planning, research, and review intents
- feat: jam facilitator emits per-round events (`rounds.N.completed`, `sessions.synthesized`)
- feat: `smaht:briefing` reads event log as primary source (falls back to domain queries)
- feat: crew `phase_manager` emits rich events on project creation and phase approval

## [3.0.0] - 2026-03-22

### Unified Event Log
- feat: `_event_store.py` — append-only SQLite event store with FTS5 full-text search
- feat: DomainStore auto-emits events on every create/update/delete (fire-and-forget)
- feat: `smaht:events-query` command — cross-domain activity queries with --domain, --project, --since, --fts flags
- feat: `smaht:events-import` command — migrate existing JSON records into event log
- feat: bootstrap hook initializes event store schema at session start
- feat: stop hook purges events older than 90 days (configurable retention)
- security: event payloads emit only safe metadata fields (no sensitive data in FTS index)
- fix: schema initialization cached after first call (no redundant DDL on every write)

### Previous (included in v3.0.0)
- Session briefing, contextual discovery, README rewrite, dead code removal (v2.10.0)
- Script path fixes, trigger disambiguation (v2.9.1)
- Quality investments: jam refs, product help, persona agent (v2.9.0)
- Domain consolidation 17→14 (v2.8.0)
- Skill quality fixes, security hygiene (v2.7.0)

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
- release: wicked-garden v2.4.0 (a8647ed)

## [2.4.0] - 2026-03-17

### Features
- feat: CLAUDE.md ↔ AGENTS.md sync + remove AGENTS.md write block (8847722)

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
- `disable-model-invocation: true` on 2 user-only skills (crew/workflow, kanban)
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

## [1.19.0] - 2026-03-05

### Refactoring
- refactor: convert all CLI command syntax to natural language invocations

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

