# Disk-Write → Bus-Emit Gap Audit (#733)

> **Headline (revised after PR #735 review)**: 63 disk-write call sites in `scripts/crew/` + `hooks/scripts/`. After accounting for the `_bus.emit_event()` helper pattern AND coverage via the caller chain (helpers invoked from emit-bearing functions like `approve_phase` and `create_project`), the true picture is:
>
> - **~17 writes covered** (directly or via caller chain) by existing emits the projector already consumes
> - **~46 writes still silent** (or covered only by lossy filesystem polling)
> - **`daemon/projector.py` already exists** and projects 13 event types into a SQLite database — the bus-as-truth substrate is partially built
>
> The bus-as-truth refactor (#732) is **smaller than the v1 of this report claimed**. The remaining work is: (1) emit additions for the truly-silent writes, (2) a resume-snapshot subscriber over the existing projector tables (#734), (3) a PreToolUse lint preventing new orphan writes.

## Method (corrected after Gemini review on PR #735)

**v1 method (incorrect)**: Searched for `subprocess.run(["wicked-bus", "emit", ...])` and `emit_validated_payloads()` in the same function as each disk write. Reported 0 of 63 sites emitting.

**False negatives in v1**:

1. The dominant emit pattern in `phase_manager.py` is `from _bus import emit_event; emit_event("wicked.X.Y", payload)` — a local helper that wraps the bus subprocess. v1's pattern set did not detect this.
2. Many writes happen in **helper functions** called by emit-bearing parents. Example: `_write_conditions_manifest` is called from `approve_phase`, which emits `wicked.gate.decided` after the helper returns. The write is *semantically* covered by the parent's emit even though the helper is silent.
3. `daemon/projector.py` already exists and projects 13 event types (`wicked.project.created`, `wicked.gate.decided`, `wicked.task.created`, etc.) into a SQLite database — the bus-as-truth substrate is partially built. v1 did not look for it.

**v2 method (corrected)**:

- Patterns scanned: same disk-write set as v1
- Bus-emit detection: all of v1's patterns PLUS `from _bus import emit_event; emit_event(...)` PLUS coverage-by-caller-chain analysis (mapping each write to its enclosing function and tracing whether any caller emits)
- Cross-check: `daemon/projector.py:_HANDLERS` for events already consumed
- Date: 2026-05-02 (v2 revision)

## Combined summary (v2 — corrected)

| Metric | scripts/crew | hooks/scripts | Total | % |
|--------|--------------|---------------|-------|---|
| Total write call sites | 47 | 16 | **63** | 100% |
| Direct emit in same function | 1 | 0 | 1 | ~2% |
| Covered indirectly via caller chain | ~16 | ~1 | ~17 | ~27% |
| **Truly silent** (no emit, no covering caller) | ~30 | ~15 | **~45** | **~71%** |
| N/A — directory creation, env setup, tempdir, deletes of idempotent flags | n/a | 8 | 8 | 13% (excluded from gap %) |

The "~" reflects that some helper functions (e.g. `cutover_action`, `skip_phase`) need a deeper trace to confirm whether their callers emit. The numbers above are conservative; #734's design must verify on a per-row basis before relying on coverage.

## What `daemon/projector.py` already covers

| Event type | Projector handler | Source emit (today) | Disk-write sites covered |
|------------|-------------------|---------------------|--------------------------|
| wicked.project.created | `_project_created` (L119) | phase_manager.py:4547 | phase_manager.py:4486, 4499, 4512 |
| wicked.project.complexity_scored | `_project_complexity_scored` (L150) | (facilitator skill) | — |
| wicked.phase.transitioned | `_phase_transitioned` (L171) | phase_manager.py:4013 | phase_manager.py:1169 (status.md init via complete_phase) |
| wicked.phase.auto_advanced | `_phase_auto_advanced` (L222) | _bus_consumers.py:145 | — |
| wicked.gate.decided | `_gate_decided` (L264) | phase_manager.py:3931 | phase_manager.py:2684, 2913, 2939, 2958, 2994, 3415, 3676; conditions_manifest.py:77, 89, 192, 203 (via approve_phase caller chain) |
| wicked.rework.triggered | `_rework_triggered` (L309) | phase_manager.py:3953 | (see above row) |
| wicked.project.completed | `_project_completed` (L340) | phase_manager.py:4088 | — |
| wicked.crew.yolo_revoked | `_crew_yolo_revoked` (L472) | phase_manager.py:4708 | — |
| wicked.task.created | `_task_created` (L355) | (TaskCreate hook) | — |
| wicked.task.updated | `_task_updated` (L391) | (TaskUpdate hook) | — |
| wicked.task.completed | `_task_completed` (L443) | (TaskUpdate hook on terminal status) | — |
| wicked.ac.declared | `_ac_declared` (L504) | acceptance_criteria.py (TBD) | — |
| wicked.ac.evidence_linked | `_ac_evidence_linked` (L539) | acceptance_criteria.py (TBD) | — |

Plus emits OUTSIDE scripts/crew that the projector may or may not consume yet:

- `scripts/qe/registry_store.py:138` — emit
- `scripts/qe/coverage_tracker.py:379` — emit
- `scripts/delivery/drift.py:501` — `wicked.quality.drift_detected`
- `hooks/scripts/stop.py:162` — `wicked.fact.extracted`

## Top 5 risky gaps (truly silent — no covering emit)

After accounting for caller-chain coverage, the genuine high-risk gaps are:

1. **`hooks/scripts/post_tool.py:963, 970`** — Consensus gate `reviewer-report.md` written silently from a hook. `phase_manager` reads this file by polling — the only file→file flow in the gate path. Highest priority for #734's lint.
2. **`scripts/crew/dispatch_log.py:330–331`** — HMAC-signed dispatch-log.jsonl entries. The orphan-check sentinel for `gate-result.json`. Needs an emit so the projector can detect orphan-without-dispatch independently of file existence.
3. **`scripts/crew/consensus_gate.py:428, 463`** — `consensus-report.json` + `consensus-evidence.json` written without emit. Used by gate evaluation; should emit `wicked.consensus.report.created` so projector can cache.
4. **`scripts/crew/amendments.py:242`** + **`scripts/crew/reeval_addendum.py:212, 244`** — Append-only re-evaluation logs. Multi-session resume needs these in the projector.
5. **`scripts/crew/phase_manager.py:1600`** (`ensure_reviewer_context`) + **`scripts/crew/phase_manager.py:2571`** (`_check_semantic_alignment_gate`) — `context.md` and `semantic-gap-report.json`. Material for the resume view.

## Findings — scripts/crew (revised)

Coverage notation:
- ✅ **direct** — emit in same function
- 🔗 **caller-chain** — helper called from emit-bearing parent; covered by parent's emit
- ❌ **silent** — no covering emit found
- ⊘ **n/a** — directory creation, log rotation, migration, or otherwise out of state-of-record scope

| file:line | target_path | mutation_type | coverage | event_type if covered | proposed_event if silent |
|-----------|-------------|---------------|----------|----------------------|--------------------------|
| solo_mode.py:328 | phases/{phase}/conditions-manifest.json.tmp | write_text | ❌ | — | wicked.crew.solo-mode.conditions.manifest |
| solo_mode.py:332 | phases/{phase}/conditions-manifest.json | replace | ❌ | — | wicked.crew.solo-mode.conditions.manifest |
| solo_mode.py:388 | phases/{phase}/inline-review-context.md | write_text | ❌ | — | wicked.crew.solo-mode.review-context.created |
| solo_mode.py:436 | phases/{phase}/gate-result.json.tmp | write_text | ❌ | — | wicked.crew.solo-mode.gate-result.recorded |
| solo_mode.py:440 | phases/{phase}/gate-result.json | replace | ❌ | — | wicked.crew.solo-mode.gate-result.recorded |
| consensus_gate.py:428 | phases/{phase}/consensus-report.json | mkdir + write_text | ❌ | — | wicked.crew.consensus.report.created |
| consensus_gate.py:463 | phases/{phase}/consensus-evidence.json | mkdir + write_text | ❌ | — | wicked.crew.consensus.evidence.recorded |
| acceptance_criteria.py:366 | phases/clarify/acceptance-criteria.json.tmp | write_text | ❌ | — | wicked.crew.acceptance-criteria.migrated |
| acceptance_criteria.py:367 | phases/clarify/acceptance-criteria.json | replace | ❌ | — | wicked.crew.acceptance-criteria.migrated |
| adopt_legacy.py:110 | project.json | write_text | ❌ | — | wicked.crew.legacy.phase-plan-mode-set |
| adopt_legacy.py:171 | phases/{phase}/reeval-log.jsonl | open(a) + write | ❌ | — | wicked.crew.legacy.reeval-migrated |
| adopt_legacy.py:179 | process-plan.md | write_text | ❌ | — | wicked.crew.legacy.markdown-reeval-cleared |
| adopt_legacy.py:209 | (various markdown files) | write_text | ❌ | — | wicked.crew.legacy.bypass-reference-removed |
| amendments.py:206 | phases/{phase}/ | mkdir | ⊘ | — | — (directory creation) |
| amendments.py:242 | phases/{phase}/amendments.jsonl | open(a) + write + fsync | ❌ | — | wicked.crew.amendments.recorded |
| conditions_manifest.py:77 | phases/{phase}/conditions-manifest.json.tmp | open(w) + write + fsync | 🔗 | wicked.gate.decided (when called from approve_phase) | — (consider explicit emit for direct callers) |
| conditions_manifest.py:89 | phases/{phase}/conditions-manifest.json | os.replace | 🔗 | wicked.gate.decided (when called from approve_phase) | — |
| conditions_manifest.py:192 | phases/{phase}/conditions-manifest.{id}.resolution.json | atomic_write_json | ❌ | — | wicked.crew.condition.resolution-sidecar |
| conditions_manifest.py:203 | phases/{phase}/conditions-manifest.json | atomic_write_json | ❌ | — | wicked.crew.condition.marked-cleared |
| convergence.py:228 | phases/{phase}/convergence-log.jsonl | open(a) + write | ❌ | — | wicked.crew.convergence.transition-recorded |
| dispatch_log.py:329 | phases/{phase}/ | mkdir | ⊘ | — | — (directory creation) |
| dispatch_log.py:330–331 | phases/{phase}/dispatch-log.jsonl | open(a) + write | ❌ | — | wicked.crew.dispatch-log.entry-appended |
| gate_ingest_audit.py:160 | phases/{phase}/ | mkdir | ⊘ | — | — (directory creation) |
| gate_ingest_audit.py:162 | phases/{phase}/gate-ingest-audit.jsonl | open(a) + write | ❌ | — | wicked.crew.gate-ingest.audit-recorded |
| hitl_judge.py:611–613 | phases/{phase}/{filename}.json | mkdir + write_text | ❌ | — | wicked.crew.hitl.decision-persisted |
| log_retention.py:168 | archive/ (subdir) | mkdir | ⊘ | — | — (directory creation) |
| log_retention.py:180–181 | archive/*.jsonl.gz | gzip + shutil.copyfileobj | ⊘ | — | — (housekeeping; arguably emit `wicked.crew.log-rotated`) |
| log_retention.py:200 | (active log path) | open(w) + truncate | ⊘ | — | — (housekeeping) |
| migrate_qe_evaluator_name.py:173 | *.bak | write_bytes | ⊘ | — | — (migration) |
| migrate_qe_evaluator_name.py:180 | *.tmp | write_text | ⊘ | — | — (migration) |
| migrate_qe_evaluator_name.py:191 | (original file) | os.replace | ⊘ | — | — (migration) |
| phase_manager.py:1169 | phases/{phase}/status.md | write_text | 🔗 | wicked.phase.transitioned (via complete_phase ← approve_phase) | — |
| phase_manager.py:1600 | phases/{phase}/context.md | write_text | ❌ | — | wicked.crew.phase.context-created |
| phase_manager.py:2571 | phases/review/semantic-gap-report.json | mkdir + write_text | 🔗 | wicked.gate.decided (called from approve_phase L3617) | — (consider explicit `wicked.crew.semantic-alignment.report-created`) |
| phase_manager.py:2684 | phases/{phase}/conditions-manifest.json | write_text | 🔗 | wicked.gate.decided (CONDITIONAL branch) | — |
| phase_manager.py:2913 | phases/{phase}/iteration-count.json | mkdir + write_text | 🔗 | wicked.rework.triggered (called from approve_phase L3948) | — |
| phase_manager.py:2939 | phases/{phase}/status.md | open(a) + read + write_text | 🔗 | wicked.gate.decided (override branch) | — |
| phase_manager.py:2958 | phases/{phase}/status.md | open(a) + read + write_text | 🔗 | wicked.gate.decided (deliverable override branch) | — |
| phase_manager.py:2994 | phases/{phase}/skip-reeval-log.json | write_text | 🔗 | wicked.gate.decided (skip-reeval branch) | — |
| phase_manager.py:3415 | (task entry file) | write_text | 🔗 | wicked.gate.decided (called from approve_phase L3985) | — |
| phase_manager.py:3676 | phases/{phase}/gate-result.json | mkdir + write_text | ✅ | wicked.gate.decided (L3931, same function) | — |
| phase_manager.py:4159 | phases/{phase}/status.md | write_text | ❌ | — | wicked.crew.phase.skipped (skip_phase has no emit today) |
| phase_manager.py:4343 | phases/{phase}/*.md | write_text | ❌ | — | wicked.crew.adoption.legacy-memo-recorded |
| phase_manager.py:4486 | project.md | write_text | 🔗 | wicked.project.created (L4547) | — |
| phase_manager.py:4499 | outcome.md | write_text | 🔗 | wicked.project.created (L4547) | — |
| phase_manager.py:4512 | phases/clarify/status.md | write_text | 🔗 | wicked.project.created (L4547) | — |
| phase_manager.py:5282 | phases/.cutover-to-mode-3.json | mkdir + write_text | ❌ | — | wicked.crew.mode-switch.cutover-marker-written |
| reeval_addendum.py:208 | phases/{phase}/ | mkdir | ⊘ | — | — (directory creation) |
| reeval_addendum.py:212 | phases/{phase}/reeval-log.jsonl | open(a) + write + fsync | ❌ | — | wicked.crew.reeval.addendum-appended |
| reeval_addendum.py:244 | process-plan.addendum.jsonl | open(a) + write + fsync | ❌ | — | wicked.crew.reeval.project-log-appended |
| traceability_generator.py:307 | phases/build/ | mkdir | ⊘ | — | — (directory creation) |
| traceability_generator.py:308 | phases/build/traceability-matrix.md | write_text | ❌ | — | wicked.crew.traceability.matrix-generated |

## Findings — scripts/crew/detectors

**Note**: Detectors emit events via `emit_validated_payloads()` and have **zero** disk-write call sites. Pure compute-to-bus. The bus-as-truth refactor leaves detectors untouched.

## Findings — hooks/scripts (revised)

| file:line | target_path | mutation_type | coverage | event_type if covered | proposed_event if silent |
|-----------|-------------|---------------|----------|----------------------|--------------------------|
| bootstrap.py:1079 | $CLAUDE_ENV_FILE | append | ⊘ | — | — (env setup) |
| bootstrap.py:1120 | ~/.something-wicked/wicked-crew/.task_suggest_shown | delete | ⊘ | — | — (idempotent flag) |
| pre_compact.py:75 | ~/.wicked-brain/memories/{tier}/ | mkdir | ⊘ | — | — (directory setup) |
| pre_compact.py:96 | ~/.wicked-brain/memories/{tier}/mem-{uuid}.md | overwrite | ❌ | — | wicked.memory.captured (emit AFTER brain index) |
| prompt_submit.py:88 | ~/.wicked-brain/memories/{tier}/ | mkdir | ⊘ | — | — (directory setup) |
| prompt_submit.py:109 | ~/.wicked-brain/memories/{tier}/mem-{uuid}.md | overwrite | ❌ | — | wicked.memory.captured (session goal) |
| post_tool.py:963 | {project_dir}/phases/{phase}/reviewer-report.md | append | ❌ | — | wicked.consensus.gate-completed |
| post_tool.py:969 | {project_dir}/phases/{phase}/ | mkdir | ⊘ | — | — (directory setup) |
| post_tool.py:970 | {project_dir}/phases/{phase}/reviewer-report.md | overwrite | ❌ | — | wicked.consensus.gate-completed |
| post_tool.py:983 | {project_dir}/phases/{phase}/ | mkdir | ⊘ | — | — (directory setup) |
| post_tool.py:984 | {project_dir}/phases/{phase}/reviewer-report.md | overwrite | ❌ | — | wicked.consensus.gate-pending |
| post_tool.py:1314 | $TMPDIR/wicked-trace-{session_id}.jsonl | append | ⊘ | — | — (tempdir-only trace) |
| subagent_lifecycle.py:133 | $TMPDIR/wicked-garden/traces/ | mkdir | ⊘ | — | — (tempdir-only) |
| subagent_lifecycle.py:135 | $TMPDIR/wicked-garden/traces/{session_id}.jsonl | append | ⊘ | — | — (tempdir-only trace) |
| subagent_lifecycle.py:260 | {project_dir}/phases/{phase}/ | mkdir | ⊘ | — | — (directory setup) |
| subagent_lifecycle.py:280 | {project_dir}/phases/{phase}/specialist-engagement.json | atomic temp + replace | ❌ | — | wicked.specialist.engagement-recorded |

`hooks/scripts/stop.py` emits `wicked.fact.extracted` (L162) but does not write to disk in that flow — emit-only, no write to pair with.

`hooks/scripts/subscribers/on_gate_decided.py` is a pure message-passing subscriber — no disk writes, emits `wicked.hook.gate_decided_processed` (underscores, not hyphens — verified at L58 of the subscriber). Canonical example of the bus-as-truth pattern.

## Notes on SessionState writes

All hooks call `SessionState.load()` → mutate → `state.save()`. This persists to `${TMPDIR or tempfile.gettempdir()}/wicked-garden-session-{session_id}.json` (per `scripts/_session.py:60-62`) and is **intentionally NOT event-sourced**:

- Hot-path: 100s of mutations per session (turn count, context flags, memory compliance)
- Per-mutation emit = bus churn with no consumer
- SessionState is cache/context, not the system-of-record for any decision

If a future refactor makes SessionState the source of truth for gate decisions (unlikely), revisit.

## Cross-reference: scripts/_event_schema.py

The TaskCreate metadata envelope in `scripts/_event_schema.py` defines the validated shape for native task events. Required cross-cutting fields:

- `chain_id` — `{project}.root` | `{project}.{phase}` | `{project}.{phase}.{gate}` (regex enforced)
- `source_agent` — never `just-finish-auto`, `fast-pass`, or anything starting with `auto-approve-`
- `phase` — must appear in `.claude-plugin/phases.json` catalog when applicable
- `event_type` — one of `task | coding-task | gate-finding | phase-transition | procedure-trigger | subtask`

For `gate-finding` events at completion: `verdict ∈ {APPROVE, CONDITIONAL, REJECT}`, `min_score`, `score`. CONDITIONAL also requires `conditions_manifest_path` (Issue #570).

Bus event envelopes (when added) SHOULD adopt the same `chain_id` + `source_agent` + `phase` fields so projections can correlate task events with bus events without lossy joins.

## Out of scope

- `scripts/qe/`, `scripts/data/`, `scripts/delivery/`, `scripts/agentic/`, `scripts/persona/`, etc. — separate audit scope (note: emits exist in qe/registry_store.py:138, qe/coverage_tracker.py:379, delivery/drift.py:501)
- Test files (`tests/**`)
- Tempdir-only writes
- `scripts/_session.py` SessionState mutations (intentionally not event-sourced — see above)

## Architectural notes

### `daemon/projector.py` is partially built

The bus-as-truth substrate already exists. `daemon/projector.py:_HANDLERS` projects 13 event types into a SQLite database. This significantly downscopes #734 — the projector does not need to be built from scratch; #734 needs to:

1. Add a **resume-snapshot subscriber** that joins the projector's tables into a per-project view (`crew/{project}/resume.json` derived from existing project / phase / gate / task tables)
2. Add the PreToolUse lint that prevents new orphan writes to load-bearing artifacts
3. Add the missing emits for the truly-silent gaps that block the resume view

### Hooks fail-open by design

All hooks return `{"continue": true}` on unhandled exceptions. The bus-as-truth refactor must preserve this — emit failure cannot block hook completion. The lint should be `warn` mode for one release before flipping to `strict`.

### Consensus gate file→file flow is the worst remaining gap

```
phase_manager.approve()
  → PostToolUse hook
    → _handle_bash_consensus()
      → write reviewer-report.md (silent)
next cycle:
  phase_manager reads reviewer-report.md (file poll, not event-driven)
```

This is the only file→file flow remaining in the gate path after caller-chain analysis. #734's lint should target it specifically.

## Recommendations for #734 (revised)

The original recommendation ("bundle HIGH-priority emit additions") was scoped to too much work because v1's "0% emitting" headline was wrong. Revised recommendation:

1. **Build the resume-snapshot subscriber over `daemon/projector.py` tables**. The existing `_project_created`, `_phase_transitioned`, `_gate_decided`, `_rework_triggered`, `_project_completed`, `_task_*` handlers already populate the SQLite tables that a per-project resume view needs to join. Snapshot to `crew/{project}/resume.json` on phase transition events.
2. **Add the PreToolUse lint** for orphan writes to `gate-result.json`, `dispatch-log.jsonl`, `conditions-manifest.json`, `reviewer-report.md`. Warn mode this release; strict next.
3. **Bundle ONE small set of emit additions** for the writes the resume view needs that are still silent: `dispatch_log.py:330–331` (`wicked.crew.dispatch-log.entry-appended`) and `consensus_gate.py:428,463` (`wicked.consensus.report.created`). Everything else can land in follow-up PRs over the subsequent release cycle.
4. **Defer**: solo-mode emits, legacy adoption emits, log retention emits, migration emits, hitl-judge emits. Not blocking the resume view.

### Priority order for emit additions in scope

1. **HIGH (block the resume view)** — `dispatch_log.py:330–331`, `consensus_gate.py:428,463`, `post_tool.py:963,970,984` (consensus reviewer-report.md)
2. **MEDIUM (improve cross-session resume completeness)** — `amendments.py:242`, `reeval_addendum.py:212,244`, `subagent_lifecycle.py:280`, `phase_manager.py:1600`, `phase_manager.py:5282`
3. **LOW (audit-trail value only)** — solo-mode flow, legacy adoption flow, log retention rotation, migration, hitl-judge persistence

## Cross-references

- Closes #733
- Umbrella: #732 (bus-as-truth)
- Blocks: #734 (resume projector + lint) — substantially smaller than originally sized
- Builds on: PR #690 (`/wicked-garden:crew:reconcile`)
- Decision memory: `bus-as-truth-event-sourced-crew-state.md` (semantic tier)
- Existing projector: `daemon/projector.py:_HANDLERS` (13 event types projected)
