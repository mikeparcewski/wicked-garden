---
description: Show available product management commands and usage
---

# /wicked-garden:product:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-product Help

Product management and UX — requirements elicitation, customer feedback analysis, stakeholder alignment, strategy, and UX review.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:product:elicit` | Elicit and document requirements through structured discovery |
| `/wicked-garden:product:acceptance <path>` | Define acceptance criteria from requirements and design |
| `/wicked-garden:product:listen` | Aggregate customer feedback from available sources |
| `/wicked-garden:product:analyze` | Analyze customer feedback for themes, sentiment, and trends |
| `/wicked-garden:product:synthesize` | Generate actionable recommendations from feedback insights |
| `/wicked-garden:product:strategy <target>` | Strategic analysis — ROI, value proposition, market, competitive |
| `/wicked-garden:product:align` | Facilitate stakeholder alignment and consensus building |
| `/wicked-garden:product:ux-review <target>` | UX and design quality review — flows, UI, accessibility |
| `/wicked-garden:product:help` | This help message |

## Quick Start

```
/wicked-garden:product:elicit
/wicked-garden:product:ux-review ./screens --focus a11y
/wicked-garden:product:strategy "new pricing tier" --focus roi
```

## Examples

### Requirements
```
/wicked-garden:product:elicit
/wicked-garden:product:acceptance ./design.md --format gherkin --scenarios
```

### Customer Feedback Pipeline
```
/wicked-garden:product:listen --days 30
/wicked-garden:product:analyze --sentiment neg
/wicked-garden:product:synthesize --priority high --format detailed
```

### Strategy
```
/wicked-garden:product:strategy "mobile app" --focus market
/wicked-garden:product:strategy "enterprise plan" --focus competitive
```

### UX Review
```
/wicked-garden:product:ux-review ./app --focus flows
/wicked-garden:product:ux-review ./components --quick
```

## Integration

- **wicked-crew**: Specialist routing for product and UX phases
- **wicked-qe**: Acceptance criteria drive test scenarios
- **wicked-delivery**: Strategic alignment for delivery priorities
- **wicked-jam**: Brainstorming for product decisions
```
