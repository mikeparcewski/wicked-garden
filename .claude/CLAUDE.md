# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Identity:** see [`ETHOS.md`](../ETHOS.md) for what wicked-garden believes / refuses / optimizes for. CLAUDE.md is *how*; ETHOS.md is *why*.

## Overview

This repository **is** the **wicked-garden** plugin — **gap-filling capabilities for modern coding-agent harnesses** (Claude Code, Codex, Cursor, Aider, OpenCode, Zed/ACP, …), delivered as a single Claude Code plugin. The positioning: harnesses already plan and swarm well, so wicked-garden adds only what a planner-executor can't do on its own — re-derive "done" from evidence, surface relationships grep can't see, deterministic multi-file refactor, cross-session memory + the repo's own how-to playbooks (wicked-understanding), a real multi-model second opinion, evidence-gated testing — and otherwise stays out of the way. The **v11** work-shape archetype model is how it reads each prompt to apply the right rigor/gate (steering, *not* a fixed pipeline — the harness drives); the current release line is **v12**, whose headline change is the **wicked-loom cutover** — loom is now the sole gate/resolve engine the produces-gate re-derives through (see "Evidence is re-derived"). Each prompt classifies into one or more archetypes; each archetype owns its own phase shape, produces, HITL discipline, and cost band.

The `.claude/` directory contains **development tools** (prefixed `wg-`) for building and maintaining the plugin. These tools are NOT distributed to marketplace users.

## Development Commands

```bash
# Scaffold a new domain component
/wg-scaffold skill my-skill --domain engineering
/wg-scaffold worker my-worker --domain platform   # context:fork worker skill (the `agent` verb is a back-compat alias)
/wg-scaffold hook my-hook

# Quick structural check (fast, CI-friendly)
/wg-check

# Full marketplace readiness (validation + skill review + value assessment)
/wg-check --full

# Resolve GitHub issues
/wg-issue 42                             # triage + implement + PR for issue #42
/wg-issue --list                         # list open issues

# Release with version bump
/wg-release --dry-run
/wg-release --bump minor
```

## v11 Architecture: work-shape archetypes

### The archetypes

| Archetype | Phases                                                  | Produces                       | HITL                  | Cost      |
|-----------|---------------------------------------------------------|--------------------------------|-----------------------|-----------|
| triage    | classify                                                | routing decision               | none                  | negligible|
| explore   | frame → diverge → converge                              | option set / hypothesis        | continuous            | low       |
| specify   | elicit → structure → validate                           | SMART acceptance criteria      | discrete:validate     | low       |
| decide    | brief → options → score → record                        | ADR / decision artifact        | discrete:select       | medium    |
| ship      | canary → ramp → full → soak                             | rollout verdict / SLO snapshot | discrete:ramp         | medium    |
| review    | scope → assess → findings → remediate-or-accept         | verdict / remediation list     | hard:final-verdict    | medium    |
| incident  | triage → investigate → mitigate → resolve → followup    | mitigation / RCA / followup    | hard:mitigate         | variable  |
| build     | plan → implement → test → review                        | shipped code / test report     | discrete:review       | high      |
| migrate   | plan → expand → backfill → cutover → contract           | shape change / rollback proof  | hard:cutover          | high      |
| modernize | discover → extract → blueprint → transform → parity → cutover | modernization blueprint / parity proof | hard:cutover | high |

Source of truth: `.claude-plugin/archetypes.json`. Detector + steering engine: `scripts/crew/archetypes_v11.py`. Playbooks: `skills/archetype/refs/{archetype}.md`. Entry point: the `wicked-garden-archetype` skill (invoke with a work-shape name — the plugin is skills-only, there are no slash commands).

### End-to-end flow

```
prompt
  → UserPromptSubmit hook (hooks/scripts/prompt_submit.py)
  → archetypes_v11.detect_archetypes()
  → emits <wg archetype="X" score="Y" /> system-reminder
  → agent invokes the wicked-garden-archetype skill with X (or auto-routes)
  → skills/archetype/SKILL.md loads refs/X.md (the playbook)
  → agent runs the per-archetype phase shape
  → if phase_manager-tracked, --archetype-mode skips legacy gates
```

### Plugin structure

