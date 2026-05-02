# Disk-Write → Bus-Emit Gap Audit (#733)

> **Headline**: 63 disk-write call sites in `scripts/crew/` + `hooks/scripts/`. **Zero** currently emit bus events. The bus-as-truth refactor (#732) starts from a clean baseline — there is nothing to *change*, only writes to *augment* with corresponding emits.

## Method

- Scanned: `scripts/crew/**/*.py` (59 files) + `hooks/scripts/**/*.py` (12 files including `subscribers/`)
- Patterns audited: `write_text`, `write_bytes`, `json.dump`, `open()` w/a/wb/ab, `os.replace`, `shutil.copy/move`, `mkdir` of state dirs, `unlink`, `rmtree`, `tempfile + os.replace`, `SessionState.save/update`
- Bus-emit detection: `subprocess.run(["wicked-bus", "emit", ...])` or helper-function calls (e.g. `emit_validated_payloads()` in `detectors/_common.py`) in the same function scope as the write
- Date: 2026-05-02

## Combined summary

| Metric | scripts/crew | hooks/scripts | Total | % |
|--------|--------------|---------------|-------|---|
| Total write call sites | 47 | 16 | **63** | 100% |
| Already emit a bus event | 0 | 0 | **0** | **0%** |
| Emit but envelope incomplete | 0 | 0 | 0 | 0% |
| Silent (no emit at all) | 47 | 16 | **63** | **100%** |

### Top 5 risky gaps across both surfaces

1. **`scripts/crew/phase_manager.py:3676`** — `gate-result.json` synthesized post-blend dispatch. Verdict deterministic but written silently. Highest-risk: this is the file the orphan-check sentinel relies on.
2. **`scripts/crew/phase_manager.py:2684`** — `conditions-manifest.json` written on gate CONDITIONAL. Core state mutation; zero emit.
3. **`scripts/crew/dispatch_log.py:330–331`** — `dispatch-log.jsonl` append for every gate dispatch. The HMAC-signed dispatch log is the orphan-check input — it's written silently.
4. **`hooks/scripts/post_tool.py:963, 970`** — Consensus gate `reviewer-report.md` silently written. `phase_manager` reads this file on next approval cycle — file poll, not event-driven.
5. **`scripts/crew/conditions_manifest.py:77, 89`** — Atomic temp+`os.replace` write of `conditions-manifest.json`. Crash-safe but silent.

## Findings — scripts/crew

| file:line | target_path | mutation_type | emits_event | event_type | envelope_complete | proposed_event |
|-----------|-------------|---------------|-------------|------------|-------------------|----------------|
| solo_mode.py:328 | phases/{phase}/conditions-manifest.json.tmp | write_text | no | — | — | wicked.crew.solo-mode.conditions.manifest |
| solo_mode.py:332 | phases/{phase}/conditions-manifest.json | replace | no | — | — | wicked.crew.solo-mode.conditions.manifest |
| solo_mode.py:388 | phases/{phase}/inline-review-context.md | write_text | no | — | — | wicked.crew.solo-mode.review-context.created |
| solo_mode.py:436 | phases/{phase}/gate-result.json.tmp | write_text | no | — | — | wicked.crew.solo-mode.gate-result.recorded |
| solo_mode.py:440 | phases/{phase}/gate-result.json | replace | no | — | — | wicked.crew.solo-mode.gate-result.recorded |
| consensus_gate.py:428 | phases/{phase}/consensus-report.json | mkdir + write_text | no | — | — | wicked.crew.consensus.report.created |
| consensus_gate.py:463 | phases/{phase}/consensus-evidence.json | mkdir + write_text | no | — | — | wicked.crew.consensus.evidence.recorded |
| acceptance_criteria.py:366 | phases/clarify/acceptance-criteria.json.tmp | write_text | no | — | — | wicked.crew.acceptance-criteria.migrated |
| acceptance_criteria.py:367 | phases/clarify/acceptance-criteria.json | replace | no | — | — | wicked.crew.acceptance-criteria.migrated |
| adopt_legacy.py:110 | project.json | write_text | no | — | — | wicked.crew.legacy.phase-plan-mode-set |
| adopt_legacy.py:171 | phases/{phase}/reeval-log.jsonl | open(a) + write | no | — | — | wicked.crew.legacy.reeval-migrated |
| adopt_legacy.py:179 | process-plan.md | write_text | no | — | — | wicked.crew.legacy.markdown-reeval-cleared |
| adopt_legacy.py:209 | (various markdown files) | write_text | no | — | — | wicked.crew.legacy.bypass-reference-removed |
| amendments.py:206 | phases/{phase}/ | mkdir | no | — | — | — (directory creation, not state) |
| amendments.py:242 | phases/{phase}/amendments.jsonl | open(a) + write + fsync | no | — | — | wicked.crew.amendments.recorded |
| conditions_manifest.py:77 | phases/{phase}/conditions-manifest.json.tmp | open(w) + write + fsync | no | — | — | wicked.crew.conditions-manifest.atomic-write |
| conditions_manifest.py:89 | phases/{phase}/conditions-manifest.json | os.replace | no | — | — | wicked.crew.conditions-manifest.atomic-write |
| conditions_manifest.py:192 | phases/{phase}/conditions-manifest.{id}.resolution.json | atomic_write_json | no | — | — | wicked.crew.condition.resolution-sidecar |
| conditions_manifest.py:203 | phases/{phase}/conditions-manifest.json | atomic_write_json | no | — | — | wicked.crew.condition.marked-cleared |
| convergence.py:228 | phases/{phase}/convergence-log.jsonl | open(a) + write | no | — | — | wicked.crew.convergence.transition-recorded |
| dispatch_log.py:329 | phases/{phase}/ | mkdir | no | — | — | — (directory creation, not state) |
| dispatch_log.py:330–331 | phases/{phase}/dispatch-log.jsonl | open(a) + write | no | — | — | wicked.crew.dispatch-log.entry-appended |
| gate_ingest_audit.py:160 | phases/{phase}/ | mkdir | no | — | — | — (directory creation, not state) |
| gate_ingest_audit.py:162 | phases/{phase}/gate-ingest-audit.jsonl | open(a) + write | no | — | — | wicked.crew.gate-ingest.audit-recorded |
| hitl_judge.py:611–613 | phases/{phase}/{filename}.json | mkdir + write_text | no | — | — | wicked.crew.hitl.decision-persisted |
| log_retention.py:168 | archive/ (subdir) | mkdir | no | — | — | — (directory creation, not state) |
| log_retention.py:180–181 | archive/*.jsonl.gz | gzip.open(wb) + shutil.copyfileobj | no | — | — | wicked.crew.log-retention.archive-rotated |
| log_retention.py:200 | (active log path) | open(w) + truncate | no | — | — | wicked.crew.log-retention.log-truncated |
| migrate_qe_evaluator_name.py:173 | *.bak | write_bytes | no | — | — | wicked.crew.migration.backup-created |
| migrate_qe_evaluator_name.py:180 | *.tmp | write_text | no | — | — | wicked.crew.migration.temp-written |
| migrate_qe_evaluator_name.py:191 | (original file) | os.replace | no | — | — | wicked.crew.migration.file-migrated |
| phase_manager.py:1169 | phases/{phase}/status.md | write_text | no | — | — | wicked.crew.phase.status-initialized |
| phase_manager.py:1600 | phases/{phase}/context.md | write_text | no | — | — | wicked.crew.phase.context-created |
| phase_manager.py:2571 | phases/review/semantic-gap-report.json | mkdir + write_text | no | — | — | wicked.crew.semantic-alignment.report-created |
| phase_manager.py:2684 | phases/{phase}/conditions-manifest.json | write_text | no | — | — | wicked.crew.gate.conditional-conditions-written |
| phase_manager.py:2913 | phases/{phase}/iteration-count.json | mkdir + write_text | no | — | — | wicked.crew.iteration.count-recorded |
| phase_manager.py:2939 | phases/{phase}/status.md | open(a) + read + write_text | no | — | — | wicked.crew.gate-override.rigor-exception-recorded |
| phase_manager.py:2958 | phases/{phase}/status.md | open(a) + read + write_text | no | — | — | wicked.crew.deliverable.override-recorded |
| phase_manager.py:2994 | phases/{phase}/skip-reeval-log.json | write_text | no | — | — | wicked.crew.reeval.skip-logged |
| phase_manager.py:3415 | (task entry file) | write_text | no | — | — | wicked.crew.gate-finding.synced-to-completed |
| phase_manager.py:3676 | phases/{phase}/gate-result.json | mkdir + write_text | no | — | — | wicked.crew.gate.verdict-synthesized |
| phase_manager.py:4159 | phases/{phase}/status.md | write_text | no | — | — | wicked.crew.phase.skipped |
| phase_manager.py:4343 | phases/{phase}/*.md | write_text | no | — | — | wicked.crew.adoption.legacy-memo-recorded |
| phase_manager.py:4486 | project.md | write_text | no | — | — | wicked.crew.project.template-initialized |
| phase_manager.py:4499 | outcome.md | write_text | no | — | — | wicked.crew.outcome.template-initialized |
| phase_manager.py:4512 | phases/clarify/status.md | write_text | no | — | — | wicked.crew.phase.template-initialized |
| phase_manager.py:5282 | phases/.cutover-to-mode-3.json | mkdir + write_text | no | — | — | wicked.crew.mode-switch.cutover-marker-written |
| reeval_addendum.py:208 | phases/{phase}/ | mkdir | no | — | — | — (directory creation, not state) |
| reeval_addendum.py:212 | phases/{phase}/reeval-log.jsonl | open(a) + write + fsync | no | — | — | wicked.crew.reeval.addendum-appended |
| reeval_addendum.py:244 | process-plan.addendum.jsonl | open(a) + write + fsync | no | — | — | wicked.crew.reeval.project-log-appended |
| traceability_generator.py:307 | phases/build/ | mkdir | no | — | — | — (directory creation, not state) |
| traceability_generator.py:308 | phases/build/traceability-matrix.md | write_text | no | — | — | wicked.crew.traceability.matrix-generated |

## Findings — scripts/crew/detectors

**Note**: Detectors emit events via `emit_validated_payloads()` in `detectors/_common.py`. This audit scanned for **disk writes**, not event emissions, and found **zero** disk-write call sites in any detector module. All detectors are pure compute-to-bus with no durable state mutations. The bus-as-truth refactor leaves detectors untouched.

## Findings — hooks/scripts

| file:line | target_path | mutation_type | emits_event | event_type | envelope_complete | proposed_event |
|-----------|-------------|---------------|-------------|------------|-------------------|----------------|
| bootstrap.py:1079 | $CLAUDE_ENV_FILE (project .claude/env or ~/.claude/env) | append | no | — | — | N/A — env setup, not state |
| bootstrap.py:1120 | ~/.something-wicked/wicked-crew/.task_suggest_shown | delete | no | — | — | N/A — idempotent flag |
| pre_compact.py:75 | ~/.wicked-brain/memories/{tier}/ | mkdir | no | — | — | N/A — directory setup |
| pre_compact.py:96 | ~/.wicked-brain/memories/{tier}/mem-{uuid}.md | overwrite | no | — | — | wicked.memory.captured (after brain index success) |
| prompt_submit.py:88 | ~/.wicked-brain/memories/{tier}/ | mkdir | no | — | — | N/A — directory setup |
| prompt_submit.py:109 | ~/.wicked-brain/memories/{tier}/mem-{uuid}.md | overwrite | no | — | — | wicked.memory.captured (session goal) |
| post_tool.py:963 | {project_dir}/phases/{phase}/reviewer-report.md | append | no | — | — | wicked.consensus.gate-completed |
| post_tool.py:969 | {project_dir}/phases/{phase}/ | mkdir | no | — | — | N/A — directory setup |
| post_tool.py:970 | {project_dir}/phases/{phase}/reviewer-report.md | overwrite | no | — | — | wicked.consensus.gate-completed |
| post_tool.py:983 | {project_dir}/phases/{phase}/ | mkdir | no | — | — | N/A — directory setup |
| post_tool.py:984 | {project_dir}/phases/{phase}/reviewer-report.md | overwrite | no | — | — | wicked.consensus.gate-pending (evaluation failed) |
| post_tool.py:1314 | $TMPDIR/wicked-trace-{session_id}.jsonl | append | no | — | — | N/A — tempdir-only trace |
| subagent_lifecycle.py:133 | $TMPDIR/wicked-garden/traces/ | mkdir | no | — | — | N/A — tempdir-only |
| subagent_lifecycle.py:135 | $TMPDIR/wicked-garden/traces/{session_id}.jsonl | append | no | — | — | N/A — tempdir-only trace |
| subagent_lifecycle.py:260 | {project_dir}/phases/{phase}/ | mkdir | no | — | — | N/A — directory setup |
| subagent_lifecycle.py:280 | {project_dir}/phases/{phase}/specialist-engagement.json | atomic temp + replace | no | — | — | wicked.specialist.engagement-recorded |

## Findings — hooks/scripts/subscribers

### `on_gate_decided.py`

This is a **bus-grain subscriber** (Issue #592, v8 PR-8) — receives `wicked.gate.decided` events and emits `wicked.hook.gate-decided-processed` events. It is the canonical example of what the bus-as-truth pattern looks like.

| file:line | mutation_type | target_path | emits_event | event_type |
|-----------|---------------|-------------|-------------|------------|
| on_gate_decided.py:59 | emit (synthetic) | stdout → wicked-bus | **yes** | wicked.hook.gate-decided-processed |

No disk writes. Pure message-passing.

## Notes on SessionState writes

All hooks call `SessionState.load()`, mutate fields, and call `state.update()` or `state.save()`. This persists to:

```
~/.something-wicked/wicked-garden/sessions/{session_id}.json
```

**SessionState is intentionally NOT event-sourced** — and this audit recommends keeping it that way:

- Hot-path: mutated 100s of times per session (turn count, context flags, memory compliance)
- Emitting per mutation = bus churn with no consumer value
- Hooks already emit ops logs via `_log()` for audit purposes
- SessionState is cache/context, not the system-of-record for any decision/gate

If a future refactor makes SessionState the source of truth for gate decisions (unlikely), revisit this assumption.

## Notes on memory capture writes

`pre_compact.py:_write_brain_memory()` and `prompt_submit.py:_write_brain_memory()` write to disk and immediately call `_brain_api("index", ...)`. The disk write itself is silent, but the brain indexing call provides synchronous confirmation.

**Recommendation for #734**: emit `wicked.memory.captured` *after* successful brain indexing returns, not before disk write — the event should reflect actual completion, not optimistic expectation.

## Cross-reference: scripts/_event_schema.py

The TaskCreate metadata envelope in `scripts/_event_schema.py` defines the validated shape for native task events. Bus events should mirror this where applicable.

Required fields (cross-cutting):
- `chain_id` — `{project}.root` | `{project}.{phase}` | `{project}.{phase}.{gate}` (regex enforced)
- `source_agent` — never `just-finish-auto`, `fast-pass`, or anything starting with `auto-approve-`
- `phase` — must appear in `.claude-plugin/phases.json` catalog when applicable
- `event_type` — one of `task | coding-task | gate-finding | phase-transition | procedure-trigger | subtask`

For `gate-finding` events at completion: `verdict ∈ {APPROVE, CONDITIONAL, REJECT}`, `min_score`, `score`. CONDITIONAL also requires `conditions_manifest_path` (Issue #570).

The bus event envelope SHOULD adopt the same `chain_id` + `source_agent` + `phase` fields so projections can correlate task events with bus events without lossy joins.

## Out of scope

- `scripts/qe/`, `scripts/data/`, `scripts/delivery/`, `scripts/agentic/`, `scripts/persona/`, etc. — separate audit scope
- Test files (`tests/**`)
- Tempdir-only writes (`$TMPDIR/wicked-trace-*`) that don't persist past process exit
- Stdlib `print()` / `sys.stdout.write()` (not persistent state)
- `scripts/_session.py` SessionState mutations (intentionally not event-sourced — see above)

## Architectural notes

### Hooks fail-open by design

All hooks return `{"continue": true}` on unhandled exceptions. The absence of bus events in hook code is partly a fail-open consequence — if emit fails, the hook still returns continue. The bus-as-truth refactor must preserve fail-open semantics: emit failure cannot block hook completion.

### Consensus gate as a critical gap

The consensus gate flow today:

```
phase_manager.approve()
  → PostToolUse hook
    → _handle_bash_consensus()
      → write reviewer-report.md (silent)
next cycle:
  phase_manager reads reviewer-report.md (file poll, not event-driven)
```

This is a subtle fail-open: if the hook write fails silently or the file is deleted, phase progression still succeeds (gates are advisory). For #732, this should emit `wicked.consensus.gate-completed` so the gate system has an event-driven signal independent of file existence.

### Atomic-write idioms are correct but silent

Multiple call sites use `tempfile + os.replace` for crash-safety: `conditions_manifest.py:77,89`, `solo_mode.py:328,332,436,440`, `subagent_lifecycle.py:280`. The atomic-write pattern is correct. The gap is solely the missing emit — adding the emit AFTER the `os.replace` succeeds preserves atomicity.

## Recommendations for #734

For each gap in the tables above, the owner of #734 must decide:

1. **Emit required (default)** — Add event payload + emit call AFTER the write succeeds (or after `os.replace` for atomic-write idioms). Use the proposed event_type from the table or refine.
2. **Emit not applicable** — Document the exception in the projector design (e.g., env setup, idempotent flags, tempdir-only traces).
3. **Borderline** — Templates, iteration counters, archives. Clarify in the envelope design whether these are audit events or ledger-only state.

### Priority order for emit additions

1. **HIGH** — Gate-result, conditions-manifest, dispatch-log, consensus reviewer-report writes. These are the orphan-check inputs and the projector's primary signals.
2. **MEDIUM** — Phase status markers, semantic-gap report, specialist-engagement, memory captures. Useful for projection completeness but not gate-correctness.
3. **LOW** — Templates, log rotation, legacy migration, iteration counters. Audit-trail value only.

### What the projector can rely on today

**Nothing.** Every disk write that the projector might want to subscribe to is currently silent. The projector design in #734 must assume:

- It either drives the emit additions itself (add emits as part of #734)
- Or it falls back to file polling on the load-bearing artifacts as an interim until per-gap PRs land

Recommendation: **#734 should bundle the HIGH-priority emit additions** (gate-result, conditions-manifest, dispatch-log, consensus reviewer-report) so the projector has real subscribable events from day one. MEDIUM and LOW gaps land in follow-up PRs over the subsequent release cycle.

## Cross-references

- Umbrella: #732 (bus-as-truth event-sourcing refactor)
- Step 2 (blocked on this): #734 (resume projector + lint)
- Closes: #733
- Builds on: PR #690 (`/wicked-garden:crew:reconcile` — drift diagnostic feeds step 3 cutover)
- Decision memory: `bus-as-truth-event-sourced-crew-state.md` (semantic tier)
