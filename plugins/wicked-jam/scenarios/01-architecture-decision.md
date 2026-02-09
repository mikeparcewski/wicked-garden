---
name: architecture-decision
title: Architecture Decision Making
description: Use brainstorming to evaluate competing technical approaches
type: workflow
difficulty: intermediate
estimated_minutes: 10
---

# Architecture Decision Making

This scenario tests wicked-jam's ability to help engineers make complex technical decisions by generating diverse expert perspectives on architectural tradeoffs.

## Setup

Create a realistic architecture decision scenario:

```bash
# Create a decision log directory
mkdir -p ~/test-wicked-jam/architecture-decisions
cd ~/test-wicked-jam/architecture-decisions

# Document a realistic architecture question
cat > caching-decision.md <<'EOF'
# Context
We're building a social media API that serves 10k requests/minute.
Current bottleneck: Database queries for user profiles.
Average profile query: 50ms
Cache hit would reduce to: 2ms

# Question
What caching strategy should we implement?
Options: Redis, Memcached, in-memory cache, CDN, or hybrid?

# Constraints
- Budget: $500/month for caching infrastructure
- Team experience: Strong with PostgreSQL, minimal with Redis
- Scale: Expected 3x growth in 6 months
EOF
```

## Steps

1. **Run Full Brainstorm**
   ```bash
   /wicked-jam:brainstorm "caching strategy for social media API handling 10k req/min with user profile bottleneck"
   ```

   Expected: Session launches with facilitator agent, generates 4-6 relevant personas (likely: Performance Engineer, DevOps, Cost Optimizer, Database Expert, etc.)

2. **Verify Persona Diversity**

   Check that output includes:
   - At least 4 distinct personas
   - Mix of archetype types (Technical, Business, Process)
   - Each persona has unique concerns (not repetitive)

3. **Verify Multi-Round Discussion**

   Check that output shows:
   - Round 1: Initial perspectives from each persona
   - Round 2: Personas building on or challenging each other's points
   - Personas reference each other by name ("Building on [Name]'s point...")

4. **Verify Synthesis Quality**

   Check synthesis section contains:
   - 3-5 key insights (not 10+)
   - Confidence levels (HIGH/MEDIUM/LOW) for each insight
   - Specific reasoning tied to discussion
   - Prioritized action items
   - Open questions or unresolved tensions

5. **Test Quick Alternative**
   ```bash
   /wicked-jam:jam "should we use Redis or Memcached for session cache?"
   ```

   Expected: Faster output with 4 personas, single round, brief synthesis

## Expected Outcome

- Session completes in under 2 minutes
- Output structured with synthesis first (context efficient)
- Insights reflect genuine technical tradeoffs, not generic advice
- Multiple perspectives that could change your thinking
- Actionable next steps, not just analysis

## Success Criteria

- [ ] Brainstorm generates 4-6 relevant personas automatically
- [ ] Personas represent different archetypes (not all technical)
- [ ] Round 2 shows personas responding to each other's points
- [ ] Synthesis includes confidence levels on insights
- [ ] Action items are specific and prioritized
- [ ] Open questions acknowledge unknowns honestly
- [ ] `/jam` command produces faster, briefer output
- [ ] Output puts synthesis before discussion details

## Value Demonstrated

**Real-world value**: Engineers making architecture decisions often face analysis paralysis or miss important perspectives. wicked-jam simulates a focus group of domain experts in seconds, surfacing considerations you might not think of alone. The confidence-rated insights help separate strong consensus from speculative ideas, and the prioritized actions turn analysis into momentum.

This replaces the need to schedule meetings with multiple stakeholders or spend hours researching pros/cons, while still getting diverse viewpoints.
