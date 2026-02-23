# wicked-product

Turn vague ideas into testable acceptance criteria, catch WCAG violations before release, and aggregate customer feedback across every channel into prioritized recommendations — all from one plugin with product managers, UX designers, researchers, and strategists.

## Quick Start

```bash
# Install
claude plugin install wicked-product@wicked-garden

# Turn a rough idea into requirements
/wicked-product:elicit outcome.md

# Review UX and accessibility
/wicked-product:ux-review src/components/ --focus a11y
```

## Workflows

### From Idea to Testable Acceptance Criteria

A product manager drops a two-paragraph brief. The elicit → acceptance pipeline turns it into something engineers can actually build to:

```bash
# Step 1: Elicit requirements from the outcome doc
/wicked-product:elicit phases/clarify/outcome.md
```

Output:
```
Requirements elicited: 8 user stories

US-01: As a registered user, I can reset my password via email link
  Acceptance criteria (draft):
    Given a valid email address
    When I submit the "Forgot Password" form
    Then I receive an email within 2 minutes
    And the link expires after 24 hours
    And using the link once invalidates it

US-02: As a user with an expired session...
[6 more stories]

Gaps identified: 3 edge cases not covered in the brief
  → What happens if email is not found?
  → Password complexity requirements not specified
  → Rate limiting on reset attempts?
```

```bash
# Step 2: Define testable acceptance criteria
/wicked-product:acceptance --feature "user-authentication"

# Step 3: Align stakeholders on approach
/wicked-product:align requirements.md
```

### Customer Voice Pipeline

Three months of support tickets, NPS surveys, and sales call notes. The listen → analyze → synthesize pipeline extracts what users actually want:

```bash
/wicked-product:listen --days 90
```

Output:
```
Feedback aggregated: 847 items across 4 sources
  Support tickets: 412  |  NPS surveys: 203  |  App reviews: 187  |  Sales notes: 45

Top themes by volume:
  1. Export functionality (156 mentions, trending up 23% vs prior period)
  2. Mobile performance (98 mentions)
  3. Onboarding confusion (87 mentions)
```

```bash
/wicked-product:analyze --theme "export"
```

Output:
```
Theme: Export functionality

Sentiment: 71% negative (frustrated by current limitations)
Pain points:
  → CSV export truncates at 10,000 rows (42 explicit mentions)
  → No bulk export option (38 mentions)
  → Excel format requested by enterprise users (29 mentions)

User segments most affected: Enterprise accounts (68% of mentions)
Revenue at risk: $340K ARR from churned/at-risk accounts citing export
```

```bash
/wicked-product:synthesize --priority high
```

Output:
```
Recommendation: Export Overhaul (Priority: P0)

Hypothesis: Removing the 10K row cap and adding bulk export reduces enterprise churn by 15%
Effort estimate: M (2-3 sprints)
Success metric: Export-related support tickets < 20/month (from current 52/month)

Suggested acceptance criteria:
  - Export up to 1M rows without truncation
  - Bulk export: select multiple reports, download as ZIP
  - Excel (.xlsx) format option for all exports
```

### Pre-Release Accessibility Audit

Before shipping a new form component:

```bash
/wicked-product:ux-review src/components/CheckoutForm --focus a11y
```

Output:
```
Accessibility Audit: CheckoutForm

WCAG 2.1 AA Violations (3)

  FAIL [1.4.3 Contrast Ratio]
  src/components/CheckoutForm/styles.css:34
  Text color #767676 on #FFFFFF = 4.48:1 (required: 4.5:1 for normal text)
  Fix: Use #757575 or darker

  FAIL [2.4.7 Focus Visible]
  src/components/CheckoutForm/CreditCardInput.jsx:89
  Custom input removes default focus ring without replacement
  Fix: Add outline: 2px solid #0066CC on :focus

  FAIL [4.1.2 Name, Role, Value]
  src/components/CheckoutForm/ExpiryField.jsx:23
  Input missing aria-label (visual label not associated programmatically)
  Fix: Add htmlFor to <label> matching input id

Passing: 12 of 15 WCAG 2.1 AA criteria
Keyboard navigation: All fields reachable, tab order logical
Screen reader: 2 minor issues flagged (non-blocking)
```

