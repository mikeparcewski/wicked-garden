# Wicked Garden Event Schema (v3)

Canonical event format for cross-plugin communication.

## Event Format

```
[namespace:entity:action:status]
```

### Components

| Component | Description | Examples |
|-----------|-------------|----------|
| **namespace** | Plugin identifier | `crew`, `pmo`, `jam`, `kanban`, `qe`, `strategy`, `devsecops`, `appeng`, `arch`, `ux`, `product`, `compliance`, `data` |
| **entity** | What is affected | `project`, `initiative`, `task`, `phase`, `report`, `review`, `analysis` |
| **action** | What happened | `started`, `completed`, `created`, `updated`, `failed` |
| **status** | Result state | `success`, `error`, `warning`, `pending` |

### Examples

```
crew:project:started:success
crew:phase:completed:success
qe:analysis:completed:success
arch:review:completed:success
ux:a11y:audit:completed:success
compliance:pii:detected:warning
data:pipeline:designed:success
```

## Event Payload

Events carry JSON payloads with references (not full data):

```json
{
  "event": "crew:task:completed:success",
  "timestamp": "2026-01-24T10:30:00Z",
  "source": "wicked-crew",
  "refs": {
    "project": "~/.something-wicked/wicked-crew/projects/my-project/",
    "task_id": "task_abc123",
    "phase": "build"
  },
  "context": {
    "files_modified": ["src/index.ts", "tests/index.test.ts"],
    "commit": "abc1234"
  }
}
```

### Payload Fields

| Field | Required | Description |
|-------|----------|-------------|
| `event` | Yes | Full event name |
| `timestamp` | Yes | ISO 8601 timestamp |
| `source` | Yes | Emitting plugin |
| `refs` | Yes | Paths/IDs to read full state |
| `context` | No | Additional metadata |

## Event Principles

1. **Observational, not imperative**: Events describe what happened, not what to do
2. **References over data**: Include paths to state, not full state
3. **Self-contained enough**: Consumer can act without reading refs
4. **Namespaced**: No collisions between plugins

## Complete Plugin Event Catalog

### wicked-crew (Orchestrator)

| Event | Trigger |
|-------|---------|
| `crew:project:started:success` | New project created |
| `crew:project:completed:success` | All phases complete |
| `crew:phase:started:success` | Phase execution begins |
| `crew:phase:completed:success` | Phase deliverables done |
| `crew:phase:approved:success` | Phase gate passed |
| `crew:task:created:success` | Task added |
| `crew:task:completed:success` | Task finished |
| `crew:specialist:needed:pending` | Smart decisioning identified need |
| `crew:specialist:engaged:success` | Specialist plugin activated |
| `crew:specialist:unavailable:warning` | Using fallback agent |
| `crew:signal:detected:success` | Input signal classified |

### wicked-jam (Ideation)

| Event | Trigger |
|-------|---------|
| `jam:brainstorm:started:success` | Session begins |
| `jam:brainstorm:completed:success` | Synthesis done |
| `jam:insight:captured:success` | Key insight recorded |
| `jam:perspective:added:success` | New perspective |

### wicked-product (Business Strategy)

| Event | Trigger |
|-------|---------|
| `strategy:analysis:started:success` | Analysis begins |
| `strategy:analysis:completed:success` | Analysis done |
| `strategy:roi:calculated:success` | ROI computation done |
| `strategy:value:assessed:success` | Value assessment complete |
| `strategy:competitive:analyzed:success` | Competitive analysis done |

### wicked-delivery (Project Management)

| Event | Trigger |
|-------|---------|
| `pmo:report:generated:success` | Report created |
| `pmo:analysis:completed:success` | Analysis finished |
| `pmo:risk:identified:warning` | Risk detected |
| `pmo:milestone:reached:success` | Milestone complete |

### wicked-qe (Quality Engineering)

| Event | Trigger |
|-------|---------|
| `qe:analysis:started:success` | QE analysis begins |
| `qe:analysis:completed:success` | Analysis done |
| `qe:scenario:generated:success` | Test scenario created |
| `qe:risk:identified:warning` | Quality risk found |
| `qe:tdd:cycle:completed:success` | Red-green-refactor done |
| `qe:coverage:assessed:success` | Coverage check complete |

### wicked-platform (DevSecOps)

