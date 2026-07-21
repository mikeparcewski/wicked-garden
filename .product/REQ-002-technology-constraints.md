---
name: REQ-002-technology-constraints
title: wicked-garden — Technology Constraints
status: draft
version: 0.1
date: 2026-07-21
author: mike.parcewski@gmail.com
review-required: true
---

# REQ-002 — Technology Constraints

## Runtime Environment

**Claude Code plugin API** — wicked-garden is delivered as a Claude Code plugin (`/plugin install wicked-garden`). All user-facing surfaces are Claude Code skills (frontmatter-described SKILL.md files). The plugin exposes no slash commands in its distributed form; the `.claude/` developer tools (`/wg-*`) are development-only.

**Node.js / Python dual runtime** — skills are Markdown files loaded by Claude Code; imperative logic lives in Python scripts under `scripts/` and `hooks/scripts/`. Node.js is required for wicked-bus (the event audit substrate) and for npm-installed peers. Python 3 is required for all hook scripts, the archetype detector, the compiler, the evidence gate, and domain store utilities. Both runtimes must be present in the agent's execution environment.

**Cross-platform requirement** — all skills, hook scripts, and shell commands must work on macOS, Linux (x86_64 and arm64), and Windows (Git Bash and WSL). Native PowerShell is a secondary target. Specific constraints:
- Hook scripts use `python3 -c "..."` with `2>/dev/null || python -c "..."` fallback.
- Temp paths use `tempfile.gettempdir()`, not hardcoded `/tmp`.
- JSON output in hooks uses Python, not shell builtins (`printf`, `echo`), which differ across platforms.
- Python scripts are invoked via `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh"` for cross-platform resolution.

---

## Required Peers

Two peers are required for the evidence gate to function. Both are verified by `/wicked-garden-core setup`:

| Peer | npm Package | Required Version | Role |
|------|-------------|-----------------|------|
| wicked-vault | `wicked-vault` | `>= 0.4.0` | Evidence backend — records, re-hashes, and verifies evidence attestations |
| wicked-loom | `wicked-loom` | resolved at runtime | Gate engine — shells `wicked-vault cross-check`; the sole gate/resolve path since v12 loom cutover |

wicked-vault `>= 0.4.0` is a breaking-change floor for hard gates: `attest` now fails closed on a weak/ambient worker identity (`created_by_source='env-user'`). Evidence for hard-gate attestation must be recorded under an explicit `--actor` (default: `WICKED_VAULT_ACTOR` env var, fallback `garden-prove`).

wicked-loom is resolved at runtime in this order: `WICKED_LOOM_BIN` env var → config → PATH → `node_modules/.bin` → `npx`. Setting `WICKED_LOOM_CUTOVER=off` disables the gate (fails closed). Setting `WICKED_VAULT_BIN=""` kill-switches the vault behind loom.

Three additional peers are opt-in:

| Peer | npm Package | Required Version | Role |
|------|-------------|-----------------|------|
| wicked-testing | `wicked-testing` | `^0.8.0` | Acceptance testing gate; also installs wicked-vault as a transitive dependency |
| wicked-brain | `wicked-brain` | `^0.18.0` | Cross-session memory, code graph, semantic search |
| wicked-bus | `wicked-bus` | `^2.0.0` | Event audit trail, append-only event store, FTS5 search |

wicked-understanding (repo playbooks from HEAD) and codegraph (structural code intelligence) are additional optional integrations.

---

## Storage

**Local JSON files** — default persistence layer via `DomainStore` (`scripts/_domain_store.py`). Paths are project-scoped: `~/.something-wicked/wicked-garden/projects/{slug}/{domain}/{subpath}` where `slug` is derived from `cwd` hash. Consumer code must use `get_local_path()` from `_paths.py` or `_domain_store.py` — never hardcode the base path.

**SQLite (via peers)** — wicked-brain provides FTS5 + BM25 search over the code graph and indexed content. wicked-bus provides an append-only event store with FTS5 search. wicked-vault provides an append-only evidence store. No standalone SQLite module in wicked-garden itself.

