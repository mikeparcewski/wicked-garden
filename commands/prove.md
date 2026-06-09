---
description: Prove a claim by re-deriving it (run + gate) instead of asserting "done"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:prove

The one-line re-derivation verb. Before you tell the user something is "done"
/ "tests pass" / "the build is clean", **prove it** — don't assert it. This
runs the command, freezes its real exit code as wicked-vault evidence, and gates
by re-running the verifier. Exit 0 only on a re-derived PASS; fail-closed (exit
3) when the loom/vault backend is unresolvable — never a vacuous pass.

It collapses the gate ritual (vault init → declare-contract → record --run →
gate) into one call, so the gate is something you reach for by reflex.

Instructions:
- Run it inline (the `--by` command executes in `--project-dir`, default `.`):
  ```bash
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
    "${CLAUDE_PLUGIN_ROOT}/scripts/qe/prove.py" \
    <claim> --by "<command>" [--verifier exit_code_eq:0] [--project-dir <dir>]
  ```
  e.g. `prove.py tests-pass --by "pytest -q"` · `prove.py build-clean --by "npm run build"`
- **Validate the OUTPUT, not just an exit code.** `--verifier` re-runs against the
  command's output: `regex_match:<re>` / `not_contains:<re>` scan stdout;
  `jq_pred:<expr>` evaluates a predicate over the command's JSON stdout;
  `commit_exists:<sha>` checks a git commit. This works on **final and interim**
  artifacts — prove an intermediate produce the moment it exists, not only at the end:
  ```
  prove.py adr-has-decision --by "cat decision.md" --verifier "regex_match:## Decision" --kind doc
  prove.py config-no-secrets --by "cat app.yaml"   --verifier "not_contains:(?i)password" --kind doc
  prove.py enough-options    --by "cat options.json" --verifier "jq_pred:.options | length >= 2" --kind doc
  ```
- Read the JSON verdict: `satisfied` is the truth; `re_derived: true` means it
  was recomputed from frozen evidence (not your claim); `gate: "unavailable"`
  means the backend is down and the gate failed closed.
- Only report the work as done when `satisfied: true`. On `REJECT`, the claim is
  false — fix it, don't narrate around it.

**Hard gates (incident/migrate/review): `--with-attestations`.** Add it and the
gate stays `REJECT` (`UNATTESTED`) until an INDEPENDENT evaluator — not the agent
that did the work — runs `wicked-vault attest <artifact-id> --opinion pass`. The
doer's own evidence cannot satisfy a hard gate; that's the point. Find the
artifact with `wicked-vault list --scope <scope> --phase <phase>`. A `reject`
attestation flips the gate to `REJECT` even if the evidence re-derives.
