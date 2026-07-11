# persona define — Create / Update Persona Rubric

Full rubric for the `define` sub-action (formerly `commands/persona/define.md`).
Stores a custom persona in the project-scoped DomainStore by default. This is the
**mechanism** that lets an enterprise inject ITS house personas. Use `--save` to
also promote to the plugin-level cache for cross-project reuse.

## What makes a persona worth defining

A persona earns its keep only when it encodes something the base model does NOT
reliably supply on its own. Three kinds of durable value:

1. **A named failure-mode defense** — a guard against a specific way work goes
   wrong that the base model does not volunteer (e.g. "refuse a deploy with no
   tested rollback").
2. **A hard constraint** — a non-negotiable house rule (e.g. "no PII in logs,
   ever — block the change").
3. **A scope guard** (`--not-focus`) — what the persona deliberately does NOT
   own, so it stays sharp instead of diffusing into a generic reviewer.

A persona that only restates a role ("act like a senior engineer") has low
durable value — the base model already does that, and the delta shrinks each
model release. Don't claim a persona is better by assertion — if you want proof
it lifts behaviour, add an eval (see `tests/persona/` and the model-eval cases
in `tests/persona/eval_cases/`).

## The GOOD pattern (constraint + named failure mode + rationale + scope guard)

Author a house persona that defends a real failure mode, not a role restatement:

```bash
/wicked-garden-persona define payments-reviewer \
  --focus "money movement is irreversible — verify before it ships" \
  --traits "exacting,paranoid,evidence-driven" \
  --role finance \
  --constraints "FAILURE MODE — double-charge: any retry on a charge/transfer path MUST carry an idempotency key; flag and block if absent; FAILURE MODE — silent rounding: every currency calc states its rounding mode and precision — unstated rounding is a defect; FAILURE MODE — unlogged money movement: every balance change MUST emit an auditable event before it is considered done" \
  --not-focus "UI copy and layout — hand to product; general code style — hand to engineering" \
  --save
```

Why this is GOOD, not generic:
- Each constraint names the **failure mode** it defends (double-charge, silent
  rounding, unlogged movement) — the base model does not raise these unprompted.
- The **scope guard** (`--not-focus`) stops the persona from drifting into a
  generic reviewer.
- The **rationale** lives in the focus + the failure-mode names, so a future
  reader knows WHY each constraint exists.

A WEAK definition to avoid:

```bash
# Low durable value — restates a role the base model already plays.
/wicked-garden-persona define senior-dev --focus "write good clean code"
```

## Step 1: Parse and Validate

Extract from the args passed to the `define` sub-action:

- `name` (required): first non-flag token — kebab-case
- `--focus` (required): the perspective this persona applies
- `--traits` (optional): comma-separated behavioral adjectives
- `--constraints` (optional): **semicolon-separated** non-negotiable rules. For a
  methodology persona, phrase each as `FAILURE MODE — <name>: <the guard the base
  model skips>`. (Semicolon, not comma — commas are common inside a single rule.)
- `--not-focus` (optional): **semicolon-separated** concerns this persona does NOT
  own (scope guard).
- `--role` (optional): category for filtering (default: "custom")
- `--save` (optional flag): also promote to plugin cache for cross-project reuse

If `name` is missing:
> "name is required. Usage: /wicked-garden-persona define <name> --focus \"<focus>\""
> STOP.

If `--focus` is absent:
> "focus is required — describe the perspective this persona applies."
> "Example: /wicked-garden-persona define pragmatic-tech-lead --focus \"delivery over perfection\""
> STOP.

If `--constraints` and `--not-focus` are both absent, gently nudge (do NOT block):
> "Tip: a persona with no constraints mostly restates a role the base model
> already plays. Consider adding `--constraints \"FAILURE MODE — …\"` so it
> defends a specific failure mode."

## Step 2: Store in DomainStore

```bash
RESULT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/persona/registry.py \
  --define "${name}" \
  --focus "${focus}" \
  [--traits "${traits}"] \
  [--constraints "${constraints}"] \
  [--not-focus "${not_focus}"] \
  [--role "${role}"] \
  --json)
```

Only include the optional flags that were actually provided.

If the command fails (exit non-zero), show the error from stderr and STOP.

## Step 3: Optionally Save to Plugin Cache

If `--save` flag is present:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/persona/registry.py \
  --save-cache "${name}" \
  --json
```

## Step 4: Confirm

Check whether `_updated: true` (existing persona overwritten) or `_updated: false` (new).

If new persona:
> "Created persona '{name}'. Invoke with: `/wicked-garden-persona as {name} <task>`"

If existing updated:
> "Updated persona '{name}'."

If `--save` was used, add:
> "Saved to plugin cache — available in all projects."

Show persona summary:
- **Focus**: {focus}
- **Traits**: {traits comma-separated or "none"}
- **Constraints**: {count, or "none — this persona mostly restates a role"}
- **Not focus**: {not_focus joined, or "none"}
- **Role**: {role}
