---
allowed-tools: ["Bash", "Read"]
description: "Compile a repo-native build gate — detect bindings, emit a vault-backed harness"
argument-hint: "[repo-path] [--trigger hook,ci]"
phase_relevance: ["bootstrap", "build"]
archetype_relevance: ["build", "migrate"]
---

# /wicked-garden:compile

Emit a **self-contained, vault-backed build gate** into a target repo. Detects
the repo's test/lint/build commands and writes `<repo>/.wicked/` (contract +
`gate.py` + README). The gate re-derives each claim through wicked-vault and
runs with **no wicked-garden runtime present**. Optionally installs the
triggers that fire it (pre-push hook / GitHub Actions). The vault is resolved
at runtime via `npx` — it is the one thing the compiler never compiles.

## Run

Parse `$ARGUMENTS`: first non-flag token is the repo path (default `.`); pass
`--trigger <value>` through verbatim when present. Then:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/compiler/compile.py" "<repo-path>" <flags>
```

Parse the JSON manifest and report, concisely:
- the emitted **claims** (`tests-pass` / `lint-clean` / `build-clean`) and their commands;
- if `needs_review: true` — **warn** which bindings were inferred at low confidence and tell the user to confirm/fix `<repo>/.wicked/contract.json`;
- any installed **triggers** and their status (created / appended / skipped);
- next step: run `python3 <repo>/.wicked/gate.py` (exit 0 = PASS); note wicked-vault must be resolvable (`npx wicked-vault` or a global install).

Never hand-edit the emitted bindings block — re-run this command after the repo changes shape.
