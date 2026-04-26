# Architecture

How wicked-garden stores data, routes work through Claude Code's native primitives, assembles context, and organizes its components.

## What v6 Leverages From Claude Code

v6 is built **on top of** Claude Code's native surface — it doesn't replace Claude's primitives, it orchestrates them:

| Claude Code Primitive | How wicked-garden uses it |
|------------------------|---------------------------|
| `TaskCreate` / `TaskUpdate` | Every phase, gate finding, and dispatch is a native task carrying a structured metadata envelope (`chain_id`, `event_type`, `source_agent`, `phase`, `archetype`). No separate task store. |
| Subagent dispatch (Task tool) | 75 specialists routed dynamically by reading `subagent_type` frontmatter in `agents/**/*.md`. No static `enhances` map. |
| Skills (progressive disclosure) | Tier 1 frontmatter (~100 words) / Tier 2 `SKILL.md` (≤200 lines) / Tier 3 `refs/` (200–300 lines on demand). The facilitator, workflow, acceptance-testing, and unified-search skills ship this way. |
| 14 lifecycle hook events | `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `TaskCompleted`, `SubagentStart`, `SubagentStop`, `Stop`, `PreCompact`, `Notification`, `PermissionRequest`, `TeammateIdle`, `SessionEnd`. Hooks validate metadata, inject procedures, store learnings, and surface findings. |
| Plugin manifest | The whole SDLC ships as one plugin install — no sidecar services. |

## Storage Layer

### Local-First Design

All data is stored as local JSON files. No external server, no sidecar process, no database to manage. Paths are resolved dynamically — consumer code never hardcodes them.

```
~/.something-wicked/wicked-garden/projects/{project-slug}/
  wicked-crew/       # crew project state, phase deliverables
  wicked-mem/        # memories (decisions, patterns, preferences)
  wicked-jam/        # brainstorm sessions, transcripts
  wicked-search/     # code index, symbol graphs
  wicked-smaht/      # context cache, session history
```

Resolve paths via `scripts/resolve_path.py` rather than string-building. Global configuration lives at `~/.something-wicked/wicked-garden/config.json`.

Storage is **project-scoped** — isolated per working directory. Two projects with the same name in different directories don't share state.

### DomainStore

The storage API used by all domains. CRUD over local JSON with optional routing to external MCP tools.

```python
from _domain_store import DomainStore

ds = DomainStore("wicked-mem")
ds.create("memories", "abc123", {"title": "...", "content": "..."})
record = ds.get("memories", "abc123")
results = ds.list("memories", limit=10)
```

### SqliteStore

FTS5 + BM25 full-text search for the search and brain layers. Used internally by domain scripts.

### Brain API

When wicked-brain is installed, a background server provides FTS5 search over indexed chunks, wiki articles, and memories.

```bash
curl -s -X POST http://localhost:4243/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"deployment","limit":10}}'
```

Port defaults to `4243` (configurable via `WICKED_BRAIN_PORT`). When brain is unavailable, the brain adapter returns empty and callers fall back to Grep/Glob.

### EventStore

Unified event log — every DomainStore write auto-emits an event to a single SQLite database with FTS5 full-text search.

```python
from _event_store import EventStore

