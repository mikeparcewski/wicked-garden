---
name: v7-0-alias-deprecation
description: "AC-30, AC-31, AC-32: verify deprecation notice emission, delegation, and block behavior for the 8 /wicked-garden:qe:* alias shims"
category: api
tools:
  required: []
difficulty: basic
timeout: 60
---

## Context

Covers AC-30, AC-31, and AC-32 of wicked-testing-extraction-v7-0.

---

## Scenario A — Deprecation notice is present in each shim file (AC-30)

### Step 1: qe.md shim contains correct deprecation text (bash)

```bash
grep -F '[DEPRECATED] /wicked-garden:qe:qe is removed in v7.1 — use /wicked-testing:review instead.' \
  "${CLAUDE_PLUGIN_ROOT}/commands/qe/qe.md" && echo PASS
```

**Expect**: exit 0 (PASS printed)

### Step 2: qe-plan.md shim contains correct deprecation text (bash)

```bash
grep -F '[DEPRECATED] /wicked-garden:qe:qe-plan is removed in v7.1 — use /wicked-testing:plan instead.' \
  "${CLAUDE_PLUGIN_ROOT}/commands/qe/qe-plan.md" && echo PASS
```

**Expect**: exit 0

### Step 3: scenarios.md shim contains correct deprecation text (bash)

```bash
grep -F '[DEPRECATED] /wicked-garden:qe:scenarios is removed in v7.1 — use /wicked-testing:authoring instead.' \
  "${CLAUDE_PLUGIN_ROOT}/commands/qe/scenarios.md" && echo PASS
```

**Expect**: exit 0

### Step 4: automate.md shim contains correct deprecation text (bash)

```bash
grep -F '[DEPRECATED] /wicked-garden:qe:automate is removed in v7.1 — use /wicked-testing:authoring instead.' \
  "${CLAUDE_PLUGIN_ROOT}/commands/qe/automate.md" && echo PASS
```

**Expect**: exit 0

### Step 5: run.md shim contains correct deprecation text (bash)

```bash
grep -F '[DEPRECATED] /wicked-garden:qe:run is removed in v7.1 — use /wicked-testing:execution instead.' \
  "${CLAUDE_PLUGIN_ROOT}/commands/qe/run.md" && echo PASS
```

**Expect**: exit 0

### Step 6: acceptance.md shim contains correct deprecation text (bash)

```bash
grep -F '[DEPRECATED] /wicked-garden:qe:acceptance is removed in v7.1 — use /wicked-testing:execution instead.' \
  "${CLAUDE_PLUGIN_ROOT}/commands/qe/acceptance.md" && echo PASS
```

**Expect**: exit 0

### Step 7: qe-review.md shim contains correct deprecation text (bash)

```bash
grep -F '[DEPRECATED] /wicked-garden:qe:qe-review is removed in v7.1 — use /wicked-testing:review instead.' \
  "${CLAUDE_PLUGIN_ROOT}/commands/qe/qe-review.md" && echo PASS
```

**Expect**: exit 0

### Step 8: report.md shim contains correct deprecation text (bash)

```bash
grep -F '[DEPRECATED] /wicked-garden:qe:report is removed in v7.1 — use /wicked-testing:insight instead.' \
  "${CLAUDE_PLUGIN_ROOT}/commands/qe/report.md" && echo PASS
```

**Expect**: exit 0

---

## Scenario B — Each shim delegates and does NOT duplicate behavior (AC-30, thin shim)

### Step 9: No shim body exceeds 25 lines (thin shim check) (bash)

```bash
python3 -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
shims = ['qe.md','qe-plan.md','scenarios.md','automate.md','run.md','acceptance.md','qe-review.md','report.md']
failures = []
for name in shims:
    path = os.path.join(root, 'commands', 'qe', name)
    with open(path) as f:
        lines = f.readlines()
    if len(lines) > 30:
        failures.append(f'{name}: {len(lines)} lines (expected <= 30)')
if failures:
    print('FAIL: shims too large:')
    for f in failures: print(' ', f)
    sys.exit(1)
print('PASS: all shims are thin (<= 30 lines)')
" 2>/dev/null || python -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
shims = ['qe.md','qe-plan.md','scenarios.md','automate.md','run.md','acceptance.md','qe-review.md','report.md']
failures = []
for name in shims:
    path = os.path.join(root, 'commands', 'qe', name)
    with open(path) as f:
        lines = f.readlines()
    if len(lines) > 30:
        failures.append(name + ': ' + str(len(lines)) + ' lines (expected <= 30)')
if failures:
    print('FAIL: shims too large:')
    for f in failures: print(' ', f)
    sys.exit(1)
print('PASS: all shims are thin (<= 30 lines)')
"
```

