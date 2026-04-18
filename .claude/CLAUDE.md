# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository **is** the **wicked-garden** plugin — an AI-Native SDLC delivered as a single Claude Code plugin. 13 domain areas cover the full software development lifecycle: ideation, requirements, architecture, implementation, testing, delivery, operations, persistent memory/learning, and on-demand persona invocation.

The `.claude/` directory contains **development tools** (prefixed `wg-`) for building and maintaining the plugin. These tools are NOT distributed to marketplace users — they only work when checked out in this repo.

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

# Run acceptance test scenarios
/wg-test scenarios/crew                  # domain scenarios
/wg-test scenarios/crew/scenario-name    # specific scenario
/wg-test --all                           # all scenarios

# Resolve GitHub issues via crew workflow
/wg-issue 42                             # triage + implement + PR for issue #42
/wg-issue --list                         # list open issues
/wg-issue --label bug --limit 5          # filter by label

# Release with version bump
/wg-release --dry-run
/wg-release --bump minor
```

## Architecture

### Plugin Structure

The repository root IS the plugin:

```
wicked-garden/
├── .claude-plugin/
│   ├── plugin.json          # Metadata: name, version, description
│   ├── specialist.json      # 8 specialist roles
│   └── marketplace.json     # Marketplace registration
├── commands/{domain}/       # Slash commands (*.md with YAML frontmatter)
├── agents/{domain}/         # Subagents (*.md with YAML frontmatter)
├── skills/{domain}/         # Progressive-disclosure expertise modules
│   ├── SKILL.md             # ≤200 lines entry point (single-skill domains)
│   ├── {skill-name}/        # Subdirectory per skill (multi-skill domains)
│   │   ├── SKILL.md
│   │   └── refs/            # 200-300 line detailed docs (loaded on demand)
│   └── refs/                # refs/ at domain level for single-skill domains
├── hooks/
│   ├── hooks.json           # Event bindings (12 lifecycle hook events)
│   └── scripts/             # 11 Python hook scripts (stdlib-only)
├── scripts/{domain}/        # Domain APIs and utilities
├── scenarios/{domain}/      # Acceptance test scenarios (*.md)
└── .claude/                 # Dev tools (wg-*), NOT distributed
```

### Command Namespace

All commands use colon-separated namespacing: `wicked-garden:{domain}:{command}`

```bash
/wicked-garden:crew:start           # crew domain, start command
/wicked-garden:search:blast-radius  # search domain, blast-radius command
/wicked-garden:engineering:review   # engineering domain, review command
/wicked-garden:setup                # no domain (root-level command)
```

Agent subagent_type uses colons: `wicked-garden:{domain}:{agent-name}`

### Domain Organization

**13 domains**, each with its own commands, agents, skills, scripts, and scenarios:

**Workflow & Intelligence**: crew, smaht, mem, search, jam
**Specialist Disciplines**: engineering, product, platform, qe, data, delivery, agentic, persona

Task tracking uses Claude Code's native `TaskCreate`/`TaskUpdate` with enriched `metadata` — no separate kanban domain. The PreToolUse validator in `hooks/scripts/pre_tool.py` enforces the envelope per `scripts/_event_schema.py`.

Specialists define personas in `.claude-plugin/specialist.json`. Crew discovers them at runtime and routes based on signal analysis.

### Cross-Domain Communication

All domains live in one plugin — direct Python imports replace the old subprocess discovery pattern:

```python
# Direct import (domains share scripts/ directory)
from _domain_store import DomainStore
from _session import SessionState
```

Smaht adapters query domain scripts directly via `_SCRIPTS_ROOT` path resolution.

### Storage Layer

Local-first persistence via `DomainStore` and `SqliteStore`:

- **DomainStore** (`scripts/_domain_store.py`): Local JSON files + integration-discovery routing to MCP tools
- **SqliteStore** (`scripts/_sqlite_store.py`): FTS5 + BM25 for full-text search
- **SessionState** (`scripts/_session.py`): Per-session state shared between hooks
- **AgentLoader** (`scripts/_agents.py`): Two-source merge (disk agents + specialist.json)

Storage paths: `~/.something-wicked/wicked-garden/local/{domain}/{source}/{id}.json`

### Context Assembly (smaht domain)

The "brain" of the plugin. Intercepts every prompt via UserPromptSubmit hook and routes through four tiers:

- **HOT path** (<100ms): Continuation/confirmation responses → session state only
- **FAST path** (<1s): Pattern-based adapter fan-out by intent type
- **SLOW path** (2-5s): Full adapter fan-out for complex/ambiguous/novel prompts + history condenser
- **SYNTHESIZE path**: Agentic synthesis via `wicked-garden:smaht:synthesize` skill for complex+risky prompts — triggers before orchestrator

Six adapters query domain scripts directly: `domain`, `brain`, `events`, `context7`, `tools`, `delegation`.

**Brain adapter** (`scripts/smaht/adapters/brain_adapter.py`) is the primary knowledge source — queries the wicked-brain FTS5 index. When brain is unavailable, returns empty and agents fall back to Grep/Glob.

**Budget enforcer** source priority: `mem=10, search=9, brain=8, crew=6, context7=4, jam=3, tools=2, delegation=1`

**Adapter fan-out by intent** (fast path): DEBUGGING: domain, brain, delegation · IMPLEMENTATION: domain, brain, context7, tools, delegation · PLANNING: domain, brain, events, delegation · RESEARCH: domain, brain, events, context7, tools, delegation · REVIEW: domain, brain, events, delegation · GENERAL: domain, delegation

**Router (v6)**: the v5 `scripts/smaht/v2/router.py` intent classifier was deleted in #428. Intent classification is now a tiny inline heuristic in `hooks/scripts/prompt_submit.py` (word count + risk signals). Synthesize skill args format: JSON string — parse with `json.loads(args)`.

**wicked-brain**: Optional but strongly recommended companion plugin. When installed, brain server runs at `localhost:4242` (configurable via `WICKED_BRAIN_PORT`) and bootstrap emits directives to run `ingest → retag → compile` if brain is empty. When not installed, brain adapter returns empty.

### Crew Workflow System

Dynamic multi-phase workflows with facilitator-driven specialist routing (v6):

1. `wicked-garden:crew:propose-process` facilitator rubric reads the project description → scores 9 factors (reversibility, blast_radius, compliance_scope, user_facing_impact, novelty, scope_effort, state_complexity, operational_risk, coordination_cost) → picks specialists by reading `agents/**/*.md` frontmatter → picks phases from catalog → sets rigor_tier (minimal/standard/full) → emits `process-plan.md` + full task chain
2. `phases.json` defines phase catalog with gate config (min scores, evidence requirements, dependencies). The facilitator decides which phases to pick; phases.json supplies their gate configuration.
3. Phase selection: rubric-driven, not rule-based. Facilitator decides inline based on factor readings.
4. Checkpoints at clarify/design/build re-invoke the facilitator in `re-evaluate` mode to adjust the plan
5. Specialists are discovered by reading frontmatter directly — no static `enhances` map
6. Swarm detection: `scripts/crew/swarm_trigger.py::detect_swarm_trigger()` monitors for 3+ BLOCK/REJECT gate findings → recommends Quality Coalition (extracted from the deleted v5 rule engine)

Review tiers map from complexity: 0-2 → minimal (advisory gates), 3-5 → standard (enforced gates), 6-7 → full (multi-reviewer). Security/compliance signals override to full regardless of complexity.

Fallback agents (facilitator, researcher, implementer, reviewer) handle phases when specialist agents aren't matched.

### Gate Enforcement (v2.5.0+)

Quality gates are hard enforcement mechanisms, not advisory:

- **REJECT** blocks phase advancement — triggers mandatory rework
- **CONDITIONAL** writes a `conditions-manifest.json` — conditions must be verified before next phase advances
- **Auto-resolution** (AC-4.4): spec gap conditions are fixed inline; intent-changing conditions escalate to user or council
- **Minimum gate scores**: `phases.json` defines `min_gate_score` per phase (0.6-0.8)
- **Banned reviewers**: `just-finish-auto`, `fast-pass`, `auto-approve-*` are rejected
- **Content validation**: zero-byte deliverables blocked; evidence needs 100+ bytes
- **Build depends on design**: `phases.json` `build.depends_on: ["clarify", "design"]`
- **Structured skip reasons**: `valid_skip_reasons` per phase; free-text rejected
- **Non-skippable test-strategy**: `skip_complexity_threshold: 3` prevents skipping at complexity >= 3
- **Rollback**: `CREW_GATE_ENFORCEMENT=legacy` env var bypasses all enforcement
- **Cross-session learning**: crew agents store learnings in wicked-garden:mem at project completion and gate failures

### Bulletproof Standards

Engineering agents enforce R1-R6 coding rules (no dead code, no bare panics, no magic values, no swallowed errors, no unbounded ops, no god functions). QE agents enforce T1-T6 testing rules (determinism, no sleep-based sync, isolation, single assertion focus, descriptive names, provenance). Rules are adapted per agent focus.

### Provenance Awareness

Review agents (crew reviewer, senior-engineer) check traceability coverage via `scripts/crew/traceability.py coverage`. Requirements analyst assigns `REQ-{domain}-{number}` IDs and creates traceability links. Provenance gaps are findings, not blockers. Existing verification_protocol.py check #6 validates requirement → design → code → test chains.

### On-Demand Personas (v2.6.0+)

Invoke any specialist persona directly without crew or jam:
- `/wicked-garden:persona:as <name> <task>` — invoke with rich characteristics
- `/wicked-garden:persona:define` — create custom personas (personality, constraints, memories, preferences)
- `/wicked-garden:persona:submit` — PR a persona to the repo
- Registry merges: DomainStore > plugin cache > specialist.json > fallbacks
- `--persona` flag on `engineering:review` for cross-domain integration

## Key Patterns

### Command Delegation

Commands with matching agents MUST delegate via the Task tool:

```markdown
<!-- DO: actual subagent dispatch -->
Task(
  subagent_type="wicked-garden:platform:security-engineer",
  prompt="Perform security review. Scope: {scope}..."
)

