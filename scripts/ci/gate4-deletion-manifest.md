# Gate 4 Phase 1 — Deletion Manifest

**Purpose**: Enumerate every file scheduled for deletion in Phase 2, every consumer that must be rewritten or removed, and every data/config surface that references the legacy engines.

**Rule for Phase 1**: *This document is descriptive only. Nothing is deleted here.* Phase 2 executes the deletions after user review.

---

## 1. Files scheduled for deletion

### 1.1 Crew rule engine

| File | LOC | Role |
|---|---|---|
| `scripts/crew/smart_decisioning.py` | 2433 | Signal detection, complexity scoring, archetype detection, routing-lane selection, specialist-fallback table, memory-payload emission, swarm-trigger detector. |

**Subtotal**: 1 file, **2,433** LOC.

### 1.2 Smaht v2 context assembly

| File | LOC | Role |
|---|---|---|
| `scripts/smaht/v2/__init__.py` | 23 | package marker |
| `scripts/smaht/v2/adapter_registry.py` | 139 | Adapter registration + `timed_query` shim |
| `scripts/smaht/v2/budget_enforcer.py` | 165 | Source-priority cap + budget math |
| `scripts/smaht/v2/context_pressure.py` | 153 | `PressureTracker` — cumulative context KB accounting |
| `scripts/smaht/v2/fact_extractor.py` | 236 | Session-fact extraction used by stop.py → wicked.fact.extracted emits |
| `scripts/smaht/v2/fast_path.py` | 304 | FAST-path adapter fan-out by intent |
| `scripts/smaht/v2/history_condenser.py` | 660 | Session state + turn log + ticket rail |
| `scripts/smaht/v2/lane_tracker.py` | 296 | Multi-lane topic tracker |
| `scripts/smaht/v2/orchestrator.py` | 289 | HOT/FAST/SLOW/SYNTHESIZE router entry point |
| `scripts/smaht/v2/router.py` | 442 | Intent classification + path selection |
| `scripts/smaht/v2/slow_path.py` | 241 | SLOW-path full fan-out + condenser |
| `scripts/smaht/v2/validate.py` | (stub) | Self-check / sanity script |

**Subtotal**: 12 files, **2,948** LOC (excluding `validate.py`, which is a small stub).

### 1.3 Grand total scheduled for deletion

**13 files · ~5,381 LOC** (matches `wc -l` on the smart_decisioning + smaht/v2 tree).

---

## 2. Callers — imports, invocations, and string references

### 2.1 Python import sites (hot path)

| File | Line | Reference | Cleanup |
|---|---|---|---|
| `hooks/scripts/prompt_submit.py` | 18 | docstring: "scripts/smaht/v2/orchestrator.py via asyncio.run()" | rewrite docstring |
| `hooks/scripts/prompt_submit.py` | 33–37 | `_V2_DIR = _SCRIPTS_DIR / "smaht" / "v2"` + sys.path.insert | remove entirely (Phase 2 replaces prompt_submit body with a thin no-op that still runs session-goal + counter hooks) |
| `hooks/scripts/prompt_submit.py` | 413, 829, 841, 989, 1143 | `from history_condenser import HistoryCondenser` | remove; session state either moves to a stdlib replacement or is dropped (pull-model assembly already replaces most of this) |
| `hooks/scripts/prompt_submit.py` | 817, 1133 | `from context_pressure import PressureTracker` | remove |
| `hooks/scripts/prompt_submit.py` | 970–972 | comments "CONTINUATION_PATTERNS in scripts/smaht/v2/router.py" | remove comments |
| `hooks/scripts/prompt_submit.py` | 1039–1040 | `from router import Router; Router(...).route(prompt)` | remove — fold routing into a minimal in-file classifier or drop (smaht pull-model means prompt_submit does far less) |
| `hooks/scripts/prompt_submit.py` | 1084–1085 | `from orchestrator import Orchestrator; Orchestrator(session_id=...)` | remove — facilitator + pull-model assembly replaces push-context assembly |
| `hooks/scripts/stop.py` | 141–148 | `from fact_extractor import FactExtractor` + emit loop | rewrite: either reimplement a stdlib fact extractor, or drop the session-end fact emission path (it relies on smaht turn log) |
| `hooks/scripts/stop.py` | 282–283 | `from history_condenser import HistoryCondenser` | remove |
| `hooks/scripts/pre_compact.py` | 173, 259 | `from history_condenser import HistoryCondenser` + `from context_pressure import PressureTracker` | remove; pre_compact loses ticket-rail preservation (acceptable — compaction is rare and facilitator re-evaluate-on-TaskCompleted covers the crew case) |
| `scripts/smaht/context_package.py` | 179 | `from smaht.v2.history_condenser import HistoryCondenser` | remove or replace with stdlib session-meta read; function is `get_session_state()` |
| `scripts/smaht/v2/history_condenser.py` | 127, 134 | internal imports of fact_extractor + lane_tracker | *deleted together* |
| `scripts/smaht/v2/fast_path.py` | 24, 25, 109, 223, 289 | cross-v2 imports | *deleted together* |
| `scripts/smaht/v2/slow_path.py` | 30–32, 111, 224 | cross-v2 imports | *deleted together* |
| `scripts/smaht/v2/orchestrator.py` | 19–22 | cross-v2 imports | *deleted together* |
| `scripts/crew/specialist_discovery.py` | 17–18 | docstring referencing `smart_decisioning.py` circular-dep note | clean docstring |
| `scripts/crew/config.py` | 76 | `trace("smart_decisioning", ...)` literal string in an example comment | leave (literal string only) — update to `trace("facilitator", ...)` for consistency |
| `scripts/_bus.py` | 37 | comment: "Crew domain — phase_manager.py + smart_decisioning.py" | update comment |