**Expect**: exit 0

### Step 10: Each shim delegates to correct wicked-testing:* target (bash)

```bash
python3 -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
expected = {
    'qe.md': 'wicked-testing:review',
    'qe-plan.md': 'wicked-testing:plan',
    'scenarios.md': 'wicked-testing:authoring',
    'automate.md': 'wicked-testing:authoring',
    'run.md': 'wicked-testing:execution',
    'acceptance.md': 'wicked-testing:execution',
    'qe-review.md': 'wicked-testing:review',
    'report.md': 'wicked-testing:insight',
}
failures = []
for name, target in expected.items():
    path = os.path.join(root, 'commands', 'qe', name)
    content = open(path).read()
    if target not in content:
        failures.append(name + ' missing delegate target ' + target)
if failures:
    for f in failures: print('FAIL:', f)
    sys.exit(1)
print('PASS: all shims reference correct delegation targets')
" 2>/dev/null || python -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
expected = {'qe.md':'wicked-testing:review','qe-plan.md':'wicked-testing:plan','scenarios.md':'wicked-testing:authoring','automate.md':'wicked-testing:authoring','run.md':'wicked-testing:execution','acceptance.md':'wicked-testing:execution','qe-review.md':'wicked-testing:review','report.md':'wicked-testing:insight'}
failures = []
for name, target in expected.items():
    path = os.path.join(root, 'commands', 'qe', name)
    content = open(path).read()
    if target not in content:
        failures.append(name + ' missing ' + target)
if failures:
    for f in failures: print('FAIL:', f)
    sys.exit(1)
print('PASS: all shims reference correct delegation targets')
"
```

**Expect**: exit 0

---

## Scenario C — Block check takes precedence over deprecation notice (AC-31)

### Step 11: All shims check wicked_testing_missing before emitting deprecation (bash)

```bash
python3 -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
shims = ['qe.md','qe-plan.md','scenarios.md','automate.md','run.md','acceptance.md','qe-review.md','report.md']
failures = []
for name in shims:
    path = os.path.join(root, 'commands', 'qe', name)
    content = open(path).read()
    if 'wicked_testing_missing' not in content:
        failures.append(name + ': missing availability check')
    # Block check must appear BEFORE the deprecation notice line
    block_pos = content.find('wicked_testing_missing')
    dep_pos = content.find('[DEPRECATED]')
    if block_pos == -1 or dep_pos == -1 or block_pos >= dep_pos:
        failures.append(name + ': block check must precede deprecation notice')
if failures:
    for f in failures: print('FAIL:', f)
    sys.exit(1)
print('PASS: all shims check availability before emitting deprecation')
" 2>/dev/null || python -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
shims = ['qe.md','qe-plan.md','scenarios.md','automate.md','run.md','acceptance.md','qe-review.md','report.md']
failures = []
for name in shims:
    path = os.path.join(root, 'commands', 'qe', name)
    content = open(path).read()
    if 'wicked_testing_missing' not in content:
        failures.append(name + ': missing availability check')
    block_pos = content.find('wicked_testing_missing')
    dep_pos = content.find('[DEPRECATED]')
    if block_pos == -1 or dep_pos == -1 or block_pos >= dep_pos:
        failures.append(name + ': block check must precede deprecation notice')
if failures:
    for f in failures: print('FAIL:', f)
    sys.exit(1)
print('PASS')
"
```

**Expect**: exit 0

---

## Scenario D — /wicked-garden:help lists deprecated section (AC-32)

### Step 12: help.md contains deprecated section header (bash)

```bash
grep -F 'Deprecated — removed in v7.1' \
  "${CLAUDE_PLUGIN_ROOT}/commands/help.md" && echo PASS
```

**Expect**: exit 0

### Step 13: help.md names all 8 aliases in the deprecated section (bash)