### Strategic Business Analysis

Before committing engineering resources to a proposal:

```bash
/wicked-product:strategy proposal.md --focus roi
```

The business-strategist agent assesses ROI, market opportunity, competitive position, and risks — returning a structured recommendation with assumptions made explicit.

## Commands

### Customer Voice Pipeline

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-product:listen` | Aggregate customer feedback from all sources | `/wicked-product:listen --days 30` |
| `/wicked-product:analyze` | Analyze feedback for themes, sentiment, and trends | `/wicked-product:analyze --theme "performance"` |
| `/wicked-product:synthesize` | Generate prioritized recommendations from insights | `/wicked-product:synthesize --priority high` |

### Requirements and Alignment

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-product:elicit` | Extract requirements and write user stories | `/wicked-product:elicit outcome.md` |
| `/wicked-product:acceptance` | Define testable acceptance criteria | `/wicked-product:acceptance --feature "user-login"` |
| `/wicked-product:align` | Facilitate stakeholder alignment | `/wicked-product:align requirements.md` |

### UX and Design

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-product:ux-review` | UX, UI, and accessibility review | `/wicked-product:ux-review src/app/ --focus a11y` |

Focus areas: `flows`, `ui`, `a11y`, `research`, `all`

### Strategy

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-product:strategy` | Strategic business analysis | `/wicked-product:strategy proposal.md --focus roi` |

Focus areas: `roi`, `value`, `market`, `competitive`, `all`

## Agents

### Product Domain

| Agent | Focus |
|-------|-------|
| `product-manager` | Roadmap, prioritization, feature trade-offs |
| `requirements-analyst` | User stories, acceptance criteria |
| `alignment-lead` | Stakeholder consensus and conflict resolution |

### UX Domain

| Agent | Focus |
|-------|-------|
| `ux-designer` | User flows, interaction patterns |
| `ui-reviewer` | Visual consistency, design systems |
| `user-researcher` | Personas, journey mapping |
| `a11y-expert` | WCAG compliance, keyboard navigation, screen readers |

### Customer Voice

| Agent | Focus |
|-------|-------|
| `customer-advocate` | Customer empathy, pain point articulation |
| `feedback-analyst` | Sentiment analysis, theme extraction, trend detection |

### Strategy

| Agent | Focus |
|-------|-------|
| `business-strategist` | ROI analysis, business alignment |
| `market-analyst` | Market sizing, trend analysis |
| `competitive-analyst` | SWOT, competitive positioning |
| `value-analyst` | Value proposition design |

## Skills

| Skill | What It Does |
|-------|-------------|
| `requirements-analysis` | Requirements elicitation methodology and user story patterns |
| `acceptance-criteria` | Writing testable, unambiguous acceptance criteria |
| `ux-review` | UX evaluation frameworks and heuristics |
| `accessibility` | WCAG 2.1 AA/AAA compliance patterns |
| `listen` | Customer feedback aggregation across sources |
| `analyze` | Feedback theme extraction and sentiment analysis |
| `synthesize` | Prioritized recommendation generation |
| `design-review` | Design quality and consistency review |
| `product-management` | Prioritization frameworks and roadmap thinking |
| `strategy` | Strategic analysis and business case development |

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-crew | Auto-engaged in clarify, design, and review phases | Use commands directly |
| wicked-kanban | Requirement traceability — user stories tracked as persistent tasks | No cross-session task tracking |
| wicked-mem | Cross-session learning from past requirements and feedback cycles | Context lost between sessions |
| wicked-workbench | Visual dashboards for feedback themes and roadmap status | Text output only |

## License

MIT
