---
name: obs-trace-capture
description: Verify that the PostToolUse hook writes JSONL trace records when tools are invoked
category: infra
tags: [observability, traces, hooks]
tools:
  required: [python3]
difficulty: basic
timeout: 30
---

# Observability Trace Capture

Validates that the PostToolUse hook appends JSONL trace records to a per-session trace file
whenever a tool is invoked. Confirms that Layer 1 (runtime tracing) is active and recording.

## Setup

```bash
# Trace files are named {session_id}.jsonl — find the most recently modified one
TRACE_DIR="${HOME}/.something-wicked/wicked-garden/local/wicked-observability/traces"
mkdir -p "${TRACE_DIR}"

# Snapshot: record total line count across all trace files as baseline
BASELINE=$(cat "${TRACE_DIR}"/*.jsonl 2>/dev/null | wc -l | tr -d ' ')
BASELINE=${BASELINE:-0}
echo "Baseline total line count: ${BASELINE}"
export TRACE_DIR BASELINE
```

**Expect**: Baseline total line count printed without error

## Steps

### Step 1: Trigger a PostToolUse event (bash)

Run a shell command so that the PostToolUse hook fires and appends a trace record.

```bash
echo "trace test"
```

**Expect**: Exit code 0, output "trace test"

### Step 2: Assert trace file grew (python3)

```bash
python3 - <<'EOF'
import glob, os, sys

trace_dir = os.path.expanduser("~/.something-wicked/wicked-garden/local/wicked-observability/traces")
baseline = int(os.environ.get("BASELINE", "0"))

# Count total lines across all session trace files
files = glob.glob(os.path.join(trace_dir, "*.jsonl"))
if not files:
    print(f"FAIL: no trace files found in {trace_dir}")
    sys.exit(1)

current = sum(sum(1 for _ in open(f)) for f in files)
if current > baseline:
    print(f"OK: trace lines grew from {baseline} to {current}")
    sys.exit(0)
else:
    print(f"FAIL: trace lines did not grow (still {current}, baseline {baseline})")
    sys.exit(1)
EOF
```

**Expect**: Exit code 0, "OK: trace lines grew" message

### Step 3: Validate last JSONL record is well-formed (python3)

```bash
python3 - <<'EOF'
import glob, json, os, sys

trace_dir = os.path.expanduser("~/.something-wicked/wicked-garden/local/wicked-observability/traces")
files = glob.glob(os.path.join(trace_dir, "*.jsonl"))
if not files:
    print("FAIL: no trace files found")
    sys.exit(1)

# Read the most recently modified trace file
latest = max(files, key=os.path.getmtime)
with open(latest) as f:
    lines = [l.strip() for l in f if l.strip()]

if not lines:
    print("FAIL: latest trace file is empty")
    sys.exit(1)

last = json.loads(lines[-1])

required_fields = {"ts", "tool", "session_id"}
missing = required_fields - last.keys()
if missing:
    print(f"FAIL: last record missing fields: {missing}")
    sys.exit(1)

print(f"OK: last record valid — tool={last.get('tool')!r}, ts={last.get('ts')!r}")
EOF
```

**Expect**: Exit code 0, last record has required fields: ts, tool, session_id

## Cleanup

Traces are append-only logs. No cleanup needed.

```bash
echo "No cleanup required — traces are append-only"
```
