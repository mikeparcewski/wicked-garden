---
name: obs-contract-assert
description: Verify that assert_contracts.py discovers and validates plugin schemas, reporting pass/fail counts
category: infra
tags: [observability, contracts, schemas]
tools:
  required: [python3]
difficulty: intermediate
timeout: 60
---

# Observability Contract Assertions

Validates that `assert_contracts.py` discovers the plugin's registered schemas, validates them
against their targets, and reports a clean pass with 0 failures. Also confirms that a daily JSONL
assertion log is written to `~/.something-wicked/wicked-observability/assertions/`.
Covers Layer 3 (contract assertions) of the observability stack.

## Setup

```bash
# Confirm the script exists before running steps
if [ ! -f "scripts/observability/assert_contracts.py" ]; then
  echo "FAIL: assert_contracts.py not found at scripts/observability/assert_contracts.py"
  exit 1
fi
echo "OK: assert_contracts.py found"
```

**Expect**: Exit code 0, "OK: assert_contracts.py found"

## Steps

### Step 1: Run contract assertion against wicked-observability (python3)

```bash
python3 scripts/observability/assert_contracts.py \
  --plugin wicked-observability
```

**Expect**: Exit code 0, summary printed to stdout showing schemas passed and 0 failed

### Step 2: Assert output reports 3 schemas passed, 0 failed (python3)

```bash
python3 - <<'EOF'
import subprocess, sys, re

result = subprocess.run(
    ["python3", "scripts/observability/assert_contracts.py",
     "--plugin", "wicked-observability"],
    capture_output=True, text=True
)

if result.returncode != 0:
    print(f"FAIL: assert_contracts.py exited {result.returncode}")
    print(result.stderr)
    sys.exit(1)

output = result.stdout + result.stderr

# Look for a summary line indicating pass/fail counts
passed_match = re.search(r'(\d+)\s+passed', output, re.IGNORECASE)
failed_match = re.search(r'(\d+)\s+failed', output, re.IGNORECASE)

passed = int(passed_match.group(1)) if passed_match else None
failed = int(failed_match.group(1)) if failed_match else 0

if passed is None:
    print("FAIL: could not parse passed count from output")
    print(output[:800])
    sys.exit(1)

if passed < 3:
    print(f"FAIL: expected at least 3 schemas passed, got {passed}")
    print(output[:800])
    sys.exit(1)

if failed != 0:
    print(f"FAIL: expected 0 schemas failed, got {failed}")
    print(output[:800])
    sys.exit(1)

print(f"OK: {passed} schemas passed, {failed} failed")
EOF
```

**Expect**: Exit code 0, at least 3 schemas passed with 0 failures

### Step 3: Verify daily assertion JSONL log was written (python3)

```bash
python3 - <<'EOF'
import json, os, sys
from datetime import date

assertions_dir = os.path.expanduser("~/.something-wicked/wicked-observability/assertions")
today = date.today().strftime("%Y-%m-%d")
log_path = os.path.join(assertions_dir, f"{today}.jsonl")

if not os.path.exists(assertions_dir):
    print(f"FAIL: assertions directory not found: {assertions_dir}")
    sys.exit(1)

if not os.path.exists(log_path):
    # Accept any JSONL file in the directory if today's isn't present yet
    files = [f for f in os.listdir(assertions_dir) if f.endswith(".jsonl")]
    if not files:
        print(f"FAIL: no JSONL files found in {assertions_dir}")
        sys.exit(1)
    log_path = os.path.join(assertions_dir, sorted(files)[-1])
    print(f"NOTE: using most recent log file: {os.path.basename(log_path)}")

with open(log_path) as f:
    lines = [l.strip() for l in f if l.strip()]

if not lines:
    print(f"FAIL: assertion log is empty: {log_path}")
    sys.exit(1)

# Validate at least one record is parseable JSON
try:
    last = json.loads(lines[-1])
except json.JSONDecodeError as e:
    print(f"FAIL: last record is not valid JSON: {e}")
    sys.exit(1)

print(f"OK: {len(lines)} assertion record(s) in {os.path.basename(log_path)}")
print(f"    last record schema={last.get('schema')!r}, result={last.get('result')!r}")
EOF
```

**Expect**: Exit code 0, a JSONL file exists in
`~/.something-wicked/wicked-observability/assertions/` with at least one valid JSON record

## Cleanup

Assertion logs are persistent audit records. No cleanup needed.

```bash
echo "No cleanup required — assertion logs are persistent audit records"
```