EventStore.ensure_schema()
EventStore.append(domain="crew", action="phases.build.approved", project_id="my-project")
events = EventStore.query(project_id="my-project", since="7d", fts="auth migration")
```

Events are append-only, auto-emitted by DomainStore, indexed on safe metadata only (full payloads stay in domain JSON), and consumed by `smaht:briefing` and smaht context assembly.

## Native Tasks as a Dual-Purpose Event Queue

v6 treats Claude Code's native tasks as both a user-visible TODO list **and** the agent-coordination event queue. Every phase boundary, gate finding, and subagent dispatch flows through one of these native tasks, carrying a structured metadata envelope validated by a `PreToolUse` hook.

### Metadata Envelope

Defined in `scripts/_event_schema.py`. Enforced by `hooks/scripts/pre_tool.py` on every `TaskCreate` / `TaskUpdate`:

| Field | Required | Purpose |
|-------|----------|---------|
| `chain_id` | Yes on crew tasks | Dotted causality: `{project}.root` → `{project}.{phase}` → `{project}.{phase}.{gate}`. Regex: `^{slug}(\.(root\|{phase}))(\.{gate})?$` |
| `event_type` | Yes | `task` (default) \| `coding-task` \| `gate-finding` \| `phase-transition` \| `procedure-trigger` \| `subtask` |
| `source_agent` | Yes | Authoring agent. Banned: `just-finish-auto`, `fast-pass`, anything starting with `auto-approve-` |
| `phase` | Yes on crew tasks | Must be a key in `.claude-plugin/phases.json` |
| `archetype` | Optional | Set at clarify time by the facilitator; consumed by phase-boundary QE evaluator |

`gate-finding` additionally requires `verdict` (APPROVE / CONDITIONAL / REJECT), `min_score`, `score`. CONDITIONAL requires `conditions_manifest_path`.

### Enforcement Mode

`WG_TASK_METADATA=warn|strict|off` (default `warn`). Warn emits a deprecation `systemMessage`; strict denies via `permissionDecision: "deny"`.

### Procedure Injection

The `SubagentStart` hook reads the most-recently-modified in-progress task at `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/` and injects the procedure bundle keyed on `metadata.event_type`:

- `coding-task` → R1–R6 bulletproof coding standards
- `gate-finding` → Gate Finding Protocol
- Other event types → matching per-role procedures

This is how v6 gets specialist-specific rigor without per-agent prompt bloat — the bundle arrives at subagent-start time, scoped to what the task is.

### Chain-Aware Smaht Scoring

Events matching `SessionState.active_chain_id` score 0.8+ in the events adapter (vs a 0.1 baseline for unrelated events). Gate findings and phase transitions get event-type boosts on top (0.35–0.4). Context that matters to the active phase surfaces first.

## Gate Policy

`.claude-plugin/gate-policy.json` codifies the **reviewer × rigor × dispatch-mode** matrix. Each gate × tier entry declares:

- **reviewers** — ordered list of `subagent_type` values
- **mode** — `self-check` \| `sequential` \| `parallel` \| `council` \| `advisory`
- **min_score** — numeric threshold for APPROVE
- **evidence_required** — list of artifact types that must accompany the verdict

Dispatch mechanics live in `scripts/crew/gate_dispatch.py`:

- `self-check` → `gate-evaluator` runs deterministic checks (byte count, required deliverables)
- `sequential` → one specialist at a time; early REJECT short-circuits
- `parallel` → all specialists dispatched in one batch; findings merged
- `council` → full panel with BLEND aggregation (`0.4 × min + 0.6 × avg`)
- `advisory` → findings-only; never blocks

### Blind Reviewer + Partial-Panel Invariant

Reviewers run with session context stripped of prior gate verdicts (prevents rubber-stamping). If a reviewer fails to respond in a panel, the gate stays `pending` — never silently approved.

### HMAC Dispatch Log

Every dispatch appends an HMAC-signed entry to `phases/{phase}/dispatch-log.jsonl`. On gate evaluation, an **orphan gate-result** (a result without a matching dispatch entry) is downgraded to CONDITIONAL. Log rotates at the configured size threshold. Ops scenario: `scenarios/crew/dispatch-log-hmac-orphan-detection-rotation.md`.

### Gate-Result Security

`gate-result.json` ingestion runs a layered defense floor:

1. Schema validator
2. Content sanitizer (codepoint allow-list + injection patterns)
3. Dispatch-log orphan detection
4. Append-only audit log

Rollback levers via `WG_GATE_RESULT_*` env vars (schema, content, dispatch — all auto-expire at `WG_GATE_RESULT_STRICT_AFTER`). This is a floor against content drift and trivial prompt-injection, not a wall against local disk-write attackers. Benchmark SLO re-baseline is owned by the `wicked-garden:platform:gate-benchmark-rebaseline` skill.

## Re-evaluation Artifacts

At clarify / design / build checkpoints the facilitator re-runs. Findings are append-only to three files per phase:

- `phases/{phase}/reeval-log.jsonl` — addendum entries (schema `1.1.0`, archetype-aware)
- `phases/{phase}/amendments.jsonl` — per-gate amendments
- `phases/{phase}/process-plan.addendum.jsonl` — plan mutations (added phases, rigor changes)

Phases can be **added** mid-flight but are **never silently removed**.

## Context Assembly (smaht)

Every prompt flows through `UserPromptSubmit` and is routed by tier.

### Four-Tier Routing

```
User prompt
     |
     v
