# Gate 4 Phase 1 — Cutover Coverage Matrix

**Verdict**: **GO with caveats** — two rows flagged `PARTIAL` require a lightweight follow-up in Phase 2 (swarm trigger extraction + session-fact emission decision). No hard gaps that block deletion.

**Rule**: Any `YES` (true gap) would halt Phase 2. The two `PARTIAL` rows below are acceptable because the missing capability is either (a) extractable stdlib logic (~70 LOC), or (b) a retire-or-replace policy call that should be made in Phase 2 anyway.

---

## Flagged rows (read these before the table)

### FLAG 1 — `detect_swarm_trigger()` (PARTIAL, extractable)

Located at `scripts/crew/smart_decisioning.py` lines ~1781–1870. Consumed by `commands/crew/swarm.md` line 41. The facilitator rubric has no swarm-crisis detector. But the logic is small (aggregate 3+ BLOCK/REJECT gate findings → recommend Quality Coalition), is independent of the signal engine, and can be extracted verbatim into `scripts/crew/swarm_trigger.py` during Phase 2. Alternative: replace with a bus query over `event_type=gate-finding` records.

**Phase 2 action**: extract before deletion, or re-implement as a bus query. ~2h of work.

### FLAG 2 — Session-fact emission via `FactExtractor` (PARTIAL, policy call)

`hooks/scripts/stop.py` `_run_memory_promotion` reads the smaht session turn log via `FactExtractor` and emits `wicked.fact.extracted` events. Brain auto-memorize subscribes. Deleting smaht/v2 breaks the feed source.

**Phase 2 action**: pick one —
1. Reimplement a stdlib extractor over `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/*.jsonl` (native task transcript).
2. Accept that per-session auto-memorize dies; explicit `wicked-brain:memory` calls remain.

Either is defensible; the facilitator does NOT depend on auto-memorize.

---

## Coverage matrix