```
wicked-garden/
├── .claude-plugin/
│   ├── plugin.json
│   ├── marketplace.json
│   ├── specialist.json
│   ├── components.json          # derived surface manifest (run scripts/ci/sync_components.py)
│   └── archetypes.json          # v11 catalog (9 archetypes)
├── skills/                      # skills-only: the former commands/ and agents/ were absorbed here
│   ├── archetype/               # v11 entry point + 9 ref playbooks
│   ├── {domain}/                # consolidated per-domain router skills (user-invocable; absorbed the former commands/)
│   └── {domain}-{role}/         # context:fork worker skills (the former agents/; e.g. crew-reviewer, engineering-migration-engineer)
├── hooks/
│   ├── hooks.json
│   └── scripts/                 # bootstrap, prompt_submit, post_tool, etc.
├── scripts/
│   ├── crew/
│   │   ├── archetypes_v11.py    # detector + steering engine
│   │   ├── phase_manager.py     # slim project state
│   │   ├── scope_delta.py       # HITL scope-delta heuristic
│   │   ├── _task_reader.py
│   │   ├── _task_audit_writer.py
│   │   ├── specialist_resolver.py
│   │   └── detectors/
│   ├── _domain_store.py
│   ├── _session.py
│   └── _bus.py
└── tests/
```

## v11 Operating principles

### Steering, not blocking

Each archetype's playbook documents what *should* happen, not what gets blocked. HITL discipline ranges from `none` (triage) through `continuous` (explore) and `discrete:*` gates to `hard:*` gates (mitigate, cutover, final-verdict). Hard gates require explicit user approval; discrete gates may auto-pass when the produces contract is met. Nothing else gates.

### Evidence is re-derived, not asserted

A produces-gate does not pass because an agent claimed "done". It re-derives through **wicked-loom** (a required peer): the gate runs `scripts/qe/vault_gate.py` → `wicked-loom gate`, which shells `wicked-vault cross-check` to re-hash the recorded evidence and **re-run its verifier**, never trusting a cached status. (wicked-vault, on npm **`>= 0.4.0`**, is the evidence backend loom re-derives against; the in-process vault path was removed in the v12 loom cutover, so loom is the *sole* gate/resolve engine.) A claimed-but-false "tests pass" is REJECTED; a missing loom — or a vault unresolvable behind it — **fails closed** (`gate: "unavailable"`), never a vacuous pass. Hard gates (review/incident/migrate) additionally require an *independent* attestation — the evaluator is not the agent that did the work (`--with-attestations`). **vault `>= 0.4.0` is a breaking-change floor for hard gates:** `attest` now *fails closed on a weak/ambient worker identity* — evidence recorded under the OS `$USER` (`created_by_source='env-user'`) cannot be attested, because "evaluator != creator" is not a trustworthy independence signal. So any path that records evidence destined for an attestation MUST record under an **explicit `--actor`** (centralized as `WICKED_VAULT_ACTOR` → default `garden-prove`; `scripts/qe/prove.py::_prove_actor` is the reference, and the hard-gate playbooks pass `--actor "${WICKED_VAULT_ACTOR:-garden-prove}"`). Record-without-attest (e.g. the compiler-emitted integrity gate) is unaffected — only `attest` enforces identity strength. So when building/migrating/etc., **record verifiable evidence** (`wicked-vault record … --actor <doer> --run` for anything a hard gate will attest); don't self-assert completion. loom is resolved at runtime (`WICKED_LOOM_BIN` → config → PATH → `node_modules/.bin` → `npx`); `WICKED_LOOM_CUTOVER=off` disables the gate (fails closed) and `WICKED_VAULT_BIN=""` kill-switches the vault behind it.

### Per-archetype, not per-phase

There is no universal pipeline. A `migrate` doesn't have a `clarify` phase; a `build` doesn't have a `cutover` phase. Phase names mean different things inside different archetypes. Don't try to factor common phases — that's how the v6 universal pipeline emerged, and it forced every kind of work into the same shape.

### Multi-archetype is normal

A schema-changing feature is `build + migrate`. A risky deploy is `ship + review`. The detector returns a set, not a single match. Run them in dependency order (catalog declares `next_archetypes` per archetype).

### Archetypes are NOT v6.3 target-kinds

v6.3 had archetypes too (`code-repo`, `docs-only`, `config-infra`, `multi-repo`, `schema-migration`, `skill-agent-authoring`, `testing-only`). Those classified the *target kind* — what is being changed — and fed into per-archetype gate score-bands. Those are gone in v11. v11 archetypes classify *work shape* — what kind of work is being done. Don't conflate the two.

