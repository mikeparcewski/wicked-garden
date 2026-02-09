# wicked-product

A full product organization in a plugin -- product managers, UX designers, requirements analysts, customer advocates, and business strategists working together. Turn vague ideas into shippable features with acceptance criteria you can test against.

A customer voice pipeline (listen, analyze, synthesize) converts raw feedback into prioritized recommendations. WCAG accessibility audits catch issues before release. Requirements elicitation, UX reviews, customer voice analysis, and business strategy in one install.

## Quick Start

```bash
# Install
claude plugin install wicked-product@wicked-garden

# Turn an idea into requirements
/wicked-product:elicit outcome.md

# Review UX and accessibility
/wicked-product:ux-review src/components/

# Analyze customer feedback
/wicked-product:listen --days 30
/wicked-product:analyze --theme "performance"

# Assess business value
/wicked-product:strategy proposal.md --focus roi
```

## Commands

### Requirements & Alignment

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-product:elicit` | Extract requirements and write user stories | `/wicked-product:elicit outcome.md` |
| `/wicked-product:acceptance` | Define testable acceptance criteria | `/wicked-product:acceptance --feature "user-login"` |
| `/wicked-product:align` | Facilitate stakeholder alignment | `/wicked-product:align requirements.md` |

### Customer Voice

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-product:listen` | Aggregate customer feedback | `/wicked-product:listen --days 30` |
| `/wicked-product:analyze` | Extract themes, sentiment, trends | `/wicked-product:analyze --theme "pricing"` |
| `/wicked-product:synthesize` | Generate actionable recommendations | `/wicked-product:synthesize --priority high` |

### UX & Design

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-product:ux-review` | UX/UI/accessibility review | `/wicked-product:ux-review src/app/ --focus a11y` |

Focus areas: `flows`, `ui`, `a11y`, `research`, `all`

### Strategy

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-product:strategy` | Strategic business analysis | `/wicked-product:strategy proposal.md --focus roi` |

Focus areas: `roi`, `value`, `market`, `competitive`, `all`

## Workflows

### Requirements to Acceptance Criteria

```bash
# 1. Elicit requirements from outcome doc
/wicked-product:elicit phases/clarify/outcome.md

# 2. Define testable acceptance criteria
/wicked-product:acceptance --feature "user-authentication"

# 3. Align stakeholders on approach
/wicked-product:align requirements.md
```

### Customer Voice Pipeline

```bash
# 1. Aggregate feedback
/wicked-product:listen --days 90

# 2. Find recurring themes
/wicked-product:analyze --theme "performance"

# 3. Generate prioritized recommendations
/wicked-product:synthesize --priority high
```

### Pre-Release UX Check

```bash
# Quick accessibility scan
/wicked-product:ux-review src/components --focus a11y

# Full UX review
/wicked-product:ux-review src/app/ --focus all
```

## Agents

### Product Domain
| Agent | Focus |
|-------|-------|
| `product-manager` | Roadmap, prioritization, trade-offs |
| `requirements-analyst` | User stories, acceptance criteria |
| `alignment-lead` | Stakeholder consensus |

### UX Domain
| Agent | Focus |
|-------|-------|
| `ux-designer` | User flows, interaction patterns |
| `ui-reviewer` | Visual consistency, design systems |
| `user-researcher` | Personas, journey mapping |
| `a11y-expert` | WCAG compliance, keyboard navigation |

### Customer Voice
| Agent | Focus |
|-------|-------|
| `customer-advocate` | Customer empathy, pain points |
| `feedback-analyst` | Sentiment, themes, trends |

### Strategy
| Agent | Focus |
|-------|-------|
| `business-strategist` | ROI, business alignment |
| `market-analyst` | Market sizing, trends |
| `competitive-analyst` | SWOT, positioning |
| `value-analyst` | Value proposition design |

## Integration

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-crew | Auto-engaged in clarify/design/review phases | Use commands directly |
| wicked-kanban | Requirement tracking and traceability | No persistent tasks |
| wicked-mem | Cross-session learning | Session-only context |
| wicked-workbench | Visual dashboards | Text output only |

## License

MIT
