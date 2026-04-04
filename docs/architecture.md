# Architecture

How wicked-garden stores data, discovers integrations, assembles context, and organizes its components.

## Storage Layer

### Local-First Design

All data is stored as local JSON files. No external server, no sidecar process, no database to manage.

```
~/.something-wicked/wicked-garden/projects/{project-slug}/
  wicked-crew/       # crew project state, phase deliverables
  wicked-kanban/     # task boards, initiatives
  wicked-mem/        # memories (decisions, patterns, preferences)
  wicked-jam/        # brainstorm sessions, transcripts
  wicked-search/     # code index, symbol graphs
  wicked-smaht/      # context cache, session history
```

Storage is **project-scoped** — isolated per working directory. Two projects with the same name in different directories don't share state.

Global configuration lives at `~/.something-wicked/wicked-garden/config.json`.

### DomainStore

The storage API used by all domains. Provides CRUD operations on local JSON files with optional routing to external tools.

```python
from _domain_store import DomainStore

ds = DomainStore("wicked-mem")
ds.create("memories", "abc123", {"title": "...", "content": "..."})
record = ds.get("memories", "abc123")
results = ds.list("memories", limit=10)
```

### SqliteStore

Full-text search via SQLite FTS5 with BM25 ranking. Used by search and memory domains for fast querying.

```python
from _sqlite_store import SqliteStore

store = SqliteStore()
store.create("wicked-mem", "memories", "id-001", {"title": "Deploy", "content": "Use WAL mode"})
results = store.search("deployment", domain="wicked-mem", limit=10)
```

### EventStore (v3.0+)

Unified event log — every DomainStore write auto-emits an event to a single SQLite database with FTS5 full-text search. Enables cross-domain queries that per-domain JSON cannot support.

```python
from _event_store import EventStore

EventStore.ensure_schema()
EventStore.append(domain="crew", action="phases.build.approved", project_id="my-project")
events = EventStore.query(project_id="my-project", since="7d", fts="auth migration")
```

Events are:
- **Append-only** — no updates or deletes (except retention purge)
- **Auto-emitted** — DomainStore create/update/delete fires events automatically
- **Safe metadata only** — full payloads are not replicated into the FTS index
- **Consumed by** — `smaht:briefing`, `smaht` context assembly, `mem:recall` cross-domain supplementation

Location: `~/.something-wicked/wicked-garden/local/wicked-garden/events/events.db`

## Integration Discovery

When a domain needs external tools (e.g., kanban looking for Jira, Linear, or Rally), it uses capability-based discovery.

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

**Key principle**: Discovery is by capability, not by name. A domain asks "I need a task tracker" — not "give me Jira". This keeps the plugin tool-agnostic.

**Resolution order**:
1. Check local settings (`config.json` preferences)
2. Check memory (stored decisions from past sessions)
3. Ask the user once, remember the choice
4. If nothing found — local JSON (always works)

## Context Assembly (smaht)

The "brain" of the plugin. Intercepts every prompt via the `UserPromptSubmit` hook and enriches it with relevant context.

### Three-Tier Routing

```
User prompt
     |
     v
+---------------------------+
|  Tier Detection           |
|                           |
|  HOT  (<100ms)  ---------> Continuation? Session state only
|  FAST (<1s)     ---------> Clear intent? 2-5 targeted adapters
|  SLOW (2-5s)    ---------> Complex/ambiguous? All 6 adapters
+---------------------------+
```

### Six Adapters

| Adapter | Source | What It Provides |
|---------|--------|-----------------|
| mem | Memory store | Past decisions, patterns, preferences |
| search | Code index | Relevant code symbols, architecture context |
| kanban | Task board | Active tasks, project status |
| crew | Crew state | Current phase, project context |
| jam | Brainstorm history | Past brainstorm decisions |
| context7 | ContextSeven MCP | Library documentation |

Each adapter returns `ContextItem` objects with relevance scores. Items are ranked, deduplicated, and injected into the prompt — all invisible to the user.

### Delegation Hints

When smaht detects domain-specific work in a prompt, it injects delegation hints suggesting specialist subagents:

```
"security review" detected -> Consider: platform:security-engineer
"architecture" detected    -> Consider: engineering:solution-architect
```

These are suggestions to Claude, not mandatory routes.

## Hook System

The plugin supports 14 lifecycle events. Six Python scripts handle the active hooks; remaining events are available for future use or custom extensions.

### Active Hooks

| Hook Script | Event | Purpose |
|-------------|-------|---------|
| bootstrap | SessionStart | Initialize session state, detect environment |
| prompt_submit | UserPromptSubmit | Context assembly via smaht |
| pretool_taskcreate | PreToolUse:TaskCreate | Inject crew initiative metadata |
| posttool_task | PostToolUse:Task* | Sync task changes to kanban |
| compact | PreCompact | Checkpoint session state before compression |
| stop | Stop (async) | Store session learnings |
| task_completed | TaskCompleted | Verify task completion quality |

### All Lifecycle Events

| Event | Fires When | Matchers |
|-------|-----------|----------|
| SessionStart | Session begins | n/a |
| UserPromptSubmit | User sends a prompt | n/a |
| PreToolUse | Before a tool executes | Tool name (`"*"`, `"TaskCreate"`, etc.) |
| PostToolUse | After a tool succeeds | Tool name |
| PostToolUseFailure | After a tool fails | Tool name |
| TaskCompleted | A task is marked completed | n/a (no matchers) |
| SubagentStart | Subagent begins execution | Agent type |
| SubagentStop | Subagent finishes execution | Agent type |
| Stop | Session ends normally | n/a |
| PreCompact | Before context compression | n/a |
| Notification | Plugin sends a notification | n/a |
| PermissionRequest | User is asked for permission | n/a |
| TeammateIdle | A teammate becomes idle | n/a |
| SessionEnd | Session terminates | n/a |

