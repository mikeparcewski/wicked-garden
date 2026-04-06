# meta.md Templates

Copy-paste templates for each level of the requirements graph.

## Root meta.md

```yaml
---
type: requirements-root
project: {project-name}
created: {YYYY-MM-DD}
status: draft
---

# Requirements: {Project Name}

{1-2 sentence summary of what is being built and why.}

## Areas

| Area | Stories | ACs | P0 ACs | Coverage |
|------|---------|-----|--------|----------|

## Scope
See: [_scope.md](_scope.md)

## Risks
See: [_risks.md](_risks.md)

## Open Questions
See: [_questions.md](_questions.md)
```

## Area meta.md

```yaml
---
id: {area-slug}
type: area
status: draft
tags: [{relevant}, {keywords}]
---

# {Area Name}

{1-2 sentence description of this feature area.}

## Stories

| Story | Title | Priority | ACs | Status |
|-------|-------|----------|-----|--------|

## Non-Functional Requirements

| NFR | Description | Target |
|-----|-------------|--------|

## Coverage
- **Total ACs**: 0
- **With IMPLEMENTED_BY**: 0
- **With TESTED_BY**: 0
```

## Story meta.md

```yaml
---
id: {area}/{US-NNN}
type: user-story
priority: {P0/P1/P2}
complexity: {S/M/L/XL}
persona: {persona-name}
status: draft
tags: [{relevant}, {keywords}]
---

# {US-NNN}: {Story Title}

**As a** {persona}
**I want** {capability}
**So that** {benefit}

## Acceptance Criteria

| AC | Description | Priority | Category |
|----|-------------|----------|----------|

## Dependencies
- {dependency}

## Open Questions
- {question}
```

## _scope.md

```yaml
---
type: scope
---

# Scope

## In Scope
- {item}

## Out of Scope
- {item}

## Future Considerations
- {item}
```

## _risks.md

```yaml
---
type: risks
---

# Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
```

## _questions.md

```yaml
---
type: questions
---

# Open Questions

- [ ] {question needing stakeholder input}
```