```bash
python3 -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
path = os.path.join(root, 'commands', 'help.md')
content = open(path).read()
aliases = [
    '/wicked-garden:qe:qe',
    '/wicked-garden:qe:qe-plan',
    '/wicked-garden:qe:scenarios',
    '/wicked-garden:qe:automate',
    '/wicked-garden:qe:run',
    '/wicked-garden:qe:acceptance',
    '/wicked-garden:qe:qe-review',
    '/wicked-garden:qe:report',
]
missing = [a for a in aliases if a not in content]
if missing:
    for m in missing: print('FAIL: missing from help.md:', m)
    sys.exit(1)
print('PASS: all 8 aliases listed in help.md deprecated section')
" 2>/dev/null || python -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
path = os.path.join(root, 'commands', 'help.md')
content = open(path).read()
aliases = ['/wicked-garden:qe:qe','/wicked-garden:qe:qe-plan','/wicked-garden:qe:scenarios','/wicked-garden:qe:automate','/wicked-garden:qe:run','/wicked-garden:qe:acceptance','/wicked-garden:qe:qe-review','/wicked-garden:qe:report']
missing = [a for a in aliases if a not in content]
if missing:
    for m in missing: print('FAIL: missing:', m)
    sys.exit(1)
print('PASS')
"
```

**Expect**: exit 0

### Step 14: help.md names all 4 wicked-testing replacement targets (bash)

```bash
python3 -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
path = os.path.join(root, 'commands', 'help.md')
content = open(path).read()
targets = ['/wicked-testing:review','/wicked-testing:plan','/wicked-testing:authoring','/wicked-testing:execution','/wicked-testing:insight']
missing = [t for t in targets if t not in content]
if missing:
    for m in missing: print('FAIL: missing target in help.md:', m)
    sys.exit(1)
print('PASS: all replacement targets listed in help.md')
" 2>/dev/null || python -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
content = open(os.path.join(root, 'commands', 'help.md')).read()
targets = ['/wicked-testing:review','/wicked-testing:plan','/wicked-testing:authoring','/wicked-testing:execution','/wicked-testing:insight']
missing = [t for t in targets if t not in content]
if missing:
    for m in missing: print('FAIL:', m)
    sys.exit(1)
print('PASS')
"
```

**Expect**: exit 0

---

## Scenario E — Non-rename commands are untouched (AC-33 inverse: check.md / list.md / setup.md / help.md unchanged)

### Step 15: Non-shim QE commands do not contain DEPRECATED marker (bash)

```bash
python3 -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
preserved = ['check.md', 'list.md', 'setup.md', 'help.md']
failures = []
for name in preserved:
    path = os.path.join(root, 'commands', 'qe', name)
    content = open(path).read()
    if '[DEPRECATED]' in content or 'DEPRECATED v7.0' in content:
        failures.append(name + ': unexpectedly marked deprecated')
if failures:
    for f in failures: print('FAIL:', f)
    sys.exit(1)
print('PASS: preserved commands are not marked deprecated')
" 2>/dev/null || python -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
preserved = ['check.md', 'list.md', 'setup.md', 'help.md']
failures = []
for name in preserved:
    path = os.path.join(root, 'commands', 'qe', name)
    content = open(path).read()
    if '[DEPRECATED]' in content or 'DEPRECATED v7.0' in content:
        failures.append(name + ': unexpectedly marked deprecated')
if failures:
    for f in failures: print('FAIL:', f)
    sys.exit(1)
print('PASS')
"
```

**Expect**: exit 0

---

## Success Criteria

- [ ] All 8 shim files contain the correct `[DEPRECATED]` notice with v7.1 removal version
- [ ] Each shim delegates to the correct `wicked-testing:*` target (qe→review, qe-plan→plan, scenarios/automate→authoring, run/acceptance→execution, qe-review→review, report→insight)
- [ ] All shims are thin (≤ 30 lines including frontmatter)
- [ ] `wicked_testing_missing` check appears before `[DEPRECATED]` in every shim (block takes precedence over deprecation notice)
- [ ] `help.md` contains a deprecated section listing all 8 aliases and their 4 replacement targets
- [ ] Non-shim QE commands (`check.md`, `list.md`, `setup.md`) do not carry the DEPRECATED marker
