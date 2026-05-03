# Bus-cutover staging plan (#746)

> **Scope**: design-only brief that informs the per-site implementation
> PRs spawned by issue #746. **No code changes.** No new emits, no
> production behavior changes, no reconciler modifications. Every cutover
> PR that follows from this plan must be reversible by `git revert`.

## 1. Background

The bus-as-truth umbrella issue **#732** decided that `wicked-bus` is the
source of truth for crew project state, and that TaskList plus the garden
chain (`process-plan.md`, `phases/{phase}/*.json`,
`phases/{phase}/dispatch-log.jsonl`, `phases/{phase}/conditions-manifest.json`,
`phases/{phase}/gate-result.json`, `phases/{phase}/reviewer-report.md`,
`phases/{phase}/reeval-log.jsonl`, `phases/{phase}/amendments.jsonl`)
become **projections** of the bus event log, not parallel write stores.
#732 is closed; the council CONDITIONALLY APPROVED the architecture
against C1-C5 captured in the decision memory
`bus-as-truth-event-sourced-crew-state` (semantic tier).

The substrate that #746 cuts over to has shipped over four PRs:

- **#735** — disk-write to bus-emit gap audit
  (`docs/audits/disk-write-bus-emit-gap.md`, 222 lines). Enumerated 63
  call sites with coverage markers (✅ direct / 🔗 caller-chain /
  ❌ silent / ⊘ n/a). **Primary input to section 3.**
- **#736** — Step 1: resume projector. `daemon/projector.py` projects
  13 event types into `event_log`/`projects`/`phases`/`tasks` SQLite
  tables (`daemon/db.py`); `scripts/crew/resume_projector.py` is the
  read-side projection layer.
- **#737** — Step 2: PreToolUse bus-emit lint. `_check_bus_emit_lint`
  in `hooks/scripts/pre_tool.py` runs at every Write/Edit/MultiEdit on
  the four target basenames (`gate-result.json`, `dispatch-log.jsonl`,
  `conditions-manifest.json`, `reviewer-report.md`) under a `phases/`
  parent. Default `WG_BUS_EMIT_LINT=warn`.
- **#738** — Part C: emit additions. `scripts/crew/dispatch_log.py`
  emits `wicked.dispatch.log_entry_appended`;
  `scripts/crew/consensus_gate.py` emits `wicked.consensus.report_created`
  + `wicked.consensus.evidence_recorded`. Both pair with the lint via
  `_BUS_EMIT_LINT_PAIR_EVENTS`.

### Council condition C2 (verbatim)

> **C2**: Reconciler drift data from PR #690 is a step-3 input, not a
> step-2 blocker. Open #733/#734 now; gate the TaskList + garden chain
> cutover (step 3) on the drift numbers.

This document is the step-3 design pass C2 references.

### Load-bearing constraint

**Every cutover PR is reversible by `git revert`.** No runtime kill
switch, no config-flag-only rollback that survives a PR revert. The
feature flags in section 3 exist so a cutover lands DARK and can be
enabled without a new PR; they do NOT replace `git revert` as the
rollback mechanism. Mirrors the existing crew gate-enforcement rollback
pattern: "Rollback: git revert on the PR; no runtime toggle"
(`.claude/CLAUDE.md`).

## 2. Drift baseline

`/wicked-garden:crew:reconcile --all --json` was invoked on this
worktree at **2026-05-02T15:35:56Z** against repo state `c0e0e62`.
Full output: `docs/audits/bus-cutover-drift-baseline-2026-05-02.json`.

### Aggregate counts

| Metric | Value |
|--------|-------|
| Projects scanned | 2 |
| Phases with `gate-result.json` | 1 |
| Total drift entries | 10 |
| `missing_native` | 0 |
| `stale_status` | 0 |
| `orphan_native` | **10** |
| `phase_drift` | 0 |
| Plan tasks total | 0 |
| Native tasks matching project chain total | 0 |
| Process-plans present | 0 of 2 |

### What the baseline shows

**Drift class that dominates: `orphan_native` (10/10 = 100% of detected
drift).** All ten entries trace to one historic project,
`issue-689-polish-bundle`, whose native tasks under
`~/.claude/tasks/{session_id}/` outlived the cleanup of its
`wicked-crew/projects/issue-689-polish-bundle/` directory. Tasks carry a
valid `chain_id` but the reconciler can no longer locate the matching
`process-plan.json`.

