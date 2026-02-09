---
name: integration-with-wicked-mem
title: Integration with wicked-mem
description: Test brainstorming with context recall and insight storage
type: integration
difficulty: intermediate
estimated_minutes: 15
---

# Integration with wicked-mem

This scenario tests wicked-jam's integration with wicked-mem for recalling prior context before sessions and storing insights afterward.

## Setup

Requires both wicked-jam and wicked-mem plugins installed:

```bash
# Verify plugins are installed
claude plugin list | grep -E "(wicked-jam|wicked-mem)"

# Create test project directory
mkdir -p ~/test-wicked-jam/database-migration
cd ~/test-wicked-jam/database-migration

# Create initial context to store
cat > initial-context.md <<'EOF'
# Database Migration Decision - Initial Context

## Previous Discussion Summary
We explored moving from PostgreSQL to Cassandra for our time-series data.

## Key Points from Last Week
- Current PostgreSQL performance: 500 writes/sec, struggling at scale
- Data is append-only time-series (sensor readings)
- 2TB of data currently, growing 500GB/month
- Team has no Cassandra experience
- Budget approved for migration costs

## Open Questions from Last Time
- What's the migration path?
- How do we maintain consistency during transition?
- Training timeline for team?

## Decision Status
Still evaluating. Need to determine if Cassandra is right choice vs.
PostgreSQL optimization vs. TimescaleDB vs. ClickHouse.
EOF
```

## Steps

1. **Store Initial Context in wicked-mem**
   ```bash
   /wicked-mem:store --type decision --tags "database,migration,time-series" "$(cat initial-context.md)"
   ```

   Expected: Confirmation that context is stored

2. **Run Brainstorm That Should Recall Context**
   ```bash
   /wicked-jam:brainstorm "time-series database migration from PostgreSQL"
   ```

   Expected:
   - Session begins with "Recalling prior context..." or similar
   - Facilitator acknowledges previous discussion points
   - Personas reference or build on prior context
   - Discussion doesn't repeat what was already covered

3. **Verify Context Integration**

   Check output mentions:
   - Previous consideration of Cassandra
   - The 500 writes/sec performance issue
   - Team's lack of Cassandra experience
   - Budget approval mentioned in context

4. **Complete Brainstorm Session**

   Let session complete with full synthesis.

5. **Verify Storage Offer**

   Check that after synthesis, wicked-jam:
   - Offers to store insights in wicked-mem
   - Provides option to accept or decline
   - Suggests appropriate tags (database, migration, etc.)

6. **Accept Storage Offer**

   Respond affirmatively to storage prompt.

   Expected: Insights stored in wicked-mem

7. **Recall Stored Insights**
   ```bash
   /wicked-mem:recall "database migration"
   ```

   Expected:
   - Original context retrieved
   - New brainstorm insights retrieved
   - Both tied together by tags

8. **Run Second Session on Related Topic**
   ```bash
   /wicked-jam:brainstorm "data consistency during database migration"
   ```

   Expected:
   - Recalls both original context AND first brainstorm insights
   - Builds on previous discussion
   - Doesn't start from scratch

9. **Test Standalone Mode (Without wicked-mem)**

   Note: This step simulates behavior when wicked-mem is not available

   Expected behavior documented:
   - Session runs without context recall
   - No storage offer at end
   - Suggests local file storage instead
   - Full functionality otherwise intact

## Expected Outcome

- First brainstorm session recalls prior context from wicked-mem
- Personas reference or build on stored context
- Session offers to store insights after completion
- Stored insights can be recalled in future sessions
- Second brainstorm builds on both original context and first session
- Progressive knowledge building across sessions
- Graceful degradation when wicked-mem unavailable

## Success Criteria

- [ ] Initial context successfully stored in wicked-mem
- [ ] Brainstorm session indicates context recall at start
- [ ] Session references specific details from stored context
- [ ] Personas don't repeat already-covered ground
- [ ] Session offers to store insights after synthesis
- [ ] Storage prompt includes suggested tags
- [ ] Accepting storage saves insights to wicked-mem
- [ ] Stored insights can be recalled with /wicked-mem:recall
- [ ] Second session on related topic recalls previous insights
- [ ] Second session builds on (not repeats) prior discussion
- [ ] Documentation acknowledges graceful degradation without wicked-mem

## Value Demonstrated

**Real-world value**: Complex decisions rarely happen in a single session. Teams revisit architecture choices, product decisions, and technical strategies over days or weeks. wicked-jam's integration with wicked-mem enables **progressive decision-making** where each brainstorm session builds on prior context.

This prevents repeating the same discussions, surfaces how thinking has evolved, and creates an institutional memory of decision rationale. When a new team member asks "why did we choose Cassandra?", you can recall the brainstorm sessions that led to that decision, complete with the perspectives considered and tradeoffs acknowledged.

The graceful degradation ensures wicked-jam works standalone while offering enhanced value when paired with wicked-mem, following the plugin ecosystem's composability principle.

## Integration Architecture Notes

This scenario validates the integration pattern:

```
wicked-jam:brainstorm
  |
  ├─> wicked-mem:recall (if available)
  |     └─> inject context into facilitator
  |
  ├─> facilitator runs session
  |
  └─> wicked-mem:store (if available & user approves)
        └─> persist insights with tags
```

This demonstrates plugin composability where wicked-jam enhances with wicked-mem but degrades gracefully without it.