+---------------------------+
|  Tier Detection           |
|                           |
|  HOT   (<100ms) ---------> Continuation? Session state only
|  FAST  (<1s)    ---------> Clear intent? Pattern-based adapter fan-out
|  SLOW  (2-5s)   ---------> Complex/ambiguous? Full fan-out + history
|  SYNTH         ----------> Complex+risky? Agentic synthesis skill first
+---------------------------+
```

Intent classification is a small inline heuristic in `hooks/scripts/prompt_submit.py` — word count plus risk signals. The v5 `scripts/smaht/v2/router.py` intent classifier was deleted in #428.

### Six Adapters (v6)

| Adapter | Source | What It Provides |
|---------|--------|------------------|
| `domain` | Domain scripts via direct import | Active tasks, project state, memories, jam transcripts, search hits |
| `brain` | wicked-brain FTS5 index | Synthesized wiki articles, indexed chunks, stored memories |
| `events` | EventStore | Cross-domain activity, chain-scoped events for the active phase |
| `context7` | Context7 MCP server | Library documentation |
| `tools` | Integration discovery | Available MCP servers, CLI tools, external LLMs |
| `delegation` | Agent catalog | Matching `subagent_type` suggestions for the current prompt |

The v4 `mem` / `search` / `kanban` / `crew` / `jam` adapters were consolidated into `domain` + `brain` + `events`. Kanban itself was deleted in v5.0.0 — tasks now use Claude Code's native TaskCreate.

**Adapter fan-out by intent** (fast path):

- DEBUGGING: domain, brain, delegation
- IMPLEMENTATION: domain, brain, context7, tools, delegation
- PLANNING: domain, brain, events, delegation
- RESEARCH: domain, brain, events, context7, tools, delegation
- REVIEW: domain, brain, events, delegation
- GENERAL: domain, delegation

**Budget enforcer source priority**: `mem=10, search=9, brain=8, crew=6, context7=4, jam=3, tools=2, delegation=1`.

### Delegation Hints

When smaht detects domain-specific work, it injects delegation hints pointing at the matching specialist `subagent_type`. These are suggestions to Claude, not mandatory routes — a security-review prompt suggests `platform:security-engineer`, an architecture prompt suggests `engineering:solution-architect`.

## Integration Discovery

Domains that need external tools (source control, task trackers, monitoring, LLM CLIs) use capability-based discovery.

```
Domain Command
     |
     v