**SessionState** (`scripts/_session.py`) — per-session ephemeral shared state. Does not persist across process restarts.

**codegraph.db** — wicked-brain builds and maintains this structural code graph at `.codegraph/codegraph.db`. wicked-patch consumes it for multi-file refactor operations.

---

## Plugin Architecture Constraints

**Skills-only** — the plugin exposes only skills. Former command surfaces and agent surfaces were absorbed into consolidated domain skills (domain router skills) and fork worker skills respectively as of v12.25. A domain router skill is user-invocable (`wicked-garden-{domain}`); a fork worker skill carries `context: fork` and is reached only via `Skill()`/`Task()` dispatch from another skill.

**Slim body contract** — skill body files must stay slim (loaded into parent context permanently). Three patterns apply:
- Pattern A (Advisory/State): ≤ 8 lines. For state mutation with no dispatch.
- Pattern B (Write Brief + Dispatch): ≤ 30 lines. For session-specific work.
- Pattern C (Interactive Branch + Dispatch): ≤ 35 lines. For user-decision-before-dispatch flows.

Refs (the detailed content) live in `skills/{domain}/refs/` files (200-300 lines each) and are loaded on demand.

**Hooks** — three active hook types: `SessionStart` (bootstrap: environment setup, peer verification), `UserPromptSubmit` (archetype detection, system-reminder injection), `Stop` (teardown: session audit write). Hooks use `command` type over `prompt`/`agent` for determinism and zero token cost. Stop hooks use `"async": true`. Bootstrap and Stop hooks return `{"ok": true}` on success; `{"ok": false, "reason": "..."}` blocks the event. The UserPromptSubmit hook returns `{"continue": true}` to proceed (with `hookSpecificOutput` for injected context) or `{"continue": false}` to block. All hook scripts are stdlib-only Python.

**Daemon** (`daemon/`) — a Flask server for long-running operations (e.g., indexing, background event processing). Not required for core plugin function; opt-in for operations that exceed hook timeout limits.

---

## Dependency and Versioning Constraints

**No mandatory cloud infrastructure** — all storage is local-first. No API keys required for wicked-garden itself (LLM calls go through the harness; external LLM CLIs for the council are the user's responsibility to configure).

**Offline operation** — the plugin must function without network access except for LLM inference calls (which the harness manages). The evidence gate, compiler, archetype detector, wicked-patch, and all skill logic operate offline.

**Plugin install path** — `npm install -g wicked-garden` or `/plugin install wicked-garden` via the Claude Code marketplace. The plugin does not require a global npm install to function; the marketplace path is the primary distribution channel.

**Peer version pins** — pinned in `plugin.json` as version ranges (`^` or `>=`). The wicked-vault floor (`>= 0.4.0`) is a hard constraint for hard gates; running an older vault behind loom silently degrades to `gate: "unavailable"`.

**Event naming** — all wicked-garden events on the bus follow the 4-segment format `wicked.<domain>.<noun>.<past-tense-verb>` per the ecosystem event grammar (WICKED_GARDEN_BUS_EVENTS.md). Divergence from this format is a contribution defect.

---

## Non-Functional Constraints

**Gate semantics: fail-closed** — a gate that cannot re-derive its claim must not pass. `gate: "unavailable"` is the only valid non-green verdict when the backend is unreachable. There is no fallback to self-assertion.

**Audit trail: append-only** — all evidence records and gate verdicts are append-only. No verdict is overwritten or deleted.

**Actor identity for hard gates** — evidence recorded under ambient OS identity (`$USER`) cannot satisfy a hard-gate attestation (vault `>= 0.4.0` enforcement). The `WICKED_VAULT_ACTOR` env var (default: `garden-prove`) must be set correctly for hard-gate paths. `scripts/qe/prove.py::_prove_actor` is the reference.

**Compiler emits stdlib-only gate** — the emitted `gate.py` from the compiler must be stdlib-only (AST-enforced in `tests/compiler/test_compile.py`). It resolves wicked-vault via `npx`, not loom. This constraint ensures the compiled gate runs in any repo with no wicked-garden or wicked-loom present.