### 2.2 Command markdown files

| File | Line | Reference | Cleanup |
|---|---|---|---|
| `commands/crew/start.md` | 403 | `scripts/crew/smart_decisioning.py --json ...` invocation in Section B | **legacy-path-only**: Section B (WG_FACILITATOR=legacy) exists as the rollback escape hatch. In Phase 2 the `start.md` legacy section B is deleted entirely along with the script. |
| `commands/crew/start.md` | 415–420 | Section B `memory_payload` handling | delete with Section B |
| `commands/crew/execute.md` | 228, 253 | `scripts/crew/smart_decisioning.py --json` for checkpoint re-analysis | rewrite: checkpoint re-analysis must invoke `wicked-garden:crew:propose-process` skill in `re-evaluate` mode (see `skills/crew/propose-process/SKILL.md#Re-evaluation mode`) |
| `commands/crew/execute.md` | 297, 303 | Section "memory_payload handling" | rewrite: payload is now the facilitator's `process-plan.md` addendum + explicit `wicked-brain:memory` call (rubric Step 9 / re-eval mode) |
| `commands/crew/just-finish.md` | 166 | `scripts/crew/smart_decisioning.py --json "{summary of deliverables}"` | rewrite: invoke propose-process skill with `mode=yolo` |
| `commands/crew/swarm.md` | 41 | `from smart_decisioning import detect_swarm_trigger` | rewrite: detect_swarm_trigger is gate-finding aggregation — move to a standalone stdlib module `scripts/crew/swarm_trigger.py` (roughly 70 LOC isolated in smart_decisioning.py lines ~1781–1870) OR replace with bus-query over `event_type=gate-finding` events. See note in §4 — this is the **one non-trivial extraction** hiding in the manifest. |
| `commands/smaht/smaht.md` | 31, 36 | `scripts/smaht/v2/orchestrator.py gather/route` | rewrite or delete command — smaht domain is being retired in favor of pull-model via facilitator + brain. If `/wicked-garden:smaht:smaht` stays, it must become a shim over brain+search. |
| `commands/smaht/debug.md` | 26 | `scripts/smaht/v2/history_condenser.py` | rewrite or delete command |
| `skills/smaht/SKILL.md` | 22, 25, 28 | orchestrator invocation | rewrite skill body or retire |
| `skills/qe/scenario-executor/refs/prose-interpretation.md` | 29, 37 | smaht/v2/orchestrator references | update prose |
| `skills/qe/qe-strategy/refs/test-type-taxonomy.md` | 295 | reference to smart_decisioning signal analysis | update prose to cite facilitator rubric |
| `skills/crew/workflow/refs/scoring-rubric.md` | 4 | "extracted from smart_decisioning.py" | rewrite or delete ref (the workflow skill's scoring refs may become obsolete — propose-process is the new rubric) |
| `skills/crew/propose-process/SKILL.md` | 7 | descriptive mention: "Replaces the v5 rule engine (smart_decisioning.py + phases.json + SIGNAL_TO_SPECIALISTS)" | leave — this is the deprecation notice pointing at the old system |

### 2.3 Config / data files

| File | Reference | Cleanup |
|---|---|---|
| `.claude-plugin/specialist.json` | 53 lines, 8 specialists with `enhances: [<phase>]` arrays pinned to phases.json keys | **keep specialist.json**; drop the `enhances` coupling to phases.json (facilitator reads frontmatter directly per SKILL.md §4). In Phase 2, either strip `enhances` field or leave as harmless metadata. |
| `.claude-plugin/phases.json` | 219 lines; referenced by `phase_manager.py`, `consensus_gate.py`, `pre_tool.py`, `post_tool.py`, `_event_schema.py` | **retain as-is for Phase 2**. phases.json is the source of truth for gate thresholds + enforcement config for phases the facilitator still picks. It is *not* the decision engine — the facilitator decides which phases to run and phases.json supplies their gate config. No deletion. |
| `scripts/_bus_consumers.json` | 55 lines, 6 consumers. None reference smart_decisioning or smaht/v2 directly — all consume events. | no change. |

### 2.4 Hooks

| File | Reference | Cleanup |
|---|---|---|
| `hooks/hooks.json` | registers `prompt_submit.py`, `stop.py`, `pre_compact.py`, `pre_tool.py`, `post_tool.py`, `task_completed.py` | **keep wiring**; the scripts themselves need the import surgery listed in §2.1. |

### 2.5 Tests scheduled for deletion or rewrite

| File | LOC | Cleanup |
|---|---|---|
| `tests/smaht/test_adapter_registry.py` | 547 | **DELETE** — tests scripts/smaht/v2/adapter_registry.py exclusively |
| `tests/smaht/test_assembler_registry.py` | 324 | **DELETE** — tests FastPath/SlowPath assemblers |
| `tests/smaht/test_orchestrator_metrics.py` | 340 | **DELETE** — tests Orchestrator metrics |
| `tests/smaht/test_context7_cheatsheet.py` | 263 | **review** — may or may not depend on v2; if pure context7 client it survives |
| `tests/hooks/test_prompt_submit_refactor.py` | 677 | **DELETE** — refactor-era test wired to v2 Orchestrator internals |
| `tests/hooks/test_prompt_submit_routing.py` | 353 | **DELETE** — sources Router from scripts/smaht/v2/router.py |
| `tests/hooks/test_hot_continuation_accumulation.py` | 140 | **DELETE** — imports HistoryCondenser |
| `tests/hooks/test_hot_path_fast_exit.py` | 203 | **DELETE** — asserts "from orchestrator import Orchestrator" ordering in prompt_submit.py |
| `tests/crew/test_gate_enforcement.py` | 364 | **retain** — tests phase_manager gate enforcement, not decisioning. No smart_decisioning imports. |

**Test deletion subtotal**: 7 files confirmed delete · 1 review · 1 retain.

### 2.6 Scenarios scheduled for deletion or rewrite

| File | Cleanup |
|---|---|
| `scenarios/crew/06-decisioning.md` | DELETE — directly exercises `smart_decisioning.py --json --files` |
| `scenarios/crew/06-archetype-scoring.md` | DELETE — exercises archetype detection in smart_decisioning |
| `scenarios/crew/multidim-scoring-breakdown.md` | DELETE — exercises 7-dimension scoring breakdown |
| `scenarios/qe/qe-lifecycle-expansion.md` | rewrite — imports `SIGNAL_KEYWORDS, SIGNAL_TO_SPECIALISTS` from smart_decisioning |
| `scenarios/smaht/fact-extraction.md` | DELETE — exercises HistoryCondenser fact extraction |
| `scenarios/smaht/multi-lane-tracking.md` | DELETE — exercises lane_tracker + HistoryCondenser |
| `scenarios/smaht/session-context-injection.md` | DELETE — exercises orchestrator.gather + HistoryCondenser |
| `scenarios/smaht/prompt-context-injection.md` | DELETE — exercises orchestrator.gather + HistoryCondenser |
| `scenarios/smaht/graceful-degradation.md` | DELETE — exercises orchestrator fail-open |
| `scenarios/smaht/intent-based-retrieval.md` | DELETE — exercises orchestrator.route |
| `scenarios/smaht/crew-auto-routing.md` | DELETE — imports `from smaht.v2.router import Router` |
| `scenarios/smaht/synthesize-e2e.md` | DELETE — exercises full synthesize path |
| `scenarios/smaht/06-context7-integration.md` | rewrite — context7 cheatsheet is orthogonal; may survive as brain-adapter exercise |

**Scenario deletion subtotal**: ~11 delete, 2 rewrite.

### 2.7 Other references (comments, docs, changelogs)

| File | Reference | Cleanup |
|---|---|---|
| `docs/crew-workflow.md` | line 127 | update prose: checkpoint re-analysis uses facilitator re-evaluate mode |
| `docs/architecture.md` | multiple | update prose: remove v2 orchestrator narrative, add facilitator |
| `CHANGELOG.md` | line 787 | leave — historical |
| `.claude/CLAUDE.md` | lines 132, 140, 221 | update project guidance to reference facilitator rubric |

---

## 3. Cleanup list — caller-by-caller disposition

For Phase 2 execution, each caller falls into one of:

**Remove entirely** (caller is obsolete after deletion):
- `tests/smaht/test_adapter_registry.py`, `tests/smaht/test_assembler_registry.py`, `tests/smaht/test_orchestrator_metrics.py`
- `tests/hooks/test_prompt_submit_refactor.py`, `test_prompt_submit_routing.py`, `test_hot_continuation_accumulation.py`, `test_hot_path_fast_exit.py`
- `scenarios/crew/06-decisioning.md`, `06-archetype-scoring.md`, `multidim-scoring-breakdown.md`
- 11 scenarios under `scenarios/smaht/`
- `commands/smaht/smaht.md`, `commands/smaht/debug.md`, `skills/smaht/SKILL.md` — **pending decision**: retire smaht domain vs. shim over brain+search

**Rewrite to use facilitator**:
- `commands/crew/execute.md` — checkpoint re-analysis → `wicked-garden:crew:propose-process` (mode=re-evaluate)
- `commands/crew/just-finish.md` — yolo completion → `wicked-garden:crew:propose-process` (mode=yolo)
- `scenarios/qe/qe-lifecycle-expansion.md` — signal-to-specialist coverage → rewrite against facilitator roster
- `hooks/scripts/prompt_submit.py` — strip v2 imports; retain session counter + goal capture + memory nudge (<100 LOC after surgery)
- `hooks/scripts/stop.py` — drop FactExtractor path OR reimplement as stdlib turn-log scanner (~60 LOC)
- `hooks/scripts/pre_compact.py` — drop ticket-rail preservation (facilitator handles the crew case via re-evaluate-on-TaskCompleted)
- `scripts/smaht/context_package.py` — `get_session_state()` becomes a no-op or reads a simpler stdlib session file

**Extract before delete** (non-trivial logic to preserve):
- `scripts/crew/smart_decisioning.py::detect_swarm_trigger()` (~lines 1781–1870, ~70 LOC) → extract to new `scripts/crew/swarm_trigger.py` OR replace with a bus-query over `event_type=gate-finding` records. Swarm detection is the only rule-engine function that remains useful after the rubric replaces scoring.

**Leave as legacy-path-only** (Section B of start.md):
- `commands/crew/start.md` Section B (lines ~224 onwards) — **delete with the script in Phase 2**. Section B exists solely as the WG_FACILITATOR=legacy rollback; once the script is gone there's nothing for it to run.

---

## 4. Totals

- **Files to delete**: 13 production files (smart_decisioning + smaht/v2) · 7 test files · ~11 scenarios = **~31 files**
- **Production LOC removed**: ~5,381 (plus ~2,500 LOC of tests, ~1,500 LOC of scenarios)
- **Caller files requiring edits**: **~18** (6 command/skill markdown · 3 hook scripts · 1 smaht script · 4 docs · misc prose)
- **Non-trivial extractions**: **1** (`detect_swarm_trigger`) — everything else is outright removal or routine rewrite.
- **Config data preserved**: `phases.json` (source of truth for gate thresholds), `specialist.json` (8 specialist personas), `_bus_consumers.json` (no v5 refs).

---

## 5. Risk callouts

1. **stop.py fact emission**: `_run_memory_promotion` currently pulls from the smaht turn log via FactExtractor. If we retire the whole pipeline, the `wicked.fact.extracted` → brain auto-memorize path goes dark. Either (a) reimplement a stdlib fact extractor over the native tasks/*.jsonl turn transcript, or (b) accept that session-fact emission dies with smaht and document it.
2. **pre_compact session preservation**: the ticket-rail that survives compaction lives in HistoryCondenser. Without it, post-compaction context is reconstructed from scratch by the facilitator. Acceptable for v6 but worth flagging.
3. **smaht domain retirement vs shim**: three commands/skills under `commands/smaht/` + `skills/smaht/` are user-facing. Phase 2 must decide: retire entirely (add redirects to brain/search), or rebuild as thin shims. Not a deletion blocker but must be resolved before merge.
4. **specialist.json enhances[]**: currently references phase names. The facilitator reads agent frontmatter directly (per SKILL.md §4), so `enhances[]` becomes vestigial. Either strip it in Phase 2 or leave as harmless metadata.
5. **Scenario coverage gap after deletion**: 11 smaht scenarios and 3 crew scenarios go away. Facilitator-rubric scenarios (10 canonical in `scenarios/crew/facilitator-rubric/`) are the replacement; Gate 4 smoke run adds 3 more. Net: broader surface but fewer adversarial tests. Plan to backfill during v6 Gate 5 if needed.
