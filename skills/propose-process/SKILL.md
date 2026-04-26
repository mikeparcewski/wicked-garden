---
name: propose-process
description: |
  Lead-facilitator rubric. Reads a project description + priors from wicked-brain + the
  specialist roster, then proposes a full task chain (TaskCreate calls with blockedBy deps
  and metadata) plus a `process-plan.md` artifact. Replaces the v5 rule engine
  (smart_decisioning.py + phases.json + SIGNAL_TO_SPECIALISTS) with LLM reasoning over a
  small number of well-defined factors.

  Use when: starting a new crew project, re-planning after a gate finding, emitting the
  initial task chain for `/wicked-garden:crew:start`, or invoked on `TaskCompleted` to
  prune / augment / re-tier the remaining chain. Also used by
  `/wicked-garden:crew:just-finish` (yolo mode) to drive autonomous completion.
---

# Propose Process (Delegation Shim)

Thin shim. Full rubric lives in [`agents/crew/process-facilitator.md`](../../agents/crew/process-facilitator.md) (extracted in #652 item 3 so callers no longer pay the ~200-line rubric context cost on every invocation).

## Inputs

- **`description`** — project description, issue text, or the task that just completed.
- **`priors`** (optional) — `wicked-brain:search` output on related projects/gotchas.
- **`constraints`** (optional) — hard constraints (deadline, stack, compliance envelope).
- **`mode`** — `propose` | `re-evaluate` | `yolo`; default `propose`.
- **`project_slug`** OR **`project`** — short snake_case identifier (required for
  real project calls; omit only on `output=json` measurement / no-project calls).
- **`project_dir`** — absolute path; agent writes the draft plan here. If absent,
  the shim resolves it via `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-crew` then appends `/projects/{slug}`. On `output=json` with no project context, an ephemeral tmp dir is used (see Step 0).
- **`bookend`** (`phase-start` | `phase-end`) and **`phase`** — required for `re-evaluate` from `phase-executor`.
- **`current_chain`** — required for `re-evaluate`: tasks created so far, status, evidence.
- **`auto_proceed`** — bool; set by yolo mode; suppresses user confirmation.
- **`output`** — `json` | unset. `json` returns the JSON content directly to the caller
  without creating tasks (used by `crew:start` Step 5 + `measure_facilitator.py`).

## Outputs (file-handoff contract)

The dispatched agent writes its plan to `${project_dir}/process-plan.draft.json`
matching `skills/propose-process/refs/output-schema.md`. The shim reads it back
after Task() returns and forwards the JSON to the caller.

Two call shapes are supported:

- **Real project call** (`mode=propose|re-evaluate`, `project_slug` or `project`
  provided): `${project_dir}` resolves under
  `~/.something-wicked/wicked-garden/local/wicked-crew/projects/{slug}/`. The
  draft persists at `${project_dir}/process-plan.draft.json`. The caller
  (`commands/crew/start.md` Step 7, etc.) is responsible for any subsequent
  persistence (`process-plan.json` + `process-plan.md`) and for cleaning up
  the draft if desired.
- **Measurement / no-project call** (`output=json` AND none of `project_dir`,
  `project_slug`, `project` provided — used by `scripts/ci/measure_facilitator.py`
  capture flows and ad-hoc rubric probes): the shim allocates an ephemeral
  handoff dir under `${TMPDIR:-/tmp}/wicked-garden-measure-{random_id}/`,
  writes the draft there, reads it back, returns the JSON content, and removes
  the directory before returning. Nothing persists past the call.

## Delegation

When invoked:

0. **Resolve `project_dir`** (in order):
   - If `project_dir` is set, use it as-is and `mkdir -p` it.
   - Else if `project_slug` or `project` is set, resolve via
     `scripts/resolve_path.py wicked-crew` + `/projects/{slug}` and `mkdir -p` it.
   - Else if `output=json` AND no project context was provided (measurement /
     no-project call), allocate an ephemeral dir
     `${TMPDIR:-/tmp}/wicked-garden-measure-{random_id}/`, `mkdir -p` it, and
     remember to remove it after Step 3 returns.
   - Otherwise STOP and surface "missing project_dir/project_slug/project (and
     output != json)" — refer the user to `/wicked-garden:report-issue`.

1. Dispatch the facilitator agent:

```
Task(
  subagent_type="wicked-garden:crew:process-facilitator",
  prompt="""
    Run the propose-process rubric.
    Inputs: description={description}, mode={mode}, project_slug={project_slug},
            output={output}, project_dir={project_dir}
            (forward priors, constraints, current_chain, bookend, phase,
             auto_proceed when set)
    Write the resulting JSON to ${project_dir}/process-plan.draft.json before
    returning. Do NOT issue TaskCreate calls — the caller emits the chain.
  """
)
```

2. After the agent returns, read `${project_dir}/process-plan.draft.json` from disk.

3. **If `output=json`**: return the JSON content directly (do NOT create tasks).
   This is the path used by `crew:start` Step 5, all `re-evaluate` callers
   (`crew:execute`, `crew:just-finish`, `phase-executor` ×2), and `measure_facilitator.py`.
   If Step 0 allocated an ephemeral `${TMPDIR}/wicked-garden-measure-{random_id}/`
   (no-project call), `rm -rf` that directory after the JSON has been read.

4. **Otherwise**: render `process-plan.md` from the JSON, persist
   `${project_dir}/process-plan.json`, then emit the task chain.

## Failure modes

Draft file missing or invalid JSON → STOP, surface the first 200 chars of agent
output (or the JSON parse error + path). No legacy fallback in v6. Refer the user
to `/wicked-garden:report-issue`.

## See also

[`agents/crew/process-facilitator.md`](../../agents/crew/process-facilitator.md) (full rubric) — [`refs/output-schema.md`](refs/output-schema.md) (JSON contract) — `refs/` (factor-definitions, specialist-selection, phase-catalog, evidence-framing, ambiguity, plan-template, interaction-mode, gate-policy, re-eval-addendum-schema, spec-quality-rubric).
