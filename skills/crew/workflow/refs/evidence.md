# Evidence Tracking

Crew gate decisions and phase artifacts are tracked as evidence to support
auditability and quality assurance across the workflow lifecycle.

## Evidence Tiers

| Tier | Name | Description | Example |
|------|------|-------------|---------|
| L1 | Assertion | Agent states a conclusion | "No security risks found" |
| L2 | Reference | Points to specific artifact | "See `tests/auth.test.ts` lines 42-68" |
| L3 | Artifact | Produces a reviewable output | Test results, review checklist, diff |
| L4 | Verified | Independent confirmation | Second agent validates L3 artifact |

Gates require minimum evidence tiers based on phase:
- **Clarify/Design gates**: L1 sufficient (assertions with rationale)
- **Build gates**: L2 minimum (references to changed files, test coverage)
- **Test/Review gates**: L3 minimum (test output, review report artifacts)

## Artifact Naming

Evidence artifacts follow the convention:

```
{phase}-{type}-{timestamp}.{ext}
```

Examples:
- `build-test-results-20260301T1420.json`
- `review-checklist-20260301T1430.md`
- `design-architecture-decision-20260301T1400.md`

## Collection Methods

### Automatic Evidence

The crew workflow automatically captures:
- **Task completion records**: TaskUpdate status transitions with timestamps
- **Gate decisions**: Pass/fail with reasoning from gate agents
- **Phase artifacts**: Files created or modified during each phase
- **Specialist dispatches**: Which agents were engaged and their outputs

### Manual Evidence

Agents can explicitly record evidence via:
- Gate reports in phase status files (`phases/{phase}/status.md`)
- Inline references in task descriptions linking to files or test output
- Review checklists produced by reviewer agents

## Accessing Evidence

Use `/wicked-garden:crew:evidence` to view evidence collected for the
current project or a specific task. Evidence is stored alongside the
crew project data and persists via StorageManager.
