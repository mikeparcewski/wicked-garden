---
name: DES-001-technical-design
title: wicked-garden — Technical Design
status: draft
version: 0.1
date: 2026-07-21
author: mike.parcewski@gmail.com
review-required: true
---

# DES-001 — Technical Design

## Overview

wicked-garden is delivered as a Claude Code plugin. Its runtime is the Claude Code harness; its surfaces are skills (Markdown files with YAML frontmatter loaded by the harness). Imperative logic — archetype detection, evidence gate, compiler, domain store, session state, event bus integration — lives in Python scripts under `scripts/` and `hooks/scripts/`. No server-side component is required for core function (the Flask daemon is opt-in).

The plugin is **skills-only** as of v12.25. There are no slash commands in the distributed artifact. Three hook types fire at harness lifecycle events. A daemon provides optional long-running operation support.

---

## Plugin Architecture

### Directory Structure

```
wicked-garden/
├── .claude-plugin/
│   ├── plugin.json              # version, peer ranges, metadata
│   ├── marketplace.json         # listing metadata
│   ├── archetypes.json          # v11 archetype catalog (source of truth)
│   ├── components.json          # derived skill surface manifest (generated)
│   └── specialist.json          # specialist resolver registry
├── skills/
│   ├── archetype/               # v11 entry point + 10 ref playbooks
│   │   └── refs/{archetype}.md  # one playbook per work-shape
│   ├── {domain}/                # domain router skills (user-invocable)
│   │   ├── SKILL.md             # frontmatter + slim body
│   │   └── refs/                # on-demand rubrics and content
│   └── {domain}-{role}/         # fork worker skills (context:fork)
│       └── SKILL.md
├── hooks/
│   ├── hooks.json               # hook registration
│   └── scripts/                 # stdlib-only Python scripts
│       ├── bootstrap.py         # SessionStart
│       ├── prompt_submit.py     # UserPromptSubmit → archetype detection
│       └── stop.py              # Stop → teardown
├── scripts/
│   ├── crew/
│   │   ├── archetypes_v11.py    # detector + steering engine
│   │   ├── phase_manager.py     # slim project state
│   │   ├── scope_delta.py       # HITL scope-delta heuristic
│   │   ├── specialist_resolver.py
│   │   ├── _task_reader.py
│   │   ├── _task_audit_writer.py
│   │   └── detectors/           # per-archetype detection helpers
│   ├── qe/
│   │   ├── vault_gate.py        # ProducesGate: shells wicked-loom gate
│   │   ├── prove.py             # evidence recording with actor logic
│   │   └── evidence_tracker.py  # legacy claim-only tracker (fallback/bookkeeping)
│   ├── compiler/
│   │   ├── compile.py           # top-level compiler entry
│   │   └── phase0/detect.py     # ecosystem/binding detection
│   ├── _domain_store.py         # local JSON persistence with optional MCP routing
│   ├── _session.py              # per-session shared state
│   ├── _bus.py                  # wicked-bus event emission
│   └── _paths.py                # project-scoped path resolution
├── daemon/                      # optional Flask server
└── tests/                       # unit tests (pytest)
```

### Skill Loading and Progressive Disclosure

All skill SKILL.md files are loaded into the harness context on invocation. Frontmatter is always loaded. The body is loaded when the skill is invoked. Refs are loaded on demand via `Skill()` dispatch from the body.

The slim body contract enforces three body patterns:
- **Pattern A** (≤ 8 lines): state mutation, advisory output. No dispatch.
- **Pattern B** (≤ 30 lines): write a session-specific brief, then dispatch to a ref or worker.
- **Pattern C** (≤ 35 lines): interactive branch to get a user decision, then dispatch.

Refs files are the heavy content layer (200-300 lines). Subagent contexts are short-lived and isolated; loading refs in them via `Skill()` is the intended pattern. Parent-context bloat is the problem being avoided.

---

## Archetype Detection Flow

The archetype detection pipeline runs on every user prompt via the `UserPromptSubmit` hook.

```
User submits prompt
  → Claude Code fires UserPromptSubmit event
  → hooks/scripts/prompt_submit.py
  → calls scripts/crew/archetypes_v11.py::detect_archetypes(prompt_text)
  → detector scores prompt against all 10 archetype definitions
      (each archetype definition is in archetypes.json; per-archetype
       helpers in scripts/crew/detectors/ refine scores)
  → returns sorted list of (archetype_name, score) pairs above threshold
  → hook script emits system-reminder:
      <wg archetype="migrate" score="0.91" />
      (or multi-archetype: <wg archetype="build,migrate" score="0.85,0.72" />)
  → hook returns {"ok": true}

Harness injects system-reminder into context
  → harness (or agent) invokes wicked-garden-archetype skill
      with detected work-shape name
  → skill body dispatches to skills/archetype/refs/{archetype}.md
  → playbook defines phase shape, produces contract, HITL discipline
  → agent executes phases; invokes domain skills for expertise
```

