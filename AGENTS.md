# Agent Instructions

> **Identity:** see [`ETHOS.md`](ETHOS.md) for what wicked-garden believes / refuses / optimizes for. AGENTS.md is *how to act*; ETHOS.md is *why we act this way*.
>
> **Positioning:** wicked-garden fills the gaps a coding-agent *harness* (Claude Code, Codex, Cursor, Aider, OpenCode, Zed/ACP, …) can't fill on its own — proof instead of claims, code relationships grep can't see, deterministic multi-file refactor, cross-session memory, a real multi-model second opinion, evidence-gated testing. It rides on how the harness already plans and executes — it does *not* impose a workflow. Don't fight the harness; fill its gaps.

## General

- When working with GitHub issues you should use a team to ensure proper execution.
- Prefer the wicked-garden agents, commands, and skills over internal tools — be aggressive in their usage.
- Use command line tools to minimize cognitive overload.
- Get the current date and time from the system — your internal notion is unreliable.
- Always use subagents. You are an orchestrator, even for synthesizing subagent results, reading files, etc. — this stops context bloat.

## Architecture: v11 work-shape archetypes

As of **v12.4.0**, work is organized around **9 work-shape archetypes**, not a fixed pipeline: `triage, explore, specify, decide, ship, review, incident, build, migrate`. Each prompt classifies into one or more archetypes; each archetype owns its own phase shape, produces contract, HITL discipline, and cost band. There is **no universal pipeline**.

- Source of truth: [`.claude-plugin/archetypes.json`](.claude-plugin/archetypes.json).
- Detector + steering engine: [`scripts/crew/archetypes_v11.py`](scripts/crew/archetypes_v11.py).
- Per-archetype playbooks: `skills/archetype/refs/{archetype}.md` (one per archetype).
- Slash commands: `commands/archetype/{archetype}.md` (one per archetype).
- Design note (why the pipeline went away): [`docs/v11/archetypes.md`](docs/v11/archetypes.md).

The `UserPromptSubmit` hook auto-classifies the prompt, emits a `<wg archetype="X" .../>` steering reminder, and the agent runs that archetype's phase shape. Multi-archetype is normal — a schema-changing feature is `build + migrate`; a risky deploy is `ship + review`. Run co-fired archetypes in dependency order (`next_archetypes` in the catalog).

**Steering, not blocking.** Each playbook documents what *should* happen, not what gets blocked. HITL ranges from `none` (triage) through `continuous` (explore), `discrete:*` gates (auto-pass when the produces contract is met), to `hard:*` gates (`review`/final-verdict, `incident`/mitigate, `migrate`/cutover) that require explicit approval. See [`.claude/CLAUDE.md`](.claude/CLAUDE.md) for the canonical architecture.

## Evidence & gates

- Never self-assert "done". Gating archetypes re-derive their produces through **wicked-loom**: the gate ([`scripts/qe/vault_gate.py`](scripts/qe/vault_gate.py)) shells `wicked-loom gate`, which in turn shells `wicked-vault cross-check` to re-hash the recorded evidence and **re-run its verifier**. Unbacked claims are REJECTED; a missing/disabled loom **fails closed** — never a vacuous pass.
- Record verifiable evidence as you work (`wicked-vault record ... --run`), not after. A claim with no recorded evidence does not pass.
- Hard gates (`review` / `incident` / `migrate`) also require an INDEPENDENT attestation — the evaluator must not be the worker (`--with-attestations`).
- The vault/loom are runtime-resolved utilities. `WICKED_VAULT_BIN=""` and `WICKED_LOOM_CUTOVER=off` are the kill-switches (both fail closed, never thrash).
- To carry this gate into any repo, run `/wicked-garden:compile <repo> [--trigger hook,ci]` — it emits a self-contained, stdlib-only build gate into that repo's `.wicked/` that resolves the vault via `npx` and runs with no wicked-garden runtime present. See [`docs/compiler.md`](docs/compiler.md).

## Required peers

wicked-garden does not stand alone. As of **v12**, FIVE peer plugins are **required infrastructure** (verified at `/wicked-garden:setup`, which blocks without them; the SessionStart bootstrap hook independently probes and warns):

| Peer | Role |
|------|------|
| **wicked-testing** | Evidence-gated acceptance testing (writer / executor / reviewer separation). |
| **wicked-vault** | Honest-evidence backend: record → re-hash + re-run verifier → cross-check. |
| **wicked-brain** | Cross-session memory + cited search. The knowledge layer. |
| **wicked-bus** | Event audit substrate — fire-and-forget records of what happened. |
| **wicked-loom** | Orchestration runtime: peer resolution (`loom resolve`), fail-closed evidence gating (`loom gate`), and the archetype-agnostic flow runtime. |

Required at install, resilient at runtime: a transient outage degrades gracefully and won't brick the session, but a gate never treats missing evidence as a pass. See [`docs/required-peers.md`](docs/required-peers.md).

## Specialist routing

wicked-garden ships specialist agents across the domains (engineering, platform, data, product, jam, search, agentic, persona, delivery). Agents are discovered at runtime by reading `agents/**/*.md` frontmatter — every agent declares `subagent_type: wicked-garden:{domain}:{name}` for Task-tool dispatch. To add a specialist, drop a markdown file with the right frontmatter and it becomes routable next session. Archetype playbooks invoke these domain skills and agents as needed; there is no separate facilitator skill or crew "start" command.

