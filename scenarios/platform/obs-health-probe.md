---
name: obs-health-probe
description: Verify that the health command validates plugin structures and reports healthy status
category: infra
tags: [observability, health, validation]
tools:
  required: [slash-command]
difficulty: basic
timeout: 60
---

# Observability Health Probe

Validates that `/wicked-garden:observability:health` can inspect installed plugins, confirm their
structure is sound, and report a healthy status. Covers Layer 2 (health probes) of the
observability stack.

## Setup

No setup required. The `/wicked-garden:observability:health` command handles all discovery and
invocation internally.

## Steps

### Step 1: Run health probe against the observability domain

Invoke the health command targeting the observability domain:

```
/wicked-garden:observability:health --plugin wicked-garden --json
```

**Expect**: The command completes without error and produces structured output.

### Step 2: Verify healthy status in the output

Examine the output from Step 1.

**Expect**:
- The output contains a `status` field with value `healthy`
- The output contains a `plugins_checked` field indicating at least 1 plugin was inspected
- No violations with severity `error` appear in the results

### Step 3: Verify health snapshot was persisted

Run the health command again without `--json` (human-readable mode):

```
/wicked-garden:observability:health
```

**Expect**:
- The command reports results grouped by plugin
- The output references a `latest.json` path for programmatic consumption
- The exit summary shows 0 failures

## Expected Outcomes

1. The health command successfully probes at least one plugin and returns a healthy status
2. The output includes structured fields (`status`, `checked_at`, `plugins_checked`) suitable for automation
3. A persistent health snapshot is written so that subsequent runs can compare against prior state
4. The human-readable output provides clear violation grouping and severity indicators

## Cleanup

Health snapshots are intentionally persisted. No cleanup needed.
