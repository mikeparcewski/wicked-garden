---
name: observability
description: |
  Plugin observability and engineer toolchain discovery. Health probes, contract assertions,
  and hook execution tracing for the plugin ecosystem. Also discovers and queries APM, logging,
  metrics, and cloud monitoring CLIs available in the engineer's environment.

  Use when: "check plugin health", "are hooks working", "silent failures",
  "trace hook execution", "validate contracts", "plugin diagnostics",
  "check logs", "query metrics", "view traces", "system monitoring",
  "datadog", "newrelic", "prometheus", "grafana", "splunk", "cloudwatch"
user-invocable: false
---

# Observability Skill

Monitor and diagnose the wicked-garden plugin ecosystem — health probes, contract assertions, and hook execution traces.

## Quick Start

```bash
# Check ecosystem health
/wicked-garden:observability:health

# Query recent hook traces
/wicked-garden:observability:traces --tail 20

# Validate script output contracts
/wicked-garden:observability:assert
```

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-garden:observability:health` | Run health probes against plugins |
| `/wicked-garden:observability:traces` | Query hook execution traces for the session |
| `/wicked-garden:observability:assert` | Validate script outputs against declared schemas |

## Three Pillars

### 1. Health Probes

Validate ecosystem integrity by checking plugin structure, hook bindings, and script availability.

```bash
# All plugins
/wicked-garden:observability:health

# Single plugin, machine-readable
/wicked-garden:observability:health --plugin wicked-garden --json
```

Exit codes: `0` = healthy, `1` = warnings, `2` = failures.

### 2. Hook Traces

Every hook execution is traced with timing, exit codes, and silent failure detection. Query traces to diagnose issues.

```bash
# Last 10 traces
/wicked-garden:observability:traces --tail 10

# Only silent failures (exit 0 but unexpected output)
/wicked-garden:observability:traces --silent-only

# Trace stats
/wicked-garden:observability:traces --stats
```

### 3. Contract Assertions

Validate that plugin scripts return data matching their declared JSON schemas.

```bash
# Run all assertions
/wicked-garden:observability:assert

# Single plugin
/wicked-garden:observability:assert --plugin wicked-garden
```

Schemas live in `schemas/{plugin}/{script}.json`.

## Common Diagnostic Flows

### "Something seems broken"
1. `/wicked-garden:observability:health` — check structural integrity
2. `/wicked-garden:observability:traces --silent-only` — find silent failures
3. `/wicked-garden:observability:assert` — validate output contracts

### "Hook didn't fire"
1. `/wicked-garden:observability:traces --tail 20` — check if hook was invoked
2. Look for: missing entries (hook never triggered) or exit code != 0

### "Script returns wrong data"
1. `/wicked-garden:observability:assert --plugin {name}` — check contract compliance
2. Review violation details for schema mismatches

## Engineer Toolchain Discovery

Discover and interact with monitoring CLIs available in the current environment.

```bash
# Discover what monitoring tools are installed
/wicked-garden:observability:toolchain

# Query logs with detected CLI
/wicked-garden:observability:toolchain --query "error last 1h"

# Detect by category
/wicked-garden:observability:toolchain --category apm
```

### CLI Categories

| Category | Tools Detected |
|----------|---------------|
| **APM** | `datadog-agent`, `newrelic-cli`, `dt` (Dynatrace) |
| **Logging** | `splunk`, `elk` / `elasticsearch`, `kibana` |
| **Metrics** | `promtool` (Prometheus), `grafana-cli` |
| **Cloud** | `aws cloudwatch`, `gcloud monitoring`, `az monitor` |

Detection uses `command -v` — no external dependencies.

→ See [refs/toolchain-discovery.md](refs/toolchain-discovery.md) for detection patterns and per-tool usage examples.

## Integration

- **wicked-smaht**: Context assembly uses trace data to detect degraded adapters
- **wicked-crew**: Health probes run during execution gates
- **DomainStore**: Traces stored via DomainStore (local JSON), with SqliteStore for search