The detector is a scoring function, not a classifier — it returns a set with scores, not a single label. Multi-archetype is normal. The harness executes archetypes in dependency order declared by `next_archetypes` in `archetypes.json`.

Archetype detection is **steering, not blocking**. The system-reminder is advisory; the harness decides whether to invoke the archetype skill. No gate blocks execution based on classification alone.

---

## Evidence Gate Mechanics

The evidence gate is the v12 loom cutover architecture: loom is the sole gate/resolve engine. The in-process vault re-derivation path was removed at v12 loom cutover.

```
agent/skill calls gate_satisfied() in scripts/qe/vault_gate.py
  → (require=True, the default: fail-closed stance)
  → resolves wicked-loom binary:
      WICKED_LOOM_BIN env → config → PATH → node_modules/.bin → npx
  → if WICKED_LOOM_CUTOVER=off:
      return {"gate": "unavailable", "reason": "loom cutover disabled"}
  → shells: wicked-loom gate [--archetype X] [--with-attestations]
  → wicked-loom shells: wicked-vault cross-check [--actor WICKED_VAULT_ACTOR]
  → wicked-vault:
      re-hashes evidence payload (content hash)
      re-runs the evidence verifier
      checks actor identity for attestation requests:
        - explicit actor → acceptable
        - env-user → rejected (vault >= 0.4.0 breaking change)
  → wicked-loom returns structured gate result
  → gate_satisfied() interprets:
      green: verifier passed, hash matched, actor acceptable
      fail-closed: any failure → {"gate": "unavailable"} or {"gate": "fail"}
      never: vacuous pass when evidence is missing
```

**Actor identity for hard gates**: the `WICKED_VAULT_ACTOR` env var (default `garden-prove`) is the identity under which evidence is recorded and attested. `scripts/qe/prove.py::_prove_actor()` is the reference for resolving the actor at runtime. Hard-gate playbooks pass `--actor "${WICKED_VAULT_ACTOR:-garden-prove}"` explicitly.

**Legacy path**: `evidence_tracker.py` (claim-only, no re-derivation) remains as a fallback and bookkeeping layer. `gate_satisfied(require=False)` opts back to the claim-only path. This path does not satisfy any hard gate.

**Kill switches**:
- `WICKED_LOOM_CUTOVER=off` — disables the gate. Gate returns `unavailable`.
- `WICKED_VAULT_BIN=""` — kills the vault behind loom. Gate fails closed.

---

## Multi-Model Council Flow

The council is a structured independent evaluation, not a simulation of multiple viewpoints by a single model.

```
Developer/skill invokes wicked-garden-jam council <target>
  → wicked-garden-jam-council fork worker skill activated
  → worker enumerates available external LLM CLIs
      (Claude Code via Antigravity, Codex, local models — configured per session)
  → for each available participant:
      Task(subagent_type=..., prompt=council_prompt_for(participant, target))
      → isolated context: no shared state with invoking session
      → participant evaluates target and returns structured verdict
          (findings, concerns, confidence)
  → council skill collects all verdicts
  → synthesizes: agreement points, disagreement points, unresolved tensions
  → returns multi-perspective evaluation to invoking skill or developer

Harness (or invoking archetype) decides how to weight verdicts:
  → unanimous failure may be treated as a hard gate
  → mixed results surface as findings for developer resolution
```

The council is the only mechanism in wicked-garden for genuine independent multi-model evaluation. The `quick` action in the jam skill is a single-model lightweight exploration — not a council.

---

## wicked-patch: Graph-Driven Multi-File Refactor

wicked-patch is the deterministic multi-file transformation engine. It is exposed as the nested `wicked-garden-engineering-patch` skill under the engineering domain.

```
Developer invokes patch action: /wicked-garden-engineering patch-plan OldName
  → engineering-patch skill reads codegraph from wicked-brain:
      .codegraph/codegraph.db (structural graph, tree-sitter)
      + injected edges (bus producer→consumer, dispatch, capability)
  → computes full affected file set:
      direct references (grep-visible)
      + injected-edge references (not grep-visible)
  → returns patch plan: files × change-kinds × risk surface

Developer approves (or scopes) the plan

Developer invokes apply: /wicked-garden-engineering apply <patch-file>
  → for each affected file:
      selects language generator (Python, TypeScript, Java, Go, SQL,
       Rust, Kotlin, C#, PHP, Ruby — out of the box)
      generator applies the transformation (rename, add-field, remove)
      writes the changed file
  → result: deterministic, complete, consistent transformation
```

New language support: `/wicked-garden-engineering new-generator` creates a generator for an additional language. Generators implement a documented interface; adding one requires no change to the patch core.

wicked-patch and wicked-brain share the same codegraph database (`.codegraph/codegraph.db`). The `wicked-garden-search index` action refreshes both layers — brain (semantic) and codegraph (structural).

