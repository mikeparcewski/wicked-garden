# Requirements Output Format: Templates

Standard format template and minimal format for documenting requirements analysis results.

## Overview

This document defines the expected output structure when conducting requirements analysis. The format ensures:
- Consistency across projects
- Complete traceability
- Clear handoff to design and QE
- Integration with native tasks (TaskCreate/TaskUpdate) and wicked-garden:mem

## Standard Output Structure

```markdown
# Requirements Analysis: {Project/Feature Name}

**Date**: {YYYY-MM-DD}
**Analyzed By**: {Name/Role}
**Stakeholders**: {Comma-separated list}
**Status**: {Draft/Review/Approved}

## Executive Summary

{2-3 sentence overview of what is being built and why}

## Context

### Business Goals
- {Goal 1}
- {Goal 2}

### User Needs
- {Need 1}
- {Need 2}

### Constraints
- {Constraint 1: technical, timeline, budget, etc.}
- {Constraint 2}

## Personas

### {Persona 1 Name}
- **Role**: {Title/Description}
- **Goals**: {What they want to achieve}
- **Pain Points**: {Current problems}
- **Technical Proficiency**: {Low/Medium/High}

### {Persona 2 Name}
- **Role**: {Title/Description}
- **Goals**: {What they want to achieve}
- **Pain Points**: {Current problems}
- **Technical Proficiency**: {Low/Medium/High}

## User Stories

### US-{ID}: {Story Title}

**As a** {persona}
**I want** {capability}
**So that** {benefit}

**Priority**: {P0/P1/P2/P3}
**Complexity**: {S/M/L/XL}

**Acceptance Criteria**:
1. Given {context}, When {action}, Then {outcome}
2. Given {error condition}, When {action}, Then {error handling}
3. Given {edge case}, When {action}, Then {graceful behavior}

**Dependencies**: {List of dependencies}
**Assumptions**: {List of assumptions}
**Open Questions**: {List of questions}

{Repeat for each user story}

## Functional Requirements

### {Feature Area 1}
1. **REQ-{ID}**: {Requirement description}
   - **Rationale**: {Why this is needed}
   - **Acceptance**: {How to verify}
   - **Priority**: {P0/P1/P2/P3}

### {Feature Area 2}
{Repeat structure}

## Non-Functional Requirements

### Performance
- **REQ-PERF-{ID}**: {Performance requirement}
  - Target: {Metric and threshold}
  - Measured by: {How to measure}

### Security
- **REQ-SEC-{ID}**: {Security requirement}
  - Compliance: {Standards/regulations}
  - Verification: {How to verify}

### Scalability
- **REQ-SCALE-{ID}**: {Scalability requirement}
  - Target: {Growth expectations}
  - Strategy: {How to achieve}

### Usability
- **REQ-UX-{ID}**: {Usability requirement}
  - Standard: {WCAG, mobile-first, etc.}
  - Verification: {User testing, automated checks}

## Scope Definition

### In Scope
- {Feature/capability 1}
- {Feature/capability 2}

### Out of Scope
- {Explicitly excluded item 1}
- {Explicitly excluded item 2}

### Future Considerations
- {Nice-to-have for future releases}

## Dependencies

### Internal
- {Team/system dependency}
- {Prerequisite work}

### External
- {Third-party service}
- {External API}

## Assumptions

1. {Assumption 1}
2. {Assumption 2}

## Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| {Risk description} | {H/M/L} | {H/M/L} | {Mitigation strategy} |

## Open Questions

- [ ] {Question requiring stakeholder input}
- [ ] {Technical decision needed}
- [ ] {Clarification needed}

## Traceability

- **Source Document**: {Link to original brief/request}
- **Design Phase**: {Link to phases/design/}
- **Test Scenarios**: {Link to phases/qe/}
- **Tasks**: {Native task IDs or initiative name}
- **Memory**: {wicked-garden:mem tags for recall}

## Appendices

### A. Glossary
- **{Term}**: {Definition}

### B. References
- {Document/URL}

### C. Revision History
| Date | Author | Changes |
|------|--------|---------|
| {YYYY-MM-DD} | {Name} | {Description} |
```

## Minimal Output Format

For smaller features or rapid analysis:

```markdown
# Requirements: {Feature Name}

## Summary
{1-2 sentence description}

## User Stories

### US-001: {Title}
**As a** {persona}
**I want** {capability}
**So that** {benefit}

**Acceptance Criteria**:
1. Given {context}, When {action}, Then {outcome}

{Repeat for 3-5 core stories}

## Out of Scope
- {Excluded item}

## Open Questions
- [ ] {Question}
```

## Validation Checklist

Before finalizing requirements document:

- [ ] All user stories have persona, capability, benefit
- [ ] All stories have at least 3 acceptance criteria
- [ ] Scope clearly defined (in scope, out of scope)
- [ ] Dependencies documented
- [ ] Open questions captured
- [ ] Traceability links included
- [ ] Non-functional requirements addressed
- [ ] Stakeholders identified
- [ ] Risks assessed

## Output Delivery

Requirements should be saved to:
- `phases/requirements/analysis.md` (in project workflow)
- `requirements.md` (standalone project)
- Linked from `outcome.md`
- Referenced in native task metadata (initiative field)

## Templates

### Quick Start Template
```bash
# Copy minimal template for new requirements
cp "${CLAUDE_PLUGIN_ROOT}/templates/requirements-minimal.md" \
   requirements.md
```

### Full Template
```bash
# Copy full template for comprehensive analysis
cp "${CLAUDE_PLUGIN_ROOT}/templates/requirements-full.md" \
   requirements.md
```

## Resources

- **User Story Guide**: `refs/user-story-guide.md`
- **Acceptance Criteria**: See product-management skill
- **Example Projects**: Search wicked-garden:mem for "requirements-example"
