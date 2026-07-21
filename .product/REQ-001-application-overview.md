---
name: REQ-001-application-overview
title: wicked-garden — Application Overview
status: draft
version: 0.1
date: 2026-07-21
author: mike.parcewski@gmail.com
review-required: true
---

# REQ-001 — Application Overview

## Purpose

wicked-garden is a Claude Code plugin (v12.28.1) that fills the gaps modern coding-agent harnesses cannot close alone. The premise is direct: harnesses — Claude Code, Codex, Cursor, Aider, OpenCode, Zed/ACP, and others — already plan, parallelize, and execute well. wicked-garden does not compete with that; it adds only what a planner-executor genuinely cannot do on its own:

- **Evidence-gated done** — re-derives "done" from recorded evidence via the internal loom engine and wicked-vault; a self-asserted "tests pass" cannot lie its way green.
- **Relationships grep cannot see** — codegraph + injected event-bus/dispatch/capability edges power blast-radius and lineage analysis.
- **Deterministic multi-file refactor** — wicked-patch applies graph-driven renames and field additions across an entire codebase without leaving silent half-applied states.
- **Cross-session memory** — wicked-brain persists decisions, patterns, and gotchas across sessions; knowledge that only lives in chat history does not exist.
- **Real multi-model second opinions** — the jam:council skill convenes external LLM CLIs (Claude Code, Antigravity, Codex, local models) for independent evaluation; it is not the model talking to itself.
- **Portable evidence gates** — the compiler (`/wicked-garden-prove compile`) emits a self-contained vault-backed gate into any repo that re-derives claims with no wicked-garden runtime present.

The core invariant: **done is re-derived, not asserted.** A gate does not go green because an agent or human said so. Evidence is re-hashed and its verifier re-run through wicked-loom on every gate check. A missing evidence backend fails closed — it never invents a pass.

Work-shape detection is how wicked-garden applies the right rigor without imposing a fixed pipeline. Each prompt classifies into one or more of **ten work-shape archetypes** (triage, explore, specify, decide, ship, review, incident, build, migrate, modernize). Each archetype owns its own phase shape, produces contract, and HITL discipline. The harness drives; wicked-garden steers by archetype.

The plugin installs via `/plugin install wicked-garden` into any Claude Code session. It is skills-only: user entry points are consolidated per-domain skills. There are no slash commands in the distributed plugin — the `.claude/` dev tools (`/wg-*`) are development-only surfaces not shipped to marketplace users.

---

## Core User Flows

### Flow 1 — Archetype-steered session: from prompt to phased execution

1. Developer submits a prompt in Claude Code (e.g., "add a NOT NULL column to the users table and backfill existing rows").
2. The `UserPromptSubmit` hook fires `hooks/scripts/prompt_submit.py`, which calls `scripts/crew/archetypes_v11.py::detect_archetypes()`.
3. The detector scores the prompt against all ten archetype definitions and emits a `<wg archetype="migrate" score="0.91" />` system-reminder (or a multi-archetype set, e.g., `build+migrate`).
4. The harness invokes the `wicked-garden-archetype` skill with the detected work-shape name. The skill loads `skills/archetype/refs/migrate.md` — the migrate playbook.
5. The playbook defines the phase shape (plan → expand → backfill → cutover → contract), produces contract (shape change artifact, rollback proof), HITL gate at cutover (hard gate: requires explicit approval), and cost band (high).
6. The harness executes the phases. At the cutover hard gate, execution pauses and surfaces the gate to the user. Approval unblocks; rejection rolls back.
7. At phase completion the produces-gate re-derives the claim via wicked-loom. A missing verifier or unresolvable evidence backend fails closed.

**Outcome**: the developer gets appropriately-scaled rigor for a schema migration — not the same lightweight flow as a typo fix, and not an arbitrary fixed pipeline.

---

### Flow 2 — Evidence gate: re-deriving done from recorded evidence

