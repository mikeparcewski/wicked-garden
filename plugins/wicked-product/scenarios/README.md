# wicked-product Test Scenarios

This directory contains real-world test scenarios that demonstrate wicked-product's functionality and value across its four capability domains: Requirements, Customer Voice, UX/Design, and Strategy.

## Overview

These scenarios are designed to:
- **Prove functionality**: Verify wicked-product works as documented
- **Demonstrate value**: Show why product teams would actually use this plugin
- **Provide examples**: Serve as usage templates for real work
- **Cover domains**: Test all major capability areas

## Scenarios

| Scenario | Domain | Type | Difficulty | Time | Commands Tested |
|----------|--------|------|------------|------|-----------------|
| [Requirements Elicitation](01-requirements-elicitation.md) | Requirements | requirements | Basic | 10 min | `/elicit` |
| [Customer Voice Analysis](02-customer-voice-analysis.md) | Customer Voice | research | Intermediate | 12 min | `/listen`, `/analyze`, `/synthesize` |
| [Accessibility Audit](03-accessibility-audit.md) | UX/Design | ux | Intermediate | 10 min | `/ux-review --focus a11y` |
| [Strategic Investment Analysis](04-strategic-investment-analysis.md) | Strategy | strategy | Advanced | 15 min | `/strategy --focus all` |
| [Stakeholder Alignment](05-stakeholder-alignment.md) | Requirements | requirements | Advanced | 12 min | `/align` |
| [UX Flow Review](06-ux-flow-review.md) | UX/Design | ux | Intermediate | 10 min | `/ux-review --focus flows` |

## Domain Coverage

### Requirements & Alignment
- **Scenario 1**: Transform vague briefs into testable user stories
- **Scenario 5**: Surface and resolve cross-functional conflicts

### Customer Voice
- **Scenario 2**: Full listen -> analyze -> synthesize workflow

### UX & Design
- **Scenario 3**: WCAG accessibility auditing
- **Scenario 6**: User flow and interaction pattern review

### Strategy
- **Scenario 4**: ROI analysis for major technical investments

## Running Scenarios

Each scenario is self-contained:

1. **Setup**: Creates realistic test data (code, documents, feedback)
2. **Steps**: Specific commands to run with expected outcomes
3. **Success Criteria**: Checkboxes to verify functionality
4. **Value Demonstrated**: Why this matters in real work

### Example: Running Customer Voice Analysis

```bash
# Navigate to scenario
cd ~/test-wicked-product

# Follow setup steps from scenario
mkdir -p customer-voice/feedback
# ... create feedback files per scenario

# Run the commands listed in the scenario
/wicked-product:listen feedback/
/wicked-product:analyze --theme "performance"
/wicked-product:synthesize --priority high

# Check success criteria in the output
```

## Scenario Types

- **requirements**: Requirements gathering, user stories, stakeholder alignment
- **research**: Customer feedback analysis, market research
- **ux**: User experience review, accessibility, design patterns
- **strategy**: Business analysis, ROI, competitive assessment

## Difficulty Levels

| Level | Description | Typical Time | Complexity |
|-------|-------------|--------------|------------|
| Basic | Single command, straightforward | 5-10 min | Simple setup |
| Intermediate | Multi-step workflow, real code | 10-12 min | Multiple commands |
| Advanced | Complex analysis, cross-domain | 12-15 min | Rich context |

## Success Criteria Format

Each scenario includes verifiable checkboxes:
- [ ] Objective criteria you can check in output
- [ ] No subjective "quality" judgments
- [ ] Focused on functional correctness

## Value Demonstration

Every scenario articulates **real-world value**:
- What problem does this solve?
- What does this replace or improve?
- Why would a product team actually use this?

This helps evaluate not just "does it work?" but "is it worth using?"

## Using Scenarios for Development

If modifying wicked-product:

1. Run scenarios before changes (baseline)
2. Make your modifications
3. Run scenarios after changes (regression check)
4. Update scenarios if behavior intentionally changed

## Adding New Scenarios

When adding scenarios, follow the template:

```yaml
---
name: kebab-case-name
title: Human Readable Title
description: One-line description
type: requirements|research|ux|strategy
difficulty: basic|intermediate|advanced
estimated_minutes: N
---

# Title

## Setup
Realistic test data creation

## Steps
1. Specific commands to run
2. Expected outcomes

## Expected Outcome
What should happen overall

## Success Criteria
- [ ] Verifiable checkboxes

## Value Demonstrated
Why this matters in real work
```

## Philosophy

These scenarios follow the principle: **test what product teams actually do, not toy examples.**

A good scenario:
- Solves a real problem a PM/UX designer would have
- Uses realistic data and context
- Demonstrates clear value
- Can be completed independently

A bad scenario:
- Tests contrived examples
- Requires extensive setup
- Unclear why anyone would do this
- No obvious value demonstrated

## Integration Testing

Several scenarios can be combined to test cross-domain workflows:

1. **Full Product Cycle**: Scenario 1 (requirements) -> Scenario 5 (alignment) -> Scenario 4 (strategy approval)
2. **Customer-Driven Development**: Scenario 2 (customer voice) -> Scenario 1 (requirements from feedback)
3. **Pre-Release Review**: Scenario 3 (a11y) + Scenario 6 (flows) for comprehensive UX validation

## Relationship to wicked-crew

When used with wicked-crew, these capabilities integrate into the workflow:

| Crew Phase | wicked-product Command | Scenario |
|------------|------------------------|----------|
| Clarify | `/elicit`, `/align` | 1, 5 |
| Design | `/ux-review --focus flows` | 6 |
| QE | `/ux-review --focus a11y` | 3 |
| Build | Customer voice for validation | 2 |
| Review | `/strategy` for sign-off | 4 |
