# wicked-crew Phase Definition of Done (DoD)

Clear completion criteria for each phase gate.

## Architecture Note (v2)

As of v2, wicked-crew supports **pluggable phase providers**. This document describes:
- Gate enforcement mechanism (applies to all workflows)
- Classic workflow DoD (default phase sequence)
- Provider-defined DoD (custom phases)

See also:
- `PHASE-PROVIDER.md` - Phase provider contract
- `WORKFLOW-TEMPLATES.md` - Workflow template definitions

---

## Gate Enforcement

### Gate Types

| Type | Behavior | Use Case |
|------|----------|----------|
| `blocking` | Must pass to proceed | Critical phases (build, security) |
| `advisory` | Can proceed with warning | Optional phases (research) |

### Approval Modes

| Mode | Behavior | Trigger |
|------|----------|---------|
| `explicit` | User must `/approve` | Default for blocking gates |
| `automatic` | Pass if criteria met | Advisory gates, CI pipelines |

### Gate Evaluation

```
Phase completes work
        ↓
Crew checks gate criteria
        ↓
┌─────────────────┐
│ All criteria met?│
└────────┬────────┘
         │
    Yes ─┼─ No
         │    │
         ↓    ↓
   ┌─────────┐  ┌──────────────┐
   │Pass gate│  │Gate BLOCKED  │
   └────┬────┘  │List failures │
        │       └──────────────┘
        ↓
┌────────────────┐
│Approval mode?  │
└───────┬────────┘
        │
 explicit / automatic
        │         │
        ↓         ↓
  Wait for     Auto-advance
  /approve     to next phase
```

### Gate Criteria Sources

1. **Phase Provider** - `phase.json` defines gate criteria
2. **Workflow Template** - Template can override gate type/approval
3. **User Override** - `/approve --force` bypasses blocking (with warning)

---

## Classic Workflow DoD

The classic workflow is the default: `clarify → design → qe → build → review → done`

Each phase requires:
1. All deliverables complete
2. DoD criteria met
3. Explicit approval via `/wicked-crew:approve`

---

## Clarify Phase

**Goal**: Define what success looks like

### Deliverables

| Artifact | Location | Required |
|----------|----------|----------|
| Outcome statement | `outcome.md` | Yes |
| Success criteria | `outcome.md` | Yes |
| Scope boundaries | `outcome.md` | Yes |
| Phase status | `phases/clarify/status.md` | Yes |

### Definition of Done

- [ ] **Outcome statement** is specific and measurable
- [ ] **Success criteria** are verifiable (can answer "is this done?")
- [ ] **In-scope** items are explicit
- [ ] **Out-of-scope** items are documented
- [ ] **Assumptions** are listed
- [ ] **Risks** are identified (if any)

### Jam Detection Trigger

Clarify should trigger `/wicked-jam:brainstorm` when:
- User description contains question marks (ambiguity)
- "Either/or" or "maybe" language (alternatives)
- Word count > 100 (complexity)
- Multiple stakeholders mentioned (alignment needed)
- Vague success criteria ("make it better")
- No clear measurable outcome

**Decision**: Err on side of suggesting jam (accept false positives).

### Approval Criteria

```markdown
## Clarify Phase Approval

### Checklist
- [ ] Outcome answers: "What does success look like?"
- [ ] Success criteria are testable
- [ ] Scope is clear (no ambiguity about what's included)
- [ ] Team alignment confirmed (if multi-stakeholder)

**Ready to advance to Design?** (Y/n)
```

---

## Design Phase

**Goal**: Research and architect the solution

### Deliverables

| Artifact | Location | Required |
|----------|----------|----------|
| Architecture doc | `phases/design/architecture.md` | Yes |
| Technical approach | `phases/design/approach.md` | Yes |
| Pattern identification | `phases/design/patterns.md` | If applicable |
| Research findings | `phases/design/research.md` | If research done |
| Phase status | `phases/design/status.md` | Yes |

### Definition of Done

- [ ] **Architecture** addresses all success criteria
- [ ] **Technical approach** is specific enough to implement
- [ ] **Existing patterns** in codebase identified and documented
- [ ] **Dependencies** are identified
- [ ] **Risks** have mitigation strategies
- [ ] **Alternatives considered** (at least briefly)

### Integration Points

| Plugin | Usage |
|--------|-------|
| wicked-search | Research codebase patterns |
| wicked-jam | Explore alternatives (if needed) |

### Approval Criteria

```markdown
## Design Phase Approval

### Checklist
- [ ] Architecture maps to outcome requirements
- [ ] Technical approach is implementable
- [ ] No major unknowns remain
- [ ] Dependencies are available/planned

**Ready to advance to QE?** (Y/n)
```

---

## QE Phase (Quality Engineering)

**Goal**: Define test strategy BEFORE building (shift-left)

### Deliverables

