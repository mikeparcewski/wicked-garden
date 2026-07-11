---
name: wicked-garden-platform-observability
description: |
  Use when monitoring or diagnosing the wicked-garden plugin ecosystem — health probes, contract assertions,
  hook traces, error pattern detection, and APM/logging/metrics toolchain discovery.
  NOT for distributed tracing across services (use the platform domain skill's traces action) or audit evidence (use platform/audit).

  Use when: "plugin health", "health probe", "hook didn't fire", "hook traces",
  "contract assertions", "validate script outputs", "what monitoring tools are
  installed", "toolchain discovery", or any former
  /wicked-garden:platform:{plugin-health|assert|toolchain} invocation.
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# Observability Skill

Monitor and diagnose the wicked-garden plugin ecosystem — health probes, contract assertions, and hook execution traces. All three pillars run inline (no agent delegation needed).

## Quick Start

```bash
# Check plugin ecosystem health
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/health_probe.py

# Query recent hook traces (operational log)
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/ops_log_viewer.py --tail 20

# Validate script output contracts
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/assert_contracts.py
```

## Three Pillars

### 1. Health Probes

Validate ecosystem integrity by checking plugin structure, hook bindings, and script availability.

Run the health probe script inline:

```bash
# All plugins
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/health_probe.py

# Single plugin, machine-readable
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/health_probe.py --plugin wicked-garden --json
```

- Display results grouped by plugin, with severity icons.
- Exit codes: `0` = healthy, `1` = warnings, `2` = failures.
- Show the path to `latest.json` for programmatic consumption.

**Auth retry** (`--retry-auth`): after the user authenticates a CLI
mid-session, re-run the plugin readiness probes from bootstrap — see
[refs/plugin-health.md](refs/plugin-health.md) for the probe invocation and
reporting steps.

### 2. Hook Traces

Every hook execution is traced with timing, exit codes, and silent failure detection. Query the operational log to diagnose issues via `scripts/platform/observability/ops_log_viewer.py`:

```bash
# Last 10 entries
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/ops_log_viewer.py --tail 10

# Filter by verbosity level (normal | verbose | debug)
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/ops_log_viewer.py --level verbose

# Machine-readable, or a specific session's log
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/ops_log_viewer.py --json --session {ID}
```

> Note: hook-trace viewing is **this script**, not distributed tracing. For
> latency/dependency analysis of distributed traces across services, use the
> `traces` action of the platform domain skill (`skills/platform/SKILL.md`).

### 3. Contract Assertions

Validate that plugin scripts return data matching their declared JSON schemas.

Run the assertion script inline:

```bash
# Run all assertions
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/assert_contracts.py

# Single plugin, machine-readable
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/assert_contracts.py --plugin wicked-garden --json
```

- Display results: pass/fail per script, violation details for failures.
- Note: schemas must exist in `schemas/{plugin}/{script}.json` before assertions can run.

## Common Diagnostic Flows

### "Something seems broken"
1. Run the health probe (pillar 1) — check structural integrity
2. Query the ops log (pillar 2) — look for hook entries with exit code != 0 or unexpected output
3. Run contract assertions (pillar 3) — validate output contracts

### "Hook didn't fire"
1. Query the ops log with `--tail 20` (pillar 2) — check if the hook was invoked
2. Look for: missing entries (hook never triggered) or exit code != 0

### "Script returns wrong data"
1. Run contract assertions with `--plugin {name}` (pillar 3) — check contract compliance
2. Review violation details for schema mismatches

## Engineer Toolchain Discovery

Discover monitoring CLIs (APM, logging, metrics, cloud) available in the
current environment and run queries against them — inline, no dispatch.

Semantics:

- **No query**: detect tools per category with `command -v` and report what
  was found, grouped by category with binary path and version.
- **`--query "..."`**: route the query to the appropriate detected tool(s) —
  logging tools search recent logs (last 1h default), metrics tools query
  matching metrics, APM tools search traces/events, cloud tools query
  CloudWatch/Stackdriver/Azure logs — and present results side-by-side with
  tool attribution.
- **`--category apm|logging|metrics|cloud`**: limit both discovery and query
  execution to that category.
- **Never fail** — discovery is read-only. A tool that errors on query is
  reported and the rest continue; when nothing is found, report "No
  monitoring CLIs detected" and suggest installation options.

→ `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/observability/refs/toolchain-discovery.md")`
for the detection script, per-tool usage examples, query routing, display
format, and next-step suggestions.

### CLI Categories

| Category | Tools Detected |
|----------|---------------|
| **APM** | `datadog-agent`, `newrelic`, `dt` (Dynatrace) |
| **Logging** | `splunk`, `elasticsearch`, `logcli` (Loki) |
| **Metrics** | `promtool` (Prometheus), `grafana-cli`, `influx` |
| **Cloud** | `aws` (CloudWatch), `gcloud` (monitoring), `az` (Azure Monitor) |

Detection uses `command -v` — no external dependencies.

## Integration

- **smaht** (domain): Context assembly uses trace data to detect degraded adapters
- **crew** (domain): Health probes run during execution gates
- **DomainStore**: Traces stored via DomainStore (local JSON), with SqliteStore for search
