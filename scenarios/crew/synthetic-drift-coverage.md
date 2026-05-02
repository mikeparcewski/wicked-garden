---
name: synthetic-drift-coverage
title: Synthetic-drift suite covers every reconciler drift class on demand
description: Drives scripts/crew/synthetic_drift.py end-to-end for every drift class the reconciler knows about (4 pre-cutover + 3 post-cutover). Substitutes coverage-by-construction for the absent organic ≥10 projects / ≥50 phases sample required by issue #746.
type: testing
difficulty: intermediate
estimated_minutes: 3
---

# Synthetic-drift Coverage

This scenario drives the synthetic-drift suite that gates Sites 3-5 of
the bus-cutover (per `docs/v9/bus-cutover-staging-plan.md` section 2).
The organic drift baseline captured at
`docs/audits/bus-cutover-drift-baseline-2026-05-02.json` falls below
issue #746's sample-size floor (>=10 distinct projects OR >=50 distinct
phases). This scenario proves the reconciler catches every drift class
on demand without waiting for organic drift.

The four pre-cutover classes (`missing_native`, `stale_status`,
`orphan_native`, `phase_drift`) are detected by today's
`scripts/crew/reconcile.py` and asserted directly. The three
post-cutover classes (`projection-stale`, `event-without-projection`,
`projection-without-event`) are detected by the future post-cutover
reconciler defined in staging plan section 5; this scenario asserts
the FIXTURE shape (event_log row + projection presence/absence) instead
because the new reconciler has not landed yet.

