---
name: propose-process
description: |
  Delegation shim for the lead-facilitator rubric. Dispatches the
  `wicked-garden:crew:process-facilitator` agent (which holds the rubric extracted
  in #652 item 3), reads back the JSON plan the agent writes to
  `${project_dir}/process-plan.draft.json`, and either returns it directly
  (`output=json`) or renders `process-plan.md` + emits the `TaskCreate` chain. Does
  NOT score factors or pick specialists itself — that all happens inside the
  dispatched agent.

  Use when: starting a new crew project, re-planning after a gate finding, emitting the
  initial task chain for `/wicked-garden:crew:start`, or invoked on `TaskCompleted` to
  prune / augment / re-tier the remaining chain. Also used by
  `/wicked-garden:crew:just-finish` (yolo mode) to drive autonomous completion.
phase_relevance: ["bootstrap", "clarify"]
archetype_relevance: ["*"]
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
  the shim resolves it via the `resolve_path.py` subpath form:
  `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-crew projects {project_slug}`.
  On `output=json` with no project context, an ephemeral tmp dir is used (see Step 0).
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
  `~/.something-wicked/wicked-garden/projects/{session-slug}/wicked-crew/projects/{project_slug}/`
  (the `{session-slug}` segment is the per-cwd slug from `_paths._get_project_slug()`).
  The draft persists at `${project_dir}/process-plan.draft.json`. The caller
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
     `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-crew projects {project_slug}`
     (the `resolve_path.py` subpath form auto-creates intermediate dirs).
   - Else if `output=json` AND no project context was provided (measurement /
     no-project call), allocate an ephemeral dir
     `${TMPDIR:-/tmp}/wicked-garden-measure-{random_id}/`, `mkdir -p` it, and
     remember to remove it after Step 3 returns.
   - Otherwise STOP and surface "missing project_dir/project_slug/project (and
     output != json)" — refer the user to `/wicked-garden:report-issue`.

1. Dispatch the facilitator agent. Forward EVERY documented input as its own
   labeled field — no parenthetical "when set" hints, no bundled lists. Substitute
   each `{token}` with the actual caller-provided value (e.g. `mode=propose`,
   `project_slug=auth_rewrite`). For optional inputs the caller did not provide,
   substitute the literal string `none` so the agent sees an explicit absence:

```
Task(
  subagent_type="wicked-garden:crew:process-facilitator",
  prompt="""
    Run the propose-process rubric. Documented inputs (one field per line):

    description: {description}
    priors: {priors}
    constraints: {constraints}
    mode: {mode}
    current_chain: {current_chain}
    auto_proceed: {auto_proceed}
    project_dir: {project_dir}
    project_slug: {project_slug}
    bookend: {bookend}
    phase: {phase}

    For any field whose value is `none`, treat it as absent (use the input's
    documented default).

    Write the resulting JSON to {project_dir}/process-plan.draft.json before
    returning. Do NOT issue TaskCreate calls — the caller emits the chain.
  """
)
```

   `output` is intentionally NOT forwarded — the agent always writes the draft
   file regardless, and the shim (Steps 3 / 4 below) decides whether to render
   `process-plan.md` based on the caller's `output` value.

   See [`refs/dispatch-example.md`](refs/dispatch-example.md) for a concrete example with documented inputs filled in for the `crew:start` Step 5 call.

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
