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

Seven Python scripts handle lifecycle events:

| Hook | Event | Purpose |
|------|-------|---------|
| bootstrap | SessionStart | Initialize session state, detect environment |
| prompt_submit | UserPromptSubmit | Context assembly via smaht |
| pretool_taskcreate | PreToolUse:TaskCreate | Inject crew initiative metadata |
| posttool_task | PostToolUse:Task* | Sync task changes to kanban |
| compact | PreCompact | Checkpoint session state before compression |
| stop | Stop (async) | Store session learnings |
| task_completed | TaskCompleted | Verify task completion quality |

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