This is the **tasklist-without-garden-chain** class — TaskList persistence
outliving the garden chain because the two cleanup lifecycles are
decoupled. It will go away NATURALLY post-cutover, because in
bus-as-truth there is no `process-plan.json` to delete out from under the
native tasks; both stores become projections of the same event log and
the reconciler stops classifying this as drift at all (see section 5).

**Conspicuously absent**: zero `missing_native`, zero `stale_status`,
zero `phase_drift`. **Absence is not evidence here** — both sampled
projects had their `process-plan.json` already cleaned up, so the
reconciler had nothing to compare on the missing/stale/phase axes.

### Sample-size assessment

Issue #746 sets a sample-size floor: **>=10 distinct projects OR >=50
distinct phases**. This baseline shows **2 projects, 1 phase** — well
below the floor.

**Runway projection**: this single repo's organic crew usage has produced
two retained project directories in the most recent cleanup cycle. Polish
bundle work and acceptance-test runs typically purge their crew project
dirs at session end (memory: `clean-worktrees-at-project-end`). On
current usage, this machine alone will not reach the floor in any
reasonable window.

#746 anticipates this:
> If we can't reach this from a single repo's organic usage in any
> window, escalate the gating signal — calendar waits are explicitly off
> the table.

Escalation: aggregate reconciler output across multiple developer
machines (one volunteer week) AND/OR run a synthetic-drift scenario
suite that deliberately induces each drift class. The synthetic suite is
the cleaner answer because it pins coverage; aggregated organic data
validates the synthetic mirrors the wild. Both are scenario work
(section 6).

### Implication for cutover order

Because the dominant class on this machine (`orphan_native`) is a cleanup
artifact that the cutover removes by construction, **this baseline does
NOT change the cutover order**. The order in section 3 derives from PR
#735's coverage map. Once the sample floor is reached, a follow-up
baseline may surface `phase_drift` or `stale_status` patterns that
re-prioritize sites — at which point this section is updated with a new
datestamped baseline JSON and section 3 amended.

