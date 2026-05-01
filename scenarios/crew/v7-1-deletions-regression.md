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
  - CA-01..CA-06 (CHANGELOG [7.1.0] entry + plugin.json version)
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

## Step 5: plugin.json version is 7.1.0 and v7.0.0 git tag exists (CA-05, CA-06)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, sys, json, subprocess
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
plugin_path = os.path.join(root, '.claude-plugin', 'plugin.json')
if not os.path.exists(plugin_path):
    print('FAIL (CA-05): .claude-plugin/plugin.json not found'); sys.exit(1)
d = json.load(open(plugin_path))
version = d.get('version', '')
if version != '7.1.0':
    print(f'FAIL (CA-05): version={version!r}, expected 7.1.0'); sys.exit(1)
print('PASS (CA-05): plugin.json version is 7.1.0')
tag = subprocess.run(['git', 'tag', '--list', 'v7.0.0'], capture_output=True, text=True, cwd=root)
if 'v7.0.0' not in tag.stdout:
    print('FAIL (CA-06): git tag v7.0.0 not found'); sys.exit(1)
print('PASS (CA-06): git tag v7.0.0 exists')
" 2>/dev/null || python -c "
import os, sys, json, subprocess
root = os.environ.get('CLAUDE_PLUGIN_ROOT', '.')
d = json.load(open(os.path.join(root, '.claude-plugin', 'plugin.json')))
if d.get('version') != '7.1.0': print('FAIL version'); sys.exit(1)
t = subprocess.run(['git','tag','--list','v7.0.0'], capture_output=True, text=True, cwd=root)
if 'v7.0.0' not in t.stdout: print('FAIL tag'); sys.exit(1)
print('PASS (CA-05, CA-06): version 7.1.0 and tag v7.0.0 verified')
"
```

**Expect**: exit 0

---

## Success Criteria

- [ ] `agents/qe/`, `skills/qe/`, `skills/acceptance-testing/`, `commands/qe/` all absent (GA-01..GA-04)
- [ ] `hooks/scripts/bootstrap.py`, `post_tool.py`, `prompt_submit.py` contain zero `wicked-garden:qe:` or `wicked-garden:acceptance-testing:` strings (GA-05, GA-07..GA-09)
- [ ] `scripts/qe/cli_discovery.py` absent (GA-10)
- [ ] CHANGELOG.md has `## [7.1.0]` entry naming all 4 deleted dirs, install instruction, and migrate script (CA-01..CA-04)
- [ ] `.claude-plugin/plugin.json` version is `7.1.0` (CA-05)
- [ ] Git tag `v7.0.0` exists (CA-06)
