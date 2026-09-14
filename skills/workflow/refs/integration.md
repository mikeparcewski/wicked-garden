---
phase_relevance: ["*"]
archetype_relevance: ["*"]
---
# Utility Plugin Integration

How wicked-crew integrates with utility plugins (graceful degradation).

## Task Management (the harness's task list)

Crew records every task-lifecycle operation in the harness's task list. **Use the full richness of task fields, including `metadata`, per the event envelope contract in `scripts/_event_schema.py`.** PreToolUse validates every TaskCreate/TaskUpdate against that contract.

### Creating Tasks

One task per unit, with these fields (`metadata` per the event envelope contract):

```
subject:      "{Phase}: {project-name} - {task description}"
description:  "WHY this task exists, what problem it solves, acceptance criteria"
activeForm:   "Working on {task}"
metadata:
  event_type:   task            # or coding-task, gate-finding, phase-transition, procedure-trigger, subtask
  chain_id:     {project}.{phase}   # dotted causality: {project}.root, {project}.{phase}, {project}.{phase}.{gate}
  source_agent: {agent-name}
  phase:        {phase}         # required for coding-task, gate-finding, phase-transition
  priority:     P1              # P0 (critical) through P3 (minor)
  assigned_to:  agent-name      # who owns this
```

**Hand-off (harness-specific)** — on Claude Code the task-list tools (create / update) take these fields directly; on any other seat keep the same fields in your working notes and report them in your output.

### Updating Tasks (use full fields)

- Link dependencies between tasks: `blockedBy: [{blocker-id}]` / `blocks: [{dependent-id}]`.
- Update with reasoning, not just status: `status: completed` + append to the description
  `## Outcome — Chose X because Y. Trade-off: Z.`

## Outcome\nChose X because Y. Trade-off: Z."
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

## wicked-garden-mem (memory over wicked-estate)

**When available**: Cross-session learning

**Hand-off** — store a decision: open the `wicked-garden-mem` skill and run its `store` action with `{decision}` and `kind=fact, about=[{project}]`; on Claude Code this is the Skill tool, on any other seat open the named skill from your catalog and carry it out inline, then continue here.

**Hand-off** — recall past context: the `wicked-garden-mem` skill's `recall` action with `{project pattern}` as the query; on Claude Code this is the Skill tool, on any other seat open the named skill from your catalog and carry it out inline, then continue here.

**Hand-off** — store an episode: the `wicked-garden-mem` skill's `store` action with `Encountered {issue}, resolved by {solution}` and `kind=episode, about=[{project}]`; on Claude Code this is the Skill tool, on any other seat open the named skill from your catalog and carry it out inline, then continue here.

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

For optional memory storage (wicked-garden-mem), use graceful degradation:

```python
# Check if a utility plugin skill is available
# by attempting to use it; if unavailable, skip gracefully
```

```
# In markdown commands, use conditional phrasing:
# "If the memory layer is available:" → a Hand-off to the wicked-garden-mem skill's store action
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