**Synthetic-drift suite (#746 sample-size mitigation)**: PR #XXX
ships `scripts/crew/synthetic_drift.py` + `tests/crew/test_synthetic_drift.py`
+ `scenarios/crew/synthetic-drift-coverage.md`. The suite proves the
reconciler correctly catches every drift class on demand — substituting
coverage-by-construction for the absent organic >=10 projects / >=50
phases sample. Sites 3-5 of the cutover order are gated on this suite
passing in CI.

## 3. Cutover order — by write-site

Each subsection follows the same shape: **Site / Current write path /
Already emits? / Cutover sequence / Rollback / Risk.** The five-step
cutover sequence is identical per site by design — that uniformity is
what makes per-site rollback predictable.

### Standard 5-step cutover sequence (applies to every site)

1. **Add bus emit BEFORE the disk write** if not already present.
   Verify a projector handler exists for the event in
   `daemon/projector.py`; add one if missing.
2. **Add feature flag** `WG_BUS_AS_TRUTH_<SITE>=on|off` (default `off`).
3. **When `on`, the write becomes "emit then disk-as-projection"** —
   the daemon is the primary store and the disk file is materialized
   from the projector handler. Existing readers are unchanged because
   the file still appears at the same path.
4. **After one full release of zero drift** (measured by the new
   reconciler shape from section 5: zero `event-without-projection` AND
   zero `projection-stale` for the cutover event), flip the default to
   `on`.
5. **After two more releases of zero drift** at the new default, delete
   the direct disk-write branch entirely. The function becomes
   pure-emit; the projector owns the file.

### Cutover order — five sites, lowest-risk first

1. `dispatch-log.jsonl` (already emits as of #738; lowest risk)
2. `consensus-report.json` + `consensus-evidence.json` (already emit;
   bundled)
3. `reviewer-report.md` (still silent in hooks layer; gate-critical but
   lint-covered)
4. `gate-result.json` (✅ direct emit; highest gate-criticality)
5. `conditions-manifest.json` (🔗 caller-chain; CONDITIONAL branch is
   load-bearing for #570)

Order optimizes:
- **(a) lowest-risk first**: `dispatch-log.jsonl` is an append-only
  signed log; a botched cutover only affects the orphan-detection
  sentinel for the next gate-result, not the verdict itself.
- **(b) highest-coverage substrate**: sites where the projector handler
  AND source emit both exist go first.
- **(c) most-recently-touched**: PR #738 is the freshest substrate;
  its emits will be live for one release cycle by the time the first
  cutover lands. Stale code = surprises; recent = fewer surprises.

`gate-result.json` has direct emit coverage but sits at #4 because its
blast radius is the entire gate-policy enforcement surface — it gets
the cutover only after three sites have validated the pattern in
production.

---

#### Site 1: `phases/{phase}/dispatch-log.jsonl`

- **Site**: `scripts/crew/dispatch_log.py:330–331` — append-only signed
  dispatch log entries.
- **Current write path**: `dispatch_log.append_entry(...)` opens in `a`
  mode, writes one HMAC-signed JSON line, fsyncs. Triggered by every
  specialist dispatch from `scripts/crew/gate_dispatch.py`.
- **Already emits?**: ✅ as of PR #738 — emits
  `wicked.dispatch.log_entry_appended` AFTER the write
  (audit upgrade: ❌ → ✅).
- **Cutover sequence**: standard 5 steps with flag
  `WG_BUS_AS_TRUTH_DISPATCH_LOG`. Step 1 is mostly NO-OP: emit already
  present; need projector handler `_dispatch_log_appended` (does not
  yet exist in `daemon/projector.py`).
- **Rollback**: `git revert` the cutover PR. Flag-flip and
  delete-direct-write are separate revert targets — three independently
  revertable PRs across three releases.
- **Risk**: a botched cutover means the orphan-check sentinel for
  `gate-result.json` ingestion runs against a JSONL that reflects
  projector state, not writer state. **Observable signal**: any rise in
  `gate_ingest_audit.py` orphan flags within 24h of the cutover landing.
  Existing `WG_GATE_RESULT_DISPATCH_CHECK=off` lever (per CLAUDE.md
  AC-9 §5.4) provides a fast bypass while the revert lands.

---

#### Site 2: `phases/{phase}/consensus-report.json` + `consensus-evidence.json`

- **Site**: `scripts/crew/consensus_gate.py:444–446` (report) and
  `consensus_gate.py:502–506` (evidence) — atomic JSON writes from
  consensus-gate evaluation.
- **Current write path**: `consensus_gate.write_report(...)` and
  `write_evidence(...)` mkdir then atomic-write the JSON. Called from
  the consensus gate evaluator at council-mode review gates.
- **Already emits?**: ✅ as of PR #738 — emits
  `wicked.consensus.report_created` /
  `wicked.consensus.evidence_recorded` AFTER each write
  (audit upgrade: ❌ → ✅).
- **Cutover sequence**: standard 5 steps with TWO flags,
  `WG_BUS_AS_TRUTH_CONSENSUS_REPORT` and
  `WG_BUS_AS_TRUTH_CONSENSUS_EVIDENCE` (paired in one PR). Add projector
  handlers `_consensus_report_created` and
  `_consensus_evidence_recorded` materializing into a
  `consensus_artifacts` table.
- **Rollback**: bundled-PR revert (the two flags landed together).
- **Risk**: consensus-gate evaluation is council-mode (multi-reviewer);
  drift can manifest as a panel score computed against stale evidence.
  **Observable signal**: any consensus-gate verdict where the panel
  score in `phase_manager.approve_phase` and the score recomputed from
  the projector tables differ by >0.01 (assertion in section 6
  scenario).

---

#### Site 3: `phases/{phase}/reviewer-report.md`

- **Site**: `hooks/scripts/post_tool.py:963, 970, 984` — written
  silently from the PostToolUse hook in the consensus-gate dispatch
  flow.
- **Current write path**: `_handle_bash_consensus()` is invoked when a
  Bash tool result matches the consensus-runner pattern. Appends to
  `reviewer-report.md` (line 963) on success, or overwrites it (lines
  970 + 984) on the `gate-completed` / `gate-pending` branches.
- **Already emits?**: ❌ silent at all three lines. Hook fail-opens, so
  there is no emit AT ALL today — the only file→file flow remaining in
  the gate path post-#738 (audit §"Top 5 risky gaps" #1 and
  §"Consensus gate file→file flow is the worst remaining gap").
- **Cutover sequence**: standard 5 steps with flag
  `WG_BUS_AS_TRUTH_REVIEWER_REPORT`. Step 1 is REAL WORK here: add new
  emits BEFORE each write — `wicked.consensus.gate_completed` for lines
  963 + 970, `wicked.consensus.gate_pending` for line 984. Hook MUST
  stay fail-open per CLAUDE.md ("All hooks return `{"continue": true}`
  on unhandled exceptions"); emit failure must not block hook
  completion.
- **Rollback**: `git revert` the cutover PR. Hook fail-open contract
  means a partial revert (re-add disk write but leave emit in place) is
  also safe.
- **Risk**: HIGHEST-risk site because (a) lives in a hook path that
  fail-opens by contract, (b) `phase_manager` polls the file rather
  than subscribing to the event, (c) the file is the only signal the
  polling reader has. **Observable signal**: any phase that reaches
  the consensus gate where `phase_manager._wait_for_reviewer_report`
  returns empty after timeout. Add a metric on hook emit
  success/failure ratio; gate the cutover flip on >99.9% emit success.

---

#### Site 4: `phases/{phase}/gate-result.json`

- **Site**: `scripts/crew/phase_manager.py:3676` is the SOLE write site
  for `gate-result.json`. Verified by
  `grep 'gate-result\.json.*write_text\|write_text.*gate-result\.json'
  scripts/crew/phase_manager.py` — only line 3676 matches. (Earlier
  drafts of this plan listed lines 2684, 2913, 2939, 2958, 2994, 3415
  as additional caller-chain writers; that was wrong — those lines
  write `conditions-manifest.json`, iteration files, status, and
  reeval-log entries, not `gate-result.json`. Corrected 2026-05-03
  during Site 4 pre-impl council.)
- **Current write path**: `_persist_gate_result()` at line 3676 is the
  canonical writer. Mkdir then `write_text()`. Triggered from
  `approve_phase` after the gate verdict is computed.
- **Already emits?**: ✅ direct emit at line 3931
  (`wicked.gate.decided`) in the same `approve_phase` flow as the
  write at line 3676. The audit marks this as the ONE row in
  `scripts/crew` with ✅ direct coverage.
- **Cutover sequence**: standard 5 steps with flag
  `WG_BUS_AS_TRUTH_GATE_RESULT`. Step 1 means moving the existing
  emit BEFORE the write (currently write happens at 3676, then emit at
  3931). The existing security floor for gate-result ingestion
  (CLAUDE.md AC-9 §5.4: schema validator, content sanitizer,
  dispatch-log orphan check, append-only audit log) MUST run on the
  projected file too — the projector handler invokes the same
  sanitize-and-validate pipeline. Load-bearing assertion for this
  site.
- **Rollback**: `git revert`. Existing levers
  (`WG_GATE_RESULT_SCHEMA_VALIDATION=off`,
  `WG_GATE_RESULT_CONTENT_SANITIZATION=off`,
  `WG_GATE_RESULT_DISPATCH_CHECK=off`) provide additional fast bypasses
  for the security pipeline; auto-expire at
  `WG_GATE_RESULT_STRICT_AFTER`.
- **Risk**: highest gate-criticality of any site. A botched cutover
  means a verdict is computed but the disk file does not appear, OR the
  disk file appears but the verdict is stale. **Observable signal**:
  diff the in-memory verdict computed by `phase_manager.approve_phase`
  against the verdict re-loaded from `gate-result.json` after the write
  returns. Any mismatch is the trip wire.

---

#### Site 5: `phases/{phase}/conditions-manifest.json`

- **Site**: `scripts/crew/conditions_manifest.py:77, 89` (canonical
  atomic write from `approve_phase`); `conditions_manifest.py:192, 203`
  (resolution sidecar + marked-cleared from condition-resolution flows);
  `phase_manager.py:2684` (CONDITIONAL branch direct write).
- **Current write path**: canonical writer is
  `conditions_manifest.write_manifest(...)`, called from `approve_phase`
  on CONDITIONAL verdicts. Resolution sidecar (192) and marked-cleared
  (203) are written by `resolve_condition(...)` and `mark_cleared(...)`
  from the `wicked-garden:crew:resolve` flow.
- **Already emits?**: 🔗 caller-chain via `wicked.gate.decided`
  (CONDITIONAL branch) for the canonical write. Resolution sidecar and
  marked-cleared updates are ❌ silent today (audit rows propose
  `wicked.crew.condition.resolution-sidecar` and
  `wicked.crew.condition.marked-cleared`).
- **Cutover sequence**: TWO sub-cutovers, sequenced not bundled:
  - **5a (canonical write)**: standard 5 steps with flag
    `WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST`. Existing emit
    `wicked.gate.decided` covers it; projector handler `_gate_decided`
    extends to materialize the manifest into a `conditions` table.
  - **5b (resolution sidecar + marked-cleared)**: REQUIRES NEW EMITS
    first (precursor PR; add emits before writes for
    `wicked.condition.resolution_recorded` and
    `wicked.condition.marked_cleared`). Then standard 5 steps with
    flag `WG_BUS_AS_TRUTH_CONDITION_RESOLUTION`.
- **Rollback**: per-sub-cutover revert. 5a and 5b have independent
  feature flags and independent revert targets.
- **Risk**: CONDITIONAL is the load-bearing branch for issue #570
  (`conditions_manifest_path` requirement on gate-finding completion).
  A botched cutover here can leave a CONDITIONAL verdict with no
  manifest path or with a stale manifest, blocking phase advancement.
  **Observable signal**: any task with `event_type=gate-finding`,
  `verdict=CONDITIONAL`, and `status=completed` where the
  `conditions_manifest_path` references a file that does not exist OR
  whose `last_modified` is older than the gate-finding task's
  `completed_at`.

---

### Sites NOT in scope for this cutover (deferred per audit §Defer)

Solo-mode (`solo_mode.py`); legacy adoption (`adopt_legacy.py`); log
retention (`log_retention.py`); migration scripts
(`migrate_qe_evaluator_name.py`); HITL judge persistence
(`hitl_judge.py`); re-eval logs (`amendments.py`,
`reeval_addendum.py`); convergence log (`convergence.py`); subagent
engagement (`subagent_lifecycle.py`); phase context + semantic-gap
report (`phase_manager.py:1600, 2571, 4159, 4343, 5282`). All stay on
direct-write paths until the five core sites have flipped and one full
release of zero drift confirms the pattern. A "wave 2" cutover document
will be written then (open question 5).

## 4. Lint-flip ordering

`WG_BUS_EMIT_LINT` ships at default `warn` (#737). The flip to
`strict` happens in the release that follows the FIRST cutover PR.

### Release sequence

- **N**: Site 1 cutover PR ships with `WG_BUS_AS_TRUTH_DISPATCH_LOG=off`.
  Lint stays `warn`. No production behavior change.
- **N+1**: Lint default flips `warn` → `strict`. Release notes call
  this out as a breaking change for any out-of-tree consumer that
  writes the four target basenames without a paired emit. Site 1 flag
  flips to `on` if zero-drift in N held. Site 2 cutover PR ships with
  flag `off`.
- **N+2**: Site 2 flag flips. Site 3 cutover PR ships.
- **N+3**: Site 3 flag flips. Site 4 cutover PR ships. Site 1
  direct-write deletion lands.
- **N+4**: Site 4 flag flips. Site 5a cutover PR ships. Site 2 deletion
  lands.
- **N+5**: Site 5a flag flips. Site 5b precursor + cutover PR ships.
- **N+6**: Site 5b flag flips. The `WG_BUS_EMIT_LINT=warn` opt-out
  goes away — env var name stays valid (no breaking-change surface) but
  is treated as an alias for `strict`. Direct disk-write deletions
  continue per the "two releases of zero drift" rule.

### Opt-out

Users opt out by setting `WG_BUS_EMIT_LINT=warn` (existing override) or
`WG_BUS_EMIT_LINT=off` (full bypass). Both are honored from the lint's
inception through release N+5. At N+6 the opt-out is removed — any
non-empty value other than `off` is treated as `strict`. The removal
lands as a one-line change in `_bus_emit_lint_mode()` plus a
release-note entry; not a separate cutover.

### What strict catches that warn does not

Detection logic is identical between `warn` and `strict` — both run
`_check_bus_emit_lint(file_path)`, both query the daemon's `event_log`
for a paired emit in the last `_bus_emit_lint_window_sec()` seconds,
both fail-open on any error. The only difference is **firing
behavior**:

- `warn`: emit a `systemMessage` deprecation notice; allow the write.
- `strict`: deny via `permissionDecision: "deny"` and surface the
  reason.

No detection-quality difference. The flip is purely about whether
silent orphan writes are advisory or blocking.

## 5. Reconciler shape change

Today `scripts/crew/reconcile.py` measures **store-vs-store drift** —
process-plan.json (garden chain) vs `~/.claude/tasks/{session_id}/*.json`
(native tasks). Its drift classes
(`missing_native`/`stale_status`/`orphan_native`/`phase_drift`) all
assume two parallel write stores that can disagree.

Post-cutover the reconciler shifts to **projection-vs-event drift** —
the single source of truth (`event_log` in `projections.db`) vs the
materialized projections. The projections cannot disagree with each
other; they can only be **stale relative to the event log** or
**orphaned** (event-less).

### New output schema (post-cutover)

```jsonc
{
  "header": {
    "captured_at": "<ISO8601 UTC>",
    "command_invoked": "...",
    "event_log_head_seq": 12345,
    "event_log_total_seq": 12350,
    "lag_events": 5,
    "projector_health": "ok" | "lagging" | "unreachable"
  },
  "results": [
    {
      "project_slug": "<slug>",
      "events_for_project": 142,
      "projections_materialized": {
        "process_plan_json": "<path or null>",
        "gate_result_files": ["clarify", "design"],
        "dispatch_log_files": ["clarify", "design"],
        "conditions_manifest_files": ["design"],
        "reviewer_report_files": ["review"],
        "native_tasks_count": 12
      },
      "drift": [
        {
          "type": "projection-stale",
          "projection": "phases/design/gate-result.json",
          "event_seq": 137,
          "projection_last_applied_seq": 130,
          "lag_events": 7
        },
        {
          "type": "event-without-projection",
          "event_seq": 142,
          "event_type": "wicked.consensus.report_created",
          "expected_projection": "phases/review/consensus-report.json"
        },
        {
          "type": "projection-without-event",
          "projection": "phases/build/gate-result.json"
        }
      ],
      "summary": { "total_drift_count": 3,
                   "projection_stale_count": 1,
                   "event_without_projection_count": 1,
                   "projection_without_event_count": 1 }
    }
  ]
}
```

### New drift classes

- **`projection-stale`**: an event has been ingested but its projection
  has not been materialized (projector lagging, crashed, or buggy
  handler). Signal: `event_seq > projection_last_applied_seq`.
- **`event-without-projection`**: event in `event_log` but no matching
  projection on disk. Either (a) handler missing, (b) handler ran and
  silently failed, or (c) target path wrong.
- **`projection-without-event`**: file on disk but no event corresponds.
  Post-cutover analogue of today's `orphan_native` — either GC'd events
  whose projections survived, OR a direct-write that bypassed the bus
  (the lint should have caught this; if it appears, the lint is
  broken or off).

### Drift classes that go away

- **`tasklist-without-garden-chain` / `orphan_native`**: vanishes —
  TaskList is no longer an independent store.
- **`stale_status`**: vanishes — both sides project from the same
  `wicked.gate.decided` event.
- **`phase_drift`**: vanishes for the same reason.
- **`missing_native`**: mostly vanishes — any gap is now
  `event-without-projection`.

The CLI surface (`--all`, `--project`, `--json`) stays the same but the
`--json` output schema bumps a major version. Bump lands in the same
release as the LAST cutover flip (N+5) so one full release runs at the
new shape under flag-default-on before strict mode removes the opt-out
at N+6.

**Implementation contract** (per ADR `docs/v9/adr-reconcile-v2.md`,
decided 2026-05-02 via the pre-Site-3 design jam on issue #750): the
post-cutover reconciler ships as a new module
`scripts/crew/reconcile_v2.py` co-existing with v1 during the cutover
window. v1 is deprecated when Site 5 lands and removed in release N+5.
Site 3's PR ships `reconcile_v2.py` and the detector assertions in
`tests/crew/test_synthetic_drift.py`'s three post-cutover test classes
per the meta-test contract already locked in #750
(`TestPostCutoverContract` — see the ADR for the exact rule).

### Required template patterns for Sites 2-5 projection tables (#753 + #754)

The pre-merge council on PR #751 (Site 1) named two template warts that
MUST be fixed in the projector template before Site 2 clones the pattern.
Both ship in the follow-up PR cited by issues **#753** and **#754** and
become preconditions for Sites 2-5:

1. **FK + ON DELETE CASCADE on every projection table's event-id column.**
   Each cutover-site projection table (`dispatch_log_entries`,
   `consensus_report_entries`, `consensus_evidence_entries`,
   `reviewer_report_entries`, `gate_result_entries`, `conditions_entries`)
   declares `event_id INTEGER PRIMARY KEY REFERENCES event_log(event_id)
   ON DELETE CASCADE`. Without this, retention/cleanup workflows that
   prune `event_log` will leak orphan projection rows. `PRAGMA
   foreign_keys=ON` is set at every connection in `daemon/db.py::connect()`
   — without that PRAGMA the FK is parsed but not enforced.

2. **WARN-once on `_bus` ImportError in projector handlers.** The Site 1
   handler `_dispatch_log_appended` swallowed `_bus` import failures into
   silent `flag_on=False`. The follow-up promotes that to a single
   `logger.warning` (latched via a module-level `_BUS_IMPORT_WARNED`
   flag) so a real misconfiguration (e.g. PYTHONPATH missing `scripts/`)
   surfaces in operator logs without breaking the fail-open contract.
   Sites 2-5 inherit this WARN-once pattern, NOT the silent skip.

Both fixes ship as one PR because they are the same "template wart"
cluster from one council session. The byte-identity contract from
Council Condition C2 is preserved: flag-off behaviour still returns
`applied` with the projection table untouched.

## 6. Scenario coverage

All scenarios live under `scenarios/crew/`. #746's "Scenario covers a
project that goes all-the-way-through with bus-as-truth" acceptance
criterion is the umbrella over the end-to-end one.

### Per-site cutover scenarios (5)

One per write-site, named `bus-cutover-{site}.md`:

- `bus-cutover-dispatch-log.md`
- `bus-cutover-consensus-report.md` (covers report + evidence)
- `bus-cutover-reviewer-report.md`
- `bus-cutover-gate-result.md`
- `bus-cutover-conditions-manifest.md` (covers 5a + 5b)

Each scenario asserts:

1. **Flag-off baseline**: with `WG_BUS_AS_TRUTH_<site>=off`, the
   existing write produces the canonical artifact byte-for-byte
   identical to pre-cutover behavior. Snapshot vs archived golden.
2. **Flag-on cutover**: with `WG_BUS_AS_TRUTH_<site>=on`, the write
   becomes a projection. Same artifact at same path, byte-for-byte
   identical modulo timestamps. Lint reports zero violations.
3. **Rollback drill**: starting from flag-on, simulate `git revert` of
   the cutover PR. Re-run; behavior matches flag-off baseline. The
   revert must not require daemon restart, manual cleanup, or any user
   action.
4. **Daemon-down resilience**: with flag on but daemon process killed,
   the write must still produce the on-disk artifact (fall-back per
   step 2 of the standard sequence). Lint stays silent in `warn`,
   fires in `strict` once the daemon recovers.

### End-to-end "bus-as-truth project" scenario

`scenarios/crew/bus-as-truth-end-to-end.md`:

- Bootstrap a new crew project at complexity 4 (forces multi-phase,
  challenge gate, semantic reviewer).
- Run clarify → design → build → test → review with all five cutover
  flags ON.
- Assert every write to the four target basenames was preceded by a
  paired bus emit (no lint warnings in `strict`).
- After completion, snapshot `event_log` and delete every projection
  file on disk (`process-plan.json`, `phases/{phase}/*.json`,
  `phases/{phase}/*.md`).
- Re-run `scripts/crew/resume_projector.py --project <slug>`. Assert
  projection files regenerated **byte-for-byte identical** (modulo
  deterministic timestamps) to the pre-deletion snapshot.
- This is the load-bearing assertion #732 called for: resume snapshot
  regenerable purely from event log with zero filesystem reads against
  project state.

### Drift-detection scenario

`scenarios/crew/bus-cutover-drift-detection.md`:

- Bootstrap a project, run through review.
- Induce each new drift class:
  - **stale**: pause daemon mid-projection; emit an event; restart
    daemon WITHOUT replaying. Reconciler MUST flag stale.
  - **event-without-projection**: emit an event whose handler raises;
    verify reconciler flags it.
  - **projection-without-event**: bypass lint with
    `WG_BUS_EMIT_LINT=off`, write a file directly, leave no event;
    reconciler MUST flag it.
- Assert reconciler `--json` matches the post-cutover spec from
  section 5.

## 7. What this PR is NOT doing

Make explicit:

- **No code changes** to any production write path.
  `dispatch_log.py`, `consensus_gate.py`, `phase_manager.py`,
  `conditions_manifest.py`, `post_tool.py`, `daemon/projector.py`,
  `daemon/db.py`, `scripts/crew/reconcile.py` are all untouched.
- **No new emits** added. PR #738 already added the emits this plan
  builds on; no new ones land here.
- **No reconciler modifications.** Section 5 specifies the post-cutover
  shape but the script change lands in a later PR.
- **No production behavior change.** The baseline JSON in `docs/audits/`
  is a snapshot, not an enforcement. The doc itself is inert markdown.
- **No feature flags wired up.** The flag NAMES are documented in
  section 3 but no code reads them yet.

This is the design pass that informs the implementation PRs. Each
implementation PR will reference this document and may amend a section
in-place if the implementation surfaces a new constraint.

## 8. Open questions for the maintainer

These need a maintainer answer before implementation begins. Each
question lists the **default this doc assumed** in case the maintainer
prefers to ratify silently.

1. **Feature-flag naming convention.** Default:
   `WG_BUS_AS_TRUTH_<SITE>=on|off` per-site. Alternative: a single
   `WG_BUS_AS_TRUTH=site1,site2,...` comma-list. Per-flag is more
   verbose but maps 1:1 to the per-site revert/rollback story.
2. **Cutover release cadence.** Default: one cutover PR per release
   (six releases for five sites — site 5 is two PRs). Alternative:
   bundle 1+2 (low risk, shared substrate), bundle 4+5a (both
   approve_phase). Bundling halves the release count but couples the
   reverts.
3. **Zero-drift threshold for flipping defaults.** Default: *exactly
   zero* drift entries of `projection-stale` or
   `event-without-projection` for the cutover site over one full
   release cycle. Alternative: <0.1% of events. Exactly-zero is
   stricter but simpler to assert in CI; tolerance bands invite debate
   over what counts as a release cycle.
4. **Reconciler schema bump timing.** Default: schema bump lands in
   release N+5 alongside the last cutover flip. Alternative: bump in
   N+1 alongside the lint flip; keep both shapes parsable for two
   release cycles. The latter is safer for downstream reconciler
   consumers but doubles the surface area for two releases.
5. **Wave-2 cutover doc.** After the five core sites flip, the
   deferred sites need a wave-2 staging plan. Inherit this doc's
   per-site structure, OR collapse into a single "deferred-sites"
   PR with one shared flag (`WG_BUS_AS_TRUTH_WAVE_2=on|off`)?
   Default: new wave-2 doc with same per-site structure.
6. **Daemon-down policy under strict lint.** Today the lint
   fail-opens on any error including "daemon DB not found"
   (`_resolve_daemon_db_path` returning None). Once strict ships,
   does strict STILL fail-open on daemon-down, or deny the write?
   Default: fail-open stays — the lint is a silent-orphan-detector,
   not a daemon-up enforcer; daemon-up enforcement is a separate
   health check. Worth a maintainer signoff because strict behavior
   in this corner case is load-bearing for the substrate.
7. **Sample-size escalation path.** Section 2 noted the sample floor
   (>=10 projects OR >=50 phases) is not reachable from this single
   repo. Default recommendation: synthetic-drift suite as primary
   (pins coverage); cross-machine aggregation as the validation layer.

---

**Status**: design-only. Cross-references: issue #746, PR #735 (audit),
PR #736/#737/#738 (substrate), council condition C2 (memory
`bus-as-truth-event-sourced-crew-state`), baseline JSON
`docs/audits/bus-cutover-drift-baseline-2026-05-02.json`.
