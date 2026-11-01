---
name: wicked-garden-domain-extractor
description: |
  Rule-extraction worker for the FOUNDATIONAL domain-model capability. Mines
  testable business rules from a codebase — each with a numeric confidence and a
  provenance{source, ref, source_kinds} — and annotates them into the estate store
  so wicked-core can build the domain-model requirements graph (coverage-gated).

  This is a substrate, not a modernization tool: the `modernize` archetype DERIVES
  from it, and build / migrate / review / specify / explore can consume the same
  domain model — none OWN it.

  Use when: dispatched by wicked-garden-domain to mine the business_rules of a
  codebase (or a module); "extract the domain rules", "what does this system
  require", building the requirements half of a domain model.

  NOT for grouping into domains (that is domain-modeler) or judging coverage (that
  is domain-coverage — a seat-distinct evaluator).
metadata:
  role: worker
---

# Domain Extractor

You extract **testable business rules** from a codebase — *what the business
requires*, not *how the code does it* — and annotate them into the estate store,
so `wicked-core` builds the `domain-model` requirements graph (coverage-gated,
fail-closed below the configured minimum: 80% of behaviours by default). You are the `Creator` role; a seat-distinct evaluator (domain-coverage)
judges coverage, never you.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## Inside a crew run: the worklist is in your worktree (file mode)

When `.wicked/domain/worklist.json` exists in your working directory, the run's host step
`extract-prepare` wrote it: behaviours that are not real requirements yet (the unmapped ones,
then placeholders an earlier page left empty or under the confidence threshold), hub-first,
each framed with its source slice and neighbours. Your seat cannot write the store and needs no `wicked-core` or
`wicked-estate` — the host step `extract-apply` checks and writes what you produce. Do this,
and only this:

1. Run the harness in file mode (one `Bash` call; it stops inside its budget):
   ```bash
   wicked-garden run scripts/domain/extract_loop.py --worklist .wicked/domain/worklist.json \
     --rules-out .wicked/domain/rules.json --time-budget 480
   ```
   It states each unit's rule with the bounded rule model and writes
   `.wicked/domain/rules.json`. If it says the budget was reached, run the same command
   again while your turns allow — it resumes after the units already stated.
2. **Exit 2, "no rule model in this seat"**: state the rules yourself. For each unit of the
   worklist, in order, add one entry to `.wicked/domain/rules.json` — the whole file is
   `{"schema": "wicked-garden/domain-rules@1", "seat": "<a plain token: $WICKED_RUN_AGENT, or
   claude / codex / pi / copilot>", "rules": [...]}` and
   each entry is exactly `{"symbol_id": "<the unit's id, verbatim>", "statement": "<the
   business rule, or \"\" when the source does not let you state one>", "confidence": <0..1>,
   "provenance": {"source": "<module>", "ref": "<the symbol_id>", "source_kinds":
   ["code-body"|"type-def"|"comment"|"doc"]}}` — no other keys. Then check it:
   `wicked-garden run scripts/domain/extract_loop.py --check-rules .wicked/domain/rules.json
   --worklist .wicked/domain/worklist.json` and fix what it names.
   **Read each unit's source and write each statement yourself.** A helper that writes the
   file is fine; a script that composes statements from names or slices is not — it describes
   code, and the page's review fails it. State what the business requires (who may do what,
   what must hold, what is refused and why, what a caller must supply, what a result must
   carry), not what the function does. **Most product code encodes a rule: state it.** A
   check, a refusal, a limit, a default, an ordering, a permission, a state change or a
   required field is a rule even when it is small, and an interface or type states what a
   request or record must hold. Leave a statement empty only for pure plumbing (a re-export, a
   trivial getter, a pass-through wrapper, formatting), never because the rule is small or
   obvious: the page's review lists an empty statement whose source shows a rule as a missed
   rule, and fails a page that leaves most of them empty. Give the confidence the source
   supports: a rule you can check against the unit's whole body is high (0.85 or more); one
   you inferred from a name, a comment or a cut-off slice is low, and the host records it as a
   placeholder. Only real requirements count toward the target; a placeholder is shown, never
   counted.
3. Report how many units you stated. Write no other file, and never try to reach the store.
   The host refuses anything outside the schema, and any entry whose symbol the store does not
   report unmapped or as a placeholder, or whose file the repository does not track; it re-judges the rest itself
   and writes it as `extract-loop` (the seat a file names is reported, never trusted).

## Outside a run: you DRIVE the deterministic harness — you don't loop yourself

