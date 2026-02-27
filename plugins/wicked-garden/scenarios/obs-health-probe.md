---
name: obs-health-probe
description: Verify that health_probe.py validates plugin structures correctly and reports healthy status
category: infra
tags: [observability, health, validation]
tools:
  required: [python3]
difficulty: basic
timeout: 60
---

# Observability Health Probe

Validates that `health_probe.py` can inspect a plugin directory, confirm its structure is sound,
and persist a `latest.json` health snapshot under `~/.something-wicked/wicked-observability/health/`.
Covers Layer 2 (health probes) of the observability stack.

## Setup

```bash
# Confirm the script exists before running steps
if [ ! -f "plugins/wicked-observability/scripts/health_probe.py" ]; then
  echo "FAIL: health_probe.py not found at plugins/wicked-observability/scripts/health_probe.py"
  exit 1
fi
echo "OK: health_probe.py found"
```

**Expect**: Exit code 0, "OK: health_probe.py found"

## Steps

### Step 1: Run health probe against wicked-observability (python3)

```bash
python3 plugins/wicked-observability/scripts/health_probe.py \
  --plugin wicked-observability \
  --json
```

**Expect**: Exit code 0, JSON output printed to stdout

### Step 2: Assert output contains healthy status (python3)

```bash
python3 - <<'EOF'
import json, subprocess, sys

result = subprocess.run(
    ["python3", "plugins/wicked-observability/scripts/health_probe.py",
     "--plugin", "wicked-observability", "--json"],
    capture_output=True, text=True
)

if result.returncode != 0:
    print(f"FAIL: health_probe.py exited {result.returncode}")
    print(result.stderr)
    sys.exit(1)

try:
    data = json.loads(result.stdout)
except json.JSONDecodeError as e:
    print(f"FAIL: output is not valid JSON: {e}")
    print(result.stdout[:500])
    sys.exit(1)

status = data.get("status")
if status != "healthy":
    print(f"FAIL: expected status='healthy', got {status!r}")
    print(json.dumps(data, indent=2)[:500])
    sys.exit(1)

print(f"OK: status={status!r}, plugins_checked={data.get('plugins_checked')!r}")
EOF
```

**Expect**: Exit code 0, status is "healthy"

### Step 3: Verify latest.json snapshot was persisted (python3)

```bash
python3 - <<'EOF'
import json, os, sys

health_dir = os.path.expanduser("~/.something-wicked/wicked-observability/health")
latest_path = os.path.join(health_dir, "latest.json")

if not os.path.exists(latest_path):
    print(f"FAIL: latest.json not found at {latest_path}")
    sys.exit(1)

try:
    with open(latest_path) as f:
        data = json.load(f)
except json.JSONDecodeError as e:
    print(f"FAIL: latest.json is not valid JSON: {e}")
    sys.exit(1)

required = {"status", "checked_at", "plugins_checked"}
missing = required - data.keys()
if missing:
    print(f"FAIL: latest.json missing required fields: {missing}")
    sys.exit(1)

print(f"OK: latest.json valid — status={data.get('status')!r}, plugins_checked={data.get('plugins_checked')!r}")
EOF
```

**Expect**: Exit code 0, `~/.something-wicked/wicked-observability/health/latest.json` exists with valid JSON
containing `status`, `checked_at`, and `plugins_checked` fields

## Cleanup

Health snapshots are intentionally persisted. No cleanup needed.

```bash
echo "No cleanup required — health snapshots are persistent records"
```
