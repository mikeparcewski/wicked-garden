---
description: Log a production incident linked to the current crew project
argument-hint: "<description> [--severity critical|high|medium|low] [--components comp1,comp2]"
---

# /wicked-garden:crew:incident

Log an incident and create traceability links back to the crew project's requirements and code.

> **Scope**: `crew:incident` **logs** a production incident against an active crew project with traceability links.
> For **rapid triage** of an active incident (root cause, blast radius, remediation), use
> `/wicked-garden:platform:incident` instead.

## Arguments

- `description` (required): Description of the incident
- `--severity` (optional): Incident severity level. Default: medium
  - `critical`: Service down, data loss, security breach
  - `high`: Major feature broken, significant user impact
  - `medium`: Partial degradation, workaround available
  - `low`: Minor issue, cosmetic, no user impact
- `--components` (optional): Comma-separated list of affected components

## Instructions

### 1. Find Active Project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

If no active project found, inform user and suggest `/wicked-garden:crew:start`. Incidents can still be logged without a project, but traceability links require one.

### 2. Parse Arguments

Extract from the command arguments:
- `description`: The incident description (required)
- `severity`: critical, high, medium, or low (default: medium)
- `components`: List of affected component names (optional)

If no description provided, ask the user to describe the incident.

### 3. Track Incident Task

```
TaskCreate(
  subject="Incident: {project-name} - {short_description}",
  description="Logging incident: {description}\nSeverity: {severity}"
)
TaskUpdate(taskId={task_id}, status="in_progress")
```

### 4. Store Incident Record

Generate an incident ID and store via DomainStore:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path('${CLAUDE_PLUGIN_ROOT}/scripts')))
from _domain_store import DomainStore
ds = DomainStore('wicked-crew')
incident = {
    'id': f'inc-{uuid.uuid4().hex[:8]}',
    'project_id': '{project_name}',
    'description': '''${DESCRIPTION}''',
    'severity': '{severity}',
    'affected_components': {components_json},
    'status': 'open',
    'created_at': datetime.now(timezone.utc).isoformat(),
    'resolved_at': None,
    'resolution': None,
    'traceability_links': []
}
result = ds.create('incidents', incident)
print(json.dumps(result or incident, indent=2))
"
```

### 5. Create Traceability Links

If the project has requirements or code artifacts, create INCIDENT_OF links:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/traceability.py create \
  --source-id "{incident_id}" \
  --source-type "incident" \
  --target-id "{requirement_or_code_id}" \
  --target-type "{requirement|code}" \
  --link-type "INCIDENT_OF" \
  --project "{project_name}" \
  --created-by "operate"
```

Create links for each affected component that maps to a known requirement or code artifact.

### 6. Delegate to Incident Responder

For critical or high severity incidents, delegate to the platform incident responder:

```
Task(
  subagent_type="wicked-garden:platform:incident-responder",
  prompt="Incident response for project '{project-name}'.

Incident ID: {incident_id}
Severity: {severity}
Description: {description}
Affected Components: {components}

Please provide:
1. Immediate actions — what to do right now
2. Root cause investigation steps
3. Mitigation recommendations
4. Communication template for stakeholders

Project context: {project_description}"
)
```

For medium or low severity, provide a brief inline triage instead.

### 7. Display Incident Summary

```markdown
## Incident Logged: {incident_id}

**Project**: {project-name}
**Severity**: {severity}
**Status**: open
**Components**: {components}

### Description
{description}

### Traceability
| Link | Type | Target |
|------|------|--------|
{links table}

### Next Steps
{incident responder recommendations OR inline triage}

---

To update this incident: edit via DomainStore
To view all incidents: check operate phase status
To close: resolve and run `/wicked-garden:crew:retro`
```

### 8. Complete Task

```
TaskUpdate(taskId={task_id}, status="completed")
```

## Examples

```bash
# Log a critical incident
/wicked-garden:crew:incident "Auth service returning 500 errors after deploy" --severity critical --components auth,api-gateway

# Log a medium incident (default severity)
/wicked-garden:crew:incident "Search results showing stale data for new users"

# Log with affected components
/wicked-garden:crew:incident "Memory leak in worker process" --severity high --components worker,queue
```
