---
name: stack-signals-react-detected
title: Stack Signals — React App is Detected and Surfaced Through the Rubric
description: A React + TypeScript repo is detected by `_stack_signals.detect_stack`, the 9-factor rubric absorbs the `has_ui` signal as a +1 band on `user_facing_impact`, and the briefing surface names "React" back to the user. No `presets/` directory and no `.wicked-garden/config.yml` are created.
type: testing
difficulty: intermediate
estimated_minutes: 5
---

# Stack Signals — React App Detected (#723)

This scenario asserts the reframe of #723: stack identity is a *projection*
of the repo, absorbed by the 9-factor rubric as a small score adjustment.

The pain being solved: when wicked-garden runs against a React app, the
session should *name* React back to the user. The original framing wanted
hand-curated `presets/` files; the reframe routes the same legibility win
through the rubric the facilitator already runs.

What this scenario verifies:

1. `crew._stack_signals.detect_stack` correctly identifies React + TypeScript
   from a `package.json` + `tsconfig.json` + `.tsx` file.
2. `crew.factor_questionnaire._apply_stack_adjustments` bumps
   `user_facing_impact` exactly one band toward higher risk because
   `has_ui=True`, capped at LOW.
3. The briefing surface (used in the smaht briefing command) names
   "React" back to the user via the additive `detected_stack` field.
4. **No** `presets/` directory and **no** `.wicked-garden/config.yml`
   are created — the rubric path replaces the preset path.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-stack-react-'))
")
echo "TEST_DIR=${TEST_DIR}"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, pathlib
test_dir = pathlib.Path(os.environ['TEST_DIR'])

(test_dir / "package.json").write_text(json.dumps({
    "name": "react-demo",
    "version": "0.1.0",
    "dependencies": {
        "react": "^18.0.0",
        "react-dom": "^18.0.0",
    },
    "devDependencies": {"typescript": "^5.0.0"},
}, indent=2), encoding="utf-8")

(test_dir / "tsconfig.json").write_text("{}", encoding="utf-8")

src = test_dir / "src"
src.mkdir()
(src / "App.tsx").write_text(
    "export const App = () => null;\n",
    encoding="utf-8",
)
print(f"react demo project written at {test_dir}")
PYEOF
```

**Expected**: `react demo project written at /…/wg-stack-react-…`

## Step 1: detect_stack identifies React + TypeScript and sets has_ui=True

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from crew._stack_signals import detect_stack
result = detect_stack('${TEST_DIR}')
print(json.dumps(result, indent=2, sort_keys=True))
assert result['language'] == 'typescript', f'language: {result[\"language\"]}'
assert result['package_manager'] == 'npm', f'pm: {result[\"package_manager\"]}'
assert 'react' in result['frameworks'], f'frameworks: {result[\"frameworks\"]}'
assert result['has_ui'] is True, 'has_ui must be True for React + .tsx'
assert result['has_api_surface'] is False, 'no api framework -> False'
print('PASS: React + TypeScript stack detected with has_ui=True')
"
```

**Expected**: `PASS: React + TypeScript stack detected with has_ui=True`

## Step 2: rubric absorbs the signal as a +1 band on user_facing_impact

This is the load-bearing reframe step: the rubric already drives every
adaptive-rigor decision. The stack signal feeds *into* it rather than
running a parallel preset selector.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from crew._stack_signals import detect_stack
from crew.factor_questionnaire import score_all, _apply_stack_adjustments

# Baseline: an all-no questionnaire response → all factors HIGH (safest).
base = score_all({})
assert base['user_facing_impact']['reading'] == 'HIGH', \
    f'baseline must start HIGH, got {base[\"user_facing_impact\"][\"reading\"]}'

stack = detect_stack('${TEST_DIR}')
adjusted, audit = _apply_stack_adjustments(base, stack)

