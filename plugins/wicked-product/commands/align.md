---
description: Facilitate stakeholder alignment and consensus building
---

# /wicked-product:align

Facilitate stakeholder alignment, surface concerns, and build consensus.

## Usage

```bash
# Analyze alignment on requirements
/wicked-product:align requirements.md

# Specific stakeholder analysis
/wicked-product:align --stakeholders "eng,qe,ops,support"

# Trade-off facilitation
/wicked-product:align --focus tradeoffs

# Conflict resolution
/wicked-product:align --conflict "scope vs timeline"
```

## Parameters

- **target** (optional): Document to analyze for alignment
- **--stakeholders**: Comma-separated stakeholder groups
- **--focus**: What to focus on (concerns, tradeoffs, conflicts)
- **--conflict**: Specific conflict to mediate
- **--output**: Where to save (default: console + kanban)

## Process

1. **Read Context**: Parse target document and parameters
2. **Dispatch to Alignment Lead**: Analyze stakeholder alignment, surface concerns, facilitate resolution
3. **Present Analysis**: Format alignment status with decisions required
4. **Document Decisions**: Capture agreement and next steps

## Instructions

### 1. Read Context

Read target document if provided and parse parameters:
- `--stakeholders`: Comma-separated stakeholder groups
- `--focus`: What to focus on (concerns, tradeoffs, conflicts)
- `--conflict`: Specific conflict to mediate

### 2. Dispatch to Alignment Lead

```
Task(
  subagent_type="wicked-product:alignment-lead",
  prompt="""Facilitate stakeholder alignment and consensus building.

## Context
{target document content if provided}

## Parameters
- Stakeholders: {specified groups or infer from context}
- Focus: {concerns, tradeoffs, conflicts, or general}
- Conflict: {specific conflict if specified}

## Task

1. **Identify Stakeholders**: Map who's affected (interest, influence, concerns)
2. **Surface Concerns**: What worries each group
3. **Analyze Alignment**: Where consensus/conflict exists
   - ALIGNED: Areas of agreement
   - CONFLICTED: Conflicts with options and recommendations
   - UNCLEAR: Items needing clarification
4. **Facilitate Resolution**: Propose compromises for conflicts
5. **Define Next Steps**: Decisions required with deadlines and owners

## Return Format

Provide:
- Status (ALIGNED, PARTIAL, CONFLICTED)
- Stakeholder Map (stakeholder, interest, influence, key concerns)
- Alignment Status (aligned items, conflicts with recommendations, unclear items)
- Decisions Required (table with decision, options, stakeholders, deadline)
- Next Steps (action, owner, deadline)
"""
)
```

### 3. Present Analysis

Format the agent's output into the standard alignment analysis structure.

## Output

```markdown
## Stakeholder Alignment Analysis

### Status: {ALIGNED / PARTIAL / CONFLICTED}

### Stakeholder Map
| Stakeholder | Interest | Influence | Key Concerns |
|-------------|----------|-----------|--------------|
| Engineering | HIGH | HIGH | Technical debt, timeline |
| QE | HIGH | MED | Testability, coverage |
| Operations | MED | HIGH | Deployment, monitoring |

### Alignment Status

**ALIGNED**:
- Core feature set agreed
- Success metrics defined

**CONFLICTED**:
- Timeline vs Scope
  - Engineering: Needs 6 weeks
  - Product: Wants 4 weeks
  - **Recommendation**: 5 weeks with reduced scope

**UNCLEAR**:
- Security requirements need compliance review

### Decisions Required
| Decision | Options | Stakeholders | Deadline |
|----------|---------|--------------|----------|
| Scope for MVP | Full vs Reduced | Product, Eng | This week |

### Next Steps
1. Schedule compliance review - Security Lead - Mon
2. Finalize scope - Product Manager - Wed
3. Confirm timeline - Engineering Lead - Thu
```

## Integration

Automatically:
- **wicked-kanban**: Documents alignment status
- **wicked-mem**: Tracks stakeholder patterns
- **Event**: Emits `[product:alignment:achieved:success]` or `[product:concern:raised:warning]`

## Example

```bash
$ /wicked-product:align requirements.md --stakeholders "eng,qe,ops"

Analyzing stakeholder alignment...
[Dispatches to alignment-lead agent]
[Agent analyzes stakeholder positions and surfaces concerns]

Stakeholders Identified: 3
Concerns Surfaced: 5
Conflicts Found: 2

Status: PARTIAL ALIGNMENT

ALIGNED:
- Core authentication feature
- Security requirements

CONFLICTED:
1. Scope vs Timeline
   - Engineering: 6 weeks realistic
   - Product: 4 weeks desired
   - Recommendation: 5 weeks with phased delivery

2. Technology Choice
   - Engineering: Prefers OAuth
   - Ops: Concerns about complexity
   - Recommendation: Start simple, add OAuth in v2

Open Items:
- Compliance review needed (Security)
- Load testing strategy (QE + Ops)

Next Steps:
1. Schedule security review
2. Define phased delivery plan
3. Document OAuth roadmap for v2

Stored in kanban: alignment-001
Events emitted: [product:concern:raised:warning]
```

## Facilitation Tips

When conflicts arise:
1. Make trade-offs explicit
2. Find shared goals
3. Propose compromise
4. Escalate if needed
5. Document decision

## Stakeholder Communication

Template messages stored in: `scripts/stakeholder-templates/`