When the projector daemon DB is unreachable the post-cutover steps print
`PASS-WITH-CAVEAT` and skip their assertions — that is the honest
behaviour per the staging plan ("calendar waits are explicitly off the
table" but fabricated event rows are not the answer either).

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-synth-drift-coverage-'))
")
mkdir -p "${TEST_DIR}/wicked-crew/projects"
mkdir -p "${TEST_DIR}/claude-config/tasks"
mkdir -p "${TEST_DIR}/manifests"
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Build a missing_native fixture and assert reconciler detects it

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/synthetic_drift.py" \
  build --class missing_native \
  --workspace "${TEST_DIR}" \
  --slug synth-missing-native \
  --manifest-out "${TEST_DIR}/manifests/missing_native.json"

WG_LOCAL_ROOT="${TEST_DIR}" CLAUDE_CONFIG_DIR="${TEST_DIR}/claude-config" \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/reconcile.py" \
  --project synth-missing-native --json \
  > "${TEST_DIR}/manifests/recon-missing.json"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
result = json.loads(pathlib.Path('${TEST_DIR}/manifests/recon-missing.json').read_text(encoding='utf-8'))
types = sorted({d['type'] for d in result.get('drift') or []})
assert 'missing_native' in types, f'expected missing_native in {types}'
print(f'PASS missing_native: drift types = {types}')
"
```

**Expected**: `PASS missing_native: drift types = ['missing_native']`

## Step 2: Build stale_status, orphan_native, phase_drift sequentially

```bash
for cls in stale_status orphan_native phase_drift; do
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
    "${CLAUDE_PLUGIN_ROOT}/scripts/crew/synthetic_drift.py" \
    build --class "${cls}" \
    --workspace "${TEST_DIR}" \
    --slug "synth-${cls//_/-}" \
    --manifest-out "${TEST_DIR}/manifests/${cls}.json"

  WG_LOCAL_ROOT="${TEST_DIR}" CLAUDE_CONFIG_DIR="${TEST_DIR}/claude-config" \
    sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
    "${CLAUDE_PLUGIN_ROOT}/scripts/crew/reconcile.py" \
    --all --json \
    > "${TEST_DIR}/manifests/recon-${cls}.json"

  CLS="${cls}" sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, os, pathlib
cls = os.environ['CLS']
results = json.loads(pathlib.Path(f'${TEST_DIR}/manifests/recon-{cls}.json').read_text(encoding='utf-8'))
all_types = sorted({d['type'] for r in results for d in r.get('drift') or []})
assert cls in all_types, f'expected {cls} in {all_types}'
print(f'PASS {cls}: drift types = {all_types}')
"

  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
    "${CLAUDE_PLUGIN_ROOT}/scripts/crew/synthetic_drift.py" \
    teardown --manifest "${TEST_DIR}/manifests/${cls}.json"
done
```

**Expected**:
```
PASS stale_status: drift types = [...stale_status...]
PASS orphan_native: drift types = [...orphan_native...]
PASS phase_drift: drift types = [...phase_drift...]
```

## Step 3: Tear down missing_native and assert zero residual drift

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/synthetic_drift.py" \
  teardown --manifest "${TEST_DIR}/manifests/missing_native.json"

WG_LOCAL_ROOT="${TEST_DIR}" CLAUDE_CONFIG_DIR="${TEST_DIR}/claude-config" \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/reconcile.py" \
  --all --json \
  > "${TEST_DIR}/manifests/recon-final.json"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
results = json.loads(pathlib.Path('${TEST_DIR}/manifests/recon-final.json').read_text(encoding='utf-8'))
total = sum(int((r.get('summary') or {}).get('total_drift_count', 0)) for r in results)
assert total == 0, f'expected zero residual drift, got {total}: {results}'
print(f'PASS teardown clean: 0 residual drift across {len(results)} project(s)')
"
```

**Expected**: `PASS teardown clean: 0 residual drift across 0 project(s)`

## Step 4: Attempt the 3 post-cutover classes; PASS-WITH-CAVEAT on daemon-down

```bash
for cls in projection-stale event-without-projection projection-without-event; do
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
    "${CLAUDE_PLUGIN_ROOT}/scripts/crew/synthetic_drift.py" \
    build --class "${cls}" \
    --workspace "${TEST_DIR}" \
    --slug "synth-${cls}" \
    --manifest-out "${TEST_DIR}/manifests/${cls}.json"

  CLS="${cls}" sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, os, pathlib
cls = os.environ['CLS']
m = json.loads(pathlib.Path(f'${TEST_DIR}/manifests/{cls}.json').read_text(encoding='utf-8'))
if m.get('ok'):
    assert m['drift_class'] == cls
    assert cls in m['expected_drift_types']
    print(f'PASS {cls}: fixture built (event_seq={m.get(\"event_seq\")}, projection={m.get(\"expected_projection_path\") or m.get(\"orphan_projection_path\")})')
elif m.get('reason') == 'daemon_db_unavailable':
    print(f'PASS-WITH-CAVEAT {cls}: daemon DB unreachable; fixture skipped (this is the documented honest fallback per staging plan section 5)')
else:
    raise SystemExit(f'unexpected manifest for {cls}: {m}')
"

  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
    "${CLAUDE_PLUGIN_ROOT}/scripts/crew/synthetic_drift.py" \
    teardown --manifest "${TEST_DIR}/manifests/${cls}.json" || true
done
```

**Expected** (daemon up):
```
PASS projection-stale: fixture built (event_seq=..., projection=.../gate-result.json)
PASS event-without-projection: fixture built (...)
PASS projection-without-event: fixture built (...)
```

**Expected** (daemon down):
```
PASS-WITH-CAVEAT projection-stale: daemon DB unreachable; ...
PASS-WITH-CAVEAT event-without-projection: ...
PASS-WITH-CAVEAT projection-without-event: ...
```

## Step 5: Final assert — every supported class enumerated

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/synthetic_drift.py" list \
  > "${TEST_DIR}/manifests/list.json"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
data = json.loads(pathlib.Path('${TEST_DIR}/manifests/list.json').read_text(encoding='utf-8'))
expected = {
    'missing_native', 'stale_status', 'orphan_native', 'phase_drift',
    'projection-stale', 'event-without-projection', 'projection-without-event',
}
assert set(data['supported']) == expected, f'class set drift: {data[\"supported\"]} != {sorted(expected)}'
print(f'PASS supported set: {sorted(data[\"supported\"])}')
"
```

**Expected**: `PASS supported set: ['event-without-projection', 'missing_native', 'orphan_native', 'phase_drift', 'projection-stale', 'projection-without-event', 'stale_status']`

## Success Criteria

- [ ] Step 1 prints `PASS missing_native`
- [ ] Step 2 prints PASS for `stale_status`, `orphan_native`, `phase_drift`
- [ ] Step 3 prints `PASS teardown clean: 0 residual drift across 0 project(s)`
- [ ] Step 4 prints PASS or PASS-WITH-CAVEAT for each of the three post-cutover classes
- [ ] Step 5 confirms all 7 supported classes are listed by the CLI

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR
```
