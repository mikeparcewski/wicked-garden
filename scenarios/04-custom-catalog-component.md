---
name: custom-data-source
title: Custom Plugin Data Source Extension
description: Create a plugin with custom data sources discoverable by the data gateway
type: integration
difficulty: advanced
estimated_minutes: 15
---

# Custom Plugin Data Source Extension

Demonstrates how plugins can expose data to the Workbench data gateway by declaring sources in `wicked.json` and implementing an `api.py` script. This proves the extensibility model: any plugin can provide data that dashboards can consume.

## Setup

We'll create a minimal plugin with a custom data source.

### 1. Create Plugin Directory

```bash
mkdir -p /tmp/demo-metrics/.claude-plugin
mkdir -p /tmp/demo-metrics/scripts
```

### 2. Create plugin.json

```bash
cat > /tmp/demo-metrics/.claude-plugin/plugin.json << 'EOF'
{
  "name": "demo-metrics",
  "version": "0.1.0",
  "description": "Demo plugin exposing custom metrics data"
}
EOF
```

### 3. Create wicked.json

```bash
cat > /tmp/demo-metrics/wicked.json << 'EOF'
{
  "$schema": "wicked-data/1.0.0",
  "api_script": "scripts/api.py",
  "sources": [
    {
      "name": "metrics",
      "description": "Application performance metrics",
      "capabilities": ["list", "get", "stats"]
    }
  ]
}
EOF
```

### 4. Create api.py

```bash
cat > /tmp/demo-metrics/scripts/api.py << 'PYEOF'
#!/usr/bin/env python3
"""Demo metrics API for wicked-workbench data gateway."""
import json
import sys

def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else "list"
    source = sys.argv[2] if len(sys.argv) > 2 else "metrics"

    if verb == "list":
        print(json.dumps({
            "items": [
                {"name": "active_users", "value": 1523, "trend": "up"},
                {"name": "error_rate", "value": 0.05, "trend": "down"},
                {"name": "response_time_ms", "value": 245, "trend": "stable"}
            ],
            "total": 3
        }))
    elif verb == "stats":
        print(json.dumps({
            "total_metrics": 3,
            "healthy": 3,
            "degraded": 0
        }))
    else:
        print(json.dumps({"error": f"Unknown verb: {verb}"}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
PYEOF
chmod +x /tmp/demo-metrics/scripts/api.py
```

### 5. Restart Workbench with Plugin Path

```bash
WICKED_PLUGINS_DIR=/tmp uvx --from wicked-workbench-server wicked-workbench
```

## Steps

### 1. Verify Custom Data Source Discovered

```bash
curl -s http://localhost:18889/api/v1/data/plugins | jq '.plugins[] | select(.name == "demo-metrics")'
```

### 2. Query Custom Data Source

```bash
curl -s http://localhost:18889/api/v1/data/demo-metrics/metrics/list | jq .
```

### 3. Get Stats

```bash
curl -s http://localhost:18889/api/v1/data/demo-metrics/metrics/stats | jq .
```

### 4. Generate Dashboard Using Custom Data

In Claude Code:

```
Create a metrics dashboard showing application performance metrics
```

## Expected Outcome

### Step 1: Discovery
```json
{
  "name": "demo-metrics",
  "schema_version": "1.0.0",
  "sources": [{"name": "metrics", "capabilities": ["list", "get", "stats"]}]
}
```

### Step 2: List Metrics
```json
{
  "items": [
    {"name": "active_users", "value": 1523, "trend": "up"},
    {"name": "error_rate", "value": 0.05, "trend": "down"},
    {"name": "response_time_ms", "value": 245, "trend": "stable"}
  ]
}
```

### Step 3: Stats
```json
{"total_metrics": 3, "healthy": 3, "degraded": 0}
```

## Success Criteria

- [ ] `wicked.json` is created with data source declaration
- [ ] `api.py` script handles list and stats verbs
- [ ] Workbench discovers the new data source on startup
- [ ] GET `/api/v1/data/plugins` includes "demo-metrics"
- [ ] GET `/api/v1/data/demo-metrics/metrics/list` returns metrics data
- [ ] GET `/api/v1/data/demo-metrics/metrics/stats` returns summary

## Value Demonstrated

**Plugin extensibility**: Any plugin can expose data by creating `wicked.json` + `scripts/api.py`. No changes to Workbench code required.

**Standard API contract**: All plugins use the same verb-based API pattern (list, get, search, stats, create, update, delete), making data access predictable.

**Real-world use**: Custom monitoring data, business KPIs, engineering metrics, data quality results — all accessible through the unified data gateway.