<!-- DON'T: informal prose that executes inline -->
### Spawn Security Engineer
Task: wicked-garden:platform:security-engineer
```

- Commands with 2+ independent steps SHOULD use parallel dispatch
- Commands wrapping a single CLI call MAY stay inline

### Script Invocation

**Cross-platform Python resolution**: Use `_python.sh` shim for all script invocations.
This resolves `python3`, `python`, or `py -3` — whichever is available on the platform.

**Hook scripts**: Dispatched via `invoke.py` with fallback chain (see hooks.json). Must be stdlib-only.

**Command/agent scripts**: Use `_python.sh` shim; `cd && uv run python` if has dependencies.
```bash
# stdlib-only (crew, mem, patch)
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" ${project} ${action}

# via _run.py wrapper (auto-help on argparse errors)
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py ${project} ${action}

# has deps (search needs tree-sitter)
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/index.py build
```

### Hook Development

- Prefer `command` hooks over `prompt`/`agent` hooks (deterministic, testable, no token cost)
- Use `"async": true` for Stop hooks so they don't block the user
- Return `{"ok": true}` on success, `{"ok": false, "reason": "..."}` to block
- Hook scripts read JSON from stdin and print JSON to stdout
- Target <5s for sync hooks, <30s for async hooks
- Fail gracefully — return `{"ok": true}` even on errors, log to stderr

### Hook Events

Valid hook events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `TaskCompleted`, `SubagentStart`, `SubagentStop`, `Stop`, `PreCompact`, `Notification`, `PermissionRequest`, `TeammateIdle`, `SessionEnd`.

`TaskCompleted` fires when a task is marked completed. Exit code 2 prevents completion and feeds stderr back to the model. Does not use matchers.

Matchers specify tool names: `"*"` for all, or specific like `"TaskCreate"`, `"Write"`, `"Edit"`.

### Storage

Plugin state is managed by DomainStore (`scripts/_domain_store.py`) — local JSON files with optional integration-discovery routing to external MCP tools. Local paths are resolved dynamically; never hardcode `~/.something-wicked/` paths in consumer code. Use `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" <domain>` in commands.

