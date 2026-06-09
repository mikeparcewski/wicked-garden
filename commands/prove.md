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
- Read the JSON verdict: `satisfied` is the truth; `re_derived: true` means it
  was recomputed from frozen evidence (not your claim); `gate: "unavailable"`
  means the backend is down and the gate failed closed.
- Only report the work as done when `satisfied: true`. On `REJECT`, the claim is
  false — fix it, don't narrate around it.
