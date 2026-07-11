---
name: wicked-garden-classify
context: fork
description: |
  v11 LLM-based work-shape classifier. Replaces the regex archetype detector
  with the model's own reasoning. Reads the user's prompt, picks the right
  archetype(s) from the catalog, identifies signals (blast_radius, novelty,
  reversibility, etc.), and persists to SessionState so subsequent turns
  steer correctly.

  Use when: the prompt_submit hook emitted a `<wg classify-due />` directive,
  OR explicitly invoked at session start, OR when re-classifying after the
  user changes scope mid-session.
allowed-tools: ["*"]
---

# /wicked-garden:classify

You are classifying a prompt into a v11 work-shape archetype. Your output
drives downstream archetype routing for the rest of the session (until
the user changes scope or invokes this skill again).

## Why this exists

The v11 hook auto-classifier is a regex + boolean-signal heuristic. It
works for prompts whose vocabulary matches the catalog phrase lists, but
it misses paraphrases and underuses signals. **You are a better classifier
than regex.** This skill is the path to use the model's full reasoning
on the classification step, then persist the result so the rest of the
session benefits without re-running classification on every turn.

## Routing model (council-is-the-router)

This skill **is the session router**. The former wicked-signals product (a
separate text-in / intent-out classifier) was archived because intent /
work-shape classification is a native model capability — the router is just a
model reading the prompt with full tool access (`allowed-tools: ["*"]`), which
is exactly this skill. Read it as one council member making the routing call on
the fast path.

When a routing or decision call is genuinely hard, ambiguous, or high-stakes,
**escalate to the multi-model council** (`wicked-garden-jam` → `council`, worker
`wicked-garden-jam-council`): multiple independent models deliberate, still with
garden tools for additional processing. The council is the *escalation*, not a
per-prompt router — convening 20 CLIs on every prompt would be absurd cost.

- **Fast path (always on)** — the `prompt_submit` hook emits `<wg classify-due />`,
  you classify + persist here, the parent turn steers on the persisted archetype.
- **Escalation (on demand)** — `wicked-garden-jam council <question> --options "…"`.

## What the catalog declares

`.claude-plugin/archetypes.json` defines the work-shape archetypes. Read it
once at the start of this skill. Summary table:

| Archetype | Phases                                        | Use when                                          |
|-----------|-----------------------------------------------|---------------------------------------------------|
| triage    | classify                                      | prompt is genuinely ambiguous; ask for clarification |
| explore   | frame → diverge → converge                    | open problem space, multiple paths, brainstorm    |
| specify   | elicit → structure → validate                 | requirements / acceptance criteria need writing   |
| decide    | brief → options → score → record              | 2+ viable options, need an ADR                    |
| ship      | canary → ramp → full → soak                   | already-built change being rolled out             |
| review    | scope → assess → findings → remediate-or-accept | independent assessment of an artifact            |
| incident  | triage → investigate → mitigate → resolve → followup | live production failure                      |
| build     | plan → implement → test → review              | implement a feature or fix (most common)          |
| migrate   | plan → expand → backfill → cutover → contract | in-place shape change with rollback proof         |
| modernize | discover → extract → blueprint → transform → parity → cutover | port a legacy codebase to a new stack (NOT in-place) |

## Procedure

### 1. Read the prompt

What is the user actually asking for? Restate in one sentence in your own
words. If you can't, the prompt is genuinely ambiguous → triage.

### 2. Pick archetype(s)

Archetypes are NOT mutually exclusive. Pick a SET. Common combinations:

- "implement schema change with backfill" → `build + migrate`
- "review the auth PR before deploy" → `review + ship`
- "should we use redis or memcached for sessions?" → `decide` (and
  possibly `build` if they want you to also implement it)

Score each match between 0.0 and 1.0. Use these calibration anchors:

- **0.9+**: keyword + signal both clear, no ambiguity (e.g. "checkout is
  down 5xx spiking" → incident 1.0).
- **0.7–0.9**: clear shape with one or two minor uncertainties.
- **0.5–0.7**: archetype matches but the prompt is partial — agent should
  read the playbook and gracefully ask if anything was missed.
- **<0.5**: too weak; don't return this archetype.

If nothing scores ≥ 0.5, return `triage` only — that's the signal to ask
for clarification before doing work.

### 3. Identify signals

Boolean flags that downstream archetypes use to scale rigor. Mark TRUE
only when the prompt clearly implies it:

- `blast_radius_high` — change affects production traffic / many users / many systems.
- `novelty_high` — pattern not yet in this codebase.
- `state_complexity_high` — touches data shape, migrations, persistent state.
- `reversibility_low` — undoing is expensive (data migrations, destructive ops).
- `reversibility_medium_or_low` — undoing is non-trivial (config changes, breaking APIs).
- `production_impact` — production users / systems affected right now.
- `compliance_scope` — GDPR / SOC2 / HIPAA / PCI surface.
- `ambiguity_high` — multiple plausible reads.
- `spec_ambiguity_high` — success criteria are fuzzy.
- `scope_unclear` — boundary of work is undefined.
- `multiple_viable_options` — 2+ paths with no obvious winner.
- `post_build` — change is already implemented; this is about deployment.
- `code_change` — implementation work involved.
- `independent_assessment_needed` — someone else's work needs review.

Default any flag you didn't explicitly mark to FALSE. Do not over-tag.

### 4. Pick intent

Intent is coarser than archetype — used by the hook to gate directive
emission. One of:

- `simple-edit` — typo, comment, formatting, single-line fix. Hook stays silent.
- `feature` — most non-trivial work (default for build/migrate/ship).
- `rigor` — high stakes (compliance, security, blast_radius_high).
- `research` — exploratory (explore, decide).

### 5. Persist

Emit a JSON object with the four keys above and pipe to the persist
script. Use this exact shape — extras get dropped:

```bash
echo '{
  "intent": "feature",
  "archetypes": [
    {"name": "build", "score": 0.85, "evidence": ["implement keyword + code_change signal"]},
    {"name": "migrate", "score": 0.65, "evidence": ["schema change + state_complexity signal"]}
  ],
  "signals": {
    "code_change": true,
    "state_complexity_high": true,
    "reversibility_low": true
  }
}' | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/classify/persist.py"
```

The script normalises and writes to SessionState. Confirm the response
shows `"ok": true`, then return control.

### 6. Persist and return

You are `context: fork` — your job is to classify, persist, and return, not to
run the work. Do **not** start executing the playbook inside this fork; the
persisted archetype is what the parent turn resumes on (the `prompt_submit`
hook's Tier-1 path re-emits the steered `<wg archetype=… />` on the next turn
from what you wrote to SessionState). The top archetype's playbook is
`skills/archetype/refs/{name}.md`. Do not re-run classification mid-session
unless the user explicitly changes scope.

## When to skip this skill

- The prompt is a continuation token ("yes", "do it", "lgtm"). The hook
  already short-circuits these.
- The user typed `/wicked-garden:archetype:<name>` directly — they
  already classified.
- SessionState already has `classified_at` set for this session and the
  prompt fits the existing classification. Re-classifying on every turn
  is exactly the cost we're trying to avoid.

## Failure modes

- Persist script fails: return the JSON to the user as text and ask
  them how to proceed. Do not invent a workflow.
- Catalog file unreadable: return triage with an explanation. The
  archetype machinery will surface the read error separately.
- Model can't decide between 3+ archetypes: return triage with a note.
  triage's job is to ask. Don't pick at random.
