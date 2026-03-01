---
name: autonomous-assumptions
title: Just-Finish Autonomous Assumptions
description: Verify just-finish mode completes without stopping and documents all assumptions
type: workflow
difficulty: intermediate
estimated_minutes: 15
---

# Just-Finish Autonomous Assumptions

This scenario validates that `/wicked-crew:just-finish` completes autonomously without stopping for clarification, making reasonable assumptions and documenting them at the end. The key behavior: just-finish should FINISH, not stop at clarify to ask questions.

## Setup

Create a project with an intentionally vague description that would normally trigger clarification questions:

```bash
# Create test project
/wicked-crew:start "Improve the search results page"
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
/wicked-crew:just-finish
```

### 2. Verify clarify phase completes without questions

Expected:
1. Clarify phase proceeds WITHOUT asking the user for input
2. Makes reasonable assumptions about scope, approach, and priorities
3. Documents assumptions in the phase deliverables (objective.md, acceptance-criteria.md)
4. Advances to build phase automatically

### 3. Verify assumptions are tracked in project.json

```bash
cat ~/.something-wicked/wicked-garden/local/wicked-crew/projects/improve-search-results-page/project.json | python3 -m json.tool
```

Expected:
1. `project.json` contains an `assumptions` array
2. Each assumption has `phase`, `assumption`, and `reason` fields
3. At least 2-3 assumptions from the clarify phase

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
- [ ] project.json contains `assumptions` array during execution
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
