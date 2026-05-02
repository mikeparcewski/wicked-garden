---
name: guide-phase-archetype-filter
title: crew:guide — Phase + Archetype-Aware Filtering (Issue #725)
description: Verify that crew:guide filters command suggestions by the active project's current phase + detected archetype, and falls back to the bootstrap entry-point set when no project is active.
type: testing
difficulty: intermediate
estimated_minutes: 6
---

# crew:guide — Phase + Archetype-Aware Filtering (Issue #725)

This scenario drives the new `filter_for_context` + `read_active_project_context`
+ `bootstrap_entry_points` surface added to `scripts/crew/guide.py`. It asserts
the three reframe behaviours:

1. With an active `docs-only` project on `build`, the filtered command set
   excludes archetype-specific commands like `engineering:review` (declared
   `archetype_relevance: ["code-repo", "schema-migration", "config-infra"]`).
2. Switching the same project to `clarify` flips the relevant set to
   clarify-tagged commands (`jam:quick`, `propose-process`).
3. With no active project, `bootstrap_entry_points` returns commands tagged
   `phase_relevance: ["bootstrap"]` — the entry-point set, derived from
   frontmatter, not a hand-curated starter list.

## Setup

```bash
export TEST_PROJECT="wg-scenario-guide-filter"
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export CLAUDE_PROJECT_NAME="wg-scenario-guide-filter"

export PROJECT_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, shutil, sys
sys.path.insert(0, os.path.join(os.environ['PLUGIN_ROOT'], 'scripts'))
from _paths import get_local_path
projects_root = get_local_path('wicked-crew', 'projects')
project = os.environ['TEST_PROJECT']
(projects_root / f"{project}.json").unlink(missing_ok=True)
shutil.rmtree(projects_root / project, ignore_errors=True)
project_dir = projects_root / project
project_dir.mkdir(parents=True)
data = {
    "id": project,
    "name": project,
    "workspace": os.environ['CLAUDE_PROJECT_NAME'],
    "current_phase": "build",
    "archetype": "docs-only",
    "phase_plan": ["clarify", "design", "build", "test", "review"],
    "phases": {p: {"status": "pending"} for p in ["clarify", "design", "build", "test", "review"]},
}
(projects_root / f"{project}.json").write_text(json.dumps(data, indent=2))
(project_dir / "project.json").write_text(json.dumps(data, indent=2))
print(project_dir)
PYEOF
)
echo "PROJECT_DIR=${PROJECT_DIR}"
```

**Expected**: `PROJECT_DIR=...` printed.

## Step 1: docs-only + build → filtered set excludes archetype-locked commands

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, os.path.join('${PLUGIN_ROOT}', 'scripts'))
os.environ['CLAUDE_PROJECT_NAME'] = '${CLAUDE_PROJECT_NAME}'

from crew import guide

ctx = guide.read_active_project_context()
assert ctx is not None, 'expected active project context'
assert ctx['archetype'] == 'docs-only', f'archetype={ctx[\"archetype\"]!r}'
assert ctx['current_phase'] == 'build', f'phase={ctx[\"current_phase\"]!r}'

commands = guide.read_command_metadata(os.path.join('${PLUGIN_ROOT}', 'commands'))
filtered = guide.filter_for_context(
    commands, phase=ctx['current_phase'], archetype=ctx['archetype']
)
ids = {c['id'] for c in filtered}

