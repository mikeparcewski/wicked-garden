# Before/After Time Estimate — Manual Rubric vs Questionnaire Scorer

## Manual rubric (post-#428, current default)

Steps the facilitator (Claude) must perform manually per `crew:start`:

1. Read description and summarize (30s)
2. Fetch priors via wicked-brain (30-60s)
3. Score 9 factors with prose justification — one sentence per factor,
   reasoning through calibration examples (4-6 min)
4. Review factor readings for internal consistency (30-60s)
5. Write full process-plan.md factor block (1-2 min)
6. Generate 19-task chain with metadata (2-3 min)

**Estimated total: ~8-12 min per crew:start invocation.**

Session data: the 2026-04-23 cluster-A crew:start was observed to take
approximately 10 minutes from description input to task chain emission.

## Questionnaire scorer (this PR, opt-in)

Steps with `WG_USE_QUESTIONNAIRE_SCORER=true`:

1. Read description and summarize (30s)
2. Fetch priors via wicked-brain (30-60s)
3. Answer ~35 yes/no questions from the questionnaire (1-2 min total;
   ~2-3s per question for factual read-and-answer; ~10s per uncertain
   question requiring a `wicked-garden:ground` call)
4. Deterministic scorer maps answers → readings (instant, Python)
5. Review readings for obvious overrides (30s)
6. Generate 19-task chain with metadata (2-3 min, unchanged)

**Estimated total: ~4-6 min per crew:start invocation.**

## Savings estimate

| Metric | Before | After | Delta |
|---|---|---|---|
| Factor scoring step | 4-6 min | 1-2 min | -3-4 min |
| Total crew:start | 8-12 min | 4-6 min | ~50% reduction |
| Consistency across runs | variable (prose) | deterministic | auditable |
| Rationale format | prose sentences | question-id trace | debuggable |

**Headline: ~50% reduction in crew:start latency when opted in. Factor
scoring step drops from 4-6 min to 1-2 min.**

## Why not 100% reduction

The questionnaire itself takes ~1-2 min because the model still needs to
read and evaluate each factual question against the description. The savings
come from eliminating the open-ended prose-justification loop and replacing
it with structured yes/no evaluation — easier for the model to do correctly
and faster to complete.

## Rollout note

`WG_USE_QUESTIONNAIRE_SCORER` defaults to `false`. The env var opt-in lets
teams validate questionnaire accuracy before making it the default path.
After a few projects' worth of validation, the default can be flipped.
