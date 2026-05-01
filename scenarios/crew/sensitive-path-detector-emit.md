---
name: sensitive-path-detector-emit
title: Sensitive-Path Detector — Emit + Schema Validation
description: |
  Acceptance scenario for PR-2 of the steering detector epic (#679). Drives
  scripts/crew/detectors/sensitive_path.py against a fixture path list that
  mixes auth + payments + migrations + secrets + non-sensitive files
  (including a README inside auth/), then asserts:

    * The detector emits one event per sensitive code file.
    * Non-code files (README.md inside a sensitive directory) are NOT emitted.
    * Every payload passes scripts/crew/steering_event_schema.validate_payload.
    * Each emitted payload carries the correct event_type + subdomain.

  No live wicked-bus is required — the scenario uses --dry-run and inspects
  the structured stdout. A separate "live" case exercises the bus path only
  when the bus is reachable.
type: testing
difficulty: beginner
estimated_minutes: 5
covers:
  - epic #679 (steering detector registry)
  - PR-2 (first real detector — sensitive-path)
  - scripts/crew/detectors/sensitive_path.py
  - scripts/crew/steering_event_schema.py (validator integration)
---

# Sensitive-Path Detector — Emit + Schema Validation

Verifies that the sensitive-path detector (PR-2) produces well-formed
`wicked.steer.escalated` payloads that pass the PR-1 schema validator and
respect the brainstorm-mandated extension filter. All assertions are
structural (JSON shape + string equality) — no LLM in the loop.

---

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export DETECTOR="${PLUGIN_ROOT}/scripts/crew/detectors/sensitive_path.py"

# Each fixture is passed as its own --paths arg (avoids shell word-splitting
# differences between bash and zsh).
sensitive_paths_invocation() {
    sh "${PLUGIN_ROOT}/scripts/_python.sh" "${DETECTOR}" \
        --paths \
            "src/auth/login.py" \
            "api/payments/charge.go" \
            "db/migrations/001_users.sql" \
            "config/secrets.env" \
            "src/auth/README.md" \
            "README.md" \
            "tests/auth/test_login.py" \
        "$@"
}
```

---

## Case 1: Dry-run emits one event per sensitive code file

**Verifies**: 5 events fire (auth + payments + migration + secrets + auth-test);
2 docs are filtered out (auth/README.md + repo README.md).

### Test

```bash
sensitive_paths_invocation \
  --session-id scenario-001 \
  --project-slug sensitive-path-scenario \
  --dry-run \
  | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
events = [json.loads(line) for line in sys.stdin if line.strip()]
print('EVENT_COUNT:', len(events))
print('FILES:', ','.join(sorted(ev['evidence']['file'] for ev in events)))
print('CATEGORIES:', ','.join(sorted(ev['evidence']['category'] for ev in events)))
print('README_AUTH_PRESENT:', any(ev['evidence']['file'] == 'src/auth/README.md' for ev in events))
print('README_ROOT_PRESENT:', any(ev['evidence']['file'] == 'README.md' for ev in events))
"
```

**Expected**:

```
EVENT_COUNT: 5
FILES: api/payments/charge.go,config/secrets.env,db/migrations/001_users.sql,src/auth/login.py,tests/auth/test_login.py
CATEGORIES: auth,auth,migration,payments,secrets
README_AUTH_PRESENT: False
README_ROOT_PRESENT: False
```

---

## Case 2: Every payload passes the PR-1 schema validator

**Verifies**: each emitted payload is valid per
`scripts/crew/steering_event_schema.py::validate_payload` — zero hard errors,
zero warnings.

### Test

```bash
sensitive_paths_invocation \
  --session-id scenario-002 \
  --project-slug sensitive-path-scenario \
  --dry-run \
  | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from crew.steering_event_schema import validate_payload
events = [json.loads(line) for line in sys.stdin if line.strip()]
all_errors = []
all_warnings = []
for ev in events:
    e, w = validate_payload('wicked.steer.escalated', ev)
    all_errors.extend(e)
    all_warnings.extend(w)
print('PAYLOADS:', len(events))
print('TOTAL_ERRORS:', len(all_errors))
print('TOTAL_WARNINGS:', len(all_warnings))
print('ALL_VALID:', not all_errors)
"
```

**Expected**:

```
PAYLOADS: 5
TOTAL_ERRORS: 0
TOTAL_WARNINGS: 0
ALL_VALID: True
```

---

## Case 3: Each payload carries the correct bus addressing fields

**Verifies**: every payload uses `detector=sensitive-path` and the
recommended-action mapping matches `ACTION_MAP` (auth+payments →
`force-full-rigor`, migration → `regen-test-strategy`, secrets →
`require-council-review`).

### Test

```bash
sensitive_paths_invocation \
  --session-id scenario-003 \
  --project-slug sensitive-path-scenario \
  --dry-run \
  | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
events = [json.loads(line) for line in sys.stdin if line.strip()]
print('ALL_DETECTOR_NAME_OK:', all(ev['detector'] == 'sensitive-path' for ev in events))
by_cat = {ev['evidence']['category']: ev['recommended_action'] for ev in events}
print('AUTH_ACTION:', by_cat.get('auth'))
print('PAYMENTS_ACTION:', by_cat.get('payments'))
print('MIGRATION_ACTION:', by_cat.get('migration'))
print('SECRETS_ACTION:', by_cat.get('secrets'))
"
```

**Expected**:

```
ALL_DETECTOR_NAME_OK: True
AUTH_ACTION: force-full-rigor
PAYMENTS_ACTION: force-full-rigor
MIGRATION_ACTION: regen-test-strategy
SECRETS_ACTION: require-council-review
```

---

## Case 4: Non-sensitive paths produce zero events (no crash)

**Verifies**: detector exits 0 with no payloads when no input file matches a
sensitive pattern. Confirms there's no false-positive on plain source.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${DETECTOR}" \
  --paths "src/utils/format.py" "src/widgets/button.tsx" "docs/architecture.md" \
  --session-id scenario-004 \
  --project-slug sensitive-path-scenario \
  --dry-run \
  > /tmp/sensitive-path-empty.out 2> /tmp/sensitive-path-empty.err
RC=$?
echo "EXIT_CODE: $RC"
echo "STDOUT_PAYLOADS: $(grep -c '"detector"' /tmp/sensitive-path-empty.out || true)"
echo "STDERR_REPORTS_ZERO: $(grep -c '0 steering event' /tmp/sensitive-path-empty.err || true)"
rm -f /tmp/sensitive-path-empty.out /tmp/sensitive-path-empty.err
```

**Expected**:

```
EXIT_CODE: 0
STDOUT_PAYLOADS: 0
STDERR_REPORTS_ZERO: 1
```

---

## Case 5: Bus emit path tolerates an unreachable bus (fail-open)

**Verifies**: when wicked-bus isn't installed, the detector still exits 0 and
prints a clear warning. The crew workflow must never crash because of a
missing bus.

### Test

```bash
# Force the bus to look unreachable by restricting PATH to system bins only.
# That keeps `sh` and `python3` resolvable but hides `wicked-bus` and `npx`,
# so the detector's bus probe returns None and the emitter takes the
# fail-open branch (warning to stderr, returns 0, exits 0).
env PATH="/usr/bin:/bin" sh "${PLUGIN_ROOT}/scripts/_python.sh" "${DETECTOR}" \
  --paths "src/auth/login.py" \
  --session-id scenario-005 \
  --project-slug sensitive-path-scenario \
  > /tmp/sensitive-path-emit.out 2> /tmp/sensitive-path-emit.err
RC=$?
echo "EXIT_CODE: $RC"
echo "STDOUT_HAS_PAYLOAD: $(grep -c '"detector":"sensitive-path"' /tmp/sensitive-path-emit.out || true)"
echo "STDERR_MENTIONS_UNREACHABLE: $(grep -ci 'wicked-bus is not installed\|unreachable' /tmp/sensitive-path-emit.err || true)"
rm -f /tmp/sensitive-path-emit.out /tmp/sensitive-path-emit.err
```

**Expected** (exit code 0 even without a bus; payload still printed; warning
on stderr):

```
EXIT_CODE: 0
STDOUT_HAS_PAYLOAD: 1
STDERR_MENTIONS_UNREACHABLE: 1
```

---

## Success Criteria

- [ ] Case 1 — 5 events fire from 7 fixture paths; both READMEs filtered
- [ ] Case 2 — every payload passes `validate_payload` with zero errors/warnings
- [ ] Case 3 — `detector` field + per-category `recommended_action` mapping is correct
- [ ] Case 4 — empty path input exits 0 with no payloads
- [ ] Case 5 — bus unreachable is fail-open (exit 0, payload still printed, warning on stderr)

## Cleanup

(No persistent state to clean — the detector and emitter only write to stdout/stderr.)
