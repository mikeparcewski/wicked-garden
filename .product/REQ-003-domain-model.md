---
name: REQ-003-domain-model
title: wicked-garden — Domain Model
status: draft
version: 0.1
date: 2026-07-21
author: mike.parcewski@gmail.com
review-required: true
---

# REQ-003 — Domain Model

This document defines the core domain concepts in wicked-garden and their relationships. These are not implementation types — they are the concepts the system is built around. Implementation locations are provided for traceability.

---

## Core Concepts

### WorkShape / Archetype

A **WorkShape** (also called an **Archetype**) is a classification of the *kind of work* a prompt represents — not the *target* of the work (what is being changed) but the *shape* of the work (what kind of human and agent effort it requires).

Ten work-shapes are defined: `triage`, `explore`, `specify`, `decide`, `ship`, `review`, `incident`, `build`, `migrate`, `modernize`.

Each archetype defines:
- **Phases**: the ordered set of activities (e.g., for `migrate`: plan → expand → backfill → cutover → contract).
- **Produces contract**: the artifact or outcome the archetype is accountable for (e.g., shape change artifact + rollback proof).
- **HITL discipline**: how and when human approval is required — `none`, `continuous`, `discrete:<gate>`, or `hard:<gate>`. Hard gates require explicit user approval and block execution until it is given.
- **Cost band**: negligible / low / medium / high — relative signal for token and time cost.
- **next_archetypes**: the set of archetypes that may follow in a multi-archetype sequence.

Source of truth: `.claude-plugin/archetypes.json`. Detection: `scripts/crew/archetypes_v11.py`. Playbooks: `skills/archetype/refs/{archetype}.md`.

Multi-archetype is normal: a schema-changing feature is `build + migrate`; a risky deploy is `ship + review`. The detector returns a scored set, and the catalog declares dependency order via `next_archetypes`.

---

### ProducesGate

A **ProducesGate** is the runtime enforcement mechanism for an archetype's produces contract. It re-derives the "done" claim from recorded evidence rather than accepting an agent's self-assertion.

A ProducesGate:
- Shells `wicked-loom gate` (the gate engine), which in turn shells `wicked-vault cross-check`.
- Re-hashes the recorded evidence and re-runs its verifier.
- Returns green only when the verifier passes and the evidence hash matches.
- Fails closed (`gate: "unavailable"`) when loom, vault, or the evidence record is unresolvable.
- For hard-gate archetypes (review, incident, migrate, modernize), additionally requires an independent attestation — evidence recorded under a distinct actor identity.

The `require=True` default (fail-closed) is the standard gate stance. The `--no-require` option opts back to the legacy claim-only path and is doctrine-light.

Implementation: `scripts/qe/vault_gate.py::gate_satisfied()`.

---

### EvidenceRecord

An **EvidenceRecord** is a tamper-evident record of a test, check, or verification run. It is:
- Written to wicked-vault's append-only store via `wicked-vault record --actor <doer> --run <suite>`.
- Keyed by a content hash of the evidence payload.
- Optionally accompanied by an **Attestation** — a structured claim that the evidence was produced by an independent evaluator (`--with-attestations`, requires vault `>= 0.4.0`).

An EvidenceRecord has:
- `actor`: the identity that produced the evidence (must be explicit for hard-gate paths; `WICKED_VAULT_ACTOR`, default `garden-prove`).
- `created_by_source`: `'explicit'` (acceptable for attestation) or `'env-user'` (rejected by attestation gate).
- `run`: the test suite or verification step.
- `hash`: content hash of the evidence payload (recomputed by the gate on every check).

Evidence records are not readable from the gate's perspective — the gate asks the vault to re-derive, not to retrieve a stored verdict.

---

### WorkUnit

A **WorkUnit** is a tracked unit of agent work within a session — a task, an issue, or a phase. WorkUnits are managed by `scripts/crew/phase_manager.py` (slim project state) and written to the session's audit trail via `scripts/crew/_task_audit_writer.py`.

A WorkUnit carries:
- `archetype`: the detected work-shape.
- `phase`: the current phase name within the archetype's phase shape.
- `state`: pending / in-progress / blocked / done.
- `produces`: the expected artifact or outcome.
- `gate_verdict`: the last ProducesGate result, if a gate has been run.

WorkUnit state is per-session and written to append-only audit files. A new session resumes from the last committed state.

---

### Council

A **Council** is a multi-model evaluation convened by the `wicked-garden-jam` skill's `council` action. It is the mechanism for obtaining independent second opinions from models that did not produce the artifact under review.

A Council:
- Dispatches the evaluation target to one or more external LLM CLIs (Claude Code via Antigravity, Codex, local models) using `Task()` dispatch with isolated contexts.
- Collects structured verdicts from each participant.
- Synthesizes agreement, disagreement, and unresolved tensions.
- Returns a multi-perspective evaluation to the invoking skill.

