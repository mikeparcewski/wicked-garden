# Wave-2 bus-cutover planning (#746 follow-on)

> **Scope**: design pass for the deferred sites listed in
> `docs/v9/bus-cutover-staging-plan.md` §3 lines 368-379. Sites 1-5
> (dispatch-log, consensus-report+evidence, reviewer-report, gate-result,
> conditions-manifest) are all default-ON in main; this document plans the
> next batch. **No code changes here** — this is the inert design brief
> that informs wave-2 implementation PRs, the same shape the wave-1 plan
> took before #751-#785.

## 1. Executive summary

Wave 1 cut over the **gate-critical** artifacts — the things review
panels read, that block phase advancement, and that the security floor
(schema + sanitizer + orphan check + audit) inspects on ingest. Wave 1 is
done: all five sites flipped to default-ON across PRs #751, #758, #776,
#782+#784, and #785. The pattern that worked across all five:

- Bus event becomes source of truth.
- Projector handler in `daemon/projector.py` materialises the file from
  the event payload — same atomic write order, same content modulo
  deterministic timestamps.
- Drift detector in `scripts/crew/reconcile_v2.py` watches event-vs-file
  consistency via `_PROJECTION_RESOLVERS` (payload-aware function-per-event-type).
- Per-file flag in `PROJECTION_FILE_FLAGS`, default-OFF for one release,
  flipped default-ON when zero drift confirms the projector.
- Site 5 introduced the **payload-aware resolver** shape so
  `wicked.gate.decided` can ALWAYS produce `gate-result.json` but
  CONDITIONALLY produce `conditions-manifest.json`. Wave 2 inherits this
  shape — every new site that has variable production wires a function,
  not a frozenset.

**What wave 2 covers**: write sites that were deferred because they are
either (a) lower blast-radius than the gate path, (b) one-shot migration
or maintenance utilities, or (c) hook-resident writers whose lifecycle
is decoupled from `phase_manager`. Nine deferred items, grouped into
three tranches.

