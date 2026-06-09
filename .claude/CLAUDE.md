# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Identity:** see [`ETHOS.md`](../ETHOS.md) for what wicked-garden believes / refuses / optimizes for. CLAUDE.md is *how*; ETHOS.md is *why*.

## Overview

This repository **is** the **wicked-garden** plugin — an AI-Native SDLC delivered as a single Claude Code plugin. The **v11** work-shape archetype model still governs how work is organized (not a fixed pipeline); the current release line is **v12**, whose headline change is the **wicked-loom cutover** — loom is now the sole gate/resolve engine the produces-gate re-derives through (see "Evidence is re-derived"). Each prompt classifies into one or more archetypes; each archetype owns its own phase shape, produces, HITL discipline, and cost band.

The `.claude/` directory contains **development tools** (prefixed `wg-`) for building and maintaining the plugin. These tools are NOT distributed to marketplace users.

## Development Commands

```bash
# Scaffold a new domain component
/wg-scaffold skill my-skill --domain engineering
/wg-scaffold agent my-agent --domain platform
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

### The 9 archetypes

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

Source of truth: `.claude-plugin/archetypes.json`. Detector + steering engine: `scripts/crew/archetypes_v11.py`. Agent playbooks: `skills/archetype/refs/{archetype}.md`. Slash commands: `commands/archetype/{archetype}.md`.

### End-to-end flow

```
prompt
  → UserPromptSubmit hook (hooks/scripts/prompt_submit.py)
  → archetypes_v11.detect_archetypes()
  → emits <wg archetype="X" score="Y" /> system-reminder
  → agent invokes /wicked-garden:archetype:X (or auto-routes)
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
│   ├── components.json
│   └── archetypes.json          # v11 catalog (9 archetypes)
├── commands/
│   ├── archetype/               # 9 slash commands (one per archetype)
│   ├── crew/archive.md          # only legacy crew command kept
│   └── {domain}/                # other domain commands (search, jam, etc.)
├── agents/
│   ├── crew/                    # implementer, researcher, reviewer
│   └── {domain}/                # other domain agents
├── skills/
│   ├── archetype/               # v11 entry point + 9 ref playbooks
│   └── {domain}/                # other domain skills
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

A produces-gate does not pass because an agent claimed "done". It re-derives through **wicked-loom** (a required peer): the gate runs `scripts/qe/vault_gate.py` → `wicked-loom gate`, which shells `wicked-vault cross-check` to re-hash the recorded evidence and **re-run its verifier**, never trusting a cached status. (wicked-vault, on npm `>= 0.3`, is the evidence backend loom re-derives against; the in-process vault path was removed in the v12 loom cutover, so loom is the *sole* gate/resolve engine.) A claimed-but-false "tests pass" is REJECTED; a missing loom — or a vault unresolvable behind it — **fails closed** (`gate: "unavailable"`), never a vacuous pass. Hard gates (review/incident/migrate) additionally require an *independent* attestation — the evaluator is not the agent that did the work (`--with-attestations`). So when building/migrating/etc., **record verifiable evidence** (`wicked-vault record … --run`); don't self-assert completion. loom is resolved at runtime (`WICKED_LOOM_BIN` → config → PATH → `node_modules/.bin` → `npx`); `WICKED_LOOM_CUTOVER=off` disables the gate (fails closed) and `WICKED_VAULT_BIN=""` kill-switches the vault behind it.

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
| A — Advisory/State | ≤8  | State mutation, no dispatch | `commands/intent.md`     |
| B — Write Brief + Dispatch | ≤30 | Session-specific brief needed | (any v11 command)        |
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

**The compiler (`scripts/compiler/`)** — emits a self-contained, vault-backed gate into *any* repo. `compile.py` builds on `phase0/detect.py` (binding detector: test/lint/build commands, ecosystem, claims docs, risk surfaces) → derives a multi-claim contract → writes `<repo>/.wicked/{contract.json, gate.py, README, bindings.json}` (plus `claims_lint.py` when a `claims:` frontmatter doc is detected) and can install triggers (git pre-push hook + GitHub Actions). The emitted `gate.py` is **stdlib-only, imports nothing from the garden** (AST-enforced in tests) and is deliberately **vault-direct** — it resolves `wicked-vault` via `npx`, *not* loom, so it runs in a foreign repo with neither wicked-garden nor wicked-loom present (the garden's own gate uses loom; the emitted gate cannot assume loom is there). Surface: `/wicked-garden:compile <repo> [--trigger hook,ci]` (`commands/compile.md`). The on-switch rule: **compile the trigger + enforcement; never the tool** — the vault is a runtime-resolved utility. Tests: `tests/compiler/test_compile.py`.

## Storage

DomainStore (`scripts/_domain_store.py`) — local JSON files with optional integration-discovery routing to MCP tools. SessionState (`scripts/_session.py`) — per-session shared state. FTS5 + BM25 search is provided by the wicked-bus event store (`scripts/_event_store.py`) and the wicked-brain index — there is no standalone `SqliteStore` module.

Storage paths: `~/.something-wicked/wicked-garden/projects/{slug}/{domain}/{subpath}` (project-scoped via cwd hash). Never hardcode `~/.something-wicked/` paths in consumer code — use `get_local_path()` from `_paths.py` or `_domain_store.py`.

## Naming Conventions

- All names: kebab-case, max 64 chars
- Commands: `wicked-garden:{domain}:{command}` (colon-separated namespace)
- Agents: `wicked-garden:{domain}:{agent-name}`
- Skills: `wicked-garden:{domain}:{skill-name}`
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
- Impact analysis → `/wicked-garden:search:blast-radius`
- Data lineage → `/wicked-garden:search:lineage`
- Fall back to Grep/Glob only when the index is unavailable.

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
- Use `wicked-brain:agent` (context) at the start of a new topic.
- Use `wicked-brain:agent` (session-teardown) at session end.
- Use `wicked-brain:memory` (store mode) to capture non-obvious decisions, patterns, gotchas.
- Always pass `session_id` with search/query calls for access tracking.
- DO NOT read brain files directly — go through skills.
