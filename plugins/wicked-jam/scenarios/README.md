# wicked-jam Test Scenarios

This directory contains real-world test scenarios that demonstrate wicked-jam's functionality and value.

## Overview

These scenarios are designed to:
- **Prove functionality**: Verify wicked-jam works as documented
- **Demonstrate value**: Show why someone would actually use this plugin
- **Provide examples**: Serve as usage templates for real work

## Scenarios

| Scenario | Type | Difficulty | Time | Focus |
|----------|------|------------|------|-------|
| [Architecture Decision](01-architecture-decision.md) | Workflow | Intermediate | 10 min | Multi-round brainstorming for technical decisions |
| [Product Feedback](02-product-feedback.md) | Feature | Basic | 8 min | `/perspectives` vs `/brainstorm` modes |
| [Refactoring Strategy](03-refactoring-strategy.md) | Workflow | Advanced | 12 min | Custom personas, complex tradeoffs |
| [Integration with wicked-mem](04-integration-with-wicked-mem.md) | Integration | Intermediate | 15 min | Context recall and insight storage |

## Running Scenarios

Each scenario is self-contained:

1. **Setup**: Creates realistic test data
2. **Steps**: Specific commands to run
3. **Success Criteria**: Checkboxes to verify functionality
4. **Value Demonstrated**: Why this matters in real work

### Example: Running Architecture Decision

```bash
# Navigate to scenario
cd ~/test-wicked-jam

# Follow setup steps from scenario
mkdir -p architecture-decisions
cd architecture-decisions

# Run the commands listed in the scenario
/wicked-jam:brainstorm "caching strategy for social media API..."

# Check success criteria in the output
```

## Scenario Types

- **Workflow**: End-to-end usage patterns
- **Feature**: Specific capability tests
- **Integration**: Cross-plugin functionality

## Success Criteria Format

Each scenario includes verifiable checkboxes:
- [ ] Objective criteria you can check in output
- [ ] No subjective "quality" judgments
- [ ] Focused on functional correctness

## Value Demonstration

Every scenario articulates **real-world value**:
- What problem does this solve?
- What does this replace or improve?
- Why would someone actually use this?

This helps evaluate not just "does it work?" but "is it worth using?"

## Using Scenarios for Development

If modifying wicked-jam:

1. Run scenarios before changes (baseline)
2. Make your modifications
3. Run scenarios after changes (regression check)
4. Update scenarios if behavior intentionally changed

## Adding New Scenarios

When adding scenarios, follow the template:

```markdown
---
name: kebab-case-name
title: Human Readable Title
description: One-line description
type: workflow|integration|feature
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

These scenarios follow the principle: **test what users actually do, not toy examples.**

A good scenario:
- Solves a real problem someone would have
- Uses realistic data and context
- Demonstrates clear value
- Can be completed independently

A bad scenario:
- Tests contrived examples
- Requires extensive setup
- Unclear why anyone would do this
- No obvious value demonstrated
