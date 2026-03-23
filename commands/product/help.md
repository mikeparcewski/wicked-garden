---
description: Show available product management commands and usage
---

# /wicked-garden:product:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# product Help

Product management, UX, and design — from requirements through visual review.

## I want to...

### Understand my users
| Command | What It Does |
|---------|-------------|
| `product:listen` | Aggregate customer feedback from available sources |
| `product:analyze` | Analyze feedback for themes, sentiment, and trends |
| `product:synthesize` | Generate actionable recommendations from insights |

### Write requirements
| Command | What It Does |
|---------|-------------|
| `product:elicit` | Elicit requirements through structured discovery |
| `product:acceptance` | Define acceptance criteria from requirements and design |

### Make strategic decisions
| Command | What It Does |
|---------|-------------|
| `product:strategy` | ROI, value proposition, market, competitive analysis |
| `product:align` | Facilitate stakeholder alignment and consensus building |

### Review UX and design
| Command | What It Does |
|---------|-------------|
| `product:ux-review` | UX quality review — user flows, usability, research |
| `product:review` | Visual design review — design system, spacing, typography |
| `product:ux` | UX flow design and information architecture |
| `product:a11y` | WCAG 2.1 AA accessibility audit |
| `product:screenshot` | Screenshot-based UI review using vision |
| `product:mockup` | Generate wireframes and prototypes |

## Quick Start

```
# Start with requirements
/wicked-garden:product:elicit

# Review a UI for accessibility
/wicked-garden:product:a11y ./src/components

# Analyze customer feedback
/wicked-garden:product:listen --days 30
/wicked-garden:product:analyze --sentiment neg
/wicked-garden:product:synthesize --priority high

# Strategic analysis
/wicked-garden:product:strategy "new pricing tier" --focus roi
```

## Integration

- **crew**: Specialist routing for product, UX, and design phases
- **qe**: Acceptance criteria drive test scenarios
- **jam**: Brainstorming for product decisions
- **engineering**: `--persona product` on engineering:review for product lens
```
