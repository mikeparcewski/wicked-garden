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
- **`project_slug`** OR **`project`** — short snake_case identifier (one is required).
- **`project_dir`** — absolute path; agent writes the draft plan here. If absent,
  the shim resolves it via `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-crew` then appends `/projects/{slug}`.
- **`bookend`** (`phase-start` | `phase-end`) and **`phase`** — required for `re-evaluate` from `phase-executor`.
- **`current_chain`** — required for `re-evaluate`: tasks created so far, status, evidence.
- **`auto_proceed`** — bool; set by yolo mode; suppresses user confirmation.
- **`output`** — `json` | unset. `json` returns the JSON content directly to the caller
  without creating tasks (used by `crew:start` Step 5 + `measure_facilitator.py`).

## Outputs (file-handoff contract)

The dispatched agent writes its plan to `${project_dir}/process-plan.draft.json`
matching `skills/propose-process/refs/output-schema.md`. The shim reads it back
after Task() returns and forwards the JSON to the caller. The caller is responsible
for any subsequent persistence (e.g. `commands/crew/start.md` Step 7 writes
`process-plan.json` + `process-plan.md` from this JSON).

## Delegation

When invoked:

0. If `project_dir` is unset, resolve it from `project_slug`/`project` using
   `scripts/resolve_path.py wicked-crew` + `/projects/{slug}`. `mkdir -p` it.

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

4. **Otherwise**: render `process-plan.md` from the JSON, persist
   `${project_dir}/process-plan.json`, then emit the task chain.

## Failure modes

Draft file missing or invalid JSON → STOP, surface the first 200 chars of agent
output (or the JSON parse error + path). No legacy fallback in v6. Refer the user
to `/wicked-garden:report-issue`.

## See also

[`agents/crew/process-facilitator.md`](../../agents/crew/process-facilitator.md) (full rubric) — [`refs/output-schema.md`](refs/output-schema.md) (JSON contract) — `refs/` (factor-definitions, specialist-selection, phase-catalog, evidence-framing, ambiguity, plan-template, interaction-mode, gate-policy, re-eval-addendum-schema, spec-quality-rubric).
