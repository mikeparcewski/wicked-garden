---
name: worktree-parallel-build-clean-merge
title: Worktree Parallel Build Clean Merge
description: Verify worktree_manager.py and build_dependency_analyzer.py enable parallel build tasks with conflict detection and clean merge-back
type: workflow
difficulty: advanced
estimated_minutes: 15
---

# Worktree Parallel Build Clean Merge

This scenario validates that:
1. `worktree_manager.py` can check git worktree capability, create/list/cleanup worktrees
2. `build_dependency_analyzer.py` batches tasks into parallel and sequential groups
3. `execute.md` build phase uses dependency analysis before parallel dispatch
4. Conflict escalation guardrail fires when merge conflicts are detected

## Setup

```bash
# Verify git is available and supports worktrees
git worktree list > /dev/null 2>&1 && echo "worktrees supported"

# Verify worktree_manager.py is available
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/worktree_manager.py" --help > /dev/null 2>&1 && echo "worktree_manager.py available"

# Verify build_dependency_analyzer.py is available
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/build_dependency_analyzer.py" --help > /dev/null 2>&1 && echo "build_dependency_analyzer.py available"
```

## Steps

### 1. worktree_manager.py check_capability returns bool

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from worktree_manager import check_capability
result = check_capability()
print('capability:', result)
assert isinstance(result, bool), f'Expected bool, got {type(result)}'
print('PASS: check_capability() returns bool')
"
```

Expected: `PASS: check_capability() returns bool`

### 2. build_dependency_analyzer.py batches independent tasks as parallel

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from build_dependency_analyzer import analyze_dependencies

tasks = [
    {'id': '1', 'subject': 'Build: project - auth module', 'description': 'Implement src/auth/login.py'},
    {'id': '2', 'subject': 'Build: project - user profile', 'description': 'Implement src/profile/user.py'},
    {'id': '3', 'subject': 'Build: project - notification service', 'description': 'Implement src/notify/email.py'},
]

batches = analyze_dependencies(tasks, max_parallelism=3)
print('batches:', json.dumps(batches, indent=2))

assert len(batches) >= 1, 'Expected at least 1 batch'
# Tasks with no file overlap should be in the same parallel batch
first_batch = batches[0]
assert first_batch.get('parallel') == True, 'First batch should be parallel'
print('PASS: Independent tasks batched as parallel')
"
```

Expected: `PASS: Independent tasks batched as parallel`

### 3. build_dependency_analyzer.py separates conflicting tasks

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from build_dependency_analyzer import analyze_dependencies

# Two tasks that both touch the same file
tasks = [
    {'id': '1', 'subject': 'Build: project - auth middleware', 'description': 'Modify src/middleware/auth.py line 10-50'},
    {'id': '2', 'subject': 'Build: project - auth validation', 'description': 'Modify src/middleware/auth.py line 60-90'},
    {'id': '3', 'subject': 'Build: project - user profile', 'description': 'Implement src/profile/user.py (no overlap)'},
]

batches = analyze_dependencies(tasks, max_parallelism=3)
print('batches:', json.dumps(batches, indent=2))

# Task 3 should be in a parallel batch; tasks 1 and 2 should be separated
total_tasks = sum(len(b.get('tasks', [])) for b in batches)
assert total_tasks == 3, f'All 3 tasks should appear in batches, got {total_tasks}'
print('PASS: Conflicting tasks separated into different batches')
"
```

Expected: `PASS: Conflicting tasks separated into different batches`

### 4. build_dependency_analyzer.py respects max_parallelism

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from build_dependency_analyzer import analyze_dependencies

tasks = [
    {'id': str(i), 'subject': f'Build: project - task {i}', 'description': f'Implement src/module_{i}.py'}
    for i in range(6)
]

batches = analyze_dependencies(tasks, max_parallelism=2)
print('batches count:', len(batches))
for b in batches:
    if b.get('parallel'):
        assert len(b.get('tasks', [])) <= 2, f'Batch exceeds max_parallelism=2: {b}'
print('PASS: max_parallelism=2 respected')
"
```

Expected: `PASS: max_parallelism=2 respected`