### Graceful Degradation

The plugin works standalone with no external dependencies. All hooks fail-open. DomainStore always has local JSON as fallback. Integration-discovery routing is optional.

### Task Lifecycle in Crew

Every crew agent must explicitly track state:
```
TaskCreate(subject="Phase: project - description")
TaskUpdate(taskId, status="in_progress")  # BEFORE starting work
# ... do work ...
TaskUpdate(taskId, status="completed")    # AFTER finishing work
```

Status vocabulary: `pending`, `in_progress`, `completed`. Native tasks persist to `${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/{session_id}/*.json`; wicked-garden hooks only validate and read — they do not mirror or shadow the store.

### Native Tasks as Dual-Purpose Event Queue

Tasks carry agent-coordination fields in the `metadata` dict passed to `TaskCreate` / `TaskUpdate`. The schema lives in `scripts/_event_schema.py`; the PreToolUse validator in `hooks/scripts/pre_tool.py` enforces it.

- **`chain_id`**: Dotted causality hierarchy — `{project}.root` at crew start, `{project}.{phase}` per phase, `{project}.{phase}.{gate}` per gate finding. Format: `^{slug}(\.(root|{phase}))(\.{gate})?$`.
- **`event_type`**: `task` (default) | `coding-task` | `gate-finding` | `phase-transition` | `procedure-trigger` | `subtask`
- **`source_agent`**: Agent that authored the event. Banned values: `just-finish-auto`, `fast-pass`, anything starting with `auto-approve-`.
- **`phase`**: Crew phase name — must be a key in `.claude-plugin/phases.json`.