A Council is not a voting mechanism — the harness or the invoking skill decides how to weight and act on the verdicts. A unanimous council failure can be treated as a hard gate by the consuming archetype playbook.

Implementation: `skills/jam/SKILL.md`, fork worker `wicked-garden-jam-council`.

---

### Skill

A **Skill** is a user-invocable or fork-worker capability surface in wicked-garden. All surfaces are skills — there are no slash commands in the distributed plugin.

Two kinds of skills exist:

**Domain router skill** — user-invocable, one per domain (`wicked-garden-{domain}`). Routes to **actions** (the former per-command surfaces) and loads refs on demand. Located at `skills/{domain}/SKILL.md`.

**Fork worker skill** — `context: fork`, reached only via `Skill()`/`Task()` dispatch from a router skill or archetype playbook. Named `wicked-garden-{domain}-{role}`. Located at `skills/{domain}-{role}/SKILL.md`. May carry `subagent_type: wicked-garden:{domain}:{role}` for pre-v12.25 back-compat.

Skills use progressive disclosure: YAML frontmatter (~100 words, always loaded) → SKILL.md body (≤200 lines, overview + navigation) → `refs/` files (200-300 lines each, loaded on demand). The body must stay slim — it loads into the parent context permanently.

Nine domains ship with the plugin: `engineering`, `platform`, `product`, `data`, `jam`, `search`, `agentic`, `persona`, `smaht`. The `archetype` skill family is a tenth surface (the v11 entry point, not a domain in the domain sense).

---

### Hook

A **Hook** is a lifecycle callback that fires at a named Claude Code event. wicked-garden registers 13 hook events across all `command` type scripts (dispatched through `hooks/scripts/invoke.py`). The three primary hooks are:

- **Bootstrap** (`SessionStart`) — environment setup, peer verification, session initialization.
- **Prompt Submit** (`UserPromptSubmit`) — archetype detection via `archetypes_v11.py`; injects `<wg archetype="X" score="Y" />` system-reminder.
- **Stop** (`Stop`) — session teardown: audit write, event flush.

Hooks are `command` type (deterministic, no token cost). Stop hooks use `"async": true`. Hook scripts are stdlib-only Python (no third-party imports). Hook registration: `hooks/hooks.json`. Scripts: `hooks/scripts/`.

---

### Daemon

The **Daemon** is a Flask server (`daemon/`) that provides long-running operation support for tasks that exceed hook timeout limits or require persistent background processing (e.g., incremental index updates, background event consumption from wicked-bus).

The Daemon is opt-in — it is not required for core plugin function. Skills that need it check for its presence before dispatching long-running operations to it.

---

### Plugin

The **Plugin** is the distributable unit of wicked-garden: the `.claude-plugin/` directory plus `skills/`, `hooks/`, `scripts/`, and `daemon/`.

`plugin.json` declares: name (`wicked-garden`), version (`12.28.1`), description, peer version ranges (`wicked_testing_version`, `wicked_vault_version`, `wicked_brain_version`, `wicked_bus_version`), repository, license, and author. It also holds forward-looking stubs (`_future_userConfig`, `_future_channels`, `_future_lspServers`, `_future_outputStyles`) for Claude Code API surface that is not yet available.

`marketplace.json` — marketplace listing metadata.
`archetypes.json` — the v11 archetype catalog (source of truth for work-shapes).
`components.json` — derived surface manifest, regenerated by `scripts/ci/sync_components.py`.
`specialist.json` — specialist resolver registry, consumed by `scripts/crew/specialist_resolver.py`.

---

## Relationships

```
Prompt
  → UserPromptSubmit Hook
  → archetypes_v11.detect() → WorkShape (one or more)
  → Archetype Skill (wicked-garden-archetype)
  → loads Archetype Playbook (skills/archetype/refs/{archetype}.md)
  → invokes Domain Skills for phase expertise
  → produces WorkUnit(s) tracked by PhaseManager
  → at produces boundary: ProducesGate
      → shells wicked-loom gate
      → shells wicked-vault cross-check
      → re-derives from EvidenceRecord(s)
      → returns green | fail-closed

EvidenceRecord
  → written by agent/skill via wicked-vault record
  → keyed by actor + content hash
  → optionally Attested (requires explicit actor, vault >= 0.4.0)
  → read (re-derived) only by ProducesGate / wicked-loom

Council
  → invoked by jam:council action
  → dispatches to external LLM CLIs via Task()
  → collects Verdicts
  → synthesized result consumed by archetype or developer

Compiler
  → invoked by prove:compile action
  → reads repo bindings (Phase 0 detection)
  → emits stdlib-only gate.py + contract.json into <repo>/.wicked/
  → emitted gate resolves wicked-vault via npx (no wicked-garden runtime required)

wicked-patch
  → reads codegraph.db (wicked-brain structural graph + injected edges)
  → computes affected file set (including injected edges grep cannot see)
  → applies language-specific generator per file
  → produces deterministic multi-file change
```
