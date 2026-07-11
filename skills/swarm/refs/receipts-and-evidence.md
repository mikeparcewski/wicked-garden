# Receipts & evidence — claims must be re-derivable

A swarm produces **receipts, not assertions**. Every "done" / "tests pass" /
"build clean" must be re-derivable from frozen evidence: the **exact command**,
its **real output**, **exit code**, and the **commit SHA** it ran against. If you
can't re-derive it, it isn't proven — it's a claim, and claims are rejected.

## Compose the garden's evidence machinery — don't hand-roll it

| Mechanism | Use it for |
|-----------|------------|
| `/wicked-garden-prove <claim> --by "<cmd>" [--verifier ...]` | The one-line receipt: runs the command, freezes its real exit code as wicked-vault evidence, gates by **re-running** the verifier. Exit 0 only on a re-derived PASS; **fail-closed** (exit 3) when the backend is down — never a vacuous pass. Works on **interim** artifacts too (prove a produce the moment it exists). |
| `/wicked-garden-prove ... --with-attestations` | Hard gates (review / incident / migrate). Stays REJECT (`UNATTESTED`) until an **independent** evaluator runs `wicked-vault attest <id> --opinion pass`. The doer's own evidence cannot satisfy it — that is the anti-self-grade point. |
| `wicked-vault attest <id> --opinion pass --evaluator <who>` | The independent sign-off itself. Fails closed on `evaluator == creator` and on weak/ambient identity (record under an explicit `--actor`, default `garden-prove`). |
| `wicked-testing:*` verdicts (writer → executor → reviewer, isolated) | When the unit needs a full evidence-gated acceptance verdict rather than a single command receipt. The reviewer is isolated from execution — same independence principle as the verify wave. |

This is the **Sentinel rule** made concrete: a done-claim needs a *re-derived
verdict*, not a self-report. `/wicked-garden-prove` is the verb you reach for by
reflex before telling the user a unit is done.

## What a receipt looks like (verbatim, never paraphrased)

Each unit's `receipt.md` (written by the **verifier**, not the implementer) holds:

```
unit:        <unit-name>
verdict:     PASS | FAIL | PARTIAL
base_sha:    <sha the change started from>
head_sha:    <sha after the change>
command:     <the exact command run, copy-pasteable>
exit_code:   <real exit code>
output: |
  <verbatim stdout/stderr — the real thing, not a summary>
prove:       <the /wicked-garden-prove JSON verdict: satisfied + re_derived>
attestation: <artifact id + evaluator, for hard gates; else "n/a">
rationale:   <one line>
```

Never write "tests pass" without the command + output + exit code that proves
it. A receipt a reviewer can't re-run is not a receipt.

## Honest marking — no padding

The swarm's credibility comes from honesty, not volume. Mark every finding:

- **GAP** — genuinely missing; should be added.
- **PARTIAL** — half-there; name exactly what's missing.
- **ALREADY-COVERED** — the unit is already ahead of this; say so plainly.

Rules:
- **Surface reverse-transfers and "you're already ahead" honestly.** If a unit
  already does the thing better than the proposed change, that's a finding, not
  an omission — and sometimes the change should flow the *other* way.
- **A short true list beats a long speculative one.** Don't pad the fit-matrix
  with maybes to look thorough.
- **Record considered-and-rejected items explicitly** in `deferred.md` so they
  read as *weighed, not missed*. "Considered X, rejected because Y" is a
  stronger signal than silence.
- **The verdict that names the gap is the value.** Never inflate a PARTIAL to
  PASS, or a GAP to ALREADY-COVERED, to be agreeable.

## Tie it back to the gate

A unit is shippable only when: its `receipt.md` verdict is PASS **and**
`/wicked-garden-prove` returns `satisfied: true, re_derived: true` for the
claim **and** (for hard-gate work) an independent `wicked-vault attest --opinion
pass` exists from an evaluator that is not the implementer. Anything short of
that is PARTIAL or FAIL and loops back to a fresh implementer slice — see
`refs/independent-verification.md`.
