---
name: custom-catalog-component
title: Custom Component Catalog Extension
description: Create and use a custom component catalog from a plugin
type: integration
difficulty: advanced
estimated_minutes: 15
---

# Custom Component Catalog Extension

Demonstrates how plugins can extend Workbench by providing custom component catalogs. This proves the extensibility model: any plugin can define new components that Claude Code can use to generate dashboards.

## Setup

We'll create a minimal plugin with a custom catalog:

### 1. Create Plugin Directory

```bash
mkdir -p ~/.claude/plugins/demo-metrics/.claude-plugin
```

### 2. Create catalog.json

Create `~/.claude/plugins/demo-metrics/.claude-plugin/catalog.json` with:
- MetricCard component: props for label, value, trend, color
- MetricGrid component: grid layout accepting MetricCard children
- show-metrics intent

(See full catalog.json example in wicked-workbench README)

### 3. Restart Workbench

```bash
# Stop and restart to discover the new catalog
wicked-workbench
```

## Steps

### 1. Verify Custom Catalog Discovered

```bash
curl http://localhost:18889/api/catalogs | jq '.[] | select(.catalogId == "demo-metrics")'
```

### 2. View Catalog Details

```bash
curl http://localhost:18889/api/catalogs/demo-metrics | jq .
```

### 3. Generate Dashboard Using Custom Component

In Claude Code:

```
Create a metrics dashboard showing:
- Active users: 1,523 (up trend, green)
- Error rate: 0.05% (down trend, green)
- Response time: 245ms (neutral, blue)
```

### 4. Verify A2UI Uses Custom Components

Claude generates A2UI using MetricGrid with 3 MetricCard children, each with label, value, trend, and color props.

### 5. View Dashboard

Open http://localhost:18889 to see the rendered metrics.

## Expected Outcome

### Step 1: Catalog Discovery
Returns catalogId "demo-metrics" with componentCount: 2

### Step 2: Catalog Details
Shows MetricCard and MetricGrid components with full prop definitions.

### Step 3: Dashboard Generation
Claude creates dashboard using demo-metrics components.

### Step 4: Custom Component Usage
A2UI uses MetricGrid and MetricCard from custom catalog.

### Step 5: Rendered Dashboard
3 metric cards in grid layout with labels, values, and trends.

## Success Criteria

- [ ] Custom catalog.json is created in plugin directory
- [ ] Workbench discovers the new catalog on startup
- [ ] GET /api/catalogs includes "demo-metrics"
- [ ] GET /api/catalogs/demo-metrics returns full component definitions
- [ ] Claude Code reads the catalog and understands when to use these components
- [ ] Claude generates A2UI using MetricCard and MetricGrid components
- [ ] Dashboard renders with custom components
- [ ] Component props (label, value, trend, color) are respected

## Value Demonstrated

**Plugin extensibility**: Any plugin can define custom components by creating a catalog.json. No changes to Workbench code required.

**AI-friendly component design**: Component descriptions in the catalog teach Claude Code when and how to use each component. Good descriptions = better dashboard generation.

**Rapid prototyping**: Create new dashboard component types in minutes. Define the component contract in JSON, Claude Code can immediately use it.

**Real-world use**: Custom monitoring dashboards (SRE metrics), business KPI dashboards (revenue, growth), engineering metrics (build times, test coverage), data quality dashboards (profiling results, validation status).