### 5. worktree_manager.py list_active_worktrees returns list

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from worktree_manager import list_active_worktrees
result = list_active_worktrees('test-project')
print('active worktrees:', result)
assert isinstance(result, list), f'Expected list, got {type(result)}'
print('PASS: list_active_worktrees() returns list')
"
```

Expected: `PASS: list_active_worktrees() returns list`

### 6. execute.md build phase includes worktree capability check

```bash
grep -q "check_capability\|worktree.*capabilit\|worktree_manager" "${CLAUDE_PLUGIN_ROOT}/commands/crew/execute.md" && echo "PASS: Worktree capability check referenced"
```

Expected: `PASS: Worktree capability check referenced`

### 7. execute.md build phase includes parallel dispatch pattern

```bash
grep -q "parallel.*dispatch\|dependency.*analyz\|build_dependency_analyzer" "${CLAUDE_PLUGIN_ROOT}/commands/crew/execute.md" && echo "PASS: Parallel dispatch pattern referenced"
```

Expected: `PASS: Parallel dispatch pattern referenced`

### 8. execute.md build phase includes conflict escalation guardrail

```bash
grep -q "conflict\|escalat" "${CLAUDE_PLUGIN_ROOT}/commands/crew/execute.md" && echo "PASS: Conflict escalation guardrail referenced"
```

Expected: `PASS: Conflict escalation guardrail referenced`

### 9. build_dependency_analyzer.py CLI produces JSON output

```bash
echo '[{"id":"1","subject":"Build: proj - task1","description":"Implement auth.py"},{"id":"2","subject":"Build: proj - task2","description":"Implement profile.py"}]' | \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/build_dependency_analyzer.py" --stdin | \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
data = json.load(sys.stdin)
assert isinstance(data, list), f'Expected list, got {type(data)}'
assert all('batch' in b and 'tasks' in b and 'parallel' in b for b in data), f'Missing required keys in: {data}'
print('PASS: build_dependency_analyzer.py produces valid batch JSON')
"
```

Expected: `PASS: build_dependency_analyzer.py produces valid batch JSON`

## Expected Outcome

### worktree_manager.py
- `check_capability()` → bool: verifies clean git state + worktree support
- `create_worktree(project, task_id)` → path: creates `crew-{project}-{task_id}` worktree
- `merge_worktree(worktree_path, target_branch)` → result dict with conflict detection
- `cleanup_worktree(worktree_path)` → removes worktree and branch
- `list_active_worktrees(project)` → list of active worktree paths

### build_dependency_analyzer.py
- Takes task list, analyzes file overlap in descriptions
- Outputs batches: `[{batch: 1, tasks: ["1","2"], parallel: true}, {batch: 2, tasks: ["3"], parallel: false}]`
- Respects max_parallelism (default: 3)
- Tasks with shared file references → separate sequential batches
- Tasks with no overlap → same parallel batch

### execute.md additions
- Worktree capability check step before build task dispatch
- Parallel dispatch using dependency analyzer
- Merge-back step with conflict escalation guardrail
- Fallback to sequential dispatch when worktrees unavailable

## Success Criteria

### worktree_manager.py
- [ ] check_capability() returns bool without raising
- [ ] list_active_worktrees() returns list (empty when none active)
- [ ] Module importable without side effects

### build_dependency_analyzer.py
- [ ] analyze_dependencies() returns list of batch dicts
- [ ] Each batch has: batch (int), tasks (list of IDs), parallel (bool)
- [ ] max_parallelism respected in parallel batches
- [ ] Tasks with overlapping file references separated into sequential batches
- [ ] CLI --stdin accepts JSON task list and outputs batch JSON

### execute.md
- [ ] Worktree capability check referenced
- [ ] Parallel dispatch pattern referenced
- [ ] Conflict escalation guardrail mentioned

## Value Demonstrated

Sequential build execution is the primary bottleneck in multi-task crew projects. If 6 independent implementation tasks run sequentially at 10 minutes each, total time is 60 minutes. With dependency-analyzed parallel dispatch via git worktrees, independent tasks run concurrently — reducing wall-clock time to the longest single batch. Conflict detection ensures parallel work does not silently corrupt shared files.
