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

The final-verdict gate **re-derives** these via `wicked-loom` (`scripts/qe/vault_gate.py` shells `wicked-loom gate`, which shells `wicked-vault cross-check`): the verdict JSON is re-validated and the
remediation-list structure re-checked, never trusting a self-asserted
"done". wicked-loom (the gate engine) and wicked-vault (the evidence backend) are **required** peers (installed by `/wicked-garden:setup`); if loom is unresolvable — or the vault behind it absent — the gate **fails closed** (`gate: "unavailable"`, `satisfied: false`) rather than passing
on a claim alone. Because final-verdict is a **hard** gate, the contract
also demands an **independent attestation** — the verdict must be signed
off by an evaluator that is NOT the worker who did the reviewed work
(anti-self-grade, G10). `--no-require` opts a throwaway/low-rigor run
back to the doctrine-light claim-only path.

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
4. If a vault is resolvable (`scripts/qe/vault_gate.py resolve` →
   `available: true`), declare the re-derivable contract for this phase
   so the final-verdict gate has a bar to check against:
   `wicked-vault init` (once per repo) then
   `wicked-vault declare-contract --scope <scope> --phase review --spec contract.json`.
   `required_evidence` should pin `verdict` to `exit_code_eq:0` on a
   verdict-schema validation (`scripts/qe/verdict_schema.py`) and
   `remediation-list` to a presence/structure `regex_match`. Because
   this is a **hard** gate, the contract also requires a passing
   independent `opinion_attestation` (the judgment tier). Skip silently
   if no vault.

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
   Then record both produces as re-derivable evidence (vault present):
   `wicked-vault record --scope <scope> --phase review --claim verdict
   --kind verdict --source "<verdict.json>" --criteria "<the bar>"
   --verifier exit_code_eq:0 --run` where the run is
   `scripts/qe/verdict_schema.py <verdict.json>`, and a second `record`
   for `--claim remediation-list ... --verifier regex_match:<pattern>`.
   The `--run` captures the validator's real exit code now and the gate
   re-runs it later — a claim you can't re-derive is not evidence. No
   vault → fall back to `evidence_tracker.py claim`.
   Then have an **independent** evaluator sign off via the
   `wicked-vault:analyze-evidence` skill, which records an
   `opinion_attestation` over the frozen criteria. The evaluator must
   NOT be the agent that did the reviewed work — the gate fails closed
   on a self-grade. This is the "never let work self-grade its own done"
   guarantee.
5. On CONDITIONAL: initialise the conditions manifest with
   `scripts/qe/conditions_manifest.py init --from-verdict <path>`.
   The downstream archetype calls `mark` as it satisfies each one.
6. Don't soften — REJECT means REJECT.

## When to stop

Review is done when the produces-gate is satisfied. Check the gate —
don't self-assert it:
`scripts/qe/prove.py <claim> --by "<command>" --scope <scope> --phase review --with-attestations` (frictionless, single claim — re-derive, don't assert) — or the full multi-claim contract via `scripts/qe/vault_gate.py gate <project_dir> --scope <scope> --phase review --with-attestations` **`--with-attestations`** keeps this gate `UNATTESTED`/`REJECT` until an INDEPENDENT evaluator (not the doer) runs `wicked-vault attest <artifact-id> --opinion pass` — find it via `wicked-vault list --scope <scope> --phase review`. The doer's own evidence cannot satisfy a hard gate.
(exit 0 = satisfied). This is a re-derived PASS over the declared
contract. `--with-attestations` makes the gate require a passing
independent `opinion_attestation` recorded via the
`wicked-vault:analyze-evidence` skill, where the evaluator ≠ the agent
that did the reviewed work — it fails closed on a self-grade. A REJECT
means the recorded evidence does not clear its contract — fix the work,
not the claim. An `unavailable` verdict means the required vault isn't
installed — run `/wicked-garden:setup`. Then hand off to `build` (when
fixes are needed before ship) or `ship` (when APPROVE).

## Anti-patterns

- **Don't sandbag with nits.** If the only findings are nits, APPROVE.
  Don't gate on cosmetic preferences.
- **Don't write a fix during review.** The reviewer's job is the
  verdict; the fix is the author's.
- **Don't auto-approve for speed.** Banned-reviewer enforcement exists
  for a reason. Time pressure is not a CONDITIONAL.