**Why wave 2 is wave 2 not wave 1**: wave 1 was a "five-site sprint"
because every wave-1 site fed the gate-policy enforcement surface. A
botched cutover on `gate-result.json` blocks every project. The wave-2
sites do not have that property — most are advisory, audit-only, or
already-migrated formats. The cost of getting them wrong is bounded to
their own surface; the cost of NOT cutting them over is a permanent
"two-store" footprint that defeats the bus-as-truth premise (#732).

**Soak inheritance**: wave 1 soaked one full release per site between
flag-off ship and default-on flip. Wave 2 inherits that cadence except
where two sites can demonstrably share a flag (see §3 tranches).

**Direct-write deletion timeline (Sites 1-5)**: §6 — the staging plan's
"two releases of zero drift" rule starts the clock at default-ON, not at
ship. Earliest deletion windows by site are tabulated there.

---

## 2. Per-site analysis

Each subsection follows the same shape as the wave-1 staging plan
sections. **Criticality** uses the wave-1 vocabulary: `low` (advisory or
already-cleanup-tolerant), `medium` (load-bearing for some workflow but
not blocking), `high` (blocks phase advancement or is read by gate-policy).

> **Verification note**: every "current write path" line below was
> verified by `grep` against the file at the line shown. The
> `memory/staging-plan-write-site-count-grep-before-trusting.md` lesson
> from this session: never trust a line-number claim without re-verifying
> against the file.

### Site W1: `solo_mode.py` — inline HITL gate evidence

- **File path**: `scripts/crew/solo_mode.py`
- **Writes** (verified at lines 328, 388, 436):
  1. `phases/{phase}/conditions-manifest.json` (line 328) — atomic write
     when the user's inline verdict is CONDITIONAL.
  2. `phases/{phase}/inline-review-context.md` (line 388) — markdown
     evidence record of the inline review (timestamp, raw response,
     gate-result ref).
  3. `phases/{phase}/gate-result.json` (line 436) — atomic write of the
     human-inline verdict with `reviewer="human-inline"` and
     `dispatch_mode="human-inline"`.
- **Write triggers**: `dispatch_human_inline()` is invoked from the
  facilitator's gate dispatch when `solo_mode` is resolved on for the
  project (precedence: `--hitl=inline` flag > project state extras >
  `~/.wicked-brain/config/crew-defaults.json`). Triggered once per gate
  per phase that the human reviews inline.
- **Existing emit?**: ❌ none. The whole module is silent today.
  `gate-result.json` and `conditions-manifest.json` written here BYPASS
  the wave-1 cutover events because `phase_manager.approve_phase` is not
  the writer — `solo_mode._write_gate_result` is.
- **Criticality**: **HIGH**. This site writes the SAME basenames as
  Sites 4 (`gate-result.json`) and 5 (`conditions-manifest.json`) but
  through a different code path. Once Sites 4/5 are default-ON, the
  presence of solo-mode-written files at the same paths WITHOUT
  corresponding `wicked.gate.decided` events is exactly the
  `projection-without-event` drift class. **This is the one wave-2 site
  that is required-not-optional for projection-vs-event consistency**.
- **New emit needed**: YES — emit `wicked.gate.decided` with
  `dispatch_mode="human-inline"` BEFORE the disk writes at lines 328 +
  436. The existing `_PROJECTION_RESOLVERS["wicked.gate.decided"]`
  (`_resolve_gate_decided`) already covers both target files; no new
  resolver. The `inline-review-context.md` is a sidecar audit file that
  is bus-tracked as a *secondary* projection — needs ONE new emit
  (`wicked.gate.inline_review_recorded`) plus a single-file resolver
  added to `_PROJECTION_RESOLVERS`.
- **Conditional shape**: YES. `conditions-manifest.json` is written only
  when verdict is CONDITIONAL (line 326-339 wrap the write in a verdict
  branch). The existing `_resolve_gate_decided` resolver already handles
  this conditional production correctly — the verdict branch reads
  `data["verdict"]` from the event payload.
- **Recommended cutover shape**: **single PR, two flags**.
  `WG_BUS_AS_TRUTH_SOLO_MODE_GATE` (covers `gate-result.json` +
  `conditions-manifest.json` via shared `wicked.gate.decided` event) and
  `WG_BUS_AS_TRUTH_SOLO_MODE_CONTEXT` (covers `inline-review-context.md`
  via the new `wicked.gate.inline_review_recorded` event). Two flags
  because they have independent rollback targets — a botched context
  emit shouldn't block the gate emit.

### Site W2: `adopt_legacy.py` — beta.3 → v6.0 migration tool

- **File path**: `scripts/crew/adopt_legacy.py`
- **Writes** (verified at lines 110, 171, 179, 209):
  1. `project.json` (line 110) — sets `phase_plan_mode = "facilitator"`.
     One-shot transformation per legacy project.
  2. `phases/{phase}/reeval-log.jsonl` (line 171, append) — migrates
     markdown re-eval addendums into JSONL. Bulk append per legacy doc.
  3. Strips markdown addendum blocks from `process-plan.md` (line 179)
     — destructive in-place rewrite.
  4. Replaces legacy gate-bypass references in any matched file (line
     209) — destructive in-place rewrite.
- **Write triggers**: `python scripts/crew/adopt_legacy.py <project_dir>
  --apply` invoked by an operator on a legacy project. Idempotent by
  design (markers stop matching after first run).
- **Existing emit?**: ❌ none.
- **Criticality**: **LOW**. One-shot operator-invoked migration; not in
  any hot path. Drift on this site means a re-run produces a different
  result, which is already true today (the markers stop matching).
- **New emit needed**: NO. **Recommend EXEMPT from cutover**. This is a
  migration utility that runs ONCE per legacy project; the bus-as-truth
  contract applies to runtime state, not migration tooling. Add a
  README note to the file marking it as exempt; the bus-emit lint at
  PreToolUse should already not fire because none of the four target
  basenames (`gate-result.json`, `dispatch-log.jsonl`,
  `conditions-manifest.json`, `reviewer-report.md`) are written here.
  The reeval-log.jsonl write IS one of the wave-2 targets but the
  migration intent is to BULK BACKFILL — emitting one bus event per
  migrated record would inflate the event log with synthetic history.
  The cleaner answer: emit ONE `wicked.crew.legacy_adopted` summary
  event per project containing the count of migrated addendums, and
  let the disk writes proceed direct.
- **Conditional shape**: N/A — exempt.
- **Recommended cutover shape**: **exempt + one summary emit PR**.
  The summary emit gives the audit log a marker so a future analyst can
  identify projects that went through the legacy adoption path.

### Site W3: `log_retention.py` — gzip log rotation

- **File path**: `scripts/crew/log_retention.py`
- **Writes** (verified at lines 180, 200):
  1. `<archive_dir>/<basename>.<timestamp>.gz` (line 180) — gzip-compress
     the current log into a timestamped archive.
  2. `<original-log>` truncated in-place (line 200) — open with `"w"`
     mode resets the file to zero bytes.
- **Write triggers**: `rotate_if_needed(path, ...)` called by any
  log-appending site (today: `dispatch_log.py`, `convergence.py`,
  `amendments.py`, `reeval_addendum.py`) when the active log exceeds
  `DEFAULT_MAX_SIZE_BYTES`.
- **Existing emit?**: ❌ none. Rotation is a maintenance side-effect of
  the append, not a first-class event.
- **Criticality**: **LOW**. The rotation does not change the source of
  truth — it just compresses old entries. The reconciler doesn't read
  archives; it reads the active log + the event_log.
- **New emit needed**: OPTIONAL. A `wicked.log.rotated` event would
  give operators a marker for "logs rotated at this point", which is
  useful for forensics ("did the log rotate before or after the bug?").
  Not required for bus-as-truth consistency.
- **Conditional shape**: N/A.
- **Recommended cutover shape**: **exempt OR optional summary emit**.
  Recommend exempt for the cutover proper; landing the optional
  `wicked.log.rotated` emit is a separate one-line PR if operators want
  the marker. Rotation does NOT participate in the projector — the
  archive files are NOT projections of any event.

### Site W4: `migrate_qe_evaluator_name.py` — QE evaluator rename

- **File path**: `scripts/crew/migrate_qe_evaluator_name.py`
- **Writes** (verified at lines 173, 180, 191):
  1. `<original>.bak` (line 173) — backup before in-place rewrite.
  2. `<original>.tmp` (line 180) — atomic-rename staging.
  3. `os.replace(tmp_path, path)` (line 191) — atomic finalize. Targets:
     `phases/*/reeval-log.jsonl` and `phases/*/amendments.jsonl`.
- **Write triggers**: `python scripts/crew/migrate_qe_evaluator_name.py
  --project-dir <path>` invoked by an operator. One-shot per project.
  Renames legacy `qe-evaluator` references to `gate-adjudicator` in
  JSONL records (v6.3 → v7.0 rename per CLAUDE.md).
- **Existing emit?**: ❌ none.
- **Criticality**: **LOW**. Same shape as W2: one-shot operator
  migration. Idempotent.
- **New emit needed**: NO. **Recommend EXEMPT**. Same rationale as W2.
  Optional summary emit `wicked.crew.qe_evaluator_migrated` per project.
- **Conditional shape**: N/A.
- **Recommended cutover shape**: **exempt + one summary emit PR**.

### Site W5: `hitl_judge.py` — HITL pause-decision evidence

- **File path**: `scripts/crew/hitl_judge.py`
- **Writes** (verified at lines 613-616):
  1. `phases/{phase}/{filename}` (line 613) — JSON evidence file with the
     `JudgeDecision` (pause flag, reason, rule_id, signals). Filename is
     caller-supplied (e.g. `hitl-decision.json`,
     `hitl-council-decision.json`, `hitl-challenge-decision.json`).
- **Write triggers**: `write_hitl_decision_evidence(...)` called from
  three integration points (per the module docstring):
  1. B1 clarify halt (`commands/crew/just-finish.md`) — at clarify gate
     when `should_pause_clarify()` decides.
  2. B2 challenge charter (currently TODO per docstring) — at challenge
     gate dispatch.
  3. B3 council synthesis (`commands/jam/council.md` →
     `scripts/jam/consensus.py`) — after consensus synthesis.
- **Existing emit?**: ❌ none for the disk write. The HITL decisions
  themselves are not currently bus events.
- **Criticality**: **MEDIUM**. The evidence files are advisory for
  audit but not read by any gate. However, they are the ONLY persistent
  record of why crew paused (or didn't); losing them silently means a
  later forensic question "why did clarify halt?" goes unanswered.
- **New emit needed**: YES. New event `wicked.hitl.decision_recorded`
  with payload carrying `pause`, `reason`, `rule_id`, `signals`,
  `phase`, `gate_or_charter`. Add a single-file resolver to
  `_PROJECTION_RESOLVERS` (the filename is caller-supplied so the
  resolver must read `payload["filename"]` to compute the projection
  path — this is a NEW resolver shape, payload-aware on FILE NAME, not
  just on conditional production).
- **Conditional shape**: **payload-aware on filename** — same conceptual
  shape as Site 5's `_resolve_gate_decided` but parameterised by the
  filename rather than by verdict. Each call produces exactly one file;
  the resolver picks WHICH file based on `payload["filename"]`. Add a
  small whitelist of allowed filenames in the resolver (the caller-set
  pattern is `hitl-{tag}-decision.json`); reject anything else as a
  projection-target to avoid path-traversal vectors via payload.
- **Recommended cutover shape**: **single PR, single flag**
  `WG_BUS_AS_TRUTH_HITL_DECISION`. Wire the emit ahead of the disk
  write in `write_hitl_decision_evidence`. Three callsites adopt the
  helper; no callsite-side changes needed because they already call
  this helper. **PRECURSOR**: register the new event in `_bus.py`
  `BUS_EVENT_MAP` first.

### Site W6: `amendments.py` — phase amendments JSONL

- **File path**: `scripts/crew/amendments.py`
- **Writes** (verified at line 242):
  1. `phases/{phase}/amendments.jsonl` (line 242, append + fsync) — one
     JSONL record per amendment (`AMD-{slug}-{ts}` ID, `trigger`,
     `scope_version`, `summary`, `patches`, `resolution_refs`).
- **Write triggers**: `amendments.append(phase_dir, ...)` called from
  the propose-process re-evaluation flow when a mid-phase scope
  correction lands. Replaces the old `design-addendum-N.md` per-file
  pattern (#478).
- **Existing emit?**: ❌ none. Amendments are append-only JSONL today
  with no bus mirror.
- **Criticality**: **MEDIUM**. Amendments are read by the propose-process
  facilitator's re-eval flow to know "what scope changes have already
  landed". A drift here means a re-eval doesn't see a prior amendment
  and re-amends in conflict. Not a phase-blocker, but a consistency
  hazard for multi-cycle projects.
- **New emit needed**: YES. New event `wicked.amendment.appended` with
  payload carrying the amendment record + `phase` + `chain_id`. The
  `chain_id` MUST be `{project}.{phase}.{amendment_id}` for
  per-amendment idempotency (the lesson from
  `memory/bus-chain-id-must-include-uniqueness-segment-gotcha.md`).
- **Conditional shape**: NO — always one file (the per-phase
  amendments.jsonl). Use `_resolve_single_file` template.
- **Recommended cutover shape**: **single PR, single flag**
  `WG_BUS_AS_TRUTH_AMENDMENTS`. **PRECURSOR**: register the new event
  in `BUS_EVENT_MAP` and add `_PROJECTION_ALLOW_OVERRIDES` carve-out
  for `raw_payload` (same pattern as Site 1 dispatch-log — the JSONL
  line bytes need to round-trip through the bus).

### Site W7: `reeval_addendum.py` — re-eval addendum JSONL

- **File path**: `scripts/crew/reeval_addendum.py`
- **Writes** (verified at line 212):
  1. `phases/{phase}/reeval-log.jsonl` (per-phase log, append + fsync).
  2. `process-plan.addendum.jsonl` (project-root log, append + fsync) —
     called from the same `append()` so both writes happen per call.
- **Write triggers**: `reeval_addendum.append(project_dir, phase=,
  record=)` called from the propose-process facilitator's re-evaluation
  flow at every phase boundary. Schema pinned by
  `skills/propose-process/refs/re-eval-addendum-schema.md` v1.1.0.
- **Existing emit?**: ❌ none. Both files are JSONL with no bus mirror.
- **Criticality**: **MEDIUM-HIGH**. The re-eval addendum log feeds the
  facilitator's "what's the current scope?" decision at every phase
  start. The propose-process gate has an addendum-freshness check that
  reads from these files. A drift means the facilitator re-evaluates
  against stale context.
- **New emit needed**: YES. New event `wicked.reeval.addendum_appended`
  with payload carrying the record + `phase` + `chain_id`. Because the
  same `append()` writes BOTH targets (per-phase + project-root), the
  resolver must produce TWO paths from one event. Use a custom resolver
  function (not `_resolve_single_file`) that returns both paths.
- **Conditional shape**: NO conditional, but TWO paths per event — the
  resolver returns `[per_phase_path, project_root_path]` unconditionally.
  Same shape as Site 5's `_resolve_gate_decided` returning multiple
  paths, just without the verdict branch.
- **Recommended cutover shape**: **single PR, single flag**
  `WG_BUS_AS_TRUTH_REEVAL_ADDENDUM`. The two writes already happen
  atomically-ish via `_atomic_append` to each file; the projector
  handler must replay BOTH writes in the same order
  (per-phase first, then project-root) for crash-safety parity.
  **PRECURSOR**: register event + `raw_payload` carve-out (same as W6).

### Site W8: `convergence.py` — artifact convergence log

- **File path**: `scripts/crew/convergence.py`
- **Writes** (verified at line 228):
  1. `phases/{phase}/convergence-log.jsonl` (line 228, append) — one
     JSONL record per state transition (Designed → Built → Wired →
     Tested → Integrated → Verified).
- **Write triggers**: `record_transition(project_dir, artifact_id,
  to_state, evidence, ...)` called from implementer/test-designer
  workflows after landing each artifact (per CLAUDE.md "Convergence
  tracking" section).
- **Existing emit?**: ❌ none. JSONL-only.
- **Criticality**: **MEDIUM**. The `convergence-verify` review gate
  reads this log to flip from REJECT to APPROVE. A drift means the gate
  may see a stale "still in Built state" reading and reject when the
  artifact is actually Verified. Not a hard blocker (the gate is a
  review-phase gate, not a phase-advancement gate), but it's the
  primary signal feeding the convergence assessment.
- **New emit needed**: YES. New event
  `wicked.convergence.transition_recorded` carrying the full record
  (`artifact_id`, `from_state`, `to_state`, `phase`, `evidence`,
  `session_id`, `timestamp`) + `chain_id` of
  `{project}.{phase}.{artifact_id}`.
- **Conditional shape**: NO — one file per call. `_resolve_single_file`
  template.
- **Recommended cutover shape**: **single PR, single flag**
  `WG_BUS_AS_TRUTH_CONVERGENCE`. **PRECURSOR**: register event + carve-out.

### Site W9: `subagent_lifecycle.py` (hooks) — specialist engagement ledger

- **File path**: `hooks/scripts/subagent_lifecycle.py`
- **Writes** (verified at lines 135, 280):
  1. `<tempdir>/wicked-garden/traces/{session_id}.jsonl` (line 135,
     append) — session trace JSONL of every subagent start/stop.
     Ephemeral by design.
  2. `phases/{current_phase}/specialist-engagement.json` (line 280,
     atomic via `.tmp` → replace) — JSON ARRAY of engagement entries
     `{domain, agent, completed_at}`. Read-rewrite-write pattern.
- **Write triggers**: SubagentStop hook fires; `_handle_stop()` calls
  `_record_specialist_engagement()` when the subagent type resolves to
  a known specialist domain.
- **Existing emit?**: ❌ none for either write. The subagent_lifecycle
  hook is hook-resident (fires from `hooks/scripts/`) and currently
  does no bus emits.
- **Criticality**:
  - Trace JSONL: **LOW** — ephemeral debug breadcrumb, not read by any
    gate or workflow.
  - Engagement JSON: **MEDIUM** — read by review gates that check "did
    the right specialists actually run?" The file is the only signal
    the auditor has that a specialist was dispatched.
- **New emit needed**: YES for the engagement JSON; NO for the trace.
  New event `wicked.subagent.engaged` with payload `{domain, agent,
  phase, completed_at, project_id}` + `chain_id` of
  `{project}.{phase}`. The trace JSONL stays as a hook-local ephemeral
  side-effect (it lives under `tempdir`, gets purged with normal temp
  cleanup; bringing it onto the bus would inflate event volume with
  debug data).
- **Conditional shape**: TRICKY — the engagement file is a JSON ARRAY,
  not append-only JSONL. The current code does
  read-modify-write (load existing array, append, atomic replace). The
  projector handler must do the same: read the in-DB engagement list
  for this phase, append the new entry, atomic-write the file. Or
  refactor the file to JSONL (one entry per line, append-only) to
  align with the rest of the bus pattern. **STRONG RECOMMENDATION**:
  refactor to JSONL as a precursor PR. Read-modify-write contradicts
  the "events are append-only" premise of bus-as-truth, and the JSON
  array shape was a pre-bus choice.
- **Recommended cutover shape**: **TWO PRs sequenced**:
  - **W9a (precursor)**: refactor `specialist-engagement.json` from
    JSON array to JSONL (`specialist-engagement.jsonl`). Both the hook
    and any reader migrated. No bus involvement.
  - **W9b (cutover)**: standard cutover with flag
    `WG_BUS_AS_TRUTH_SUBAGENT_ENGAGEMENT`. Use `_resolve_single_file`
    after W9a lands.
  - The trace JSONL stays exempt.

### Site W10: `phase_manager.py` — phase context + semantic-gap report

- **File path**: `scripts/crew/phase_manager.py`
- **Writes** (verified at lines indicated; staging plan §3 cited 1600,
  2571, 4159, 4343, 5282 — all confirmed):
  1. **Line 1600**: `phases/{phase}/reviewer-context.md` — auto-generated
     stub written when the path doesn't exist before gate dispatch.
  2. **Line 2571**: `phases/review/semantic-gap-report.json` —
     persisted by the semantic reviewer at review-phase gate (reads
     numbered AC-* / FR-* / REQ-* items, emits gap report).
  3. **Line 4159 (status_file.write_text on line 4168)**: 
     `phases/{phase}/status.md` — frontmatter + body written when a
     phase is marked SKIPPED (audit trail).
  4. **Lines 4343 area (phase_dir / fname write_text on line 4352)**:
     `phases/{phase}/{deliverable}.md` — adopted-from-design-memo
     pointer file, written when a clarify deliverable is satisfied via
     a memo reference.
  5. **Line 5282 area (marker_path.write_text on line 5291)**:
     `phases/.cutover-to-mode-3.json` — one-shot mode-3 cutover marker.
- **Write triggers**: each site has its own caller chain in
  `phase_manager` — too distributed to enumerate; see file. They are
  collectively the "phase scaffolding" writes that produce
  audit/context/marker files outside the gate-result/dispatch-log
  hot path.
- **Existing emit?**:
  - reviewer-context stub: ❌
  - semantic-gap report: ❌
  - status.md (skipped phase): ❌. The phase-skip itself emits
    `wicked.phase.transitioned` but the markdown file is silent.
  - adopted-from-memo pointer: ❌ (related: `reeval_addendum.append` is
    called nearby at line 4360+ which is W7 territory)
  - mode-3 cutover marker: ❌
- **Criticality** (per write):
  - reviewer-context stub: **LOW** — placeholder for the executor to
    overwrite. Drift means the executor sees an empty stub and writes
    over it; harmless.
  - semantic-gap report: **MEDIUM** — read by the semantic review gate
    to compute the alignment verdict. A drift means the gate sees stale
    gap data.
  - status.md (skipped): **LOW** — pure audit artifact, no reader.
  - adopted-from-memo pointer: **LOW** — pure audit artifact.
  - mode-3 cutover marker: **LOW** — one-shot marker for operator
    forensics.
- **New emit needed**:
  - reviewer-context stub: NO (recommend exempt — placeholder behavior).
  - semantic-gap report: YES — new event
    `wicked.review.semantic_gap_recorded` with the report dict.
  - status.md (skipped): NO — already covered by
    `wicked.phase.transitioned`. The MD file becomes a projection of
    that existing event with verdict = SKIPPED. **The
    `_phase_transitioned` projector handler is extended to write the
    MD file** when the transition is to SKIPPED.
  - adopted-from-memo pointer: NO — recommend exempt; the file is an
    operator convenience.
  - mode-3 cutover marker: NO — recommend exempt; one-shot.
- **Conditional shape**:
  - semantic-gap report: NO — one file per emit.
  - status.md (skipped): conditional on transition kind — only on
    SKIPPED transitions does the projector materialise the MD. This is
    a conditional path INSIDE the existing `_phase_transitioned`
    handler (no new event type, just a payload-aware write inside the
    handler).
- **Recommended cutover shape**: **multi-PR**:
  - **W10a**: semantic-gap report cutover with flag
    `WG_BUS_AS_TRUTH_SEMANTIC_GAP`. New event +
    `_resolve_single_file` resolver. Standalone PR.
  - **W10b**: extend `_phase_transitioned` handler to materialise
    `status.md` on SKIPPED transitions. Flag
    `WG_BUS_AS_TRUTH_SKIPPED_PHASE_STATUS`. Reuses existing event;
    only handler change. Add a custom resolver that produces the MD
    path conditionally on `payload["data"]["status"] == "skipped"`.
  - The other three writes (reviewer-context stub, adopted-memo
    pointer, mode-3 marker) stay exempt.

---

## 3. Recommended sequencing

Dependencies and risk inform the order. Wave 1's "lowest-risk first"
heuristic still applies, but wave 2 has more independence — most sites
are decoupled from each other and can land in parallel tranches.

### Tranche A — independent, low-blast-radius (parallel-safe)

These four sites have no inter-dependencies and zero overlap with the
gate-policy hot path. Land in any order, any release; can ship
side-by-side in the same release if review bandwidth allows.

1. **W3** `log_retention.py` — exempt + optional summary emit. Lowest
   risk: rotation is maintenance-only. Can ship as a single one-line
   PR.
2. **W2** `adopt_legacy.py` — exempt + summary emit. One-shot migration;
   no runtime path.
3. **W4** `migrate_qe_evaluator_name.py` — exempt + summary emit. Same
   as W2.
4. **W10** part exempt (reviewer-context stub, adopted-memo pointer,
   mode-3 marker) — exempt + audit doc note. No emits, no flags.

**Cumulative footprint**: three new optional summary emits, four exempt
declarations. Zero new resolvers. Zero default-on flips. Tranche A is
"clean up the surface" work.

### Tranche B — load-bearing JSONL appends (sequential within tranche)

These four sites all introduce new bus events for append-only JSONL
artifacts. They share the `raw_payload` carve-out pattern from Site 1
(dispatch-log) and the single-file resolver template. **Sequence them
one per release** so that any pattern wart (e.g. another "WARN-once on
ImportError" finding from a wave-1-style council) can be fixed in the
template before the next site clones it.

5. **W6** `amendments.py` — `wicked.amendment.appended`. Single file,
   single flag. Smallest blast radius of the four.
6. **W8** `convergence.py` — `wicked.convergence.transition_recorded`.
   Same shape as W6. Can ship one release later.
7. **W7** `reeval_addendum.py` — `wicked.reeval.addendum_appended`.
   Slightly more complex (two paths per event); ship after W6+W8 prove
   the JSONL-append pattern.
8. **W10a** semantic-gap report — `wicked.review.semantic_gap_recorded`.
   Last in the tranche because the semantic-gap report is read by a
   gate (medium criticality); ship after W6/W7/W8 have validated the
   "advisory append" pattern.

**Cumulative footprint**: four new events, four new resolvers, four
new flags, four default-on flips across four releases.

### Tranche C — overlapping or refactor-required (must sequence)

These sites either OVERLAP with wave-1 paths (W1 solo-mode writes
gate-result.json + conditions-manifest.json) or require a precursor
refactor (W9 specialist-engagement JSON → JSONL). They are the highest
risk and must land last so wave 1 + tranche B have battle-tested the
pattern.

9. **W5** `hitl_judge.py` — `wicked.hitl.decision_recorded`. Three
   integration points (B1/B2/B3); land before W1 because it
   establishes the HITL event vocabulary that W1 reuses.
10. **W9a (precursor)** — refactor `specialist-engagement.json` to
    `.jsonl`. No bus involvement. Standalone cleanup PR.
11. **W9b** subagent engagement — `wicked.subagent.engaged`. Cutover
    after W9a soaks one release.
12. **W10b** skipped-phase status.md — extend `_phase_transitioned`
    handler. Reuses existing event; only handler change. Land after
    W10a establishes the semantic-gap precedent.
13. **W1** `solo_mode.py` — **highest-criticality wave-2 site**.
    Reuses existing `wicked.gate.decided` event (no new event for the
    gate write) plus one new event for inline-review-context.md.
    Land LAST in wave 2 so the projector has every other wave-2
    handler in place; a botched solo-mode cutover writes
    `gate-result.json` files at the SAME path as wave-1 Site 4
    without a corresponding event, which would surface as
    `projection-without-event` drift.

**Cumulative footprint**: tranche C lands across 5 releases. Total
wave-2 release count: tranche A (1 release, parallel-safe), tranche B
(4 releases, one site per), tranche C (5 releases, sequential). **Ten
releases for full wave-2 cutover** if no parallel ships in tranche A.
Optimistic: **seven releases** if tranche A bundles into one release
and W6/W8 ship side-by-side.

### Sequencing diagram

```
Release      | Tranche | Sites
-------------+---------+--------------------------------------------
N+7  (open)  | A       | W2, W3, W4, W10-exempts (single PR each)
N+8          | B       | W6 ships flag-off
N+9          | B       | W6 default-on; W8 ships flag-off
N+10         | B       | W8 default-on; W7 ships flag-off
N+11         | B       | W7 default-on; W10a ships flag-off
N+12         | C       | W10a default-on; W5 ships flag-off
N+13         | C       | W5 default-on; W9a (precursor refactor) lands
N+14         | C       | W9b ships flag-off
N+15         | C       | W9b default-on; W10b ships flag-off
N+16         | C       | W10b default-on; W1 ships flag-off
N+17         | C       | W1 default-on
N+18         | clean   | wave-2 deletion window opens (see §6)
```

`N` = release that landed Site 5 (PR #785). `N+1` through `N+6` are the
wave-1 deletion windows per the staging plan §4 sequencing. Wave 2
starts at `N+7` to give wave 1 one full clean release before adding
new cutover surface.

---

## 4. Open questions

These are the things future implementers need to resolve. Each carries
a **default this doc assumed** for silent ratification.

### Q1: Inline-review-context.md — sidecar or separate event?

The W1 plan recommends a NEW event
`wicked.gate.inline_review_recorded` for the markdown context file.
Alternative: bundle the context content into `wicked.gate.decided`
payload as `payload["context_md"]` and have the projector handler
materialise both files from the same event.

- **Default assumed**: separate event. Two reasons: (a) the gate.decided
  event must NOT carry the full review markdown — `_PAYLOAD_DENY_LIST`
  bans `body`/`raw_text`/`content` and the inline review IS prose; the
  carve-out per-event is a structural smell. (b) The two files have
  different reader audiences (gate-result.json is machine-read by the
  policy enforcer; context.md is human-read by auditors); separate
  events keep their lifecycles independent.
- **Why a maintainer might prefer the alternative**: one event = one
  cutover. Bundling means tranche-C W1 is one flag, not two.

### Q2: Migration tools (W2, W4) — exempt or summary-only emit?

Wave 2 recommends exempt + ONE summary emit per project. Alternative:
strict bus-as-truth — emit one event per migrated record. This would
inflate event volume with synthetic history and arguably violate the
"events represent things that happened, not things being backfilled"
principle.

- **Default assumed**: summary emit only.
- **Why a maintainer might prefer per-record**: forensic completeness
  — every legacy addendum becomes traceable in the event log. Cost: a
  legacy project with 200 addendums emits 200 historical events on
  migration day, and they all carry the present timestamp (because
  the original write timestamp is buried in the markdown).

### Q3: Should W9a (engagement JSONL refactor) bundle into W9b?

W9a refactors `specialist-engagement.json` (JSON array) into
`specialist-engagement.jsonl` (line-per-entry). The reason to split: a
botched refactor that reverts cleanly should not also revert the
cutover. The reason to bundle: one PR is one cognitive unit, two PRs
are two test surfaces.

- **Default assumed**: split. Wave-1 lesson — Site 5 was one PR
  bundling structural change + cutover, and the council found the
  payload-aware resolver shape needed an extra round of review. A
  precursor split would have surfaced that earlier.
- **Why a maintainer might prefer bundling**: the JSON-array shape only
  exists today because of the read-modify-write pattern; nothing else
  reads it. If we're going to delete the read path AND the write path
  on cutover, why preserve the file shape?

### Q4: How does the W10b "extend existing handler" pattern interact with `_PROJECTION_HANDLERS_AVAILABLE`?

Wave 1 introduced `_PROJECTION_HANDLERS_AVAILABLE` as a per-event-type
boolean keyed on whether `daemon/projector.py` has the handler. W10b
EXTENDS an existing handler (`_phase_transitioned`) to also write
`status.md` on SKIPPED transitions. The registry says "handler exists"
either way — but it does not capture "handler ALSO produces this file".

- **Default assumed**: register the SKIPPED-status-md production as a
  separate event-derived projection in `_PROJECTION_RESOLVERS` with a
  predicate-style resolver (returns `[]` unless the payload says
  `status == "skipped"`). The `_PROJECTION_HANDLERS_AVAILABLE` entry
  for `wicked.phase.transitioned` already exists (or is added if
  absent); the resolver makes the conditional production explicit.
- **Open**: do we need a "handler-produces-WHICH-files" map, not just a
  "handler-exists" boolean? Likely yes for wave 2, since the resolver
  function shape and the handler-availability shape are no longer
  1:1. Worth a wave-2 design memo before W10b.

### Q5: Do we need a wave-2 sample-floor escalation?

Wave 1's `synthetic_drift.py` (#746 sample-size mitigation) covers the
five wave-1 sites by deliberately inducing each drift class. Wave 2
adds five new event types (W5, W6, W7, W8, W9b — the W10 family
extends existing patterns). Each new resolver needs synthetic-drift
coverage.

- **Default assumed**: extend `synthetic_drift.py` per cutover PR. Each
  wave-2 site PR adds a fixture for its event type and a test class
  in `tests/crew/test_synthetic_drift.py` per the meta-test contract
  from the wave-1 ADR.
- **Open**: do we need a wave-2 acceptance scenario at the
  end-to-end level (analogue of wave-1's
  `bus-as-truth-end-to-end.md`)? Probably yes — a "second wave
  end-to-end" scenario that runs a project with ALL wave-1 + wave-2
  flags ON and asserts byte-identity round-trip. Decide before
  tranche B lands.

### Q6: Naming convention for wave-2 flags

Wave 1 used `WG_BUS_AS_TRUTH_<TOKEN>` per the staging plan §8 Q1
default. Wave 2 introduces 8 new tokens. Any risk of collision? The
existing tokens are `DISPATCH_LOG`, `CONSENSUS_REPORT`,
`CONSENSUS_EVIDENCE`, `REVIEWER_REPORT`, `GATE_RESULT`,
`CONDITIONS_MANIFEST`. Wave-2 proposed:
- `SOLO_MODE_GATE`
- `SOLO_MODE_CONTEXT`
- `HITL_DECISION`
- `AMENDMENTS`
- `REEVAL_ADDENDUM`
- `CONVERGENCE`
- `SUBAGENT_ENGAGEMENT`
- `SEMANTIC_GAP`
- `SKIPPED_PHASE_STATUS`

No collisions. **Default assumed**: keep the per-token convention.
Open: the staging plan §8 Q1 noted a comma-list alternative
(`WG_BUS_AS_TRUTH=a,b,c`). Wave 2 doubles the flag count;
re-evaluating that convention may be worth a one-line discussion at
tranche-A start.

---

## 5. Soak policy

Wave 1's soak rule: one full release between flag-off ship and
default-on flip, gated on **zero drift** (zero `projection-stale` AND
zero `event-without-projection` for the cutover event over the release
cycle). Wave 2 inherits this rule with two adjustments:

### Per-tranche soak

- **Tranche A**: NO SOAK. These are exempt declarations or one-line
  summary emits with no projection. Land and forget.
- **Tranche B**: standard wave-1 soak — one release flag-off, flip to
  default-on the following release iff zero drift held.
- **Tranche C**: **double soak for W1 specifically** — two releases
  flag-off before default-on. Rationale: W1 writes the same basenames
  as Sites 4 + 5; if drift surfaces, the diagnostic is harder because
  the projector receives `wicked.gate.decided` events from BOTH
  `phase_manager.approve_phase` (existing) and `solo_mode.dispatch_human_inline`
  (new) and the resolver doesn't distinguish. Two-release soak gives
  more drift signal.

### Drift threshold

Same as wave 1 (staging plan §8 Q3 default): **exactly zero** for the
cutover event over the soak window. Any drift entry blocks the flip.
The synthetic-drift suite must continue passing in CI throughout the
soak; a regression in synthetic coverage halts the next flip.

### Cross-site interaction soak

Wave 2 sites can interact in non-obvious ways. Specifically:

- **W1 + Sites 4/5**: the projector handler for `wicked.gate.decided`
  is now invoked by TWO emitters. Add a soak assertion that the
  projection table has a `dispatch_mode` column populated (so an
  auditor can tell which emitter produced any given row). If the
  emitter doesn't populate it, the projector defaults to `unknown` —
  a high count of `unknown` is a soak signal that the W1 emit is
  missing the field.
- **W6 + W7**: `amendments.appended` and `reeval.addendum_appended`
  often fire in the same flow (re-eval → amendment + addendum). Soak
  assertion: per-project, per-phase, the count of these events in the
  bus matches the line counts of the JSONL files. Mismatch is drift.

### Daemon-down policy

Wave 2 inherits the wave-1 fail-open contract: hooks and emitters
return success on bus-unreachable; the disk write proceeds. This
preserves the load-bearing constraint that **bus-as-truth does NOT
mean bus-required-for-write**. The projector catches up on event-log
replay when the daemon recovers. Soak signal: the lag
(`event_log_head_seq` vs `projection_last_applied_seq`) MUST drop to
zero within `_LAG_EVENTS_THRESHOLD` (10 events) of daemon recovery.

---

## 6. Direct-write removal timeline

Per the staging plan §4, the rule is "two more releases of zero drift"
at the new default before deleting the direct disk-write branch. Wave 1
default-on flips landed across releases N (Site 1) through N (Site 5),
so the deletion windows compute as:

### Wave-1 deletion windows

| Site | PR landed default-on | Deletion eligible at | Notes |
|------|----------------------|----------------------|-------|
| 1 — `dispatch_log.py` | #751 (release `N`) | release `N+2` | Append-only; deletion is removing the `with open(..., "a")` branch behind `_bus_as_truth_enabled("DISPATCH_LOG")`. |
| 2 — `consensus_gate.py` (report) | #758 (release `N`) | release `N+2` | Atomic-write deletion. |
| 2 — `consensus_gate.py` (evidence) | #758 (release `N`) | release `N+2` | Bundled with report — same deletion PR. |
| 3 — `post_tool.py` (reviewer-report) | #776 (release `N`) | release `N+2` | Hook-resident direct write; deletion preserves the fail-open contract. |
| 4 — `phase_manager.py:3676` (gate-result) | #782+#784 (release `N`) | release `N+2` | Highest-criticality deletion; coordinate with security floor team — confirm projector-side runs the same sanitize/validate before deleting the writer-side. |
| 5a — `conditions_manifest.py` (canonical) | #785 (release `N`) | release `N+2` | Same deletion as Site 4 (both feed `_gate_decided_disk`). |
| 5b — `conditions_manifest.py` (sidecar/cleared) | #785 (release `N`) | release `N+2` | `mark_cleared()` direct write deletion. |

**Earliest wave-1 deletion window**: release `N+2`. Realistic landing:
release `N+3` to give one extra release cycle of buffer for any
late-surface drift.

### Deletion ordering

Match the cutover order — delete in the order the sites flipped:

1. `dispatch_log.py` (lowest blast radius)
2. `consensus_gate.py` (report + evidence as one PR)
3. `post_tool.py` (reviewer-report)
4. `phase_manager.py:3676` (gate-result) — couple with security-floor
   re-baseline (the
   `wicked-garden:platform:gate-benchmark-rebaseline` skill is the
   owner per CLAUDE.md AC-9 §5.4)
5. `conditions_manifest.py` (manifest + sidecar + cleared as one PR)

### Deletion preconditions per site

Before any deletion PR ships, verify:

1. **Two consecutive releases of zero drift** for the cutover event
   (per staging plan §4 step 5).
2. **Synthetic-drift suite** still asserts the projection-without-event
   class fires correctly when a direct write is induced (the suite
   becomes the regression net for the deletion).
3. **Bus-emit lint at `strict`** in the release before deletion (so any
   downstream consumer that still does the direct write gets blocked
   at PreToolUse, not silently drifted).
4. **Reconciler v2** at default-on (it is, post-Site-5).
5. **Operator notice** in the previous release notes — "in release X,
   `<site>` direct-write is removed; if you have downstream tooling
   that writes `<basename>` directly, switch to the bus-emit pattern".

### Wave-2 deletion windows

Wave 2 direct-writes follow the same two-releases-of-zero-drift rule
from the wave-2 default-on flip date. Per the §3 sequencing diagram,
the earliest wave-2 deletion would be:

- **Tranche A**: nothing to delete (exempt).
- **Tranche B** earliest deletion: W6 default-on at N+9 → eligible at
  N+11.
- **Tranche C** earliest deletion: W1 default-on at N+17 → eligible at
  N+19.

**Full wave-2 deletion completion**: realistic estimate **N+20** (one
buffer release after the last tranche-C eligibility).

### When the lint goes away

Per staging plan §4 release N+6, `WG_BUS_EMIT_LINT=warn` opt-out is
removed and the lint becomes effectively always-strict. Wave 2 inherits
this; no lint-policy changes needed for wave 2 sites (the lint targets
the four wave-1 basenames; wave-2 basenames are NOT lint-tracked
because their bus-as-truth contract is ESTABLISHED at cutover, not
retroactively). However, the lint allow-list in
`hooks/scripts/pre_tool.py` should grow to include the wave-2 target
basenames (`amendments.jsonl`, `convergence-log.jsonl`,
`reeval-log.jsonl`, `process-plan.addendum.jsonl`,
`semantic-gap-report.json`, `specialist-engagement.jsonl`,
`hitl-decision.json`, `inline-review-context.md`) at the release each
goes default-on. **Open question**: should the wave-2 lint also start
in `warn` and flip per the same rhythm as wave-1's lint? Default:
yes, mirror wave 1; flip to strict one release after the last wave-2
deletion.

---

## 7. Cross-cutting concerns

### Security floor extension

The wave-1 security floor (CLAUDE.md AC-9 §5.4: schema validator,
content sanitizer, dispatch-log orphan check, append-only audit log)
runs on `gate-result.json` ingestion. Wave 2 introduces five new
projection paths (semantic-gap report, amendments JSONL, convergence
JSONL, reeval addendum JSONL, hitl-decision JSON, subagent engagement
JSONL, inline-review-context MD).

**Recommendation**: the gate-result security floor stays gate-result-specific
because it encodes gate-policy semantics (banned reviewers, score
bands, evidence-byte thresholds). Wave-2 projections get a LIGHTER
floor — schema validation only, no content sanitization beyond the
existing `_PAYLOAD_DENY_LIST` enforcement at emit time. Rationale:
wave-2 artifacts are not read by the gate-policy enforcer; they are
audit/advisory artifacts. Over-applying the gate floor would inflate
the security surface for no enforcement benefit.

**Exception**: `inline-review-context.md` (W1) is human-prose and
should pass through the same content sanitizer as the consensus
reviewer-report.md (Site 3) does today. Inherit Site 3's pattern.

### Observability

Wave 1 added per-event projection-state metrics (event count,
projection lag, drift count by class) to the reconciler v2 output.
Wave 2 should extend the SAME metric surface — no new metric schema,
just new event types added to the existing
`projections_materialized` dict in the reconciler v2 JSON output.

### Documentation

- Update `.claude/CLAUDE.md` "Bulletproof Standards" section with wave-2
  events listed alongside wave-1 (the events mentioned are the bus
  vocabulary of the platform).
- Update `docs/v9/bus-cutover-staging-plan.md` §3's "Sites NOT in scope"
  paragraph to point at THIS document.
- Add a wave-2 ADR (`docs/v9/adr-wave-2-cutover.md`) capturing the
  per-tranche sequencing decision and the W1-vs-Sites-4/5 overlap
  rationale.

### Test coverage

Each wave-2 site PR ships:
1. A unit test for the new event in `_bus.py` (event type registered,
   payload deny-list / allow-overrides correctly applied).
2. A projector handler test in `tests/daemon/test_projector.py`
   verifying byte-identity round-trip (event in → file out matches
   pre-cutover file content).
3. A reconciler v2 test extending `test_synthetic_drift.py` with the
   three drift classes for the new event.
4. An acceptance scenario under `scenarios/crew/bus-cutover-wave-2-*.md`
   following the wave-1 four-assertion shape (flag-off baseline,
   flag-on cutover, rollback drill, daemon-down resilience).

---

## 8. What this PR is NOT doing

Mirror wave-1 staging plan §7 — make explicit:

- **No code changes** to any production write path. Every script
  enumerated in §2 is untouched by THIS document. Wave-2 implementation
  PRs land separately, one per site, each referencing this document.
- **No new emits** added. The new event types (`wicked.amendment.appended`,
  `wicked.convergence.transition_recorded`, etc.) are NAMED here but
  registered in `BUS_EVENT_MAP` only when their cutover PR ships.
- **No reconciler modifications.** §3 specifies what new resolvers go
  into `_PROJECTION_RESOLVERS`; the script change lands per cutover PR.
- **No production behavior change.** This document is inert markdown.
- **No feature flags wired up.** The flag NAMES are documented in §2/§3
  but no code reads them yet.
- **No security-floor extension.** §7 recommends the floor stays
  gate-result-specific; the actual decision is per-PR.

This is the design pass that informs the wave-2 implementation PRs.
Each implementation PR will reference this document and may amend a
section in-place if the implementation surfaces a new constraint
(same rolling-amendment pattern as wave 1).

---

## 9. Design discipline checklist

The following design lessons from this session apply to every wave-2
PR. Reference, do not quote at length.

- **Bundle activation with functionality, default-ON from start** —
  `memory/ship-inert-and-activate-later-is-a-contradiction-bundle-instead.md`.
  Wave 2 sites ship flag-OFF for one soak release, then default-ON
  with a single PR per the wave-1 cadence; the inert-then-activate
  anti-pattern (which would have us land the resolver but not register
  it in the daemon's handler map) is forbidden.
- **Fix structural shape, don't add workaround events** —
  `memory/workaround-vs-fix-stop-shaping-plans-around-bad-design.md`.
  When a wave-2 site has variable production (different files based on
  payload), use a payload-aware resolver function (Site 5 pattern), not
  a static frozenset plus a "well, sometimes we also write X" event.
- **Verify call-site claims with grep** —
  `memory/staging-plan-write-site-count-grep-before-trusting.md`.
  Every line number in this document was verified against the file.
  Wave-2 implementation PRs MUST do the same — cite a line number,
  re-grep before relying on it.
- **`_PROJECTION_RESOLVERS` is the right shape for new sites** —
  `scripts/crew/reconcile_v2.py:126`. Wave 2 sites use the
  `Dict[str, Callable]` payload-aware resolver shape from Site 5; do
  NOT regress to the static `Dict[str, FrozenSet[str]]` pattern that
  was deprecated when Site 5 introduced conditional production.

---

**Status**: design-only. Wave 2 implementation begins when a maintainer
approves the §3 sequencing and the §4 open questions reach defaults
(silent ratification or explicit override). Cross-references: issue
#746, wave-1 staging plan `docs/v9/bus-cutover-staging-plan.md`,
wave-1 deletion timeline §6 above, council condition C2 (memory
`bus-as-truth-event-sourced-crew-state`).