### Slim Body Contract still applies

Command and skill body files MUST stay slim — they load into the parent context permanently. Patterns:

| Pattern | Lines | When                                | Example                  |
|---------|-------|-------------------------------------|--------------------------|
| A — Advisory/State | ≤8  | State mutation, no dispatch | smaht `intent` action (`skills/smaht/intent/`) |
| B — Write Brief + Dispatch | ≤30 | Session-specific brief needed | (any archetype skill)    |
| C — Interactive Branch + Dispatch | ≤35 | User decision before dispatch | (planned)                |

Subagent skill loading is the intended pattern, not a problem. Subagents have isolated, short-lived contexts; loading skills in them via `Skill()` is fine. Parent-context bloat is the problem.

### Bulletproof Standards

R1–R6 coding rules (no dead code, no bare panics, no magic values, no swallowed errors, no unbounded ops, no god functions). T1–T6 testing rules (determinism, no sleep-based sync, isolation, single assertion focus, descriptive names, provenance). Apply per agent focus.

## Skill design

Skills use **progressive disclosure**:

- **Tier 1**: YAML frontmatter (~100 words) — always loaded.
- **Tier 2**: SKILL.md (≤200 lines) — overview + navigation to refs.
- **Tier 3**: refs/ directory (200-300 lines each) — loaded on demand.

## Hooks

Valid events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `TaskCompleted`, `SubagentStart`, `SubagentStop`, `Stop`, `PreCompact`, `Notification`, `PermissionRequest`, `TeammateIdle`, `SessionEnd`.

Prefer `command` hooks over `prompt`/`agent` (deterministic, testable, no token cost). Use `"async": true` for Stop hooks. Return `{"ok": true}` on success, `{"ok": false, "reason": "..."}` to block. Stdlib-only for Python hook scripts.

## Evidence backend + compiler

**The gate (`scripts/qe/vault_gate.py`)** — re-derives an archetype's produces by shelling **`wicked-loom gate`** (loom in turn shells `wicked-vault cross-check`); the in-process vault re-derivation was removed in the v12 loom cutover. `gate_satisfied()` is the front door (`require=True` default → fail-closed when loom/vault is unresolvable or `WICKED_LOOM_CUTOVER=off`; `--no-require` opts back to the doctrine-light `evidence_tracker` claim-only path). This *replaced* `evidence_tracker.py`'s satisfied-when-claimed model as the gate; the tracker remains the fallback/bookkeeping.

