---
name: stakeholder-alignment
title: Cross-Functional Stakeholder Alignment
description: Surface and resolve conflicts between engineering, product, and operations teams
type: requirements
difficulty: advanced
estimated_minutes: 12
---

# Cross-Functional Stakeholder Alignment

This scenario tests wicked-product's ability to identify stakeholder concerns, surface hidden conflicts, and facilitate alignment on complex cross-functional decisions.

## Setup

Create a realistic cross-functional decision scenario:

```bash
# Create test project
mkdir -p ~/test-wicked-product/alignment
cd ~/test-wicked-product/alignment

# Create a requirements document with implicit conflicts
cat > requirements.md <<'EOF'
# Feature: Real-Time Collaboration

## Product Vision
Enable multiple users to edit documents simultaneously, like Google Docs.

## Requirements
1. Real-time cursor presence (see who's editing where)
2. Instant sync across all users (< 100ms latency)
3. Conflict resolution when two users edit same paragraph
4. Works offline with sync when reconnected
5. Scale to 50 concurrent editors per document
6. Ship in Q1 (8 weeks)

## Technical Notes (from Engineering)
- Current architecture is request/response, not real-time
- Would need WebSocket infrastructure
- Offline sync requires CRDT or OT implementation
- 50 concurrent editors is aggressive for first version

## Operations Concerns
- WebSocket connections are persistent = more server resources
- How do we monitor real-time connections?
- What happens during deployments?

## Support Concerns
- How do we troubleshoot "my changes disappeared"?
- Need visibility into sync state

## Security Notes
- Real-time means more attack surface
- Need rate limiting on WebSocket connections
- Audit trail for who changed what
EOF

# Create stakeholder context
cat > stakeholders.md <<'EOF'
# Stakeholder Map

## Product (Sarah)
- VP of Product, reports to CEO
- Committed Q1 date to board
- Previous company had real-time features
- Key metric: user engagement

## Engineering (Marcus)
- Engineering Director, 12 reports
- Burned by rushed projects before
- Wants to build it right
- Key metric: system reliability

## Operations (Priya)
- SRE Lead, 4 reports
- Responsible for uptime SLA (99.9%)
- Currently at 99.7% due to incidents
- Key metric: uptime, MTTR

## Security (James)
- Security Engineer (solo)
- Recent audit found issues
- Under pressure to reduce risk
- Key metric: vulnerability count

## Customer Success (Lisa)
- CS Director, handles enterprise
- Enterprise customers asking for this
- Also hearing "too many bugs lately"
- Key metric: NPS, churn
EOF
```

## Steps

1. **Analyze Stakeholder Alignment**
   ```bash
   /wicked-product:align requirements.md --stakeholders "product,engineering,operations,security"
   ```

   **Expected**: Should identify:
   - Where stakeholders agree
   - Where they conflict
   - Hidden concerns not explicitly stated
   - Power dynamics (who has decision authority)

2. **Verify Conflict Identification**

   The analysis should surface conflicts:
   - **Timeline vs Quality**: 8 weeks for CRDT implementation?
   - **Features vs Reliability**: 50 concurrent editors is risky
   - **Offline vs Complexity**: Offline sync adds significant scope
   - **Speed vs Security**: Real-time increases attack surface

3. **Check Concern Surfacing**

   Should identify unstated concerns:
   - Engineering worried about another rushed project
   - Operations worried about impact on already-struggling SLA
   - Security worried about being blamed if breach occurs
   - Product worried about losing credibility if they slip date

4. **Verify Mediation Suggestions**

   For each conflict, suggest resolution:
   ```
   Timeline vs Quality Conflict:
   - Option A: Reduce scope (no offline sync in v1)
   - Option B: Extend timeline to Q2
   - Option C: Ship MVP with 10 editors, scale later
   - Recommendation: Option C (validates demand, manages risk)
   ```

5. **Check Decision Framework**

   Output should include:
   - Which decisions need to be made
   - Who needs to make them
   - What information is missing
   - Proposed next steps

6. **Run Conflict Deep-Dive**
   ```bash
   /wicked-product:align --conflict "scope vs timeline"
   ```

   **Expected**: Focused analysis on the specific tradeoff with options and recommendations.

## Expected Outcome

- Clear map of stakeholder interests and concerns
- Explicit identification of conflicts
- Options for resolution with tradeoffs
- Recommendation with reasoning
- Actionable next steps

## Success Criteria

- [ ] All 4 stakeholder groups analyzed
- [ ] At least 3 conflicts identified
- [ ] Timeline vs scope conflict explicitly called out
- [ ] Unstated concerns surfaced (not just what's written)
- [ ] Power dynamics noted (Product committed to board)
- [ ] Each conflict has 2+ resolution options
- [ ] Recommendations are specific, not "communicate better"
- [ ] Next steps include who does what by when
- [ ] MVP/phased approach suggested as middle ground
- [ ] Risk of "shipping broken feature" acknowledged

## Value Demonstrated

**Real-world value**: Cross-functional alignment is one of the hardest problems in product development. Engineers want to build it right, product wants it now, operations wants stability, and security wants no changes. These conflicts often stay hidden until the project is in crisis.

wicked-product's `/align` command makes conflicts explicit before they become crises. By systematically analyzing each stakeholder's interests, concerns, and influence, it surfaces the hidden dynamics that derail projects.

The mediation suggestions help move from "we disagree" to "here are our options." The phased approach recommendations (MVP first, iterate later) often break deadlocks by giving everyone something.

This replaces contentious stakeholder meetings where the loudest voice wins, with structured analysis that ensures all perspectives are heard. For PMs navigating complex organizational dynamics, it provides a framework for facilitating alignment rather than just documenting disagreement.