| Event | Trigger |
|-------|---------|
| `devsecops:scan:started:success` | Security scan begins |
| `devsecops:scan:completed:success` | Scan finished |
| `devsecops:vulnerability:found:warning` | Security issue detected |
| `devsecops:deployment:ready:success` | Deployment artifacts ready |
| `devsecops:pipeline:validated:success` | CI/CD pipeline verified |
| `devsecops:infra:reviewed:success` | Infrastructure review done |

### wicked-engineering (Engineering)

| Event | Trigger |
|-------|---------|
| `appeng:review:started:success` | Code review begins |
| `appeng:review:completed:success` | Review done |
| `appeng:implementation:completed:success` | Code written |
| `appeng:debug:completed:success` | Debugging done |
| `appeng:refactor:completed:success` | Refactoring done |
| `appeng:issue:found:warning` | Code issue detected |

### wicked-arch (Architecture)

| Event | Trigger |
|-------|---------|
| `arch:review:started:success` | Architecture review begins |
| `arch:review:completed:success` | Review done |
| `arch:design:completed:success` | Design finalized |
| `arch:adr:created:success` | ADR documented |
| `arch:integration:designed:success` | Integration design done |
| `arch:concern:identified:warning` | Architectural concern |

### wicked-ux (User Experience)

| Event | Trigger |
|-------|---------|
| `ux:review:started:success` | UX review begins |
| `ux:review:completed:success` | Review done |
| `ux:a11y:audit:completed:success` | Accessibility audit done |
| `ux:design:reviewed:success` | Design review complete |
| `ux:persona:created:success` | User persona defined |
| `ux:wcag:violation:error` | WCAG violation found |
| `ux:a11y:issue:warning` | A11y concern detected |

### wicked-product (Product Management)

| Event | Trigger |
|-------|---------|
| `product:requirements:gathered:success` | Requirements complete |
| `product:story:written:success` | User story created |
| `product:acceptance:defined:success` | AC defined |
| `product:alignment:achieved:success` | Stakeholder alignment |
| `product:priority:set:success` | Priority determined |

### wicked-compliance (Compliance)

| Event | Trigger |
|-------|---------|
| `compliance:audit:started:success` | Audit begins |
| `compliance:audit:completed:success` | Audit done |
| `compliance:evidence:collected:success` | Evidence gathered |
| `compliance:violation:detected:warning` | Compliance issue |
| `compliance:pii:detected:warning` | PII exposure found |
| `compliance:policy:checked:success` | Policy verified |

### wicked-data (Data Engineering)

| Event | Trigger |
|-------|---------|
| `data:analysis:completed:success` | Data analysis done |
| `data:pipeline:designed:success` | Pipeline design done |
| `data:quality:assessed:success` | Data quality check |
| `data:schema:validated:success` | Schema validation done |
| `data:model:reviewed:success` | ML model review done |
| `data:architecture:reviewed:success` | Data arch review done |
| `data:profiling:completed:success` | Data profiling done |

### wicked-kanban (Task Management)

| Event | Trigger |
|-------|---------|
| `kanban:task:created:success` | Task added to board |
| `kanban:task:moved:success` | Task status changed |
| `kanban:task:completed:success` | Task done |
| `kanban:initiative:created:success` | Initiative created |

## Event Storage

Events are logged to:
```
~/.something-wicked/{plugin}/events.jsonl
```

Format: JSON Lines (one event per line)

### Rotation

- Max file size: 10MB
- Rotate to `events.{timestamp}.jsonl`
- Keep last 5 rotated files

## Hook Ordering

When multiple plugins subscribe to the same event:

1. Hooks execute in **priority order** (lower = earlier)
2. Default priority: 100
3. Priority declared in `hooks.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "crew:task:completed",
        "hooks": [
          {
            "type": "command",
            "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/on-task-complete.py",
            "priority": 50
          }
        ]
      }
    ]
  }
}
```

### Priority Guidelines

| Range | Use Case |
|-------|----------|
| 0-25 | System/critical (logging, audit) |
| 26-50 | Data collection (pmo, mem) |
| 51-75 | Processing (qe analysis) |
| 76-100 | Default |
| 101+ | Cleanup, notifications |

## Integration Checklist

For plugins emitting events:

- [ ] Events follow `[namespace:entity:action:status]` format
- [ ] Payloads use refs, not full data
- [ ] Events logged to `events.jsonl`
- [ ] Events are observational, not imperative

For plugins consuming events:

- [ ] Subscribe via hooks.json
- [ ] Declare priority if order matters
- [ ] Handle missing refs gracefully
- [ ] Don't assume other plugins present