1. A build phase completes. The agent records evidence via `wicked-vault record --actor garden-prove --run <test-suite>`. Evidence is stored in the vault's append-only store with a content hash and the actor identity.
2. At the produces gate, the agent invokes `scripts/qe/vault_gate.py::gate_satisfied()`. The gate shells `wicked-loom gate`, which in turn shells `wicked-vault cross-check`.
3. wicked-vault re-hashes the recorded evidence and re-runs the verifier. If the evidence hash matches and the verifier passes, the gate returns green. If evidence is missing, the hash does not match, or loom/vault is unresolvable, the gate **fails closed** — it returns `gate: "unavailable"`, never a vacuous pass.
4. For hard gates (review, incident, migrate archetypes), the gate additionally requires an independent attestation recorded under a distinct `--actor` identity. Evidence recorded under the ambient OS `$USER` (`created_by_source='env-user'`) cannot satisfy an attestation gate — the evaluator-must-not-equal-creator constraint is enforced structurally, not by convention.
5. The gate verdict is appended to the session's audit trail. Subsequent sessions resume from the recorded verdict without re-running the gate unless evidence changes.

**Outcome**: "done" is a re-derived claim backed by tamper-evident evidence, not a self-assertion that can lie its way green.

---

### Flow 3 — Compiler: emitting a portable gate into a foreign repo

1. A developer in a repo that does not have wicked-garden installed wants a build gate that re-derives claims on push and in CI.
2. They (or an agent with wicked-garden) invoke the `wicked-garden-prove` skill's `compile` action: `/wicked-garden-prove compile <repo> --trigger hook,ci`.
3. The compiler (`scripts/compiler/compile.py`) runs Phase 0 detection: it identifies the ecosystem (Node, Python, Rust, etc.), locates test/lint/build commands, identifies claims documents (files with `claims:` frontmatter), and maps risk surfaces.
4. It derives a multi-claim contract and writes four files into `<repo>/.wicked/`: `contract.json`, `gate.py`, `README`, `bindings.json`. When a claims document is detected, it also writes `claims_lint.py`.
5. The emitted `gate.py` is stdlib-only, imports nothing from wicked-garden, and resolves `wicked-vault` via `npx` — so it runs in any repo with neither wicked-garden nor wicked-loom present.
6. With `--trigger hook,ci`, the compiler also installs a git pre-push hook and a GitHub Actions workflow. Every push re-derives the gate claims; a failing gate blocks the push.

**Outcome**: the evidence-gate guarantee outlives the session that created it and requires no wicked-garden runtime in the target repo.

---

### Flow 4 — Multi-model council: independent second opinion

1. An agent or developer wants a structural evaluation of an architecture proposal that is not self-graded — the model should not review its own work.
2. They invoke the jam:council action: `/wicked-garden-jam council <proposal>`.
3. The `wicked-garden-jam-council` fork worker skill convenes an evaluation session. It dispatches the proposal to available external LLM CLIs (Claude Code via Antigravity/Codex, and any locally-configured model) using `Task()` dispatch with isolated contexts.
4. Each model evaluates the proposal independently, returning a structured verdict (findings, concerns, confidence). The council skill synthesizes the responses: agreement, disagreement, and unresolved tensions.
5. The synthesized output is returned as a multi-perspective evaluation. The harness can treat a unanimous council failure as a hard gate.

**Outcome**: the developer receives an independent evaluation from models that did not produce the work, structurally preventing self-grading.

---

### Flow 5 — wicked-patch: deterministic multi-file refactor

1. A developer needs to rename a domain type across a large codebase — source files, tests, migration files, configuration, and documentation.
2. They invoke the patch skill: `/wicked-garden-engineering rename OldName NewName`.
3. The `wicked-garden-engineering-patch` nested skill reads the codegraph from wicked-brain (`scripts/codegraph/codegraph.db`), identifies all nodes referencing `OldName`, and computes the full set of affected files including injected edges (bus producer→consumer, dispatch links) that grep cannot see.
4. The skill shows the patch plan (files affected, kinds of change, risk surface). The developer approves or scopes the change.
5. On approval, the patch applies deterministically using the language-specific generator for each file type. Generators exist out of the box for Python, TypeScript, Java, Go, SQL, Rust, Kotlin, C#, PHP, and Ruby. A `new-generator` action lets contributors add additional languages.
6. The result is a complete, consistent rename across every file that references the symbol — including the relationships grep cannot see.

**Outcome**: multi-file refactor is a graph operation, not a search-and-replace that leaves injected-edge references broken.
