---
description: Start a new wicked-crew project with outcome clarification
argument-hint: "<project description>"
---

# /wicked-garden:crew:start

Create a new project and begin work. The **facilitator rubric** is the path —
no router, no legacy engine. The v5 rule engine (`smart_decisioning.py`) and
the `WG_FACILITATOR` env var were removed in v6 (#428).

## Instructions

### 1. Parse Arguments

Extract the project description from `$ARGUMENTS`. If empty, ask the user for one and
STOP. Do not proceed with an empty description.

**v6 flags (orthogonal axes):**

| Flag | Axis | Effect |
|---|---|---|
| `--yolo` / `--just-finish` | interaction mode | Run to completion without user confirmations; auto-approve APPROVE gates; escalate only on REJECT or intent-changing CONDITIONAL. Does **not** change phase plan, rigor, or specialists — the facilitator already chose those. |
| `--rigor={minimal\|standard\|full}` | override | Override the facilitator's rigor tier (rarely needed). Sanity check: facilitator's selection is usually right. |
| `--force` | override | Suppress complexity-based stop prompts (e.g. low-complexity → single-task recommendation). |
| `--consensus-threshold=N` | gate policy | Per-phase consensus threshold for multi-perspective gate decisions. |

**Removed in v6** (were v5 conflations):
- `--quick` — was shorthand for "minimal rigor AND yolo mode." These are now
  orthogonal axes. Use `--rigor=minimal` for fewer phases, `--yolo` for no user
  prompts, or both.
- `--no-auto-finish` — no longer needed. Yolo is opt-IN via `--yolo`, not opt-OUT.

The facilitator decides phase plan + specialists + rigor tier from the work itself.
Flags only adjust interaction mode or override downstream gate behavior.

### 2. Generate Project Slug

Use a three-stage theme-aware slug algorithm (theme prefix + key concepts + assembly),
truncated to 64 characters on a word boundary. The slug feeds into `chain_id` as
`{slug}.root`.

**Stage 1: Detect theme prefix** — scan the description (case-insensitive) for the
first matching signal group:

| Signal Keywords | Theme Prefix |
|-----------------|--------------|
| "issue", "gh-", "github issue", `#\d+` | `issue` |
| "bug", "fix", "broken", "regression", "crash" | `fix` |
| "refactor", "cleanup", "clean up", "reorganize" | `refactor` |
| "docs", "documentation", "readme", "changelog" | `docs` |
| "feature", "feat", "add", "implement", "new", "introduce" | `feat` |
| (no match) | (no prefix — fall through to Stage 3 fallback) |

**Stage 2: Extract key concepts** — from the description, remove the matched theme
keywords and stop words ("the", "a", "an", "for", "to", "of", "in", "and", "with"),
then take the first 3–4 remaining meaningful nouns or phrases and kebab-case each one.

**Stage 3: Assemble** — join as `{theme-prefix}-{concept1}-{concept2}-{concept3}`.
Truncate at 64 characters on a word boundary (never split mid-word). If no theme
prefix was matched, fall back to plain kebab-case behavior: lowercase the full
description, replace spaces with hyphens, strip special characters, truncate at 64.

### 3. Check for Existing Project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

Parse the JSON result. If an active project exists, ask the user to choose one of
four options:

1. **Resume** — continue working on the existing project (abort new project creation)
2. **Rename** — rename the new project to avoid conflict, then proceed with creation
3. **Cancel** — abort entirely
4. **Switch** — pause the current project and create the new one

If the user chooses **Switch**:

1. Set `paused: true` on the existing project via phase_manager so it no longer
   appears as active:
   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {existing-project} update \
     --data '{"paused": true}' \
     --json
   ```
2. The old project's state remains intact (not archived, not deleted) and can be
   resumed later by setting `paused: false`.
3. Proceed to Step 4 to create the new project.

### 4. Create Project Shell

Create the project via `phase_manager` so the DomainStore record and project dir exist
before the facilitator writes `process-plan.md`:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {slug} create \
  --description "{description}" \
  --json
```

Parse the JSON response for `project_dir`. This path is where `process-plan.md` will
land in step 7.

### 5. Invoke the Facilitator Skill

Invoke the `wicked-garden:crew:propose-process` skill with the description. The skill
is a rubric (Tier-1/2/3 progressive disclosure) that reasons over the 9 factors and
emits a full plan.

```
Skill(
  skill="wicked-garden:crew:propose-process",
  args={
    "description": "{description}",
    "mode": "propose",
    "project_slug": "{slug}",
    "output": "json"
  }
)
```

The skill returns a single JSON object matching
`skills/crew/propose-process/refs/output-schema.md` — with `project_slug`, `summary`,
`factors`, `specialists`, `phases`, `rigor_tier`, `complexity`, `open_questions`,
`tasks[]`. Each task carries full metadata (chain_id, event_type, source_agent:
"facilitator", phase, test_required, test_types, evidence_required, rigor_tier).

**Failure modes**: if the skill is unavailable, returns non-JSON, or omits required
fields (`tasks`, `phases`, `rigor_tier`), STOP and surface the error to the user with
the first 200 chars of output. There is no legacy fallback in v6 — the rubric IS the
path. If the facilitator cannot produce a plan, the user needs to know so they can
refine the description or file an issue.

### 5.5. Validate the Facilitator Plan

After the facilitator skill returns its JSON, run the plan validator before doing anything else with the output:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/validate_plan.py" "${project_dir}/process-plan.json"
```

**If exit non-zero** (validator printed violations to stderr):

1. Copy the draft plan to `${project_dir}/process-plan.draft.json` for debugging.
2. STOP the command — do not create tasks or advance further.
3. Show the validator's stderr output to the user verbatim.
4. Instruct the user: "The facilitator returned a malformed plan. Please file a bug at `/wicked-garden:report-issue` with the above violations and the draft plan at `${project_dir}/process-plan.draft.json`."

**If exit zero**: continue to Step 6.

### 6. Open Questions Gate

If `open_questions` is non-empty AND `rigor_tier == "full"` AND `--force` was NOT
passed: STOP and surface the questions to the user as a numbered plain-text list. Do
NOT create tasks yet. Store the facilitator's draft plan to
`${project_dir}/process-plan.draft.md` for resumption. The user's answers feed a
follow-up invocation with `mode: "propose"` + their answers appended to the
description.

For `standard` or `minimal` rigor, questions are surfaced but do NOT block task
creation — they're included in `process-plan.md` for the clarify phase to answer.

### 7. Persist `process-plan.md`

Render the returned JSON into the Markdown template at
`skills/crew/propose-process/refs/plan-template.md`. Write to
`${project_dir}/process-plan.md` using the Write tool.

Also persist the raw JSON alongside for audit at
`${project_dir}/process-plan.json` so re-evaluation runs can diff cleanly.

### 8. Emit the Task Chain

For each task in the JSON's `tasks[]` array, issue one `TaskCreate` call:

```
TaskCreate(
  subject="<task.title>",
  description="<optional longer description if present>",
  blockedBy=<task.blockedBy>,
  metadata={
    "chain_id": "<task.metadata.chain_id>",     # e.g. "{slug}.root"
    "event_type": "<task.metadata.event_type>", # "task" | "coding-task" | ...
    "source_agent": "facilitator",              # always
    "phase": "<task.metadata.phase>",
    "test_required": <bool>,
    "test_types": [...],
    "evidence_required": [...],
    "rigor_tier": "<minimal|standard|full>"
  }
)
```

Use **parallel TaskCreate calls** when the chain has multiple tasks with no
inter-dependencies within a phase. `blockedBy` captures the DAG, so downstream
tasks wait on upstream ones regardless of creation order.

### 8.5 Verify Emission (issue #432)

After all TaskCreate calls, verify that every plan task has a corresponding
native task record:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/verify_chain_emission.py" \
  "${project_dir}/process-plan.json" "{slug}.root"
```

- **Exit 0**: all plan tasks emitted. Continue to Step 9.
- **Exit 1**: count mismatch. The validator prints the delta + likely-missing
  titles to stderr. Surface the output to the user, offer to re-emit the
  missing tasks (you can pick the missing titles straight from the plan JSON),
  and only advance to Step 9 after the counts match. Do NOT silently ignore.

### 9. Persist Plan Metadata on Project

Store the facilitator-derived fields on the crew project record so `status` /
`execute` / downstream commands can read them without re-invoking the skill:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {slug} update \
  --data '{"phase_plan": ["clarify","design","build","test","review"], "phase_plan_mode": "facilitator", "complexity_score": <N>, "rigor_tier": "<tier>", "facilitator_version": "propose-process-v1", "initiative": "{slug}"}' \
  --json
```

### 10. Store Decision in wicked-brain

Record the planning decision as a memory so future runs can surface it as a prior:

```
Skill(
  skill="wicked-brain:memory",
  args={"action": "store", "type": "decision",
        "title": "crew:start facilitator plan for {slug}",
        "content": "<summary from JSON + factor readings + rigor_tier + specialist list>",
        "tags": ["crew", "facilitator", "process-plan", "{slug}"],
        "importance": 6}
)
```

**Failure handling (issue #433)** — brain storage is best-effort but not silent:

1. If the skill call raises, retry ONCE (most brain failures are transient connection blips).
2. If the retry also fails, write a sentinel at `${project_dir}/.pending-brain-store.json` with:
   ```json
   {
     "title": "crew:start facilitator plan for {slug}",
     "type": "decision",
     "content": "<same content that was passed to the failed call>",
     "tags": ["crew", "facilitator", "process-plan", "{slug}"],
     "importance": 6,
     "queued_at": "<ISO 8601 timestamp>",
     "attempts": 2
   }
   ```
   A later `/wicked-garden:crew:execute` (or any future crew command) should check
   for this sentinel and flush it if the brain is now reachable.
3. Surface a WARNING to the user — do NOT fail silently. Example:
   > `[crew:start] wicked-brain unreachable after 2 attempts — plan decision queued at .pending-brain-store.json. Future sessions may produce divergent plans until this is flushed.`

The plan file (`process-plan.md` + `process-plan.json`) remains the system of record;
the sentinel is a recovery mechanism for the brain-as-prior-source path.

### 11. Report to User

Summarize the facilitator's decision in a short markdown report:

```markdown
## Project Created: {slug}

**Rigor**: {standard | minimal | full} — {rigor_why}
**Complexity**: {N}/7 — {complexity_why}

### Factors (facilitator reading)
- Reversibility: {LOW/MED/HIGH} — {why}
- Blast radius: {LOW/MED/HIGH} — {why}
- ... (rest of 9 factors)

### Specialists
{bulleted list with one-sentence why per pick}

### Phases
{ordered list of phases with one-sentence why}

### Task chain
{count} tasks created. See `process-plan.md` for the full table.

### Next step
Run `/wicked-garden:crew:execute` to begin the first phase (`{first_phase}`).
```

If `--yolo` was passed, skip the "Next step" prompt and immediately invoke:

```
Skill(skill="wicked-garden:crew:just-finish")
```

Otherwise exit and let the user drive.