| Legacy behavior (v5) | Facilitator equivalent (v6) | Gap? |
|---|---|---|
| **Signal detection** — `SIGNAL_KEYWORDS` (18 categories, word-boundary regex) + `SIGNAL_TO_SPECIALISTS` (map to 8 plugins) in `smart_decisioning.py` lines 48–174 | Factor scoring: rubric Step 3 "Score the 9 factors" + Step 4 "Select specialists by reading agents/**/*.md frontmatter directly". Signals are replaced by the 9 factors (reversibility, blast_radius, compliance_scope, user_facing_impact, novelty, scope_effort, state_complexity, operational_risk, coordination_cost). Factor readings are LOW/MEDIUM/HIGH prose, not numeric scores. | **NO** — factor-based scoring is a deliberate replacement of keyword-based signal detection; calibrated across the 10 canonical scenarios at Gate 1 with 10/10 PASS. |
| **Complexity scoring** — multi-dimensional algorithm: impact, reversibility, novelty, test_complexity, documentation, coordination_cost, operational, scope_effort, integration_surface, state_complexity → composite 0–7 with archetype adjustments, file-impact bonuses, incident-history bonus (lines 200–2280) | Rubric Step 8 "Estimate complexity (0–7). Judgment, not checklist. 0–1 trivial. 2–3 small. 4–5 feature. 6–7 cross-cutting or compliance-bound." Calibrated by the 9-factor reading from Step 3. | **NO** — judgment-driven 0–7 estimate with factor priors replaces the weighted-sum algorithm; Gate 1 measurement passed 10/10 scenarios within ±1 complexity tolerance. |
| **Archetype detection** — 12 archetypes (content-heavy, ui-heavy, api-backend, infrastructure-framework, data-pipeline, mobile-app, ml-ai, compliance-regulated, monorepo-platform, real-time, text-as-code, greenfield) with impact_bonus + min_complexity + inject_signals | **Facilitator does NOT carry archetypes as a concept.** The rubric instead expects the facilitator to read the description for meaning (Step 1 "Name the user-facing outcome, surface area — UI/API/data/infra/docs — and any risk words") + pull priors (Step 2). Archetypes re-emerge implicitly in the factor readings and phase selection. No formal archetype name is attached. | **NO** (intentional) — archetypes were a heuristic that layered keyword-detection on top of keyword-detection. The rubric's "summarize surface area in your own words" step captures the same information without committing to a 12-class taxonomy. Accept the loss of the explicit label. |
| **Phase selection** from phases.json — complexity_range + triggers + depends_on dependency graph; non-skippable-first then signal-matched then complexity-based (`phase_manager.py` + `smart_decisioning.py`) | Rubric Step 5 "Pick from: ideate, clarify, design, test-strategy, build, test, review. Dependencies are soft — skip design for a trivial typo, collapse clarify+design for a crisp bugfix, insert migrate between design and build when state_complexity is high." Catalog in `refs/phase-catalog.md` with skip/collapse guidance. phases.json is retained for gate thresholds and deliverable specs. | **NO** — phase selection moves from a rule-graph computation to rubric-driven templates; phases.json stays as gate-config source of truth. Canonical scenarios confirm selection quality. |
| **Specialist fallback table** — `SPECIALIST_FALLBACKS` (`jam→facilitator`, `qe→reviewer`, etc.) + `VALID_FALLBACK_AGENTS` (lines 177–190) | Facilitator reads `agents/**/*.md` frontmatter directly per SKILL.md §4 "Read agents/**/*.md frontmatter (descriptions + 'Use when'). Pick the smallest set that covers the factor scores." Fallback logic becomes "if a matched agent isn't available, pick the closest on the roster." No static map. | **NO** — the roster is the source of truth; the fallback map was a band-aid for missing agents. Rubric's direct-read approach is more robust as the roster evolves. |
| **routing_lane = auto/fast/standard** — `determine_routing_lane(NormalizedScore)` → WRI-based lane selection (lines 1018 + 2232) | Rubric Step 7 "Assign rigor tier — minimal / standard / full" based on factor readings. `minimal` ≈ old `auto`; `standard` ≈ old `fast`+`standard`; `full` is the security/compliance override. Also interaction mode (yolo) orthogonal per SKILL.md §"Interaction mode". | **NO** — rigor_tier is a direct semantic match for routing_lane; the fix in commit `ee807bd` explicitly un-conflated interaction mode (yolo) from phase plan / rigor, matching the user's mental model. |
| **Pre-flight complexity gate** — "This request has low complexity" prompt in `start.md` Section B triggered by routing_lane=auto/fast | Rubric Step 9 "Open questions" + Step 7 rigor tier. When rigor_tier=minimal AND factors are all LOW, facilitator can auto-proceed in yolo mode (SKILL.md §"Interaction mode"). When ambiguity is high, rubric STOPS and emits 2–5 clarifying questions BEFORE task creation. | **NO** — the pre-flight "this is too heavy" nudge is replaced by rigor_tier=minimal + open-questions gate. Stricter than v5: v5's pre-flight prompted the user; the rubric stops autonomously on ambiguity. |
| **Memory payload emission** — `memory_payload` field on JSON output; caller (start.md / execute.md) stores via `/wicked-garden:mem:store` | Rubric writes `process-plan.md` to the project directory (Step 2) + explicit `wicked-brain:memory` store call for "non-obvious decisions, patterns, gotchas" per the project CLAUDE.md. The Gate 3 wiring in `commands/crew/start.md` Section A includes a brain-memory store for the facilitator plan (line ~182). | **NO** — process-plan.md is the durable artifact; brain memory stores are explicit, not keyword-gated. Richer than v5. |
| **HOT/FAST/SLOW/SYNTHESIZE context paths** — smaht/v2 orchestrator tiers triggered by prompt_submit.py | Pull-model context assembly (v4.10 / commit 80e024f): subagents and skills pull context on demand via `wicked-brain:search`/`query` + `wicked-garden:search` + `smaht:context` skill. No push from prompt_submit. | **NO** — push-model context was the point of smaht/v2; pull-model replaces it. Facilitator + brain + search cover the ground. Smaht domain (commands/skills) survives as optional shim or retires — Phase 2 policy call, not a coverage gap. |
| **HOT path consumers outside prompt_submit.py**? — does anything else rely on HistoryCondenser, PressureTracker, or Orchestrator? | See manifest §2.1. Confirmed consumers: `hooks/scripts/stop.py` (HistoryCondenser + FactExtractor), `hooks/scripts/pre_compact.py` (HistoryCondenser + PressureTracker), `scripts/smaht/context_package.py` (HistoryCondenser), `commands/smaht/debug.md` (history_condenser script CLI). | **PARTIAL** (FLAG 2) — session-fact emission in stop.py depends on FactExtractor + HistoryCondenser turn-log read. Requires policy call in Phase 2 (reimplement stdlib or retire feature). Other consumers are cosmetic and drop cleanly. |
| **Swarm trigger detection** — `detect_swarm_trigger()` aggregates BLOCK/REJECT gate findings across session, recommends Quality Coalition when ≥3 found | Facilitator rubric has no equivalent — swarm detection is orthogonal to per-project decisioning. | **PARTIAL** (FLAG 1) — extract ~70 LOC into `scripts/crew/swarm_trigger.py` before deleting smart_decisioning.py, OR re-implement as bus query over gate-finding events. Must be resolved in Phase 2 but not a deletion blocker. |

---

## Summary

- **9 rows NO GAP** — facilitator covers v5 behavior, often with semantic upgrades (judgment over rules, direct frontmatter read over static maps, explicit artifact over keyword-gated payload).
- **2 rows PARTIAL** — both extract-or-retire decisions, both documented above.
- **0 rows YES GAP** — no coverage holes that block deletion.

**Recommendation**: GO for Phase 2 deletion, conditional on (a) extracting `detect_swarm_trigger` OR reimplementing it as a bus query, and (b) making the session-fact emission policy call (reimplement or retire) in the Phase 2 PR.
