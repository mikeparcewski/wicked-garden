# Changelog

This project follows [Semantic Versioning](https://semver.org/).

The version line restarted at **v11.0.0** with the v11 work-shape archetype
reframe. The pre-v11 changelog (versions 0.x through 10.x) is preserved in
the git history but is not maintained as living documentation — those
releases describe a prior architecture (universal pipeline + rigor tier
dial) that was replaced wholesale.

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