# Wildcards must survive both filters.
assert 'wicked-garden:help' in ids, 'help (wildcard/wildcard) should pass'
assert 'wicked-garden:crew:guide' in ids, 'guide (wildcard/wildcard) should pass'
# Build-tagged + wildcard archetype.
assert 'wicked-garden:search:blast-radius' in ids, 'blast-radius (build, *) should pass'
# Build-tagged but archetype excludes docs-only — must drop.
assert 'wicked-garden:engineering:review' not in ids, 'engineering:review must drop on docs-only'
# bootstrap-only commands must drop on build phase.
assert 'wicked-garden:setup' not in ids, 'setup (bootstrap-only) must drop on build'
print('PASS: docs-only + build filter excludes archetype-locked + bootstrap-only commands')
"
```

**Expected**: `PASS: docs-only + build filter excludes archetype-locked + bootstrap-only commands`

## Step 2: change phase to clarify → clarify-tagged commands surface

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, sys
sys.path.insert(0, os.path.join(os.environ['PLUGIN_ROOT'], 'scripts'))
from _paths import get_local_path
projects_root = get_local_path('wicked-crew', 'projects')
project = os.environ['TEST_PROJECT']
data = json.loads((projects_root / f"{project}.json").read_text())
data['current_phase'] = 'clarify'
(projects_root / f"{project}.json").write_text(json.dumps(data, indent=2))
(projects_root / project / "project.json").write_text(json.dumps(data, indent=2))
print('phase flipped to clarify')
PYEOF

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, os.path.join('${PLUGIN_ROOT}', 'scripts'))
os.environ['CLAUDE_PROJECT_NAME'] = '${CLAUDE_PROJECT_NAME}'

from crew import guide

ctx = guide.read_active_project_context()
assert ctx['current_phase'] == 'clarify', f'expected clarify, got {ctx[\"current_phase\"]!r}'

commands = guide.read_command_metadata(os.path.join('${PLUGIN_ROOT}', 'commands'))
filtered = guide.filter_for_context(
    commands, phase=ctx['current_phase'], archetype=ctx['archetype']
)
ids = {c['id'] for c in filtered}

# Clarify+design tagged.
assert 'wicked-garden:jam:quick' in ids, 'jam:quick (clarify, design) should pass'
# approve covers clarify.
assert 'wicked-garden:crew:approve' in ids, 'crew:approve covers clarify'
# Build-only tagged commands must drop now that phase is clarify.
assert 'wicked-garden:search:blast-radius' not in ids, 'blast-radius (build, review) must drop on clarify'
print('PASS: clarify phase surfaces jam:quick + crew:approve, drops build-only commands')
"
```

**Expected**: `PASS: clarify phase surfaces jam:quick + crew:approve, drops build-only commands`

## Step 3: no active project → bootstrap entry-point set

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, sys
sys.path.insert(0, os.path.join(os.environ['PLUGIN_ROOT'], 'scripts'))
from _paths import get_local_path
projects_root = get_local_path('wicked-crew', 'projects')
project = os.environ['TEST_PROJECT']
# Mark the project complete so read_active_project_context returns None.
data = json.loads((projects_root / f"{project}.json").read_text())
data['current_phase'] = 'complete'
(projects_root / f"{project}.json").write_text(json.dumps(data, indent=2))
(projects_root / project / "project.json").write_text(json.dumps(data, indent=2))
print('project marked complete')
PYEOF

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, os.path.join('${PLUGIN_ROOT}', 'scripts'))
os.environ['CLAUDE_PROJECT_NAME'] = '${CLAUDE_PROJECT_NAME}'

from crew import guide

ctx = guide.read_active_project_context()
assert ctx is None, f'expected None on completed project, got {ctx!r}'

commands = guide.read_command_metadata(os.path.join('${PLUGIN_ROOT}', 'commands'))
entry_points = guide.bootstrap_entry_points(commands)
ids = {c['id'] for c in entry_points}

# Daily-driver bootstrap commands must surface.
assert 'wicked-garden:setup' in ids, 'setup must be in bootstrap set'
assert 'wicked-garden:crew:start' in ids, 'crew:start must be in bootstrap set'

# Add skills to the source so propose-process is also visible to the entry point set.
# Skill ids are path-derived: skills/propose-process/SKILL.md -> wicked-garden:propose-process:SKILL.
skills_records = guide.read_command_metadata(os.path.join('${PLUGIN_ROOT}', 'skills'))
skill_entry = guide.bootstrap_entry_points(skills_records)
skill_ids = {c['id'] for c in skill_entry}
assert any('propose-process' in sid for sid in skill_ids), \
    f'propose-process skill must be in bootstrap set, got {sorted(skill_ids)!r}'

print('PASS: no active project — bootstrap entry-point set surfaces setup + crew:start + propose-process')
"
```

**Expected**: `PASS: no active project — bootstrap entry-point set surfaces setup + crew:start + propose-process`

## Success Criteria

- [ ] Step 1: `docs-only` + `build` filter excludes `engineering:review` and bootstrap-only commands.
- [ ] Step 2: switching to `clarify` surfaces `jam:quick` + `crew:approve` and drops build-only commands.
- [ ] Step 3: with the project marked complete, `bootstrap_entry_points` returns the entry-point set derived from frontmatter (no hand-curated list).

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import os, shutil, sys
sys.path.insert(0, os.path.join(os.environ['PLUGIN_ROOT'], 'scripts'))
from _paths import get_local_path
projects_root = get_local_path('wicked-crew', 'projects')
project = os.environ['TEST_PROJECT']
(projects_root / f"{project}.json").unlink(missing_ok=True)
shutil.rmtree(projects_root / project, ignore_errors=True)
print('cleaned up')
PYEOF

unset TEST_PROJECT PROJECT_DIR PLUGIN_ROOT CLAUDE_PROJECT_NAME
```
