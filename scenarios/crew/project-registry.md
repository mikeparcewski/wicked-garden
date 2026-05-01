---
name: project-registry
title: Multi-Project Registry Management
description: Verify project_registry.py CLI creates, lists, switches, archives, and filters projects
type: testing
difficulty: basic
estimated_minutes: 10
---

# Multi-Project Registry Management

This scenario verifies that `project_registry.py` correctly manages the project registry:
creating projects, listing by workspace, setting and switching active projects, archiving
and unarchiving, finding by name, and producing correct filter output.

## Setup

```bash
# Verify project_registry.py is available
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" --help > /dev/null 2>&1 \
  && echo "project_registry.py available" || echo "NOT FOUND"
```

## Steps

### 1. Create project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" create \
  --name test-proj-1 --workspace test-ws --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
print('HAS_ID:', bool(d.get('id')))
print('NAME:', d.get('name', 'N/A'))
print('WORKSPACE:', d.get('workspace', 'N/A'))
print('STATUS:', d.get('status', 'N/A'))
proj_id = d.get('id', '')
print('PROJ1_ID:', proj_id)
"
```

**Expected**: `HAS_ID: True`, `NAME: test-proj-1`, `WORKSPACE: test-ws`, `STATUS: active`.

### 2. Create second project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" create \
  --name test-proj-2 --workspace test-ws --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
print('NAME:', d.get('name', 'N/A'))
print('PROJ2_ID:', d.get('id', ''))
"
```

**Expected**: `NAME: test-proj-2`. Record PROJ2_ID.

### 3. List projects

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" list \
  --workspace test-ws --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
projects = d.get('projects', d if isinstance(d, list) else [])
names = sorted([p.get('name', '') for p in projects])
print('COUNT:', len(projects))
print('NAMES:', names)
print('BOTH_PRESENT:', 'test-proj-1' in names and 'test-proj-2' in names)
"
```

**Expected**: `COUNT: 2`, `BOTH_PRESENT: True`.

### 4. Set active

```bash
# Get proj-1 ID
PROJ1_ID=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" find \
  --name test-proj-1 --workspace test-ws --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); print(d.get('id', d.get('projects',[{}])[0].get('id','') if isinstance(d.get('projects'),list) else ''))")

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" set-active \
  --id "${PROJ1_ID}" 2>&1
echo "Exit: $?"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" get-active \
  --workspace test-ws --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
print('ACTIVE_NAME:', d.get('name', 'N/A'))
"
```

**Expected**: Exit 0, `ACTIVE_NAME: test-proj-1`.

### 5. Switch project

```bash
PROJ2_ID=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" find \
  --name test-proj-2 --workspace test-ws --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); print(d.get('id', d.get('projects',[{}])[0].get('id','') if isinstance(d.get('projects'),list) else ''))")

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" switch \
  --id "${PROJ2_ID}" --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
print('SWITCHED_TO:', d.get('name', 'N/A'))
"
```

**Expected**: `SWITCHED_TO: test-proj-2`.

### 6. Get project filter

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" filter --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
has_project = bool(d.get('project_id'))
print('HAS_PROJECT_ID:', has_project)
"
```

**Expected**: `HAS_PROJECT_ID: True` (active project is proj-2).

### 7. Archive

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" archive \
  --id "${PROJ1_ID}" 2>&1
echo "Exit: $?"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" list \
  --workspace test-ws --active --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
projects = d.get('projects', d if isinstance(d, list) else [])
names = [p.get('name', '') for p in projects]
print('PROJ1_VISIBLE:', 'test-proj-1' in names)
print('PROJ2_VISIBLE:', 'test-proj-2' in names)
"
```

**Expected**: Exit 0, `PROJ1_VISIBLE: False`, `PROJ2_VISIBLE: True`.

### 8. Unarchive

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" unarchive \
  --id "${PROJ1_ID}" 2>&1
echo "Exit: $?"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" list \
  --workspace test-ws --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
projects = d.get('projects', d if isinstance(d, list) else [])
names = [p.get('name', '') for p in projects]
print('BOTH_BACK:', 'test-proj-1' in names and 'test-proj-2' in names)
"
```

**Expected**: Exit 0, `BOTH_BACK: True`.

### 9. Find by name

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" find \
  --name test-proj-1 --workspace test-ws --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
name = d.get('name', d.get('projects', [{}])[0].get('name', '') if isinstance(d.get('projects'), list) else '')
print('FOUND:', name == 'test-proj-1')
"
```

**Expected**: `FOUND: True`.

### 10. Empty filter when no active

```bash
# Archive both projects
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" archive --id "${PROJ1_ID}" 2>/dev/null
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" archive --id "${PROJ2_ID}" 2>/dev/null

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" filter --json \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
print('EMPTY_FILTER:', d == {} or not d.get('project_id'))
"
```

**Expected**: `EMPTY_FILTER: True`.

## Success Criteria

- [ ] Create returns JSON with id, name, workspace, status=active
- [ ] List by workspace returns both projects
- [ ] Set-active + get-active returns correct project
- [ ] Switch changes the active project
- [ ] Filter returns project_id for active project
- [ ] Archive hides project from --active list
- [ ] Unarchive restores project visibility
- [ ] Find by name returns correct project
- [ ] Filter returns empty when no active project exists

## Cleanup

```bash
# Unarchive to enable deletion if needed
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" unarchive --id "${PROJ1_ID}" 2>/dev/null || true
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/project_registry.py" unarchive --id "${PROJ2_ID}" 2>/dev/null || true
```
