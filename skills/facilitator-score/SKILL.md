---
name: facilitator-score
description: |
  Score 9 risk factors for a new project via structured yes/no questionnaire.
  Use *before* propose-process to skip the manual rubric tax. Returns a factors
  block (same shape as propose-process output-schema.md) for direct injection
  into Step 3. NOT for: re-evaluation of an in-flight project (use
  propose-process re-evaluate mode), one-off complexity guesses (use deliberate),
  or any use that requires overriding all 9 factors by hand (just use
  propose-process directly).
portability: portable
allowed-tools:
  - wicked-garden:ground
---

# wicked-garden:facilitator-score — Questionnaire Scorer

Converts a ~30-second structured Q&A into deterministic factor readings,
replacing the ~10-minute manual prose-justification pass in propose-process.

## Inputs

- **`description`** — project description (required)
- **`priors`** (optional) — wicked-brain search results already fetched; if
  absent, call `wicked-brain:search` with 3–4 salient nouns before proceeding.

## Outputs

A `factors` block matching `skills/propose-process/refs/output-schema.md`:

```json
{
  "factors": {
    "reversibility":      {"reading": "HIGH|MEDIUM|LOW", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "blast_radius":       {"reading": "HIGH|MEDIUM|LOW", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "compliance_scope":   {"reading": "HIGH|MEDIUM|LOW", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "user_facing_impact": {"reading": "HIGH|MEDIUM|LOW", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "novelty":            {"reading": "HIGH|MEDIUM|LOW", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "scope_effort":       {"reading": "HIGH|MEDIUM|LOW", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "state_complexity":   {"reading": "HIGH|MEDIUM|LOW", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "operational_risk":   {"reading": "HIGH|MEDIUM|LOW", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."},
    "coordination_cost":  {"reading": "HIGH|MEDIUM|LOW", "risk_level": "low_risk|medium_risk|high_risk", "why": "..."}
  }
}
```

`reading` (backward-compat): HIGH = least risky, LOW = most risky. This direction is counter-intuitive
for downstream display. Prefer `risk_level` when showing results to users: `low_risk` / `medium_risk` /
`high_risk` maps directly to standard risk language.
```

## Procedure

### Step 1 — Fetch priors (if not supplied)

```
wicked-brain:search query="{3-4 salient nouns from description}" limit=5
```

Record up to 3 priors that materially affect the answers (e.g. prior rollbacks
raise novelty; prior data migrations raise reversibility).

### Step 2 — Render and answer the questionnaire

Run this to get the questionnaire markdown:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
   "${CLAUDE_PLUGIN_ROOT}/scripts/crew/factor_questionnaire.py" render
```

For each yes/no question: answer based on the description + priors.

**When uncertain on a question**, invoke `wicked-garden:ground` with the
question text before answering. Example:

> Are there external API consumers depending on a surface being removed?

If unclear → `wicked-garden:ground question="external API consumers for this surface"`

Do NOT answer "yes" speculatively. Uncertainty without grounding → answer "no"
and note it in the override rationale below.

### Step 3 — Score deterministically

Pass the YAML answers block to the scorer:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
   "${CLAUDE_PLUGIN_ROOT}/scripts/crew/factor_questionnaire.py" score \
   --answers-file "${TMPDIR:-/tmp}/answers.yaml"
```

Or call `score_all(answers)` directly when composing from Python.

### Step 4 — Override if judgment conflicts

The questionnaire score is the *basis*, not the *verdict*. You (Claude) may
override individual readings when:

- A prior decision explicitly contradicts the mechanical score
- The description contains nuance the questionnaire cannot capture
- Two reasonable readings exist; factor-definitions.md says err toward higher risk

Document every override in the `why` field:

```json
"reversibility": {
  "reading": "LOW",
  "why": "3 pts from: r1, r2 — OVERRIDE: prior #proj-foo showed silent data loss on similar migration"
}
```

### Step 5 — Return factors block

Return the JSON factors block to the caller (propose-process). The caller
handles specialists, phases, rigor, tasks.

## Calibration reference

`skills/propose-process/refs/factor-definitions.md` — what LOW / MEDIUM / HIGH
mean per factor. When the questionnaire score and your prose read disagree, the
factor-definitions calibration examples are the tiebreaker.

## Graceful degradation

- Scorer script unavailable → answer the questionnaire inline and score manually
  using the weight tables in `factor_questionnaire.py` QUESTIONNAIRE dict.
- Brain unavailable → answer without priors, note degradation in each `why` field.

## Composition

```
propose-process
  └─ facilitator-score          ← this skill (Step 2.5 of propose-process)
       └─ wicked-garden:ground  ← called per uncertain question
```