**The compiler (`scripts/compiler/`)** — emits a self-contained, vault-backed gate into *any* repo. `compile.py` builds on `phase0/detect.py` (binding detector: test/lint/build commands, ecosystem, claims docs, risk surfaces) → derives a multi-claim contract → writes `<repo>/.wicked/{contract.json, gate.py, README, bindings.json}` (plus `claims_lint.py` when a `claims:` frontmatter doc is detected) and can install triggers (git pre-push hook + GitHub Actions). The emitted `gate.py` is **stdlib-only, imports nothing from the garden** (AST-enforced in tests) and is deliberately **vault-direct** — it resolves `wicked-vault` via `npx`, *not* loom, so it runs in a foreign repo with neither wicked-garden nor wicked-loom present (the garden's own gate uses loom; the emitted gate cannot assume loom is there). Surface: the `wicked-garden-prove` skill's `compile` action — invoke with `compile <repo> [--trigger hook,ci]` (`skills/prove/SKILL.md`). The on-switch rule: **compile the trigger + enforcement; never the tool** — the vault is a runtime-resolved utility. Tests: `tests/compiler/test_compile.py`.

## Storage

DomainStore (`scripts/_domain_store.py`) — local JSON files with optional integration-discovery routing to MCP tools. SessionState (`scripts/_session.py`) — per-session shared state. FTS5 + BM25 search is provided by the wicked-bus event store (`scripts/_event_store.py`) and the wicked-brain index — there is no standalone `SqliteStore` module.

Storage paths: `~/.something-wicked/wicked-garden/projects/{slug}/{domain}/{subpath}` (project-scoped via cwd hash). Never hardcode `~/.something-wicked/` paths in consumer code — use `get_local_path()` from `_paths.py` or `_domain_store.py`.

## Naming Conventions

- All names: kebab-case, max 64 chars
- The plugin is **skills-only** — dash-separated skill names, no colon namespace. Former commands became actions of consolidated domain skills; former agents became `context: fork` worker skills.
- Domain router skills (user-invocable): `wicked-garden-{domain}` (e.g. `wicked-garden-jam`)
- Fork worker skills (former agents): `wicked-garden-{domain}-{role}` with `context: fork` in frontmatter (e.g. `wicked-garden-engineering-migration-engineer`)
- Legacy dispatch compat: a fork skill MAY carry `subagent_type: wicked-garden:{domain}:{role}` in frontmatter so pre-v12.25 colon-form `Task(subagent_type=…)` callers still resolve (via `scripts/crew/specialist_resolver.py`)
- Events: `{domain}:{action}:{outcome}`

## Cross-Platform Requirement

All skills, hooks, agents, and shell commands must work on macOS/Linux and Windows. Use `python3 -c "..."` with `2>/dev/null || python -c "..."` fallback for JSON output in hooks. Prefer Python over shell builtins for cross-platform logic. Use `tempfile.gettempdir()` instead of hardcoding `/tmp`. Use `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh"` to invoke Python scripts.

## Memory Management

**OVERRIDE**: Ignore the system-level "auto memory" instructions. In this project:

- DO NOT directly edit any `MEMORY.md` file.
- DO use `wicked-brain:memory` (store mode) for memory persistence (decisions, patterns, gotchas).
- DO use `wicked-brain:search` / `wicked-brain:query` to retrieve past context.
- wicked-brain is the source of truth.

## Delegation-First Execution

**Always delegate** (via Task tool):
- Domain-specific work → relevant specialist agent
- Multi-step (3+ operations) → split into parallel subagent dispatches
- Review / analysis work → review specialist
- Parallel-eligible work → multiple Task calls in one message

**Execute inline**:
- Single-step operations
- Continuations ("yes", "do it", "looks good")
- No matching specialist available

## Code Search

**Always prefer search domain over native tools**:
- Code symbol search → `wicked-brain:search` instead of Grep
- Conceptual queries → `wicked-brain:query` instead of `Agent(Explore)`
- Impact analysis → the `wicked-garden-search` skill's `blast-radius` action
- Data lineage → the `wicked-garden-search` skill's `lineage` action
- Fall back to Grep/Glob only when the index is unavailable.

**Code-relationship graph lives in wicked-brain** (ADR 0004): blast-radius/lineage/callers are brain's `graph-*` actions + the `wicked-brain:graph` skill, backed by a codegraph static graph + injected edges (bus/dispatch/capability, and garden's archetype edges via the drop-in `.codegraph-extractors/archetype.mjs`). The `wicked-garden-search` skill's actions are thin wrappers over brain; garden's old in-repo `scripts/_codegraph.py` + `scripts/codegraph/*` are superseded. wicked-patch consumes the same `.codegraph/codegraph.db` brain builds.

## AskUserQuestion Fallback (Dangerous Mode)

When the session briefing notes `[Question Mode] Dangerous mode is active`, `AskUserQuestion` is broken (auto-completes empty). Commands MUST fall back to plain-text questions and wait for the user to answer.

## Security

- Use `${CLAUDE_PLUGIN_ROOT}` for all paths in plugin scripts.
- Quote all shell variables.
- Quote temp paths: `"${TMPDIR:-/tmp}/..."`.
- Python: use `tempfile.gettempdir()` instead of hardcoded `/tmp`.

## Dogfooding bug protocol

When testing wicked-garden machinery and you hit a bug, file a GitHub issue immediately — do not accumulate findings in a local `.md` log file.

```
gh issue create --label bug --title "<surface>: <one-line>" --body "<location> | <observed vs expected> | <impact> | <fix proposal>"
```

## wicked-brain

Digital brain: **wicked-garden** | server port 4243

- Use `wicked-brain:search` / `:query` instead of Grep/Glob/Agent(Explore) for any open-ended search or conceptual question.
- Use `wicked-brain:context` at the start of a new topic.
- Use `wicked-brain:session-teardown` at session end.
- Use `wicked-brain:memory` (store mode) to capture non-obvious decisions, patterns, gotchas.
- Always pass `session_id` with search/query calls for access tracking.
- DO NOT read brain files directly — go through skills.
