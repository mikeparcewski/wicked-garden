---
name: v7-1-deletions-regression
title: v7.1 Deletion Wave Regression Guard
description: "GA-01..GA-12: absence-assertions for all v7.1-deleted paths, grep audits, wg-check guard, CHANGELOG/version assertions"
type: testing
difficulty: basic
estimated_minutes: 5
covers:
  - GA-01..GA-04 (4 deleted directories absent)
  - GA-05..GA-09 (dispatch-path grep audits clean)
  - GA-10 (cli_discovery.py absent)
  - CA-01..CA-04 + CA-06 (CHANGELOG [7.1.0] entry + v7.0.0 git tag; CA-05 retired)
  - INV-01 (pytest count >= 1012)
ac_ref: "v7.1 AC-7..AC-18, AC-23..AC-26, AC-27..AC-30"
---

# v7.1 Deletion Wave Regression Guard

Guards the v7.1 deletion wave against re-introduction. All assertions are absence-only
or structural grep audits — no side-effects on the repo.

## Step 1: 4 deleted directories are absent (GA-01..GA-04)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
absent = ['agents/qe', 'skills/qe', 'skills/acceptance-testing', 'commands/qe']
failures = [p for p in absent if os.path.exists(os.path.join(root, p))]
if failures:
    for f in failures: print('FAIL: directory still exists:', f)
    sys.exit(1)
print('PASS (GA-01..GA-04): all 4 directories absent')
" 2>/dev/null || python -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
absent = ['agents/qe', 'skills/qe', 'skills/acceptance-testing', 'commands/qe']
failures = [p for p in absent if os.path.exists(os.path.join(root, p))]
if failures:
    for f in failures: print('FAIL:', f); sys.exit(1)
print('PASS (GA-01..GA-04): all 4 directories absent')
"
```

**Expect**: exit 0

## Step 2: Zero wicked-garden:qe: refs in dispatch-path code (GA-05, GA-07..GA-09)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, sys, pathlib
root = pathlib.Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.'))
targets = [
    root / 'hooks' / 'scripts' / 'bootstrap.py',
    root / 'hooks' / 'scripts' / 'post_tool.py',
    root / 'hooks' / 'scripts' / 'prompt_submit.py',
]
stray = []
for p in targets:
    if not p.exists(): continue
    txt = p.read_text(errors='replace')
    for i, line in enumerate(txt.splitlines(), 1):
        if 'wicked-garden:qe:' in line or 'wicked-garden:acceptance-testing:' in line:
            stray.append(f'{p.name}:{i}: {line.strip()[:80]}')
if stray:
    for s in stray: print('FAIL:', s)
    sys.exit(1)
print('PASS (GA-05, GA-07..GA-09): zero qe: refs in dispatch-path files')
" 2>/dev/null || python -c "
import os, sys, pathlib
root = pathlib.Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.'))
targets = ['hooks/scripts/bootstrap.py', 'hooks/scripts/post_tool.py', 'hooks/scripts/prompt_submit.py']
stray = []
for t in targets:
    p = root / t
    if not p.exists(): continue
    txt = p.read_text(errors='replace')
    if 'wicked-garden:qe:' in txt or 'wicked-garden:acceptance-testing:' in txt:
        stray.append(t)
if stray: print('FAIL:', stray); sys.exit(1)
print('PASS (GA-05, GA-07..GA-09): dispatch-path files clean')
"
```

**Expect**: exit 0

## Step 3: cli_discovery.py deleted (GA-10)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, sys
path = os.path.join(os.environ.get('CLAUDE_PLUGIN_ROOT', '.'), 'scripts', 'qe', 'cli_discovery.py')
if os.path.exists(path):
    print('FAIL (GA-10): cli_discovery.py still exists at', path); sys.exit(1)
print('PASS (GA-10): scripts/qe/cli_discovery.py absent')
" 2>/dev/null || python -c "
import os, sys
path = os.path.join(os.environ.get('CLAUDE_PLUGIN_ROOT', '.'), 'scripts', 'qe', 'cli_discovery.py')
if os.path.exists(path): print('FAIL'); sys.exit(1)
print('PASS (GA-10): cli_discovery.py absent')
"
```

**Expect**: exit 0

## Step 4: CHANGELOG has [7.1.0] entry with all 4 deleted dirs (CA-01, CA-02)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
path = os.path.join(root, 'CHANGELOG.md')
if not os.path.exists(path):
    print('FAIL: CHANGELOG.md not found'); sys.exit(1)
content = open(path).read()
checks = {
    'CA-01: [7.1.0] header':    '## [7.1.0]' in content,
    'CA-02a: agents/qe/':       'agents/qe' in content,
    'CA-02b: skills/qe/':       'skills/qe' in content,
    'CA-02c: skills/acceptance-testing/': 'skills/acceptance-testing' in content,
    'CA-02d: commands/qe/':     'commands/qe' in content,
    'CA-03: install instruction': 'npx wicked-testing install' in content,
    'CA-04: migrate script':    'migrate_qe_evaluator_name.py' in content,
}
fails = [k for k, v in checks.items() if not v]
if fails:
    for f in fails: print('FAIL:', f)
    sys.exit(1)
print('PASS (CA-01..CA-04): CHANGELOG [7.1.0] entry complete')
" 2>/dev/null || python -c "
import os, sys
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
c = open(os.path.join(root, 'CHANGELOG.md')).read()
checks = {'[7.1.0]': '## [7.1.0]' in c, 'agents/qe': 'agents/qe' in c, 'skills/qe': 'skills/qe' in c, 'migrate_script': 'migrate_qe_evaluator_name.py' in c}
fails = [k for k,v in checks.items() if not v]
if fails: print('FAIL:', fails); sys.exit(1)
print('PASS (CA-01..CA-04): CHANGELOG checks passed')
"
```

**Expect**: exit 0

## Step 5: v7.0.0 git tag exists (CA-06)

The original CA-05 assertion (plugin.json version == "7.1.0") was a snapshot pin
that became stale on every release. The plugin has since advanced past 7.1.0 (see
the deletion-presence guards in Steps 1-4 — those are the load-bearing checks for
this scenario's name). Step 5 retains only the v7.0.0 git-tag presence check.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, sys, subprocess
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
tag = subprocess.run(['git', 'tag', '--list', 'v7.0.0'], capture_output=True, text=True, cwd=root)
if 'v7.0.0' not in tag.stdout:
    print('FAIL (CA-06): git tag v7.0.0 not found'); sys.exit(1)
print('PASS (CA-06): git tag v7.0.0 exists')
"
```

**Expect**: exit 0

---

## Success Criteria

- [ ] `agents/qe/`, `skills/qe/`, `skills/acceptance-testing/`, `commands/qe/` all absent (GA-01..GA-04)
- [ ] `hooks/scripts/bootstrap.py`, `post_tool.py`, `prompt_submit.py` contain zero `wicked-garden:qe:` or `wicked-garden:acceptance-testing:` strings (GA-05, GA-07..GA-09)
- [ ] `scripts/qe/cli_discovery.py` absent (GA-10)
- [ ] CHANGELOG.md has `## [7.1.0]` entry naming all 4 deleted dirs, install instruction, and migrate script (CA-01..CA-04)
- [ ] (retired CA-05: plugin.json version assertion was a stale snapshot pin)
- [ ] Git tag `v7.0.0` exists (CA-06)