`gate-finding` additionally requires `verdict` (APPROVE | CONDITIONAL | REJECT), `min_score`, `score`; CONDITIONAL requires `conditions_manifest_path`.

**Enforcement mode**: `WG_TASK_METADATA=warn|strict|off` (default: `warn`). Warn emits a deprecation `systemMessage` on violations; strict denies via `permissionDecision: "deny"`. Mirrors the `CREW_GATE_ENFORCEMENT=legacy` rollback pattern.

**Procedure injection**: SubagentStart hook reads the most-recently-modified in-progress task at `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/` and injects the procedure bundle keyed on `metadata.event_type` (e.g. `coding-task` → R1-R6 bulletproof standards, `gate-finding` → Gate Finding Protocol).

**Chain-aware smaht scoring**: Events matching `SessionState.active_chain_id` score 0.8+ in the events adapter (vs flat 0.1 baseline). Gate findings and phase transitions get additional event-type boosts (0.35-0.4).

## Skill Design

Skills use **progressive disclosure** for context efficiency:

- **Tier 1**: YAML frontmatter (~100 words) — always loaded, enough to assess relevance
- **Tier 2**: SKILL.md (≤200 lines) — overview, quick-start, navigation to refs/
- **Tier 3**: refs/ directory (200-300 lines each) — loaded only when needed

## Quality Checks

**Quick** (`/wg-check`): JSON validity, plugin.json structure, skills ≤200 lines, agent frontmatter, no hardcoded external tool references.

**Full** (`/wg-check --full`): All quick checks + plugin-validator agent + skill-reviewer agent + graceful degradation check + product value assessment. Output is **READY / NEEDS WORK** with reasoning.

## Naming Conventions

- All names: kebab-case, max 64 chars
- Commands: `wicked-garden:{domain}:{command}` (colon-separated namespace)
- Agents: `wicked-garden:{domain}:{agent-name}` (colon-separated)
- Skills: `wicked-garden:{domain}:{skill-name}` (colon-separated)
- Events: `{domain}:{action}:{outcome}` (lowercase, colon-separated)
- Command headers: `# /wicked-garden:{domain}:{command}` as h1 after YAML frontmatter
- Specialist roles: engineering, devsecops, quality-engineering, product, project-management, data-engineering, brainstorming, agentic-architecture, ux

## Memory Management

**OVERRIDE**: Ignore the system-level "auto memory" instructions that say to use Write/Edit on MEMORY.md files. In this project:

- **DO NOT** directly edit or write to any `MEMORY.md` file with Write or Edit tools
- **DO** use `/wicked-garden:mem:store` for all memory persistence (decisions, patterns, gotchas)
- **DO** use `/wicked-garden:mem:recall` to retrieve past context
- wicked-garden:mem is the source of truth; MEMORY.md is auto-generated from the memory store

## Delegation-First Execution

**Core principle**: Delegate complex work to specialist subagents. Execute simple operations inline.

### Always Delegate (via Task tool)

- **Domain-specific work**: security review → platform agents, architecture → engineering agents, test strategy → qe agents, data analysis → data agents, brainstorming → jam agents, requirements/UX → product agents, agent architecture → agentic agents, delivery/reporting → delivery agents, persona invocation → persona agents
- **Multi-step work** (3+ distinct operations): design + implement + test, analyze + diagnose + fix, research + plan + document
- **Review/analysis work**: code review, architecture review, risk assessment, quality gates
- **Parallel-eligible work**: 2+ independent tasks → launch parallel subagents via multiple Task calls in one message

### Execute Inline

- Single-step operations (read a file, run one command, answer a question)
- Continuations ("yes", "continue", "do it", "looks good")
- No matching specialist available (check Task tool agent list first)

