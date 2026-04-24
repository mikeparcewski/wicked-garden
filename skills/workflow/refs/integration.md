# Utility Plugin Integration

How wicked-crew integrates with utility plugins (graceful degradation).

## Task Management (Claude Native)

Crew uses Claude's native task tools for all task lifecycle operations. **Use the full richness of task fields, including `metadata`, per the event envelope contract in `scripts/_event_schema.py`.** PreToolUse validates every TaskCreate/TaskUpdate against that contract.

### Creating Tasks

```
TaskCreate(
  subject="{Phase}: {project-name} - {task description}",
  description="WHY this task exists, what problem it solves, acceptance criteria",
  activeForm="Working on {task}",
  metadata={
    "event_type": "task",          # or coding-task, gate-finding, phase-transition, procedure-trigger, subtask
    "chain_id": "{project}.{phase}",  # dotted causality: {project}.root, {project}.{phase}, {project}.{phase}.{gate}
    "source_agent": "{agent-name}",
    "phase": "{phase}",             # required for coding-task, gate-finding, phase-transition
    "priority": "P1",               # P0 (critical) through P3 (minor)
    "assigned_to": "agent-name"     # who owns this
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
- **addBlockedBy/addBlocks**: Set dependencies — task views render blocked state until the dependency closes.
- **metadata.priority**: Set explicitly instead of relying on keyword inference.
- **description updates on completion**: Document what was decided, learned, or changed.

### Querying

```
TaskList()  # filter by subject: (?i)^{phase}[\s:-].*{project-name}
TaskGet(taskId="{id}")
```

**Validation & persistence**: PreToolUse runs `pretool_taskcreate.py` on every TaskCreate/TaskUpdate, validating the `metadata` dict against `scripts/_event_schema.py` (event_type, chain_id shape, source_agent, required per-type fields). Tasks persist natively under `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/`.

## wicked-brain:memory

**When available**: Cross-session learning

```
# Store decision
Skill(skill="wicked-brain:memory", args="store \"{decision}\" --type decision --tags \"{project}\"")

# Recall past context
Skill(skill="wicked-brain:memory", args="recall \"{project pattern}\"")

# Store episodic memory
Skill(skill="wicked-brain:memory", args="store \"Encountered {issue}, resolved by {solution}\" --type episodic --tags \"{project}\"")
```

**Fallback**: Project files stored locally via DomainStore under the wicked-crew domain

### Memory Types for Projects

| Type | Use Case |
|------|----------|
| decision | Architecture choices, tradeoffs |
| episodic | Bugs fixed, lessons learned |
| procedural | Patterns that worked |
| preference | User workflow preferences |

## Detection Pattern

Crew uses Claude's native task tools (TaskCreate, TaskUpdate, TaskList, TaskGet) directly — no plugin detection needed for task management. The PreToolUse hook enforces the metadata envelope defined in `scripts/_event_schema.py`.

For optional memory storage (wicked-brain:memory), use graceful degradation:

```python
# Check if a utility plugin skill is available
# by attempting to use it; if unavailable, skip gracefully
```

```
# In markdown commands, use conditional phrasing:
# "If wicked-brain:memory is available:" → Skill(skill="wicked-brain:memory", args="store ...")
# Otherwise, skip the step (no fallback needed)
```

## Configuration

Users can customize utility plugin usage in the wicked-crew local storage `config.yaml`:

```yaml
utilities:
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
  └── context: {utility: "mem", action: "store-decision"}

crew:utility:unavailable:warning
  └── context: {utility: "mem", fallback: "file-based"}
```
