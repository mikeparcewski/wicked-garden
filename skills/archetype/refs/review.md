# review — independent assessment with hard verdict

When an artifact (code, design, spec, incident response) needs an
external quality check. Produces a verdict: APPROVE / CONDITIONAL /
REJECT, with a remediation list when not APPROVE.

## Phase shape

| Phase                  | Goal                                       |
|------------------------|--------------------------------------------|
| scope                  | Name what's being reviewed and what isn't. |
| assess                 | Apply the relevant rubric / quality bar.   |
| findings               | List what's wrong, what's missing, what's good (in that order). |
| remediate-or-accept    | Pick: fix the findings, accept them with a CONDITIONAL, or reject. |

## Produces

- **Verdict**: `APPROVE` / `CONDITIONAL` / `REJECT`.
- **Remediation list**: each item has an id, severity, and a concrete
  action. Empty when APPROVE.

## HITL

`hard:final-verdict` — the verdict is a hard gate. Auto-approve is
banned (banned-reviewer enforcement applies — `auto-approve-*`,
`fast-pass`, `just-finish-auto` are rejected at the gate).

## How to run

### scope

1. Name what's in scope: this PR, this commit, this design doc.
2. Name what's out of scope: don't drift into adjacent code that wasn't
   changed.
3. Pick the rubric: code review uses R1–R6; design review uses
   testability + boundary clarity; spec review uses SMART+T.

### assess

1. Apply the rubric. Take notes; don't write the findings yet.
2. Use the right specialist subagent — `pr-review-toolkit:code-reviewer`,
   `wicked-garden:engineering:senior-engineer`, `qe:semantic-reviewer`,
   etc. Match the artifact to the specialist.
3. For high-stakes reviews, run a council via
   `wicked-garden:jam:council` — independent multi-model verdicts
   catch what a single reviewer misses.

### findings

1. Write the findings list. Each finding:
   - `id`: F-1, F-2, ...
   - `severity`: blocker / major / minor / nit
   - `claim`: what's wrong, in one sentence.
   - `fix`: a concrete action.
2. Order: blockers first, then major, then minor. Nits last (or
   collapsed into a "nit-pile" comment).

### remediate-or-accept

1. Decide the verdict:
   - **APPROVE**: no blockers, no majors, the code is shippable as-is.
   - **CONDITIONAL**: blockers/majors that have a clear fix path. Each
     condition gets a row in the conditions manifest so the next
     archetype (build / migrate / etc.) can pin it to the resolution
     artifact.
   - **REJECT**: fundamental issues. Don't bandaid; send back to the
     author.
2. Write the verdict JSON. Validate with `scripts/qe/verdict_schema.py`
   — confirms shape (verdict enum, reviewer not banned, score in
   range, invariants per verdict type).
3. Sanitize free-text fields with `scripts/qe/content_sanitizer.py`
   to strip prompt-injection patterns from reasons / findings /
   condition descriptions before persisting.
4. Append to the audit log with `scripts/qe/verdict_audit.py append`
   so the verdict is replayable.
5. On CONDITIONAL: initialise the conditions manifest with
   `scripts/qe/conditions_manifest.py init --from-verdict <path>`.
   The downstream archetype calls `mark` as it satisfies each one.
6. Don't soften — REJECT means REJECT.

## When to stop

Review is done when the verdict is recorded. Hand off to `build` (when
fixes are needed before ship) or `ship` (when APPROVE).

## Anti-patterns

- **Don't sandbag with nits.** If the only findings are nits, APPROVE.
  Don't gate on cosmetic preferences.
- **Don't write a fix during review.** The reviewer's job is the
  verdict; the fix is the author's.
- **Don't auto-approve for speed.** Banned-reviewer enforcement exists
  for a reason. Time pressure is not a CONDITIONAL.