SubagentStart, SubagentStop, PermissionRequest, and Notification were added in v3.3.0.

All hooks are **stdlib-only Python** — no pip dependencies. All hooks **fail open** — if a hook errors, it returns `{"ok": true}` and logs to stderr.

## Plugin Structure

```
wicked-garden/
+-- .claude-plugin/
|   +-- plugin.json          # name, version, description
|   +-- specialist.json      # 8 specialist roles (lean manifest)
|   +-- marketplace.json     # marketplace registration
|   +-- phases.json          # 7-phase catalog with gates
+-- commands/{domain}/       # slash commands (*.md with YAML frontmatter)
+-- agents/{domain}/         # subagents (*.md with YAML frontmatter)
+-- skills/
|   +-- {domain}/SKILL.md    # single-skill domains
|   +-- {domain}/{skill}/    # multi-skill domains
|       +-- SKILL.md         # entry point (<=200 lines)
|       +-- refs/            # detailed docs (loaded on demand)
+-- hooks/
|   +-- hooks.json           # event bindings
|   +-- scripts/             # Python hook scripts
+-- scripts/{domain}/        # domain APIs and utilities
+-- scenarios/{domain}/      # acceptance test scenarios
```

### Progressive Disclosure

Skills use a three-tier loading strategy to minimize context usage:

1. **Tier 1**: YAML frontmatter (~100 words) — always loaded, enough to assess relevance
2. **Tier 2**: SKILL.md (<=200 lines) — overview, quick start, navigation
3. **Tier 3**: refs/ directory (200-300 lines each) — loaded only when needed

This keeps Claude's context window efficient. A full skill with 5 ref files might be 1500 lines total, but only 200 are loaded unless deep expertise is needed.

### Command Namespace

All components use colon-separated namespacing:

```
/wicked-garden:{domain}:{command}       # commands
wicked-garden:{domain}:{agent-name}     # agent subagent_type
wicked-garden:{domain}:{skill-name}     # skills
```

### Specialist System

Specialists are defined in `.claude-plugin/specialist.json` as a lean manifest. Each specialist has:
- **name**: Short identifier (e.g., "engineering")
- **role**: Category (e.g., "engineering", "devsecops", "quality-engineering")
- **enhances**: Which crew phases they participate in

Crew's smart decisioning maps signals to specialists and determines which to engage for each project.

## Knowledge Graph (v3.4.0+)

A typed entity and relationship layer backed by SQLite, managed by `scripts/smaht/knowledge_graph.py`. Tracks requirements, designs, tasks, tests, decisions, and their traceability relationships across crew phases.

### Entity Types (8)

`requirement`, `acceptance_criteria`, `design_artifact`, `task`, `test_scenario`, `evidence`, `decision`, `incident`

### Relationship Types (7)

`TRACES_TO`, `IMPLEMENTED_BY`, `TESTED_BY`, `VERIFIES`, `DECIDED_BY`, `BLOCKS`, `SUPERSEDES`

### Storage

Entities and relationships are stored in a single SQLite database at `~/.something-wicked/wicked-garden/local/wicked-smaht/knowledge/knowledge_graph.db`. Indexed by entity type, project, phase, and relationship endpoints for fast lookups.

### Subgraph Traversal

`get_subgraph(entity_id, depth=2)` performs BFS from a starting entity, collecting all reachable entities and relationships within the specified depth. Used by the impact analyzer to discover transitive dependencies.

```bash
# Create an entity
knowledge_graph.py create-entity --type requirement --name "Auth must use OAuth2" --phase clarify --project P1

# Get related entities
knowledge_graph.py related --id <entity-id> --direction forward

# Extract a subgraph (2 hops deep)
knowledge_graph.py subgraph --id <entity-id> --depth 2

# View graph statistics
knowledge_graph.py stats
```

## Lifecycle Scoring (v3.4.0+)

Five composable scorers in `scripts/search/lifecycle_scoring.py` that boost or penalize search and memory results based on crew phase, artifact freshness, traceability links, and gate status.

### Scorers

| Scorer | Effect |
|--------|--------|
| `phase_weighted` | Boosts items matching the active crew phase via an affinity matrix (e.g., `requirement` gets 1.4x during clarify) |
| `recency_decay` | Exponential decay based on item age in days (`e^(-rate * days)`, default rate 0.01) |
| `traceability_boost` | Boosts items with traceability links (1.3x for 1-2 links, 1.5x for 3+) |
| `gate_status` | Multiplier based on artifact state (VERIFIED 1.4x, APPROVED 1.3x, DRAFT 0.7x) |
| `reciprocal_rank_fusion` | Fuses multiple independent rankings via RRF with configurable k parameter |

### Pipeline Composition

Scorers are chained via `score_pipeline()`. The default pipeline runs `phase_weighted`, `recency_decay`, `traceability_boost`, and `gate_status` in order. RRF is opt-in for multi-ranker fusion.

```bash
# Score items with default pipeline
lifecycle_scoring.py score --phase build < items.json

# Score with specific scorers
lifecycle_scoring.py score --phase test --scorers phase_weighted,recency_decay < items.json

# Custom decay rate
lifecycle_scoring.py score --phase build --decay-rate 0.05 < items.json
```

Each item in the output includes `_score` (final composite score) and `_score_breakdown` (per-scorer multipliers) for transparency.