| Artifact | Location | Required |
|----------|----------|----------|
| Test strategy | `phases/qe/strategy.md` | Yes |
| Test scenarios | `phases/qe/scenarios.md` | Yes |
| Acceptance criteria | `phases/qe/acceptance.md` | Yes |
| Edge cases | `phases/qe/edge-cases.md` | Yes |
| Risk assessment | `phases/qe/risks.md` | If applicable |
| Phase status | `phases/qe/status.md` | Yes |

### Definition of Done

- [ ] **Happy path** scenarios documented
- [ ] **Error cases** identified
- [ ] **Edge cases** enumerated
- [ ] **Acceptance criteria** map to success criteria
- [ ] **Test approach** defined (unit, integration, e2e)
- [ ] **Security considerations** addressed (if applicable)

### Integration Points

| Plugin | Usage |
|--------|-------|
| wicked-qe | Generate test scenarios, risk assessment |
| wicked-product | QE perspective review |

### Approval Criteria

```markdown
## QE Phase Approval

### Checklist
- [ ] All success criteria have test scenarios
- [ ] Edge cases covered
- [ ] Error handling defined
- [ ] Security reviewed (if applicable)

**Ready to advance to Build?** (Y/n)
```

---

## Build Phase

**Goal**: Implement the solution

### Deliverables

| Artifact | Location | Required |
|----------|----------|----------|
| Implementation | Source files | Yes |
| Tests | Test files | Yes |
| Progress tracking | Kanban board or `phases/build/tasks/` | Yes |
| Documentation tasks | Created/linked | If patterns detected |
| Phase status | `phases/build/status.md` | Yes |

### Definition of Done

- [ ] **Implementation** complete per design
- [ ] **Tests** pass (unit, integration as defined in QE)
- [ ] **Acceptance criteria** met (from QE phase)
- [ ] **No regressions** introduced
- [ ] **Build succeeds** (if applicable)
- [ ] **Lint/format** passes
- [ ] **Documentation** tasks created for new APIs/exports

### Parallel Execution

Build phase supports parallel task execution when:
- Tasks have `parallel: true` flag
- Tasks declare non-overlapping `resources`
- No logical dependencies between tasks

Default: Serial execution (conservative)

### Integration Points

| Plugin | Usage |
|--------|-------|
| wicked-kanban | Task tracking, parallel swimlanes |
| wicked-delivery | Progress reporting |
| Fallback | `TodoWrite` + markdown files |

### Events Emitted

```
crew:task:created:success
crew:task:completed:success
crew:file:modified:success
crew:milestone:reached:success
```

### Approval Criteria

```markdown
## Build Phase Approval

### Checklist
- [ ] All tasks complete
- [ ] Tests pass
- [ ] No build errors
- [ ] Documentation tasks created (if applicable)

**Ready to advance to Review?** (Y/n)
```

---

## Review Phase

**Goal**: Multi-perspective validation

### Deliverables

| Artifact | Location | Required |
|----------|----------|----------|
| Review findings | `phases/review/findings.md` | Yes |
| Security review | `phases/review/security.md` | If applicable |
| Recommendations | `phases/review/recommendations.md` | If issues found |
| Sign-off | `phases/review/signoff.md` | Yes |
| Phase status | `phases/review/status.md` | Yes |

### Definition of Done

- [ ] **Code review** completed (dev perspective)
- [ ] **Security review** completed (if applicable)
- [ ] **QE review** confirms test coverage
- [ ] **Product review** confirms requirements met
- [ ] **Critical issues** addressed
- [ ] **Recommendations** documented (even if deferred)

### Integration Points

| Plugin | Usage |
|--------|-------|
| wicked-product | Multi-perspective review |
| wicked-qe | Verify test coverage |
| wicked-delivery | Final status report |

### Approval Criteria

```markdown
## Review Phase Approval

### Checklist
- [ ] All critical issues resolved
- [ ] Non-critical issues documented
- [ ] Stakeholders signed off
- [ ] Ready for release/merge

**Approve and complete project?** (Y/n)
```

---

## Project Completion

After Review phase approval:

1. **Status**: Project marked `complete`
2. **Event**: `crew:project:completed:success` emitted
3. **Report**: Final summary generated (if wicked-delivery available)
4. **Memory**: Key decisions stored (if wicked-mem available)

### Final Checklist

- [ ] All phases approved
- [ ] All success criteria verified
- [ ] Documentation complete
- [ ] Knowledge captured

---

## Naming Convention

| Term | Definition |
|------|------------|
| **Project** | Container for work, typically = repo/folder name |
| **Initiative** | Time-boxed effort within a project (was: sprint) |
| **Phase** | Stage in delivery workflow |
| **Task** | Atomic unit of work |

---

## Quick Reference

| Phase | Key Question | Key Deliverable |
|-------|--------------|-----------------|
| Clarify | What does success look like? | `outcome.md` |
| Design | How will we build it? | `architecture.md` |
| QE | How will we test it? | `scenarios.md` |
| Build | Is it implemented? | Working code + tests |
| Review | Is it ready? | Sign-off |
