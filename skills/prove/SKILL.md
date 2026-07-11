---
name: wicked-garden-prove
description: |
  Prove a claim by re-deriving it (run + gate) instead of asserting "done" —
  the one-line re-derivation verb — plus the compile action that emits a
  self-contained, vault-backed build gate into any repo.

  Use when: "prove it", "prove tests pass", "prove the build is clean",
  "re-derive done", "run the produces-gate", "gate this claim",
  "--with-attestations", "compile", "emit a build gate", "stamp a gate into
  a repo", "compile a repo-native build gate", "--trigger hook,ci", or any
  former /wicked-garden:{prove|compile} invocation.
user-invocable: true
allowed-tools: ["Bash", "Read"]
phase_relevance: ["bootstrap", "build", "review", "operate"]
archetype_relevance: ["*"]
---

# Prove

**Run this skill inline — never fork it.** prove is designed to run in the
parent context so the gate stays a reflex verb, not a dispatch ritual.

## Action: prove (default)

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

## Action: compile

Trigger phrases: "compile", "emit a build gate", "stamp a gate into a repo".

Emit a **self-contained, vault-backed build gate** into a target repo. Detects
the repo's test/lint/build commands and writes `<repo>/.wicked/` (contract +
`gate.py` + README). The gate re-derives each claim through wicked-vault and
runs with **no wicked-garden runtime present**. Optionally installs the
triggers that fire it (pre-push hook / GitHub Actions). The vault is resolved
at runtime via `npx` — it is the one thing the compiler never compiles.

> The emitted gate is deliberately **vault-direct** (shells `wicked-vault`,
> not `wicked-loom`). The garden's own gate uses loom; the emitted gate can't
> assume loom is installed in a foreign repo, so it depends only on the vault.

### Run

Parse the arguments: first non-flag token is the repo path (default `.`); pass
`--trigger <value>` through verbatim when present. Then:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/compiler/compile.py" "<repo-path>" <flags>
```

Parse the JSON manifest and report, concisely:
- the emitted **claims** (`tests-pass` / `lint-clean` / `build-clean`) and their commands;
- if `needs_review: true` — **warn** which bindings were inferred at low confidence and tell the user to confirm/fix `<repo>/.wicked/contract.json`;
- any installed **triggers** and their status (created / appended / skipped);
- next step: run `python3 <repo>/.wicked/gate.py` (exit 0 = PASS); note wicked-vault must be resolvable (`npx wicked-vault` or a global install).

Never hand-edit the emitted bindings block — re-run this action after the repo changes shape.
