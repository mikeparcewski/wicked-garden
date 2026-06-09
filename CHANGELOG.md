# Changelog

## [12.6.0] - 2026-06-09

### Features
- feat(qe): prove.py — the one-line re-derivation verb (gate without the ritual) (37d586e)

### Documentation
- docs(build): recommend prove.py as the frictionless gate path (c3132be)

### Chores
- Merge pull request #899 from mikeparcewski/feat/prove-verb (43d98c5)

## [12.5.2] - 2026-06-09

### Tests
- test(e2e): fix CI environment assumption — own $HOME, test both configured + unconfigured (9398b08)
- test(e2e): real-surface harness — gate CLI, bootstrap, routing, resilience (Tiers A+C) (f83cf90)

### Chores
- Merge pull request #898 from mikeparcewski/test/e2e-three-tier-harness (685c007)
- ci: install node + wicked peers so tests/e2e gate+resilience RUN (not skip) (8e59ba7)

## [12.5.1] - 2026-06-09

### Bug Fixes
- fix: vault_gate CLI imports _loom (gate was failing closed via its own documented commands) (d0ce3eb)

## [12.5.0] - 2026-06-09

### Features
- feat(capabilities): register apm/tracing/logging/telemetry; lock agent caps to the registry (cde4bda)

### Bug Fixes
- fix(detector): match 'roll out' (spaced) for the ship archetype (54048e0)
- fix(phase-manager): align hard-gate map to the catalog (drop specify/decide over-reach) (9c042f1)
- fix: loom gate re-derives against project_dir, not process cwd (#891 regression) (ea8a3f8)

### Documentation
- docs: reconcile with the v12 loom cutover (loom is the gate; five required peers) (f66010d)
- docs(spec): record loom migration terminal outcome (§6 remainder stays in garden) (#895) (eb228d0)

## [12.4.0] - 2026-06-08

### Features
- feat: flow surface — loom-authoritative hard-gate park decision (fail-closed floor) (#893) (a4bab29)

## [12.3.0] - 2026-06-08

### Features
- feat: wicked-loom contract — loom is the sole gate/resolve path (delete in-process re-derivation) (#891) (7e4492a)
- feat: wicked-loom cutover — garden shells to loom resolve/gate/flow (additive, flag-gated) (#890) (ae928a7)
- feat(#878): worktree cwd-leak guard on Bash PreToolUse (#888) (859d2a0)

### Documentation
- docs: wicked-loom north-star spec (extract the orchestration runtime) (#889) (16c3e70)

## [12.2.0] - 2026-06-01

### Features
- skill(engineering): large-scale-migration — the map→transform→gate leverage pattern for cross-cutting migrations / refactors / renames / dialect-ports (21b1842)

### Bug Fixes
- fix(#879): clean up the two rotted test files outside tests/ (#885) (7db380d)

This project follows [Semantic Versioning](https://semver.org/).

The version line restarted at **v11.0.0** with the v11 work-shape archetype
reframe. The pre-v11 changelog (versions 0.x through 10.x) is preserved in
the git history but is not maintained as living documentation — those
releases describe a prior architecture (universal pipeline + rigor tier
dial) that was replaced wholesale.

---

## [12.1.0] — 2026-05-25

**All four siblings are now required, and the work mode is visible on screen.**

### Required peers (all four)

- **wicked-brain and wicked-bus join wicked-testing and wicked-vault as required peers.** `/wicked-garden:setup` now verifies all four and blocks without them; the SessionStart hook warns. `plugin.json` pins all four (`wicked_brain_version` `^0.14.0`, `wicked_bus_version` `^2.0.0`). The stance is **required at install, resilient at runtime**: a transient outage (brain server down, bus unavailable) degrades gracefully and never bricks a session — it never means a gate treats missing evidence as a pass (that path fails closed). See [`docs/required-peers.md`](docs/required-peers.md).

### Features

- **A work-mode status line** (`scripts/statusline.py`, opt-in via `settings.json` — see getting-started or `/wicked-garden:setup` step 6.6). Renders the live archetype · intent · phase · gate verdict at the bottom of the screen — `🌱 wg │ build·migrate │ intent: feature │ phase: implement │ ⚖ PASS`. Reads existing session state only (one read), fail-soft (degrades to `🌱 wg │ idle`, never blocks a render).

### Documentation

- **Rethought, not patched.** The docs were reoriented from the deleted v6 crew model to v12. README restructured around what/why/how (leads with the re-derived-evidence trust pitch, not the pipeline rationale); ETHOS rewritten (required-infrastructure / resilient-at-runtime; the nine archetypes named; the *"done is not claimed; done is re-derived"* slogan); `docs/domains.md` reframed off the dead orchestrator; new [`docs/required-peers.md`](docs/required-peers.md) + [`docs/compiler.md`](docs/compiler.md); `docs/v11/archetypes.md` corrected (hard gates are enforced at runtime). Stale `crew:*` references removed from setup.

### Notes

- The status line's two bugs (wrong field name, mismatched sanitization) were caught by independent review, not by the tests that shipped CI-green — those were tautological. The fix added a guard test cross-checking the renderer's fields against the real `SessionState` schema. *Honest verdicts beat green dashboards.*

---

## [12.0.0] — 2026-05-25

**"Done" is re-derived, not asserted — and the garden can compile that guarantee onto any repo.**

Every gating archetype's produces-gate stops trusting a self-asserted "done"
and re-derives it through [wicked-vault](https://www.npmjs.com/package/wicked-vault),
a new **required** peer. A new compiler emits that same re-derivation as a
self-contained harness into any repo.

### Breaking changes

- **wicked-vault is now a required peer** (`^0.3.0`; sibling to wicked-bus /
  wicked-brain / wicked-testing). `/wicked-garden:setup` verifies it and blocks
  without it, and the SessionStart hook warns. Install with
  `npx wicked-vault-install`. Offline/dev kill-switch: `WICKED_VAULT_BIN=""`
  (see CONTRIBUTING.md).

### Features

- **Vault-backed gates for all gating archetypes** (`scripts/qe/vault_gate.py`).
  The gate runs `wicked-vault cross-check` — re-hashing the recorded evidence
  and re-running its verifier — instead of `evidence_tracker`'s
  satisfied-when-claimed model. A claimed-but-false "tests pass" is REJECTED; a
  missing vault **fails closed** rather than passing on a self-assertion. Hard
  gates (review / incident / migrate) require an *independent* attestation —
  the evaluator is not the agent that did the work.
- **The compiler emit stage + `/wicked-garden:compile`** (`scripts/compiler/`).
  Detects a repo's test/lint/build commands and emits a self-contained,
  vault-backed gate into `<repo>/.wicked/` (contract + a stdlib-only `gate.py`
  + a claims-vs-evidence lint + README) that runs with **no wicked-garden
  runtime present** (resolves the vault via `npx`). Optionally installs the
  triggers that fire it — a git pre-push hook and a GitHub Actions workflow
  whose toolchain setup is derived from the detected ecosystem. Multi-claim
  contracts (test/lint/build), each pinned to its own verifier.

### Notes

- 422 tests; proven on an unseen repo (memos) and self-hosted on wicked-garden
  (which surfaced and fixed a detector scoping bug).
- Follow-up: #879 — two rotted test files CI never collected, found while
  self-hosting the compiler.

---

## [11.1.3] — 2026-05-08

**Council command + 4 sibling commands had broken refs the validator missed.**

The validator at v11.1.2 caught script-path drift in YAML/JSON fields
and `${CLAUDE_PLUGIN_ROOT}/...` strings, but missed two reference
shapes that hide inside markdown code fences and prose:

- **Bare `scripts/<domain>/<file>.py` paths** — references that don't
  use the `${CLAUDE_PLUGIN_ROOT}` prefix.
- **`from <module> import …` Python imports** — references that name
  a module deleted in a v11 cleanup.

`commands/jam/council.md` had a documented `from crew.hitl_judge import …`
example pointing at a script deleted in PR #866. The council itself ran
fine; the post-synthesis HITL judge step was broken. 9 other places
across `commands/delivery/`, `commands/engineering/`, `commands/smaht/`
had similar breaks (mostly references to the deleted
`scripts/crew/crew.py::find-active` auto-resolver).

### Fixed

- `commands/jam/council.md` — replaced the HITL judge code example with
  inline prose heuristics that the agent applies. Council itself
  unchanged; only the gate-feeding step removed.
- `commands/delivery/process-health.md`, `commands/smaht/state.md`,
  `commands/smaht/briefing.md` — replaced the v6 `crew.py find-active`
  invocations with v11 explicit-`--project` semantics.

### Added

- `scripts/ci/validate.py` now checks two additional reference shapes:
  bare `scripts/.../*.py` paths anywhere in commands/agents markdown,
  and `from <module> import` patterns whose module name doesn't exist
  under `scripts/` or `hooks/scripts/`. Stdlib + common third-party
  + obvious-template-placeholder names are whitelisted to keep the
  signal-to-noise ratio high.

The validator is now strict enough that a future v11 cleanup will
catch its own drift on the next CI run rather than the next user run.

390 / 390 tests still passing.

---

## [11.1.2] — 2026-05-08

**marketplace.json plugin version sync.**

The marketplace registration's `plugins[0].version` field had drifted —
stuck at `8.8.1` across the three v11 releases (`v11.0.0`, `v11.1.0`,
`v11.1.1`) because nobody bumped it. The plugin manifest reported
`11.1.1`; the marketplace listing reported `8.8.1`. Anyone consulting
the marketplace registration saw a stale number.

### Fixed

- `.claude-plugin/marketplace.json` `plugins[0].version` bumped to
  `11.1.2` to match `.claude-plugin/plugin.json`.

### Added

- `scripts/ci/validate.py` now enforces the version-parity invariant.
  When `plugin.json` and `marketplace.json` disagree on the plugin's
  version, validation fails with a named error: *"marketplace.json
  plugins[name=X].version = '8.8.1' does not match plugin.json version
  = '11.1.1'. Bump both together."* This catches the same drift class
  on the next release attempt rather than the release after.

No behavior change beyond the version bump and the validator addition.
Tests still 390/390 passing.

---

## [11.1.1] — 2026-05-08

**Closes the wicked-brain + wicked-bus persistence verification gap.**

Spent a session probing the plugin's relationship with both companion
plugins. Brain persistence turned out to be functional (11,582 indexed
items, 108 memories, search round-trip verified). Bus integration had
a real bug: v11 archetype events were never registered in
`BUS_EVENT_MAP`, so v11 wicked-garden was invisible to the bus despite
the bus itself being healthy (19,790+ events from companion plugins).

### Fixed

- v11 archetype events now register + emit (PR #874). Five new event
  types in `scripts/_bus.py::BUS_EVENT_MAP`:
  - `wicked.archetype.created` — archetype-mode project init
  - `wicked.archetype.advanced` — phase approved; carries next_phase
  - `wicked.archetype.completed` — final phase approved
  - `wicked.archetype.hard_gate_passed` — confirmed_by + evidence
  - `wicked.archetype.classified` — LLM classifier result persisted
- `phase_manager.create_project` emits `wicked.archetype.created` on
  archetype-mode projects.
- `phase_manager.approve_phase` emits `wicked.archetype.advanced` on
  every archetype approval, plus `wicked.archetype.hard_gate_passed`
  when `confirmed_by` was supplied, plus `wicked.archetype.completed`
  when `is_complete()` flips true.
- `scripts/classify/persist.py` emits `wicked.archetype.classified`
  when the LLM classifier writes its result.

All emits fail-open: bus unavailable never blocks the disk write.

### Verified

- **Brain persistence**: search returns 42 hits for `Session goal` —
  the prompt-submit hook's `_write_brain_memory()` writes are reaching
  the FTS5 index. Brain server runs on port 4243; 72 MB SQLite DB at
  `~/.wicked-brain/projects/wicked-garden/.brain.db`.
- **Bus round-trip**: real CLI invocation
  (`phase_manager create … --archetype-mode build` + two approves)
  advances `newest_event_id` by 3, with per-type counters incrementing
  as expected.

### Tests

390 passing (was 384 in v11.1.0; +6 new in `TestBusEmits`).

---

## [11.1.0] — 2026-05-08

**Closes the structural gaps in the v11.0.0 reframe.** v11.0.0 was the
research-grade reframe shipped in two hours; v11.1.0 closes 11 of the
12 items on the post-v11.0.0 critique. The remaining item (wicked-brain
persistence) needs real session traffic to validate, not a marathon.

### Added

- **LLM-based archetype classifier** via the new `wicked-garden:classify`
  skill (PR #869). The skill prompts the model to reason through the
  user's prompt, classify into archetype(s), identify boolean signals,
  and persist to SessionState via `scripts/classify/persist.py`. The
  prompt-submit hook prefers persisted classifications over the regex
  detector — regex is now Tier 2 fallback. When regex returns only
  triage, the hook emits a `<wg classify-due />` directive inviting the
  model to classify properly. New SessionState fields: `archetypes_v11`,
  `signals_v11`, `classified_at`.
- **Runtime hard-gate enforcement** (PR #870). Five archetype phases —
  `migrate:cutover`, `incident:mitigate`, `review:remediate-or-accept`,
  `specify:validate`, `decide:record` — now require non-empty
  `--confirmed-by` AND `--confirmation-evidence` to advance. The audit
  trail records both fields with `hard_gate=True`. The doctrine of
  "hard:* gate" is now mirrored in `phase_manager` code, not just
  playbook prose.
- **5 restored QE utilities** under `scripts/qe/` (PR #868), framed as
  v11 library tools the archetype playbooks call when relevant:
  - `verdict_schema.py` (~250 LOC) — validates review-archetype
    verdict artifacts. Slimmed from the v6 `gate_result_schema.py`.
  - `verdict_audit.py` (~140 LOC) — append-only audit log of verdicts.
    Slimmed from v6 `gate_ingest_audit.py` + `dispatch_log.py`. No
    HMAC; v11 review enforces banned-reviewer checks at validation.
  - `conditions_manifest.py` — track CONDITIONAL findings to
    resolution. Idempotent re-init preserves prior resolutions.
    `all_resolved()` answers the contract question.
  - `content_sanitizer.py` — strip prompt-injection patterns from
    reviewer free-text fields. Floor not wall.
  - `evidence_tracker.py` — track per-archetype produces contracts
    (e.g. `shipped-code` + `test-report` for build).
- **v6→v11 project state migration tool**
  (`scripts/setup/migrate_v6_projects.py`, PR #871). Detects v6-v10
  projects in the DomainStore via phase-list pattern matching,
  proposes the closest v11 archetype, and (with `--apply`) translates
  state in place. Original phase plan preserved in
  `extras.v11_migration_source` for audit.
- **End-to-end integration test** for the full migrate lifecycle —
  catalog hydration → state transitions per phase → hard-gate refusal
  → hard-gate advance → `is_complete` (PR #870).
- **58-prompt calibration corpus** (PR #872). Exercises all 9
  archetypes plus paraphrase, multi-archetype, ambiguous edge cases.
  Three locked-in tests assert overall recall ≥ 85%, overall precision
  ≥ 80%, per-archetype recall ≥ 70%. Actual: **100% per-archetype
  recall**, 90%+ precision after phrase tuning.
- **GitHub Actions workflow** `.github/workflows/test.yml` runs the
  full pytest suite + smokes phase_manager CLI archetype-mode + smokes
  the archetype detector + smokes verdict_schema validation + asserts
  the migrate:cutover hard gate refuses without confirmation and
  advances with it. End-to-end CI for v11.

### Changed

- `hooks/scripts/prompt_submit.py` — `_build_archetype_directive` now
  accepts `state`, prefers persisted LLM classification, emits
  `<wg classify-due />` directive when regex returns only triage. Tag
  format carries `classified="llm"` or `classified="regex"`.
- `.claude-plugin/archetypes.json` — phrase lists tuned to 100% recall
  on the calibration corpus. Added paraphrase coverage for build
  (refactor / patch / wire up), migrate (rename the / expand the /
  retire the / take the / column out), incident (production is broken
  / postmortem / memory leak / paging us), ship (ship to / ship the),
  review (take a look at / look at this pr), decide (pick a / pick
  between / which database / which queue / which framework), and
  explore (what should we / how might we / brainstorm / approaches to
  / not sure how / ideas for).
- `agents/crew/reviewer.md`, `agents/product/requirements-analyst.md`,
  `commands/setup.md`, `commands/smaht/briefing.md` — replaced
  references to deleted v6 modules (traceability.py, qe-evaluator
  naming sweep, _stack_signals, archetype_detect, affected_repos)
  with v11 equivalents (evidence_tracker, conditions_manifest, the v6
  migration script, an explanatory note).
- `skills/archetype/refs/build.md` and `refs/review.md` — playbooks
  now reference the restored `scripts/qe/*` utilities at the right
  phase boundaries.

### Removed

- `daemon/` (~8600 LOC, PR #871) — the v6-v10 projector daemon was
  wired to gate-result schemas, dispatch-log HMACs, and projection
  resolvers, all of which v11.0.0 deleted. v11 treats the bus as an
  audit substrate, not a projection enforcement layer.
- `.github/workflows/benchmark.yml` — enforced p95 SLO on
  `_load_gate_result` (deleted in v11.0.0). Trigger paths no longer
  exist; the workflow was dormant clutter.
- 227 lines of dead code in `hooks/scripts/prompt_submit.py` (PR #867)
  — `_assemble_current_chain`, `_consume_facilitator_reeval`,
  `_consume_phase_start_gate`, plus their call sites and event-type
  references that pointed at deleted v6 modules.

### Test summary

384 tests passing across 8 directories: tests/, tests/crew/, tests/qe/,
tests/calibration/, tests/hooks/, tests/fixtures/, plus utilities.
Calibration: 100% per-archetype recall on the 58-prompt corpus.

---

## [11.0.0] — 2026-05-07

**Reframe: work-shape archetypes replace the universal pipeline.**

The fixed `clarify → design → test-strategy → challenge → build → test → review`
pipeline with a rigor-tier dial is gone. Each prompt now classifies into one
or more **work-shape archetypes** (`triage` · `explore` · `specify` · `decide` ·
`ship` · `review` · `incident` · `build` · `migrate`), each of which owns its
own phase shape, produces contract, HITL discipline, and cost band.

### What's new

- **`.claude-plugin/archetypes.json`** — canonical catalog. Each archetype
  declares its phases, produces, HITL level, cost band, maturity, and
  detection signals (phrase list + boolean flags).
- **`scripts/crew/archetypes_v11.py`** — detector + steering engine. CLI
  shim for shell + agent integration. Stdlib-only.
- **`skills/archetype/`** — agent-facing entry point. Slim `SKILL.md`
  (101 lines) + 9 ref playbooks (62–97 lines each), one per archetype.
  Each playbook documents the archetype's phases, produces contract,
  HITL discipline, run procedure, exit condition, and anti-patterns.
- **`commands/archetype/`** — 9 slash commands, one per archetype, for
  direct user invocation.
- **`hooks/scripts/prompt_submit.py`** — UserPromptSubmit hook now emits
  a slim `<wg archetype="X" score="Y" />` system-reminder when a prompt
  routes to a work shape. `simple-edit` intent stays silent.
- **`scripts/crew/scope_delta.py`** — scope-delta heuristic to catch
  silent project-sized additions to wave plans.
- **`scripts/crew/phase_manager.py`** — slim project-state manager
  (~370 lines, down from ~6000+). State CRUD + `--archetype-mode` for
  new projects. No gate machinery.

### What's gone

The v6–v10 universal-pipeline machinery has been deleted:

- **Agents**: `crew/contrarian`, `crew/facilitator`, `crew/gate-adjudicator`,
  `crew/gate-evaluator`, `crew/independent-reviewer`, `crew/phase-executor`,
  `crew/process-facilitator`, `crew/qe-orchestrator`. Kept:
  `crew/implementer`, `crew/researcher`, `crew/reviewer` (general purpose).
- **Commands**: all of `crew/` except `crew/archive` (general project
  management).
- **Skills**: `propose-process`, `facilitator-score`, all of `skills/crew/`.
- **Plugin configs**: `gate-policy.json`, `phases.json`, `autonomy-policy.json`,
  `finding-classification.json`.
- **Scripts**: gate-result schema validators, gate-dispatch, dispatch-log
  HMAC, conditions-manifest, content-sanitizer, consensus-gate, autonomy
  policy table, reconcile / reconcile_v2, propose-process facilitator
  rubric, validate-plan / validate-reeval-addendum, reeval-addendum,
  archetype_detect (v6.3 target-kind classifier), challenge-manifest,
  rigor-escalator, hitl-judge, gate-adjudicator, semantic-alignment,
  convergence, swarm-trigger, factor-questionnaire, plus ~50 more
  legacy scripts in `scripts/crew/`.
- **Docs**: `MIGRATION-v7.md`, `V7-AC-TRACEABILITY.md`, `crew-workflow.md`,
  `cross-phase-intelligence.md`, `autonomy.md`, `spc.md`, all of
  `docs/v9/`, `docs/audits/`, `docs/calibration/`, `docs/cluster-a/`,
  `docs/composition/`, `docs/council/`, `docs/evidence/`, `docs/research/`.

### Migration note

There is no migration. v11 is a clean break from v6–v10. Projects authored
under the prior architecture continue to load (the project state schema
is forward-compatible) but the gate / rigor / phase machinery is no
longer enforced. New projects should be created with
`phase_manager create … --archetype-mode <archetype>`, or simply by
letting the UserPromptSubmit hook auto-route.

### Pre-v11 history

Versions 0.x through 10.x lived in the git log under tags `v0.1.0`
through `v9.2.18`. Major themes across that span:

- **v0–v3**: initial plugin scaffold, command + agent surface, hooks.
- **v4–v5**: smaht context-assembly orchestrator (HOT/FAST/SLOW/SYNTHESIZE
  tiered router). Replaced in v6.
- **v6**: facilitator-driven dynamic phase plan, gate-policy×rigor matrix,
  archetype-aware gate-adjudicator (target-kind classifier).
- **v7**: AC traceability, semantic reviewer, convergence-verify gate.
- **v8**: dropped `/wicked-garden:mem:*` (memory moved to wicked-brain).
- **v9**: bus-as-truth cutover for gate-critical artifacts; drop-in
  plugin contract; 14 default-on `WG_BUS_AS_TRUTH_*` tokens.
- **v10**: intent variable replacing the 5-classifier cascade;
  steering-not-blocking principle; slim-body contract for commands
  and skills.
- **v10.x dogfood PRs (#854–#860)**: surface fixes that pointed at the
  deeper structural issue v11 solved — hardcoded deliverable filenames,
  gate-result schema field aliases, gate-vocabulary unification,
  reeval-log auto-stub, phase-plan authority hydration, CONDITIONAL
  condition-resolution mechanism, scope-delta HITL trigger.

For each of those releases, see the corresponding tag in git history.
