# Utility Plugin Integration

How wicked-crew integrates with utility plugins (graceful degradation).

## Task Management (Claude Native)

Crew uses Claude's native task tools for all task lifecycle operations. **Use the full richness of task fields** — kanban syncs everything automatically.

### Creating Tasks

```
TaskCreate(
  subject="{Phase}: {project-name} - {task description}",
  description="WHY this task exists, what problem it solves, acceptance criteria",
  activeForm="Working on {task}",
  metadata={
    "priority": "P1",           # P0 (critical) through P3 (minor)
    "assigned_to": "agent-name"  # who owns this
  }
)
```

### Updating Tasks (use full fields)

```
# Set dependencies between tasks
TaskUpdate(taskId="{id}", addBlockedBy=["{blocker-id}"])
TaskUpdate(taskId="{id}", addBlocks=["{dependent-id}"])

# Update with reasoning, not just status
TaskUpdate(
  taskId="{id}",
  status="completed",
  description="Original desc + \n\n## Outcome\nChose X because Y. Trade-off: Z."
)
```

### Enrichment Guidelines

- **description**: Include the WHY, not just the WHAT. Add outcomes when completing.
- **addBlockedBy/addBlocks**: Set dependencies — kanban tracks and visualizes them.
- **metadata.priority**: Set explicitly instead of relying on keyword inference.
- **description updates on completion**: Document what was decided, learned, or changed.

### Querying

```
TaskList()  # filter by subject: (?i)^{phase}[\s:-].*{project-name}
TaskGet(taskId="{id}")
```

**Automatic sync**: If wicked-kanban is installed, its PostToolUse hook automatically syncs all TaskCreate/TaskUpdate fields to persistent kanban storage. No explicit kanban calls needed.

## wicked-mem

**When available**: Cross-session learning

```bash
# Store decision
/wicked-mem:store --type decision --tags "{project}" "{decision}"

# Recall past context
/wicked-mem:recall "{project pattern}"

# Store episodic memory
/wicked-mem:store --type episodic --tags "{project}" "Encountered {issue}, resolved by {solution}"
```

**Fallback**: Project files in `~/.something-wicked/wicked-crew/projects/`

### Memory Types for Projects

| Type | Use Case |
|------|----------|
| decision | Architecture choices, tradeoffs |
| episodic | Bugs fixed, lessons learned |
| procedural | Patterns that worked |
| preference | User workflow preferences |

## wicked-cache

**When available**: Cache specialist discovery and signal analysis

```bash
# Cache analysis results
python3 "${CLAUDE_PLUGIN_ROOT}/../wicked-cache/scripts/cache.py" set \
  "crew:analysis:{project}" "{analysis_json}" --ttl 3600

# Retrieve cached
python3 "${CLAUDE_PLUGIN_ROOT}/../wicked-cache/scripts/cache.py" get \
  "crew:analysis:{project}"
```

**Fallback**: Re-run analysis each time (no persistence)

### Cache Keys

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `crew:specialists` | 1h | Available specialists |
| `crew:analysis:{project}` | 1h | Signal analysis results |
| `crew:phase:{project}` | 24h | Phase state |

## Detection Pattern

Crew uses Claude's native task tools (TaskCreate, TaskUpdate, TaskList, TaskGet) directly — no plugin detection needed for task management. Utility plugins like wicked-kanban enhance this automatically via hooks.

For optional utility plugins (wicked-mem, wicked-cache), use graceful degradation:

```python
# Check if a utility plugin command is available
# by attempting to use it; if unavailable, skip gracefully
```

```
# In markdown commands, use conditional phrasing:
# "If wicked-mem is available:" → /wicked-mem:store ...
# Otherwise, skip the step (no fallback needed)
```

## Configuration

Users can customize utility plugin usage in `~/.something-wicked/wicked-crew/config.yaml`:

```yaml
utilities:
  kanban:
    enabled: true
    auto_track: true  # Auto-create tasks from phase deliverables

  mem:
    enabled: true
    auto_store_decisions: true  # Store architectural decisions

  cache:
    enabled: true
    ttl_hours: 1
```

## Integration Events

Crew emits events when engaging utilities:

```
crew:utility:engaged:success
  └── context: {utility: "kanban", action: "create-task"}

crew:utility:unavailable:warning
  └── context: {utility: "mem", fallback: "file-based"}
```