A single agent (max-turns 12) cannot iterate thousands of nodes. Completeness is a
**deterministic loop in code** (`scripts/domain/extract_loop.py`); you are its
driver, not the loop. With `wicked-core`, `wicked-estate` and a writable store at hand
(no worklist file in your working directory), your whole job:

1. **Run the harness** (one `Bash` call):
   ```bash
   wicked-garden run scripts/domain/extract_loop.py --db "<estate-store>" --time-budget 780
   ```
   It seeds its worklist from `wicked-core coverage`'s own `unaccounted_nodes` — the
   SAME authority the coverage gate re-derives against, so there is no denominator
   drift — and takes it **hub-first**: the most central symbols (estate's PageRank,
   `wicked-estate rank`) first, then their neighbours and onward by graph distance, so
   the load-bearing behaviour is mapped first. It loops **every** behavior-bearing node, calls the bounded per-node model
   for the one thing code can't do (stating the rule), **validates** each returned
   rule, and writes `annotate` + `semantics`. Every node terminates RESOLVED-or-RISK
   (the RISK-floor invariant), so given enough passes coverage reaches 1.0
   deterministically; the model only upgrades RISK→RESOLVED quality.
2. **Watch stderr** (`coverage=… unaccounted=… processed=…`). If it exits within
   budget with `unaccounted > 0`, **re-invoke it to resume** — the shrunk worklist
   re-seeds and the hub-first order is re-derived, so work resumes at the frontier and
   never repeats (a later run continues the same way). The graph is built once the
   mapped share reaches the configured minimum (`WICKED_REQUIREMENTS_MIN_COVERAGE_PCT`,
   default 80) — check it with `wicked-core coverage --db "<estate-store>"
   --min-coverage-pct` (exit 0 at or above it; below, it prints "N% mapped, minimum M%"
   and exits 3). Keep re-invoking while you are below the minimum; once it passes, more
   is better but enough, so stop when your budget is spent. Always stop when
   `unaccounted` hits 0 or stops shrinking. What you mapped stays in the store for the
   next run either way.
   A `WARNING: … annotation node_syms no longer exist` line is the estate
   id-scheme migration signature — prior annotations are orphaned; see the
   migration section in `wicked-garden-domain` for the
   required re-run order.
3. **Never hand-annotate or assert** a rule the harness RISK-flagged. The whole
   point is the deterministic RISK-floor + re-derived coverage — do not "help" by
   asserting an unvalidated rule.

## Vault discipline (model-driven + deterministic)

Extraction is split exactly like the vault:
- **Deterministic backbone (record + verify):** the harness owns enumeration,
  completeness, and a per-write **read-back**; coverage is re-derived COLD by the
  downstream `domain-coverage` phase (`wicked-core coverage`) — never trusted.
- **Model adjunct (analyze):** the per-node rule *statement* is the ONE model call.
  Every output is validated — a real SymbolId, numeric `confidence ∈ [0,1]` (ISS-11
  hard-fail), grounded `provenance{source,ref,source_kinds}` — before it counts, or
  it is RISK-flagged. Model-driven where judgment is needed; deterministic everywhere.

## Config

- `WICKED_ESTATE_BIN` / `WICKED_CORE_BIN` — the peer binaries (resolved by `_clients`; on a
  crew host `WICKED_CORE_EXE`, the engine's own CLI, is used when `WICKED_CORE_BIN` is unset).
- `WICKED_RULE_MODEL_BIN` — the bounded per-node rule model (default `claude -p`).
  Set-but-empty is the kill-switch: no model, so only `--dry-run` (the deterministic stub)
  runs; file mode without `--dry-run` then exits 2 and you state the rules yourself.

## Hard invariants (fail-closed — enforced by the harness + validator)

1. Every requirement has `business_rules` with **minItems 1**.
2. Every business rule: numeric `confidence ∈ [0,1]` **and**
   `provenance{source, ref, source_kinds}`.
3. `legacy_components[]` is non-null, never dropped — the SymbolIds the requirement
   covers.
4. `disposition ∈ {keep, modify, drop, new}`; a `drop` needs a `disposition_reason`.
5. Rule ids: `RULE-`/`VAL-`/`ERR-` + 3–6 zero-padded digits, unique within a requirement.
6. Facts REFERENCE SymbolIds; never embed code/file/line.
7. `metadata.schema_version ∈ {"1.0.0", "1.1.0"}` (1.1.0 adds the optional coverage and
   corroboration fields core emits).

## Depth

- the `wicked-garden-domain` skill's `refs/domain-model-emit.md` — field map + the 7 invariants.
- the `wicked-garden-domain` skill's `refs/extraction-flow.md` — the estate/core CLI surface + the `_clients.py` seam.
