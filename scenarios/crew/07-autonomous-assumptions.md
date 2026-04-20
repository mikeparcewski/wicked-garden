---
name: autonomous-assumptions
title: Just-Finish Autonomous Assumptions
description: Verify just-finish mode completes without stopping and documents all assumptions
type: workflow
difficulty: intermediate
estimated_minutes: 15
---

# Just-Finish Autonomous Assumptions

This scenario validates that `/wicked-garden:crew:just-finish` completes autonomously without stopping for clarification, making reasonable assumptions and documenting them at the end. The key behavior: just-finish should FINISH, not stop at clarify to ask questions.

## Setup

Create a project with an intentionally vague description that would normally trigger clarification questions:

```bash
# Create test project
/wicked-garden:crew:start "Improve the search results page"
```

This description is intentionally vague -- it doesn't specify:
- Which search page (there could be multiple)
- What "improve" means (performance? UX? accuracy?)
- What technology stack
- What success metrics

Normally, the clarify phase would ask the user to clarify these. In just-finish mode, it should make assumptions and proceed.

## Steps

### 1. Launch just-finish mode

```bash
/wicked-garden:crew:just-finish
```

### 2. Verify clarify phase completes without questions

Expected:
1. Clarify phase proceeds WITHOUT asking the user for input
2. Makes reasonable assumptions about scope, approach, and priorities
3. Documents assumptions in the phase deliverables (objective.md, acceptance-criteria.md)
4. Advances to build phase automatically

### 3. Verify assumptions are tracked

Assumptions are stored in `project.json` by the just-finish orchestrator. Read them directly from the project file (assumptions bypass the status summary):

```bash
Run: python3 -c "
import json, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from _paths import get_local_path
proj_root = get_local_path('wicked-crew', 'projects')
# find the improve-the-search-results-page project dir (name prefix match)
import pathlib
matches = [p for p in proj_root.iterdir() if 'improve-the-search-results-page' in p.name or 'improve' in p.name]
if not matches:
    print('ERROR: project directory not found under', proj_root)
    sys.exit(1)
proj_dir = matches[0]
with open(proj_dir / 'project.json') as f:
    d = json.load(f)
assumptions = d.get('assumptions', [])
print(f'{len(assumptions)} assumption(s) tracked')
for a in assumptions:
    print(f'  - [{a[\"phase\"]}] {a[\"assumption\"]}')
"
Assert: "2 assumption(s) tracked" or more, each with phase and assumption fields
```

Expected:
1. At least 2-3 assumptions logged from the clarify phase
2. Each assumption has `phase`, `assumption`, and `reason` fields
3. Output lists the assumptions with their phase context

### 4. Verify completion includes assumptions appendix

When the project completes, the final output should include:

```markdown
### Assumptions Made

- **Clarify**: {list of assumptions}
- **Build**: {list of assumptions}
- **Review**: {list of assumptions}
```

### 5. Verify smaht context gathered (if available)

Expected:
1. wicked-smaht context_package.py called before phase work
2. Context package included in subagent Task() dispatches
3. Graceful degradation if smaht not installed

### 6. Verify orchestrator-only behavior

Expected:
1. Main agent does NOT perform complex analysis inline
2. All processing delegated via Task() dispatches
3. Main agent only reads state, routes, dispatches, tracks, reports

## Expected Outcome

### Autonomous completion
- All phases complete without user intervention
- No clarification questions asked
- Reasonable assumptions made based on available context

### Assumptions documented
- project.json tracks assumptions as they're made
- Final output includes full assumptions appendix
- Each assumption explains what was assumed and why

### Context-enriched
- smaht context gathered at phase start (if available)
- Specialists receive structured context packages
- Main agent stays lean as orchestrator

## Success Criteria

### Core Behavior
- [ ] Just-finish completes all phases without stopping for clarification
- [ ] Clarify phase makes assumptions instead of asking questions
- [ ] Assumptions are reasonable given the vague description

### Assumption Tracking
- [ ] project.json contains assumptions array populated during execution
- [ ] Each assumption has phase, assumption, and reason fields
- [ ] Final output includes "Assumptions Made" appendix

### Orchestrator Pattern
- [ ] Main agent does not perform complex inline work
- [ ] All processing delegated to subagents
- [ ] Context managed through tools (TaskList, Read, etc.)

### Integration
- [ ] smaht context gathered if available
- [ ] Archetype pre-analysis runs before signal analysis
- [ ] Graceful degradation without optional plugins

## Value Demonstrated

Users invoke just-finish because they want autonomous completion. Stopping at clarify to ask questions defeats the purpose -- it's the opposite of "just finish." By making reasonable assumptions and documenting them transparently at the end, crew delivers results while maintaining accountability. Users can review assumptions post-hoc and course-correct if needed, which is faster than blocking on clarification upfront.

## Cleanup

```bash
/wicked-garden:crew:archive improve-the-search-results-page
```
