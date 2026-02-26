# wicked-observability

Three-layer observability for the wicked-garden ecosystem — traces every tool call, validates plugin outputs against JSON schemas, and runs structural health checks across all installed plugins.

## Quick Start

```bash
# Install
claude plugin install wicked-observability@wicked-garden

# Check all installed plugins for structural issues
/wicked-observability:health

# Query recent tool traces
/wicked-observability:traces --tail 20

# Validate plugin outputs against contracts
/wicked-observability:assert
```

## Workflows

### Check ecosystem health before a release

Running `/wicked-observability:health` validates every installed plugin's structure and prints a summary:

```
[OK] Health probe: HEALTHY
   Plugins checked: 18  |  Errors: 0  |  Warnings: 1
   Healthy: 17  |  Degraded: 1  |  Unhealthy: 0

   Violations (1):
   [WARNING] wicked-kanban  (hooks/hooks.json)
             Hook event 'TaskCompleted' is documented but silently never fires
             in the Claude Code runtime. Scripts bound to it will not execute.

   Report written to: ~/.something-wicked/wicked-observability/health/latest.json
```

Five checks run per plugin:

| Check | What It Validates |
|-------|------------------|
| Hook events | All event names match the valid Claude Code event set; `TaskCompleted` flagged as WARNING |
| Script paths | Every `${CLAUDE_PLUGIN_ROOT}/...` path referenced in hooks.json actually exists |
| Cross-plugin refs | Every `subagent_type="wicked-x:agent-name"` points to a real plugin and agent file |
| Specialist contracts | `specialist.json` has required fields; persona agent paths resolve |
| plugin.json fields | `name`, `version`, `description` are present and non-empty |

Exit codes: `0` healthy, `1` warnings only, `2` one or more errors.

### Diagnose a silent hook failure

Hook failures don't always surface as errors — a hook that writes empty output or swallows an exception looks like success. Run `/wicked-observability:traces --silent-only` to find these:

```
SILENT FAILURES (last 50 traces)

  seq  tool             plugin              hook_script                  stderr
  ─────────────────────────────────────────────────────────────────────────────
  012  Write            wicked-kanban       todo_sync.py                 KeyError: 'initiative'
  031  TaskUpdate       wicked-mem          task_checkpoint.py           FileNotFoundError: ...
```

### Validate a plugin script output against its schema

After adding a schema for a plugin script, run `/wicked-observability:assert --plugin wicked-mem` to verify outputs match:

```
CONTRACT ASSERTIONS: wicked-mem

  memory.py       PASS  (12 assertions)
  recall.py       FAIL
    $.data.items[0].type: 'episodic' is not one of ['working', 'semantic', 'procedural', 'episodic']
    $.meta.total_ms: -3 is less than minimum 0

  1 passed, 1 failed
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-observability:health` | Run structural health probes on all (or one) installed plugin | `/wicked-observability:health --plugin wicked-crew` |
| `/wicked-observability:assert` | Validate plugin script outputs against JSON schemas | `/wicked-observability:assert --plugin wicked-mem --json` |
| `/wicked-observability:traces` | Query hook execution traces | `/wicked-observability:traces --tail 50 --silent-only` |

## Safety Guarantees

The trace writer runs on every tool call via a `PostToolUse` hook. Four guarantees prevent it from interfering with normal operation:

| Guarantee | Mechanism |
|-----------|-----------|
| SG-1: Fail-open | All errors are caught; hook always exits 0 with `{"continue": true}` |
| SG-2: Anti-recursion | Skips if `WICKED_TRACE_ACTIVE=1` is set, preventing infinite hook loops |
| SG-3: Correlation | Each record carries `session_id` + `seq` counter for session-scoped ordering |
| SG-4: Atomic append | Single write per invocation; records capped at 4KB to prevent disk abuse |

Secret values (API keys, tokens, Bearer headers) are redacted from command summaries before writing.

## Schema Layout

Contract assertions discover schemas from `schemas/{plugin}/{script-name}.json`. To add validation for a new plugin:

```
schemas/
└── wicked-mem/
    └── memory.json        ← JSON Schema for memory.py stdout
```

Example schema (`schemas/wicked-mem/memory.json`):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["data", "meta"],
  "properties": {
    "data": {
      "type": "object",
      "required": ["items"],
      "properties": {
        "items": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "type", "content"],
            "properties": {
              "type": {
                "enum": ["working", "semantic", "procedural", "episodic"]
              }
            }
          }
        }
      }
    },
    "meta": {
      "type": "object",
      "required": ["total_ms"],
      "properties": {
        "total_ms": { "type": "number", "minimum": 0 }
      }
    }
  }
}
```

Once the schema file is in place, `/wicked-observability:assert --plugin wicked-mem` will run it on the next invocation of `memory.py`.

## Storage

| Path | Contents |
|------|---------|
| `~/.something-wicked/wicked-observability/traces/` | JSONL trace files, one per session (`{session_id}.jsonl`) |
| `~/.something-wicked/wicked-observability/assertions/` | Daily assertion results (`{YYYY-MM-DD}.jsonl`) |
| `~/.something-wicked/wicked-observability/health/` | Latest health probe report (`latest.json`) |

## Integration

| Plugin | What It Adds | Without It |
|--------|-------------|------------|
| wicked-workbench | Dashboard views for traces, assertion results, and health data via the data gateway | Raw JSONL only; no visual summaries |
| wicked-scenarios | Run observability acceptance test scenarios for all three layers | No structured acceptance tests |
| wicked-crew | Health probe runs during phase gates to catch structural regressions before build phases | Health checks must be triggered manually |
| wicked-smaht | Context assembly pulls recent health and assertion data into prompt context | Health/assertion data not surfaced automatically |

## License

MIT
