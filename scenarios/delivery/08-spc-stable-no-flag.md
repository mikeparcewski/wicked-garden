---
name: spc-stable-no-flag
title: SPC Stays Quiet on Stable Process + Warmup Gate
description: Stable timeline produces zero SPC flags; pre-warmup timeline produces zero flags even with noise
type: workflow
difficulty: intermediate
estimated_minutes: 5
execution: manual
---

# SPC Stays Quiet on Stable Process + Warmup Gate

This scenario validates the *negative* side of issue #719: SPC must NOT fire on a healthy process, and must NOT fire before the 8-sample warmup gate is satisfied. False positives erode trust; the warmup gate prevents a freshly-onboarded project from spamming flags during its first noisy week.

## Setup

Two checks share one sandboxed DomainStore root:

1. 20 stable sessions (`gate_pass_rate ≈ 0.90` ± noise) → expect zero flags.
2. 7 noisy sessions (below the 8-sample warmup threshold) → expect zero flags even though the values dip aggressively at the end.

```bash
set -euo pipefail
# Sandbox by redirecting CLAUDE_CWD — _paths.py derives the project-scoped
# storage root from cwd, so a unique tmpdir → a fresh isolated DomainStore
# slot the scenario can write to and rm afterwards.
WG_SANDBOX="${TMPDIR:-/tmp}/wg-spc-stable-$$"
mkdir -p "$WG_SANDBOX"
export CLAUDE_CWD="$WG_SANDBOX"
STABLE="spc-stable-demo"
WARMUP="spc-warmup-demo"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from delivery.telemetry import _timeline_path

def write_timeline(project, values):
    path = _timeline_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        for i, v in enumerate(values):
            rec = {
                'version': '1',
                'session_id': f's{i:02d}',
                'project': project,
                'recorded_at': f'2026-04-{i+1:02d}T00:00:00Z',
                'sample_window': {'tasks_observed': 1},
                'metrics': {'gate_pass_rate': v},
            }
            fh.write(json.dumps(rec) + '\n')
    print('WROTE', project, len(values))

# 20 stable sessions — small natural noise, no trend.
stable = [0.90, 0.91, 0.89, 0.90, 0.92, 0.88, 0.91, 0.90, 0.89, 0.91,
          0.90, 0.92, 0.88, 0.91, 0.89, 0.90, 0.92, 0.91, 0.89, 0.90]
write_timeline('${STABLE}', stable)

# 7 sessions with steep decline — must still produce zero flags
# because the warmup gate (n>=8) blocks emission.
warmup = [0.95, 0.92, 0.85, 0.70, 0.55, 0.40, 0.30]
write_timeline('${WARMUP}', warmup)
"

echo '--- Check 1: stable process, expect no flags ---'
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/drift.py" flag "$STABLE" gate_pass_rate

echo '--- Check 2: pre-warmup noisy process, expect no flags ---'
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/drift.py" flag "$WARMUP" gate_pass_rate

echo '--- list-flags must be empty for both ---'
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/drift.py" list-flags "$STABLE"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/drift.py" list-flags "$WARMUP"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import shutil, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from _paths import get_project_root
shutil.rmtree(get_project_root(), ignore_errors=True)
"
rm -rf "$WG_SANDBOX"
```

## Expected Output

For the stable project:

- `classification.drift = false`
- `classification.we_rules` is empty
- `classification.zone` is `common-cause`
- `flags_written` is empty
- `list-flags` returns empty

For the warmup project:

- `classification.insufficient_warmup = true`
- `classification.drift = false` even though the latest value (0.30) is far below baseline mean
- `flags_written` is empty
- `list-flags` returns empty

## Success Criteria

- [ ] Stable project: `drift = false`, `flags_written = []`, `list-flags = []`
- [ ] Warmup project: `insufficient_warmup = true`, `drift = false`, `flags_written = []`
- [ ] Neither project produces a `delivery:spc:flag` record
- [ ] No errors raised by `drift.py` or telemetry

## Value Demonstrated

Two failure modes for any monitoring system are (a) crying wolf on noise and (b) firing on incomplete data. Healthy variation in `gate_pass_rate` should not look like a regression, and a project with five sessions of telemetry doesn't have enough history to call *anything* drift. The 8-sample warmup gate combined with the Western Electric rules' minimum-window requirements (3, 5, 6, or 8 points depending on rule) makes SPC quiet by default — flags only appear when a real signal emerges.

## Related

- `docs/spc.md` — chart-reading guide and silencing tips.
- `scenarios/delivery/07-spc-drift-detected.md` — the positive counterpart.