+---------------------------+
|  Integration Discovery    |     Resolution:
|                           |     1. config.json -> "use linear"
|  Find matching tools -----+-->  2. memory -> "chose jira last time"
|  Resolve which to use     |     3. ask user -> store choice
|  Fall back to local JSON  |     4. no tools? -> local JSON
+---------------------------+
```

Discovery is by **capability**, not by name. A domain asks "I need a task tracker" — not "give me Jira". The plugin stays tool-agnostic.

## Hook System

14 lifecycle events. 11 stdlib-only Python scripts back the active hooks; remaining events are available for custom extensions.

### Active Hooks

| Script | Event | Purpose |
|--------|-------|---------|
| `bootstrap` | SessionStart | Session state init, environment detection, dangerous-mode detection |
| `prompt_submit` | UserPromptSubmit | Four-tier context assembly via smaht |
| `pre_tool` | PreToolUse:* | Validate TaskCreate/TaskUpdate metadata envelope |
| `post_tool_task` | PostToolUse:Task* | Chain-id propagation, event emission |
| `subagent_start` | SubagentStart | Procedure injection keyed on `metadata.event_type` |
| `subagent_stop` | SubagentStop | Finding extraction, dispatch-log append |
| `task_completed` | TaskCompleted | Completion-quality verification |
| `compact` | PreCompact | Checkpoint session state before compression |
| `stop` | Stop (async) | Session-close guard pipeline, learning capture |

All hooks fail open — an errored hook returns `{"ok": true}` and logs to stderr. Hook scripts read JSON from stdin and print JSON to stdout. Sync hooks target <5s; async hooks <30s.

### All Lifecycle Events

| Event | Fires When | Matchers |
|-------|-----------|----------|
| SessionStart | Session begins | n/a |
| UserPromptSubmit | User sends a prompt | n/a |
| PreToolUse | Before a tool executes | Tool name (`"*"`, `"TaskCreate"`, etc.) |
| PostToolUse | After a tool succeeds | Tool name |
| PostToolUseFailure | After a tool fails | Tool name |
| TaskCompleted | A task is marked completed | n/a |
| SubagentStart | Subagent begins execution | Agent type |
| SubagentStop | Subagent finishes execution | Agent type |
| Stop | Session ends normally | n/a (async-eligible) |
| PreCompact | Before context compression | n/a |
| Notification | Plugin sends a notification | n/a |
| PermissionRequest | User is asked for permission | n/a |
| TeammateIdle | A teammate becomes idle | n/a |
| SessionEnd | Session terminates | n/a |

## Plugin Structure

```
wicked-garden/
+-- .claude-plugin/
|   +-- plugin.json          # name, version, description
|   +-- specialist.json      # lean specialist manifest (roles)
|   +-- marketplace.json     # marketplace registration
|   +-- phases.json          # phase catalog with gate config
|   +-- gate-policy.json     # gate x rigor x reviewer matrix
+-- commands/{domain}/       # slash commands (*.md with YAML frontmatter)
+-- agents/{domain}/         # subagents (*.md, subagent_type frontmatter)
+-- skills/
|   +-- {domain}/SKILL.md    # single-skill domains
|   +-- {domain}/{skill}/    # multi-skill domains
|       +-- SKILL.md         # entry point (<=200 lines)
|       +-- refs/            # detailed docs (loaded on demand)
+-- hooks/
|   +-- hooks.json           # event bindings
|   +-- scripts/             # 11 Python hook scripts, stdlib-only
+-- scripts/{domain}/        # domain APIs and utilities
+-- scenarios/{domain}/      # acceptance test scenarios (*.md)
+-- docs/                    # user-facing documentation
```

### Progressive Disclosure

Skills use a three-tier loading strategy to minimize context usage:

1. **Tier 1**: YAML frontmatter (~100 words) — always loaded, enough to assess relevance
2. **Tier 2**: `SKILL.md` (≤200 lines) — overview, quick start, navigation to refs
3. **Tier 3**: `refs/` directory (200–300 lines each) — loaded only when needed

A full skill with 5 ref files might be 1,500 lines total, but only 200 are loaded unless deep expertise is needed.

### Command Namespace

All components use colon-separated namespacing:

```
/wicked-garden:{domain}:{command}       # commands
wicked-garden:{domain}:{agent-name}     # subagent_type (agents)
wicked-garden:{domain}:{skill-name}     # skills
```

### Specialist System

`.claude-plugin/specialist.json` is a lean manifest of role categories (`engineering`, `devsecops`, `quality-engineering`, `product`, `project-management`, `data-engineering`, `brainstorming`, `agentic-architecture`, `ux`). **The facilitator reads `agents/**/*.md` directly** to discover specialists at runtime — the static `enhances` map from v5 was removed in v6. Each agent carries a `subagent_type: wicked-garden:{domain}:{name}` frontmatter line for dispatch.

## Knowledge Graph

A typed entity and relationship layer backed by SQLite, managed by `scripts/smaht/knowledge_graph.py`. Tracks requirements, designs, tasks, tests, decisions, and their traceability relationships across crew phases. See [Cross-Phase Intelligence](cross-phase-intelligence.md) for the full model and CLI.

## Lifecycle + Convergence Scoring

- **`scripts/search/lifecycle_scoring.py`** — 4 default scorers (phase-weighted, recency-decay, traceability-boost, gate-status) with opt-in RRF. Ranks search + memory results by relevance to the current crew phase.
- **`scripts/crew/convergence.py`** — tracks build/test artifacts through Designed → Built → Wired → Tested → Integrated → Verified. The `convergence-verify` gate refuses APPROVE until every artifact reaches at least Integrated; stall-detection at 3 sessions becomes a finding.

See [Cross-Phase Intelligence](cross-phase-intelligence.md) for details and the [Crew Workflow](crew-workflow.md) for how gates consume these signals.
