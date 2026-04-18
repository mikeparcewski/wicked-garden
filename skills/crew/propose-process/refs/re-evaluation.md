# Re-Evaluation Mode (Bidirectional, v6)

The facilitator runs at every phase boundary — not just at `crew:start`. Two modes:

## Phase-start heuristic

Before the first specialist engages, `phase_start_gate.check()` fires a lightweight check. If task-completion count or evidence file mtimes have changed since `last_reeval_ts`, it emits a `systemMessage` directing the facilitator to run `re-evaluate` mode before proceeding. Fail-open: missing chain data → no-op with warning.

See `scripts/crew/phase_start_gate.py` for the stdlib implementation. Heuristic bias per D6: when mtime resolution is ambiguous, prefer false-positive (trigger re-eval) over false-negative (skip).

## Phase-end full re-eval

After the phase's primary deliverable is written, before `crew:approve`, the facilitator is invoked in `re-evaluate` mode with the structured `current_chain` dict (from `scripts/crew/current_chain.py`). The output is appended as a JSONL record to `phases/{phase}/reeval-log.jsonl`.

`crew:approve` is **blocked fail-closed** until a conformant addendum exists. Schema: `refs/re-eval-addendum-schema.md`. Emergency bypass: `--skip-reeval --reason "<justification>"` which writes to `skip-reeval-log.json` and is consumed by `final-audit` gate per D9.

## Bidirectional mutation rules (per D7)

On `TaskCompleted` or a gate-finding, read `current_chain` + latest evidence. Then:

1. **Prune** — pending tasks now satisfied, or whose assumptions the evidence invalidates. One sentence WHY per pruned task. **Auto-applies** regardless of user overrides (pruning is evidence-driven).
2. **Augment** — tasks for emergent concerns (discovered migration, new compliance surface, blocked dependency). One sentence WHY. **Cap: 2 new tasks per re-eval**; 3rd and beyond → open questions only, not TaskCreated.
3. **Re-tier UP** — if evidence sharpens risk, upgrade rigor one or more levels. **Always auto-applies**; safety is one-way.
4. **Re-tier DOWN** — reduce rigor one level. **Auto-applies only when** tier was rubric-set AND ≥2 HIGH/MEDIUM factors are disproven. **Deferred for user confirmation** when tier was user-overridden (`rigor_override` set in project state).

Emit mutations as follow-up `TaskCreate` / `TaskUpdate`. Do NOT rewrite completed tasks. Addendum is JSONL (one record per re-eval), not markdown prose.

## Addendum JSONL shape

One line = one complete re-eval record. Required keys: `chain_id`, `triggered_at`, `trigger` ("phase-end" or "task-completion"), `prior_rigor_tier`, `new_rigor_tier`, `factor_deltas`, `mutations` (array of `{op, task_id?, new_rigor_tier?, why}`), `mutations_applied` (subset of mutations that auto-applied), `mutations_deferred` (subset awaiting user confirmation), `validator_version`.

Validated by `scripts/crew/validate_reeval_addendum.py`. Exit 0 = valid; exit 1 with stderr = reject.

## Interaction-mode interaction

D7 bidirectional rules apply in all modes (normal/yolo/just-finish). Re-tier UP always auto-applies; re-tier DOWN defers when `rigor_override` is set. No interaction mode overrides this safety property.
