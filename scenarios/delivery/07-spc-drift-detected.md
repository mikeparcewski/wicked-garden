---
name: spc-drift-detected
title: SPC Drift Flag Fires on Declining Gate Quality
description: Synthetic timeline with declining gate_pass_rate triggers a delivery:spc:flag via drift.py
type: workflow
difficulty: intermediate
estimated_minutes: 5
execution: manual
---

# SPC Drift Flag Fires on Declining Gate Quality

This scenario validates issue #719: Statistical Process Control drift detection. A timeline of 10 sessions with monotonically degrading `gate_pass_rate` should trip at least one Western Electric rule (`trending_down`, `4_of_5_zone_c`, or `8_consecutive_one_side`) and produce a persisted `delivery:spc:flag` record in the DomainStore.

## Setup

Inject 10 synthetic timeline records into a sandboxed DomainStore root, then ask `drift.py` to classify the headline `gate_pass_rate` metric and persist any fired flags. Sandboxing keeps the scenario from polluting real telemetry.

```bash
set -euo pipefail
# Sandbox by redirecting CLAUDE_CWD — _paths.py derives the project-scoped
# storage root from cwd, so a unique tmpdir → a fresh isolated DomainStore
# slot the scenario can write to and rm afterwards.
WG_SANDBOX="${TMPDIR:-/tmp}/wg-spc-drift-$$"
mkdir -p "$WG_SANDBOX"
export CLAUDE_CWD="$WG_SANDBOX"
PROJECT="spc-drift-demo"

# Step 1: write 10 declining sessions to the project's timeline.jsonl, then
# Step 2: invoke drift.py classify + flag, then
# Step 3: list any persisted SPC flags.
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, os, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from delivery.telemetry import _timeline_path
path = _timeline_path('${PROJECT}')
path.parent.mkdir(parents=True, exist_ok=True)
declining = [0.95, 0.93, 0.92, 0.90, 0.88, 0.78, 0.70, 0.65, 0.60, 0.55]
with open(path, 'w', encoding='utf-8') as fh:
    for i, v in enumerate(declining):
        rec = {
            'version': '1',
            'session_id': f's{i:02d}',
            'project': '${PROJECT}',
            'recorded_at': f'2026-04-{i+1:02d}T00:00:00Z',
            'sample_window': {'tasks_observed': 1},
            'metrics': {'gate_pass_rate': v},
        }
        fh.write(json.dumps(rec) + '\n')
print('TIMELINE_WRITTEN', path)
"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/drift.py" flag "$PROJECT" gate_pass_rate

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/drift.py" list-flags "$PROJECT"

# Cleanup the sandboxed storage slot + tmp cwd.
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import shutil, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from _paths import get_project_root
shutil.rmtree(get_project_root(), ignore_errors=True)
"
rm -rf "$WG_SANDBOX"
```

## Expected Output

The classify+flag invocation should return JSON with:

- `classification.drift = true`
- `classification.insufficient_warmup = false` (10 samples > 8 warmup gate)
- `classification.we_rules` includes at least one of: `trending_down`, `4_of_5_zone_c`, `8_consecutive_one_side`
- `flags_written` is a non-empty list — each entry includes `metric: "gate_pass_rate"`, a `rule`, `severity` (`warn` or `critical`), `sample_window`, `current_value`, and `baseline_mean`

The list-flags invocation should echo the same flag(s) back via DomainStore.

## Success Criteria

- [ ] `classification.drift` is `true`
- [ ] At least one Western Electric rule fires
- [ ] `flags_written` contains >= 1 record with `rule` set to one of the WE rules
- [ ] `list-flags` returns the same flag(s)
- [ ] No errors raised by `drift.py` or telemetry

## Value Demonstrated

Process degradation that creeps in over weeks (not a single bad session) is exactly what Western Electric rules catch. Without SPC, a team only notices when the latest run is catastrophically bad — by which point the regression has been compounding for many sessions. The `delivery:spc:flag` record gives an audit trail of *when* drift was first detected and *which* rule caught it, enabling earlier intervention.

## Related

- `docs/spc.md` — chart-reading guide.
- `/wicked-garden:delivery:process-health --spc` — surfaces flags in the process-health report.