---

## Compiler Architecture

The compiler emits a self-contained vault-backed gate into any repo — no wicked-garden or wicked-loom runtime required in the target.

```
Developer invokes: /wicked-garden-prove compile <repo> [--trigger hook,ci]
  → scripts/compiler/compile.py entry point
  → Phase 0 detection (scripts/compiler/phase0/detect.py):
      identifies ecosystem (Node, Python, Rust, ...)
      locates test/lint/build commands (binding detection)
      identifies claims documents (files with claims: frontmatter)
      maps risk surfaces
  → derives multi-claim contract
  → writes to <repo>/.wicked/:
      contract.json   — the derived contract
      gate.py         — stdlib-only, vault-direct gate script
      bindings.json   — ecosystem bindings
      README.md       — usage instructions
      claims_lint.py  — written when claims: frontmatter doc is detected
  → if --trigger hook:
      installs git pre-push hook that runs gate.py
  → if --trigger ci:
      writes GitHub Actions workflow that runs gate.py
```

The emitted `gate.py` is vault-direct: it resolves `wicked-vault` via `npx`, not loom. This is intentional — the compiled gate cannot assume wicked-loom is present in the target repo. The garden's own gate uses loom; the emitted gate does not.

AST enforcement: `tests/compiler/test_compile.py` verifies that the emitted `gate.py` is stdlib-only (no third-party imports, no wicked-garden imports). This test is part of CI.

The on-switch rule: **compile the trigger and the enforcement; never compile the tool**. The vault is a runtime-resolved utility, not a compiled-in dependency. The guarantee is self-contained without shipping wicked-garden.

---

## Storage and State

### DomainStore (`scripts/_domain_store.py`)

Local JSON files with optional integration-discovery routing to MCP tools. Project-scoped paths via `scripts/_paths.py`. Path structure: `~/.something-wicked/wicked-garden/projects/{slug}/{domain}/{subpath}`. Do not hardcode the base path in consumer code.

### SessionState (`scripts/_session.py`)

Per-session ephemeral shared state. Not persisted across process restarts. Used for in-session coordination between skills and hooks.

### Event Store (`scripts/_bus.py`)

wicked-bus integration. Emits events in 4-segment format (`wicked.<domain>.<noun>.<past-tense-verb>`). The bus provides at-least-once delivery, append-only event records, and FTS5 search via the wicked-bus backing store.

### codegraph.db

Structural code graph built and maintained by wicked-brain at `.codegraph/codegraph.db`. Consumed by wicked-patch. The `search:index` action refreshes it.

---

## Hook Architecture

Three active hooks, all `command` type:

| Hook | Event | Script | Purpose |
|------|-------|--------|---------|
| Bootstrap | `SessionStart` | `hooks/scripts/bootstrap.py` | Environment setup; peer verification (`/wicked-garden-core setup` flow); session initialization |
| Prompt Submit | `UserPromptSubmit` | `hooks/scripts/prompt_submit.py` | Archetype detection; system-reminder injection |
| Stop | `Stop` | `hooks/scripts/stop.py` | Session teardown; audit write; event flush |

Hook scripts are stdlib-only Python — no third-party imports. All hooks return `{"ok": true}` on success. A hook returning `{"ok": false, "reason": "..."}` blocks the triggering event. The Stop hook uses `"async": true` to avoid blocking session shutdown.

Hook scripts access `CLAUDE_PLUGIN_ROOT` to construct paths. All shell variables are quoted. Temp paths use `tempfile.gettempdir()`.

---

## Daemon (Optional)

The Flask daemon (`daemon/`) provides:
- Long-running operation support for indexing and background event processing.
- A local HTTP API for skills to dispatch work that exceeds hook timeout limits.
- Not required for any core plugin capability.

Skills check for daemon availability before dispatching to it. If the daemon is absent, skills fall back to synchronous inline execution.

---

## Peer Integration Points

| Peer | Integration Point | How Resolved |
|------|------------------|-------------|
| wicked-vault | `scripts/qe/vault_gate.py`, `scripts/qe/prove.py` | `WICKED_VAULT_BIN` env → PATH → `npx wicked-vault` |
| wicked-loom | `scripts/qe/vault_gate.py` | `WICKED_LOOM_BIN` env → config → PATH → `node_modules/.bin` → `npx` |
| wicked-testing | `scripts/qe/` (acceptance pipeline) | Installed peer; invoked by acceptance skills |
| wicked-brain | `scripts/crew/`, search/smaht skills | Brain server on port 4243; auto-starts on skill invocation |
| wicked-bus | `scripts/_bus.py` | Installed peer; event emit/consume |
| codegraph | `.codegraph/codegraph.db` | Built by wicked-brain; consumed by patch skill |

All peers degrade gracefully on absence — except the evidence gate, which fails closed when vault or loom is unreachable. A transient peer outage never invents a pass.