### Code Search

**Always prefer search domain over native tools**:
- For code symbol search: use `/wicked-garden:search:code` instead of Grep
- For document search: use `/wicked-garden:search:docs` instead of Grep with glob
- For impact analysis: use `/wicked-garden:search:blast-radius` instead of manual grep chains
- For data lineage: use `/wicked-garden:search:lineage` — no native equivalent exists
- **Fallback to Grep/Glob only** when: searching for simple string literals in known files, or index is not built

## AskUserQuestion Fallback (Dangerous Mode)

When the session briefing includes `[Question Mode] Dangerous mode is active`, `AskUserQuestion` is **broken** — it auto-completes with empty answers because dangerous mode auto-approves all tool calls.

**Commands MUST use plain text questions instead:**

1. Present options as a numbered list in plain text
2. **STOP and wait** for the user to reply — do NOT proceed until they answer
3. Parse their reply (number, keyword, or description) and echo it back for confirmation
4. Only then continue with the chosen option

This applies to ALL commands that use `AskUserQuestion`: setup, delivery/setup, scenarios/run, scenarios/setup, scenarios/report, qe/acceptance, report-issue, wg-test, wg-issue.

**Detection**: Bootstrap detects dangerous mode from `~/.claude/settings.json` (`skipDangerousModePermissionPrompt: true`) and stores it in session state + briefing. Commands do not need to re-detect.

## Security

- Use `${CLAUDE_PLUGIN_ROOT}` for all paths in plugin scripts — never hardcode paths
- Quote all shell variables: `"$VAR"` not `$VAR`
- Quote temp paths: `"${TMPDIR:-/tmp}/..."` (Codex catches unquoted)
- Python scripts: use `tempfile.gettempdir()` instead of hardcoding `/tmp` — Windows has no `/tmp`
- Script invocation: use `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh"` — never bare `python3` (not available on Windows)

## wicked-brain

Digital brain: **wicked-garden** | 9,352 indexed items | 9,352 chunks, 0 wiki articles, 0 memories | server port 4243

**Domain expertise:** review, integration, requirements, architecture, analysis, evidence, context, patterns, quality, documentation, scenarios, agents, acceptance, system, criteria, structure

**Knowledge gaps:** none recorded yet (fresh ingest — gaps will be logged as `search_miss` entries on unanswered queries)

**Linked brains:** none (sibling `wicked-bus` brain lives at `~/.wicked-brain/projects/wicked-bus` on port 4242 but is not linked)

### How to use

- **Search/explore**: use `wicked-brain:search` — replaces Grep, Glob, and Agent(Explore) for any open-ended search
- **Answer questions**: use `wicked-brain:query` — replaces Agent(Explore) for conceptual questions
- **Wiki catalog**: use `wicked-brain:read` at depth 0/1 to browse wiki articles progressively
- **Surface context**: call `wicked-brain:agent` (context) at the start of any new topic
- **Capture learnings**: call `wicked-brain:agent` (session-teardown) at session end
- **Store a decision/pattern/gotcha**: call `wicked-brain:memory` (store mode)
- **Available agents**: consolidate, context, session-teardown, onboard (via `wicked-brain:agent`)

### Search result source types

Brain search/query results include `source_type` and `path` fields. Use these to decide depth:

- **`wiki`** — Synthesized knowledge articles. High-value. Read deeper with `wicked-brain:read {path} depth=2`.
- **`chunk`** — Raw indexed source content. The excerpt in the search result is usually sufficient.
- **`memory`** — Experiential learnings (decisions, patterns, gotchas). Compact; excerpt is usually enough.

### Rules (follow strictly)

- **ALWAYS check the brain BEFORE using Grep, Glob, Read, or Agent(Explore)** — for any find, search, explore, explain, or "what is/how does" request
- Use `wicked-brain:search` for finding content ("find X", "where is Y", "look for Z")
- Use `wicked-brain:query` for questions ("what does X do", "how does Y work", "explain Z")
- Use `wicked-brain:agent` (context) when starting a new topic or unfamiliar area
- When search results include `source_type: wiki`, follow up with `wicked-brain:read` at depth 1-2 for the full synthesized article
- Only fall back to Grep/Glob for **exact pattern matching** after the brain returns no results
- Do NOT read brain files directly — always go through skills and agents
- Always pass `session_id` with search/query calls for access tracking
- Capture non-obvious decisions, patterns, and gotchas with `wicked-brain:memory`
