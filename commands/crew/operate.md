---
description: Enter and manage the operate phase for the current crew project
argument-hint: "[--status]"
---

# /wicked-garden:crew:operate

Enter the operate phase for post-delivery monitoring, incident tracking, and feedback collection.

> **Scope**: `crew:operate` **enters** the post-delivery operate phase and manages ongoing operations.
> For a **read-only state view** without entering a new phase, use `/wicked-garden:crew:status` instead.

## Arguments

- `--status` (optional): Show operational checklist status without entering the phase

## Instructions

### 1. Find Active Project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

If no active project found, inform user and suggest `/wicked-garden:crew:start`.

### 2. Read Project State

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} status --json
```

Verify the project has completed the review phase. If review is not completed, inform the user that operate depends on review completion.

### 3. Track Operate Task

```
TaskCreate(
  subject="Operate: {project-name} - post-delivery operations",
  description="Running operate phase: monitoring setup, incident tracking, feedback collection"
)
TaskUpdate(taskId={task_id}, status="in_progress")
```

### 4. Generate Operational Checklist

If `--status` flag is set, skip to Step 7.

Build the operational checklist based on the project's signals and complexity:

```markdown
## Operational Checklist

- [ ] Monitoring: Health checks and alerting configured
- [ ] Logging: Structured logging for new components
- [ ] Runbook: Incident response procedures documented
- [ ] Rollback: Rollback procedure tested or documented
- [ ] Feedback: User feedback collection channel identified
- [ ] Metrics: Key performance indicators defined
```

If the project has security signals, add:
- [ ] Security: Post-deployment security scan completed

If the project has performance signals, add:
- [ ] Performance: Baseline performance metrics captured

If the project has data signals, add:
- [ ] Data: Data quality monitoring configured

### 5. Delegate Reliability Assessment

Delegate to the platform SRE agent for a reliability assessment of the delivered work:

```
Task(
  subagent_type="wicked-garden:platform:sre",
  prompt="Perform a post-delivery reliability assessment for project '{project-name}'.

Review the project deliverables and provide:
1. Monitoring gaps — what should be monitored that isn't
2. Alerting recommendations — thresholds and escalation paths
3. Runbook outline — key operational procedures
4. Rollback readiness — can we safely revert if needed

Project description: {description}
Complexity: {complexity_score}/7
Signals: {signals}

Focus on actionable recommendations, not theoretical best practices."
)
```

If the SRE agent is not available, fall back to generating a basic reliability assessment inline based on the project's signals and complexity.

### 6. Store Operational Checklist

Store the checklist as a deliverable:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} update \
  --data '{"operate_checklist": {checklist_json}, "operate_started_at": "{iso_timestamp}"}' \
  --json
```

### 7. Display Status

```markdown
## Operate Phase: {project-name}

**Status**: {active|checklist-complete}

### Operational Checklist
{checklist with completion status}

### Reliability Assessment
{SRE assessment summary or basic inline assessment}

### Available Actions
- `/wicked-garden:crew:incident` — Log a production incident
- `/wicked-garden:crew:feedback` — Capture user/stakeholder feedback
- `/wicked-garden:crew:retro` — Generate retrospective from operate data
- `/wicked-garden:crew:approve operate` — Complete the operate phase
```

### 8. Complete Task

```
TaskUpdate(taskId={task_id}, status="completed")
```

## Examples

```bash
# Enter operate phase
/wicked-garden:crew:operate

# Check operational status
/wicked-garden:crew:operate --status
```
