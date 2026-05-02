---
name: crew-resolve-mechanical
title: crew:resolve — Mechanical Findings Get Sidecar; Gate Verdict Untouched
description: Verifies the #717 reframed contract — classify-don't-retry. Mechanical findings get a resolution sidecar via crew:resolve --accept; escalation findings refuse; gate-result.json SHA256 is byte-identical before/after.
type: testing
difficulty: intermediate
estimated_minutes: 8
---

# crew:resolve — Mechanical Resolution + Verdict Preservation

This scenario asserts the load-bearing contract from issue #717's
reframe: `crew:resolve --accept` writes resolution sidecars for
`mechanical` findings AND leaves `gate-result.json` byte-identical.
The verdict stays CONDITIONAL until `crew:approve` runs.

The reframe is documented in
[issue #717 comment](https://github.com/mikeparcewski/wicked-garden/issues/717#issuecomment-4363961150).

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-resolve-mechanical-'))
")
echo "TEST_DIR=${TEST_DIR}"
export PHASE="design"
```

## Step 1: Seed manifest with one mechanical, one escalation, one judgment finding

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, pathlib
test_dir = pathlib.Path(os.environ['TEST_DIR'])
phase_dir = test_dir / "phases" / os.environ['PHASE']
phase_dir.mkdir(parents=True, exist_ok=True)

# conditions-manifest.json — three findings
(phase_dir / "conditions-manifest.json").write_text(json.dumps({
    "phase": os.environ['PHASE'],
    "conditions": [
        {"id": "mech-1", "message": "AC-3 not found in clarify/acceptance-criteria.json", "verified": False},
        {"id": "esc-1", "message": "SQL injection vulnerability in user_input handler", "verified": False},
        {"id": "judge-1", "message": "outcome statement is ambiguous", "verified": False},
    ],
}, indent=2), encoding="utf-8")

# gate-result.json — the file that MUST stay byte-identical
(phase_dir / "gate-result.json").write_text(json.dumps({
    "verdict": "CONDITIONAL",
    "score": 0.65,
    "min_score": 0.7,
    "reviewer": "rev-1",
}, indent=2), encoding="utf-8")
print("seeded manifest + gate-result")
PYEOF
```

**Expected**: `seeded manifest + gate-result`

## Step 2: Capture gate-result SHA256 before any resolve action

```bash
gate_sha_before=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import hashlib, pathlib
print(hashlib.sha256(pathlib.Path('${TEST_DIR}/phases/${PHASE}/gate-result.json').read_bytes()).hexdigest())
")
echo "gate_sha_before=${gate_sha_before}"
```

## Step 3: Preview run (no --accept) classifies but does not write

```bash
preview=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/resolve.py" \
  "${TEST_DIR}" "${PHASE}" --json)
echo "${preview}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
r = json.loads(sys.stdin.read())
assert r['manifest_loaded'] is True
assert len(r['mechanical']) == 1
assert r['mechanical'][0]['condition_id'] == 'mech-1'
assert r['mechanical'][0]['applied_rule'] == 'ac-numbering'
assert len(r['escalation']) == 1
assert r['escalation'][0]['condition_id'] == 'esc-1'
assert 'crew:swarm' in r['escalation'][0]['refused_with']
assert len(r['judgment']) == 1
assert r['resolved'] == [], 'preview must not write resolutions'
assert r['verdict_unchanged'] is True
print('PASS preview: 1 mechanical / 1 escalation (refused) / 1 judgment / 0 resolved')
"

# No sidecar should exist after preview.
test ! -f "${TEST_DIR}/phases/${PHASE}/conditions-manifest.mech-1.resolution.json" \
  && echo "PASS preview: no sidecar written" \
  || (echo "FAIL preview wrote a sidecar"; exit 1)
```

**Expected**: two `PASS preview:` lines.

## Step 4: --accept writes sidecar for mechanical, refuses escalation, leaves gate-result untouched

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/resolve.py" \
  "${TEST_DIR}" "${PHASE}" --accept --json | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
r = json.loads(sys.stdin.read())
assert len(r['resolved']) == 1, f'expected 1 resolved, got {len(r[\"resolved\"])}: {r}'
resolved = r['resolved'][0]
assert resolved['condition_id'] == 'mech-1'
assert 'sidecar_path' in resolved
assert r['verdict_unchanged'] is True
print(f'PASS accept: mech-1 resolved → {resolved[\"sidecar_path\"]}')
print(f'      emit_status={resolved[\"emit_status\"]}')
"

# Sidecar MUST exist now.
test -f "${TEST_DIR}/phases/${PHASE}/conditions-manifest.mech-1.resolution.json" \
  && echo "PASS accept: sidecar written" \
  || (echo "FAIL accept did not write sidecar"; exit 1)
```

**Expected**: two `PASS accept:` lines.

## Step 5: gate-result.json byte-identical (the load-bearing contract)

```bash
gate_sha_after=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import hashlib, pathlib
print(hashlib.sha256(pathlib.Path('${TEST_DIR}/phases/${PHASE}/gate-result.json').read_bytes()).hexdigest())
")
echo "gate_sha_after=${gate_sha_after}"

if [ "${gate_sha_before}" = "${gate_sha_after}" ]; then
  echo "PASS contract: gate-result.json SHA256 byte-identical — verdict NEVER mutated"
else
  echo "FAIL contract: gate-result.json was modified by crew:resolve"
  echo "  before=${gate_sha_before}"
  echo "  after=${gate_sha_after}"
  exit 1
fi
```

**Expected**: `PASS contract: gate-result.json SHA256 byte-identical — verdict NEVER mutated`

## Step 6: conditions-manifest.json itself is also untouched

The verified flag must NOT flip — only `crew:approve` is allowed to do
that. The sidecar is the resolution evidence, not the verification.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
m = json.loads(pathlib.Path('${TEST_DIR}/phases/${PHASE}/conditions-manifest.json').read_text())
mech_entry = next(c for c in m['conditions'] if c['id'] == 'mech-1')
assert mech_entry['verified'] is False, (
    'mech-1.verified MUST stay False after crew:resolve --accept; '
    'only crew:approve flips it'
)
print('PASS contract: conditions-manifest.mech-1.verified is still False')
"
```

**Expected**: `PASS contract: conditions-manifest.mech-1.verified is still False`

## Success Criteria

- [ ] Step 3: preview classifies findings without writing any resolution sidecar
- [ ] Step 4: --accept writes a sidecar for the `mechanical` finding only
- [ ] Step 4: escalation finding is refused with a pointer to crew:swarm
- [ ] Step 5: `gate-result.json` SHA256 is byte-identical before vs after `--accept`
- [ ] Step 6: `conditions-manifest.json` `verified` flag for the resolved finding is still `False` (only `crew:approve` flips it)

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR PHASE
```
