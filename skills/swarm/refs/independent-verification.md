# Independent verification — the verify wave (the core)

This is the mechanism the whole skill exists for. The verifier is a **separate
agent from the implementer** that **re-derives** each result from a clean state.
Self-graded "done" is rejected. This is the vault / `prove` ethos applied to a
swarm: a claim is only true if it can be recomputed from frozen evidence.

> **Independence is structural, not polite.** Use a *different* agent type than
> the one that did the work. The `wicked-garden-qe-semantic-reviewer` worker skill is
> independent by construction and **refuses to attest code it authored**; `wicked-vault attest`
> fails closed when `evaluator == creator` (G10). If you let the implementer
> verify itself, you have a self-grade — the one thing this skill forbids.

## Pick the verifier agent

| Verdict needed | Agent |
|----------------|-------|
| Does the code do what the spec/AC MEANS? | `wicked-garden-qe-semantic-reviewer` worker skill (independent-by-construction) |
| General correctness when no specialist fits | a reviewer following `wicked-garden-governed-worker` Evaluator (output-only; evaluator ≠ creator) |
| High-stakes verdict needing multiple opinions | the `wicked-garden-jam-council` skill (independent multi-model) inside the wave |
| The raw "did the suite actually pass" receipt | `/wicked-garden-prove` (run + gate) — see `refs/receipts-and-evidence.md` |

Run M verifiers — one per unit, none of them that unit's implementer — in parallel where
your harness runs parallel sub-agents, serially otherwise (record `serial_reason`; the
structural rule that survives every harness is verifier ≠ implementer, not the parallelism).

**Hand-off** — for each unit, open the verifier skill the table names (or
`wicked-garden-governed-worker`, Evaluator section) with the brief below as the argument; on Claude Code this is one Task per unit in one message, on any other seat open the named skill from your catalog and run the brief inline, one unit after another, each verdict in its own scratch file and never in the implementer's context, then continue here.

## The verifier brief template

```
You are the swarm VERIFIER for unit: <unit-name>. You did NOT implement this.
Your job is to re-derive the result from a clean state and render a verdict.
Trust nothing the implementer asserted — re-derive it.

INPUTS: <scratch>/<unit-name>/  (the implementer's artifacts) and
        BASE COMMIT SHA: <sha>  (the state before the change).

1. RE-RUN FROM CLEAN.
   Check out / reset to a clean tree. Run the unit's REAL build + test suite
   yourself. Do not read the implementer's test-output.txt as truth — produce
   your own. Capture exact command + full output + exit code.

2. READ THE ACTUAL DIFF, not the prose.
   git diff <base-sha>..HEAD (or the diff.patch). Verify the change is what the
   summary claimed, scoped where it claimed, with no smuggled-in extra edits.

3. KILL FORCE-FITS AND OVER-CLAIMS.
   - If the implementer said a failure is "pre-existing", CHECK OUT THE BASE
     COMMIT and confirm it actually fails there. A "pre-existing failure" that
     passes on base is a regression the implementer introduced — FAIL.
   - If a test was weakened, skipped, or its assertion gutted to go green — FAIL.
   - If the change does less than claimed — FAIL, and say exactly what's missing (a
     partial result is a FAIL with the gap named; the verdict grammar has no third token).

4. RENDER THE VERDICT: PASS / FAIL.
   - PASS: re-ran clean, diff matches claim, no over-claims, tests genuinely green.
   - FAIL: does not re-derive — name the exact command + output that disproves it;
     or works but incomplete / claim overstated — list the gap (never a third token).

5. WRITE THE AUTHORITATIVE RECEIPT to <scratch>/<unit-name>/receipt.md:
   verdict, the exact command(s) you ran, their verbatim output + exit codes,
   the base SHA and head SHA, and a one-line rationale. This receipt — not the
   implementer's summary — is the record of truth for this unit.

6. RETURN ~150 words: verdict + the single most load-bearing piece of evidence
   (the command + exit code that proves it) + receipt path.
```

## The wave structure

```
implementers wave  →  (disk artifacts)  →  verifiers wave  →  (receipts)  →  prove gate
```

- The two waves never run as one agent. The hand-off is **disk artifacts**, so
  the verifier starts from the implementer's outputs but re-derives the result
  independently.
- A unit is only "done" when its `receipt.md` says PASS **and** the claim is
  re-derived through `/wicked-garden-prove` (next ref). A FAIL (a partial result included) goes
  back to a fresh implementer slice — the original implementer does not get to
  argue its way to PASS.

## Why re-derivation beats assertion

A traceability/claim heuristic reports an untagged-but-correct change as
"missing" and a tagged-but-wrong one as "done" — both wrong (this is exactly
why `semantic_review.py` is only a pre-filter and the `wicked-garden-qe-semantic-reviewer`
worker skill does the real read). The verifier closes that gap: it judges by re-running and
reading, not by trusting a label or a summary. The verdict that **names the gap**
is the value; never inflate to PASS to be helpful.
