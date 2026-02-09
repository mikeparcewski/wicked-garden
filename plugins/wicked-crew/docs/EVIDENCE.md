# Evidence Tracking

Evidence tracking in wicked-crew uses Claude's native task tools (TaskCreate/TaskUpdate/TaskList/TaskGet) and crew's phase directories. If wicked-kanban is installed, its PostToolUse hook automatically syncs task state to persistent storage.

## Evidence Tiers

| Tier | When | Evidence Type | Storage |
|------|------|---------------|---------|
| **L1** | Every task | `commit` | git commits linked to tasks |
| **L1** | Every task | `comment` | TaskUpdate descriptions |
| **L2** | Design phase | `doc:requirements` | `phases/design/` directory |
| **L2** | Design phase | `doc:design` | `phases/design/` directory |
| **L2** | Design phase | `qe:scenarios` | `phases/qe/` directory |
| **L3** | Post-build | `qe:gate-result` | `phases/{phase}/` gate output file |
| **L3** | Post-build | `test:results` | CI run URL or test output |
| **L3** | Post-build | `decision:rationale` | wicked-mem decision |
| **L4** | Compliance | `audit:control-{id}` | evidence file in project |

## Artifact Naming Convention

Format: `{tier}:{type}:{detail}`

Examples:
- `L1:commit:abc1234` - Commit linked to task
- `L2:doc:architecture` - Architecture design doc
- `L2:qe:scenarios` - Test scenarios from strategy gate
- `L3:qe:value-gate` - Value gate decision
- `L3:qe:execution-gate` - Execution gate decision
- `L3:test:unit-coverage` - Test coverage report
- `L4:audit:SOC2-CC6.1` - SOC2 control evidence

## Automatic Evidence Collection

### Gate Results (L3)

When a QE gate runs, the orchestrator:
1. Writes decision + rationale to the project's phase directory
2. Names the file with convention: `{gate}-gate-{timestamp}.md`
3. Stores rationale in wicked-mem as `decision` type

### Commits (L1)

Commits are tracked via git and linked to tasks through commit messages.

### Comments (L1)

Orchestrator updates are recorded via TaskUpdate descriptions and formatted markdown output.

## Manual Evidence Attachment

Place evidence files in the appropriate phase directory:

```
phases/design/architecture.md          # L2:doc:architecture
phases/qe/test-scenarios.md            # L2:qe:scenarios
phases/build/execution-gate-*.md       # L3:qe:execution-gate
phases/review/audit-evidence/          # L4:audit:*
```

For external URLs (CI runs, etc.), reference them in the gate result files or phase status.

## Querying Evidence

Use `/wicked-crew:evidence` to query evidence for a task:

```bash
/wicked-crew:evidence {task-id}
```

Output includes:
- L1: Commits and activity log entries
- L2: Design docs and scenarios
- L3: Gate results and test runs
- L4: Audit evidence (if any)

## Coverage Indicators

Evidence summary shows coverage per tier:
- `✓` - Evidence present
- `partial` - Some evidence, not complete
- `n/a` - Tier not applicable (e.g., L4 for non-compliance work)

## Integration with wicked-mem

Gate decisions are stored in wicked-mem for cross-session recall:

```bash
# Recall past gate decisions
/wicked-mem:recall "gate decision {target}"
```

Memory type: `decision`
Tags: `qe`, `gate`, `{gate-type}`

## Best Practices

1. **Let automation work** - L1 and L3 evidence is collected automatically
2. **Name artifacts consistently** - Use the `{tier}:{type}:{detail}` convention
3. **Link, don't copy** - Use URLs and paths, not inline content
4. **Tier matches task size** - Small tasks need L1, large initiatives need L3+
