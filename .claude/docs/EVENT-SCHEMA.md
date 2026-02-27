# Wicked Garden Event Schema (v4 - Unified)

Canonical event format for cross-domain communication within the wicked-garden plugin.

## Event Format

```
[domain:entity:action:status]
```

### Components

| Component | Description | Examples |
|-----------|-------------|----------|
| **domain** | Domain identifier | `crew`, `delivery`, `jam`, `kanban`, `qe`, `product`, `platform`, `engineering`, `data`, `agentic` |
| **entity** | What is affected | `project`, `initiative`, `task`, `phase`, `report`, `review`, `analysis` |
| **action** | What happened | `started`, `completed`, `created`, `updated`, `failed` |
| **status** | Result state | `success`, `error`, `warning`, `pending` |

### Examples

```
crew:project:started:success
crew:phase:completed:success
qe:analysis:completed:success
engineering:review:completed:success
platform:scan:completed:success
data:pipeline:designed:success
```

## Event Payload

Events carry JSON payloads with references (not full data):

```json
{
  "event": "crew:task:completed:success",
  "timestamp": "2026-01-24T10:30:00Z",
  "source": "wicked-garden",
  "domain": "crew",
  "refs": {
    "project": "~/.something-wicked/wicked-garden/crew/projects/my-project/",
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
| `source` | Yes | Always `wicked-garden` (unified plugin) |
| `domain` | Yes | Domain that emitted the event |
| `refs` | Yes | Paths/IDs to read full state |
| `context` | No | Additional metadata |

## Event Principles

1. **Observational, not imperative**: Events describe what happened, not what to do
2. **References over data**: Include paths to state, not full state
3. **Self-contained enough**: Consumer can act without reading refs
4. **Domain-namespaced**: No collisions between domains

## Complete Domain Event Catalog

### crew (Orchestrator)

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
| `crew:specialist:engaged:success` | Specialist domain activated |
| `crew:specialist:unavailable:warning` | Using fallback agent |
| `crew:signal:detected:success` | Input signal classified |

### jam (Ideation)

| Event | Trigger |
|-------|---------|
| `jam:brainstorm:started:success` | Session begins |
| `jam:brainstorm:completed:success` | Synthesis done |
| `jam:insight:captured:success` | Key insight recorded |
| `jam:perspective:added:success` | New perspective |

### product (Business Strategy + Product)

| Event | Trigger |
|-------|---------|
| `product:analysis:started:success` | Analysis begins |
| `product:analysis:completed:success` | Analysis done |
| `product:roi:calculated:success` | ROI computation done |
| `product:value:assessed:success` | Value assessment complete |
| `product:requirements:gathered:success` | Requirements complete |
| `product:story:written:success` | User story created |
| `product:acceptance:defined:success` | AC defined |
| `product:priority:set:success` | Priority determined |

### delivery (Project Management)

| Event | Trigger |
|-------|---------|
| `delivery:report:generated:success` | Report created |
| `delivery:analysis:completed:success` | Analysis finished |
| `delivery:risk:identified:warning` | Risk detected |
| `delivery:milestone:reached:success` | Milestone complete |

### qe (Quality Engineering)

| Event | Trigger |
|-------|---------|
| `qe:analysis:started:success` | QE analysis begins |
| `qe:analysis:completed:success` | Analysis done |
| `qe:scenario:generated:success` | Test scenario created |
| `qe:risk:identified:warning` | Quality risk found |
| `qe:tdd:cycle:completed:success` | Red-green-refactor done |
| `qe:coverage:assessed:success` | Coverage check complete |

### platform (DevSecOps)

| Event | Trigger |
|-------|---------|
| `platform:scan:started:success` | Security scan begins |
| `platform:scan:completed:success` | Scan finished |
| `platform:vulnerability:found:warning` | Security issue detected |
| `platform:deployment:ready:success` | Deployment artifacts ready |
| `platform:pipeline:validated:success` | CI/CD pipeline verified |
| `platform:infra:reviewed:success` | Infrastructure review done |

### engineering (Engineering)

| Event | Trigger |
|-------|---------|
| `engineering:review:started:success` | Code review begins |
| `engineering:review:completed:success` | Review done |
| `engineering:implementation:completed:success` | Code written |
| `engineering:debug:completed:success` | Debugging done |
| `engineering:refactor:completed:success` | Refactoring done |
| `engineering:issue:found:warning` | Code issue detected |

### data (Data Engineering)

| Event | Trigger |
|-------|---------|
| `data:analysis:completed:success` | Data analysis done |
| `data:pipeline:designed:success` | Pipeline design done |
| `data:quality:assessed:success` | Data quality check |
| `data:schema:validated:success` | Schema validation done |
| `data:model:reviewed:success` | ML model review done |

### agentic (Agentic Architecture)

| Event | Trigger |
|-------|---------|
| `agentic:review:completed:success` | Architecture review done |
| `agentic:pattern:identified:success` | Pattern detected |
| `agentic:design:completed:success` | Agent design finalized |
| `agentic:audit:completed:success` | Capability audit done |

### kanban (Task Management)

| Event | Trigger |
|-------|---------|
| `kanban:task:created:success` | Task added to board |
| `kanban:task:moved:success` | Task status changed |
| `kanban:task:completed:success` | Task done |
| `kanban:initiative:created:success` | Initiative created |

## Event Storage

Events are logged to:
```
~/.something-wicked/wicked-garden/events.jsonl
```

Format: JSON Lines (one event per line)

### Rotation

- Max file size: 10MB
- Rotate to `events.{timestamp}.jsonl`
- Keep last 5 rotated files

## Hook Ordering

When multiple hooks subscribe to the same event:

1. Hooks execute in **priority order** (lower = earlier)
2. Default priority: 100
3. Priority declared in `hooks/hooks.json`

### Priority Guidelines

| Range | Use Case |
|-------|----------|
| 0-25 | System/critical (logging, audit) |
| 26-50 | Data collection (delivery, mem) |
| 51-75 | Processing (qe analysis) |
| 76-100 | Default |
| 101+ | Cleanup, notifications |

## Integration Checklist

For domains emitting events:

- [ ] Events follow `[domain:entity:action:status]` format
- [ ] Payloads use refs, not full data
- [ ] Events logged to `events.jsonl`
- [ ] Events are observational, not imperative

For domains consuming events:

- [ ] Subscribe via hooks/hooks.json
- [ ] Declare priority if order matters
- [ ] Handle missing refs gracefully