# +1 band toward higher risk: HIGH -> MEDIUM (cap at LOW).
assert adjusted['user_facing_impact']['reading'] == 'MEDIUM', (
    f'expected +1 band to MEDIUM, got {adjusted[\"user_facing_impact\"][\"reading\"]}'
)

# Audit trail must record the adjustment so reviewers can see *why*.
ufi_audit = [e for e in audit if e['factor'] == 'user_facing_impact']
assert ufi_audit, f'audit trail empty; got: {audit}'
assert ufi_audit[0]['adjustment'] == '+1'
assert ufi_audit[0]['reason'] == 'stack:has_ui'
assert ufi_audit[0]['from'] == 'HIGH'
assert ufi_audit[0]['to'] == 'MEDIUM'
assert ufi_audit[0]['capped'] is False

print('PASS: user_facing_impact bumped HIGH -> MEDIUM with audit reason stack:has_ui')
"
```

**Expected**: `PASS: user_facing_impact bumped HIGH -> MEDIUM with audit reason stack:has_ui`

## Step 3: archetype_detect carries detected_stack so the briefing can name it

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from crew.archetype_detect import detect_archetype

result = detect_archetype({
    'files': ['package.json', 'tsconfig.json', 'src/App.tsx'],
    'project_dir': '${TEST_DIR}',
})

# detected_stack is purely additive — archetype enum is unchanged.
assert 'detected_stack' in result, 'detected_stack field missing'
stack = result['detected_stack']
assert stack['language'] == 'typescript', f'language: {stack[\"language\"]}'
assert 'react' in stack['frameworks'], f'frameworks: {stack[\"frameworks\"]}'
assert stack['has_ui'] is True

# The briefing-style line that should be named back to the user.
line = (
    f\"Detected stack: {stack['language']} ({stack['package_manager']}, \"
    f\"frameworks: {', '.join(stack['frameworks'])}). \"
    f\"Archetype: {result['archetype']}.\"
)
print(line)
assert 'react' in line.lower(), 'briefing line must name React back to the user'
print('PASS: briefing names React back to the user')
"
```

**Expected** (last two lines):

```
Detected stack: typescript (npm, frameworks: react, react-dom). Archetype: code-repo.
PASS: briefing names React back to the user
```

## Step 4: NO presets/ directory and NO .wicked-garden/config.yml are created

The reframe explicitly forbids parallel state. This step asserts that
running detection does not create those forbidden surfaces — they would
have been the symptoms of the original framing.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import pathlib
test_dir = pathlib.Path('${TEST_DIR}')

forbidden = [
    test_dir / 'presets',
    test_dir / '.wicked-garden' / 'config.yml',
    test_dir / '.wicked-garden' / 'config.yaml',
    test_dir / 'wicked-garden.yml',
]
for path in forbidden:
    assert not path.exists(), (
        f'forbidden parallel-state file appeared: {path} — '
        'the reframe requires zero new state surfaces'
    )

# Also guard against the .wicked-garden directory itself being silently
# created (it would be a regression toward parallel state).
assert not (test_dir / '.wicked-garden').exists(), (
    '.wicked-garden/ directory created — stack detection must be a '
    'projection, never a persisted artifact'
)

print('PASS: no presets/ dir, no .wicked-garden/config.yml — projection only')
"
```

**Expected**: `PASS: no presets/ dir, no .wicked-garden/config.yml — projection only`

## Success Criteria

- [ ] `detect_stack` returns `language=typescript`, `has_ui=True`, `react` in frameworks
- [ ] `_apply_stack_adjustments` bumps `user_facing_impact` HIGH -> MEDIUM with audit reason `stack:has_ui`
- [ ] `detect_archetype` result carries `detected_stack` as an additive field (archetype enum unchanged)
- [ ] Briefing-style line names "React" back to the user
- [ ] No `presets/` directory created
- [ ] No `.wicked-garden/config.yml` (or `.yaml`) file created
- [ ] No `.wicked-garden/` directory created at all

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR
```