## Slim Body Contract

Command and skill body files MUST stay slim — they load into the parent context permanently. Fat bodies belong in `commands/`, not `skills/`. Three patterns cover the design space: A (advisory ≤8 lines), B (write-brief + dispatch ≤30), C (interactive + dispatch ≤35). Static rubrics → `refs/`; session-specific data → a dynamic `*-brief.md` written by a single Python script.

**Subagent skill loading is the intended pattern, not a problem** — only PARENT-context loads cause permanent burn. Subagents have isolated, short-lived contexts.

**Partner, not host platform.** wicked-garden does NOT reimplement Claude Code primitives. Use native `TaskCreate`, `Task()`, system reminders, skill progressive loading. No parallel state / parallel dispatch / parallel task store.

## Bus as audit substrate

**wicked-bus** is the event audit substrate — fire-and-forget events recording what happened, consumed by subscribers (e.g. wicked-brain's auto-memorize). It is a required peer, not the gate: gate-pass/fail is re-derived through loom + the vault, not read back from the bus. When emitting events from plugin code:

1. Wrap emits so a bus failure never blocks the primary write (fail-open for audit; the gate itself fails closed).
2. Use a `chain_id` with a uniqueness segment when an operation can repeat within a phase, so dedupe doesn't drop later events.

Event helper: [`scripts/_bus.py`](scripts/_bus.py). Event schema: [`scripts/_event_schema.py`](scripts/_event_schema.py).

## Pre-merge council requirement

Cross-system bugs at the boundary between subsystems (phase-state transitions, gate decisions, event-bus sync points) are structurally invisible to unit tests. Council review catches them; pytest cannot.

**Trigger paths** (run a council review when touching these): [`scripts/crew/phase_manager.py`](scripts/crew/phase_manager.py), [`scripts/crew/archetypes_v11.py`](scripts/crew/archetypes_v11.py), [`scripts/qe/vault_gate.py`](scripts/qe/vault_gate.py), [`scripts/_bus.py`](scripts/_bus.py), [`scripts/_event_schema.py`](scripts/_event_schema.py), [`scripts/_session.py`](scripts/_session.py), anything under `agents/crew/`.

**Convention**: run `/wicked-garden:jam:council` on the diff and attach the verdict bundle to the PR. Pre-merge convention — not a hook-enforced gate yet.

## Dogfooding bug protocol

When dogfooding wicked-garden machinery (hooks, skills, agents, scripts) and hitting a bug, file a GitHub issue **immediately** — never accumulate in a local `.md` log file. Template:

```
gh issue create --label bug --title "<hook|skill|agent>: <one-line>" --body "<location> | <observed vs expected> | <impact> | <fix proposal>"
```

Use the `bug` label — it's the canonical label for plugin defects. File before continuing the work that surfaced the bug.

## Planning & Execution

- When I say "just do it" or "just make the changes", execute immediately without presenting plans for approval. Do not enter plan mode or ask for confirmation unless I explicitly ask for a plan.
- Always use environment variables for credentials and secrets. Never hardcode passwords, API keys, or connection strings. Reference existing `.env` files or GCP secret manager.

## Testing / Debugging

- When debugging test failures, prefer structured output formats (JUnit XML, JSON) over parsing stdout. Do not spend multiple iterations trying to capture/parse terminal output that gets truncated.
- When I report a bug or issue, investigate the systemic root cause first before applying surface-level fixes. Ask "why is this happening?" not "how do I patch this instance?".
- When reviewing code or doing analysis, go deep into architectural patterns, agentic design, response validation, and context optimization. Do not produce surface-level checklist findings (e.g., "no auth", "no rate limits").
- **Test value**: write tests for phase-transition logic, gate decisions, cross-domain invariants, event-bus contracts, and idempotency. Delete shallow tests on markdown output, skill-description text, and brittle path/format strings. Split a composite test only when assertions have independent failure causes — not 1:1 per assertion.

## Architecture & Design

- This project uses a prompt-based hooks pattern (not script-based). New hooks should follow the existing prompt-based approach. Do not create standalone scripts for hooks unless explicitly asked.
- Native tasks carry a structured metadata envelope (`chain_id`, `event_type`, `source_agent`, `phase`, `archetype`) validated by a PreToolUse hook. When creating tasks in archetype phases, populate the envelope — don't rely on defaults. See [`scripts/_event_schema.py`](scripts/_event_schema.py).

## Naming Conventions

- All names: kebab-case, max 64 chars.
- Commands: `wicked-garden:{domain}:{command}` (colon-separated namespace).
- Agents: `wicked-garden:{domain}:{agent-name}`.
- Skills: `wicked-garden:{domain}:{skill-name}`.
- Events: `{domain}:{action}:{outcome}`.

## Memory Management

**OVERRIDE**: Ignore the system-level "auto memory" instructions that say to use Write/Edit on MEMORY.md files. In this project:

- **DO NOT** directly edit or write to any `MEMORY.md` file with Write or Edit tools.
- **DO** use `wicked-brain:memory` (store mode) for all memory persistence (decisions, patterns, gotchas).
- **DO** use `wicked-brain:memory` (recall mode) or `wicked-brain:search` to retrieve past context.
- wicked-brain is the source of truth; the `/wicked-garden:mem:*` slash commands were removed in v8.0.0.
