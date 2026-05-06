---
description: Start a new wicked-crew project with outcome clarification
argument-hint: "<project description>"
phase_relevance: ["bootstrap"]
archetype_relevance: ["*"]
---

# /wicked-garden:crew:start

Start a new wicked-crew project. Phase 2A of v10 (#813 successor): the
slug algorithm, flag parsing, conflict check, project shell creation,
and crew-brief composition are all encapsulated in
`scripts/crew/write_brief.py`. This command body is the slim Pattern B
shape — it writes the brief, dispatches the facilitator, and surfaces
the result. Full ≤28-line target lands in Phase 2B once the facilitator
agent absorbs the post-rubric steps.

## 1. Empty-args guard

If `$ARGUMENTS` is empty, ask the user for a project description and STOP.
Do not proceed with an empty description.

## 2. Write the brief (slug, flags, project shell, crew-brief.md)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
   "${CLAUDE_PLUGIN_ROOT}/scripts/crew/write_brief.py" \
   --command crew:start \
   --description "$ARGUMENTS"
```

The script generates the theme-aware slug, parses v6 flags
(`--yolo` / `--just-finish`, `--rigor={minimal|standard|full}`, `--force`,
`--consensus-threshold=N`), checks for an existing active project, creates
the project shell, and writes `{project_dir}/crew-brief.md`.

**Exit codes**:
- `0` → parse the JSON on stdout. The `action` key tells you what happened:
  - `action=create` → new shell + brief written. Fields: `{slug, theme_prefix, project_dir, brief_path, flags}`. Continue to step 3.
  - `action=resume` → user chose Resume; carry on with the existing project. Fields: `{slug, phase, project_dir}`. Skip steps 3–8 — the existing project is unchanged.
  - `action=cancel` → user aborted. STOP cleanly. No further work this command.
- `2` → conflict: an active project exists and `--on-conflict` was not supplied. Parse the JSON on stderr: `{conflict, existing_slug, existing_phase}`. Surface the conflict to the user as a numbered plain-text list of four choices (Resume / Rename / Cancel / Switch). For **Switch**, **Resume**, **Cancel**, re-invoke `write_brief.py` with the matching `--on-conflict=...` value and parse the next exit-0 response. For **Rename**, ask the user for a new project description and re-invoke `write_brief.py` from step 2 (no `--on-conflict` flag).
- `1` → validation/IO error (or `--on-conflict=rename` was passed by mistake — write_brief expects the user to re-invoke with a fresh description, not to handle rename in-script). Surface the stderr message and STOP.

## 3. Invoke the facilitator (rubric scoring + plan emission)

Read the brief, then dispatch the facilitator skill with the parsed inputs:

```
Skill(
  skill="wicked-garden:propose-process",
  args={
    "description": "<description from brief>",
    "mode": "propose",
    "project_slug": "<slug from step 2>",
    "output": "json"
  }
)
```

The skill returns a JSON plan matching `skills/propose-process/refs/output-schema.md`
(`project_slug`, `summary`, `factors`, `specialists`, `phases`, `rigor_tier`,
`complexity`, `open_questions`, `tasks[]`).

**Failure modes**: if the skill is unavailable, returns non-JSON, or omits
required fields, STOP and surface the error with the first 200 chars of output.
There is no legacy fallback — the rubric IS the path. Brief and project shell
remain on disk; the user can refine and re-invoke.

## 4. Persist the plan JSON to disk

The validator and downstream consumers read from disk. Write the raw plan
JSON to `${project_dir}/process-plan.json` BEFORE running the validator —
this avoids the file-not-found failure mode where validation tries to
read a path that hasn't been written yet.

(The human-readable `process-plan.md` rendering happens in step 6 after
the open-questions gate and the validator both pass.)

## 5. Validate the plan

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
   "${CLAUDE_PLUGIN_ROOT}/scripts/crew/validate_plan.py" \
   "${project_dir}/process-plan.json"
```

Note: per PR #812, `risk_level/reading` drift is now an advisory warning,
not a fatal violation — plans with intuitive direction parse cleanly. If
the validator exits non-zero, copy the JSON to
`${project_dir}/process-plan.draft.json`, surface stderr to the user, and STOP.

## 5.5. Open Questions gate

If `open_questions` is non-empty AND `rigor_tier == "full"` AND `--force`
was NOT in the parsed flags: STOP and surface questions as a numbered
plain-text list. Persist the draft to `${project_dir}/process-plan.draft.md`.
For `standard` / `minimal` rigor, questions are surfaced but do NOT block —
they're appended to `process-plan.md` for the clarify phase to answer.

## 6. Render `process-plan.md` + emit the task chain

Render the plan JSON into the markdown template at
`skills/propose-process/refs/plan-template.md` and write to
`${project_dir}/process-plan.md`. The raw JSON was already persisted in
step 4 for the validator.

For each task in `plan.tasks[]`, issue one `TaskCreate` call carrying the
task's metadata envelope (`chain_id`, `event_type`, `source_agent="facilitator"`,
`phase`, `test_required`, `test_types`, `evidence_required`, `rigor_tier`).
Use parallel `TaskCreate` calls when tasks within a phase have no
inter-dependencies; `blockedBy` captures the DAG.

After emission, verify chain integrity:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
   "${CLAUDE_PLUGIN_ROOT}/scripts/crew/verify_chain_emission.py" \
   "${project_dir}/process-plan.json" "{slug}.root"
```

Exit 1 → count mismatch; surface the delta and offer to re-emit missing tasks
before advancing.

## 7. Persist plan metadata + store decision in wicked-brain

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
   "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {slug} update \
   --data '{"phase_plan": [...], "phase_plan_mode": "facilitator", "complexity_score": <N>, "rigor_tier": "<tier>", "facilitator_version": "propose-process-v1", "initiative": "{slug}"}' \
   --json
```

Store the planning decision via `wicked-brain:memory` (type `decision`,
importance 6) so future runs surface it as a prior. On brain failure, retry
once; on second failure, write `${project_dir}/.pending-brain-store.json`
sentinel and surface a WARN — do NOT fail silently.

## 8. Report + optional --yolo handoff

Render a short markdown summary: rigor + complexity, factors (per-factor
`risk_level`, NOT the inverted `reading`), specialists with one-line whys,
phases with one-line whys, task count, next-step prompt.

If the parsed flags include `yolo: true`, skip the next-step prompt and
immediately invoke `Skill('wicked-garden:crew:just-finish')`. Otherwise
exit and let the user drive.
