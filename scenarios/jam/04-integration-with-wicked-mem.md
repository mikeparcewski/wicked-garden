---
name: integration-with-wicked-brain-memory
title: Jam Integration with wicked-brain Memory Recall
description: Test brainstorming with context recall and insight storage via wicked-brain:memory (v8.0.0+ replacement for deprecated wicked-garden:mem:* commands)
type: integration
difficulty: intermediate
estimated_minutes: 15
---

# Jam Integration with wicked-brain Memory Recall

This scenario tests wicked-jam's integration with wicked-brain for recalling prior context before sessions and storing insights afterward.

**Note (v8.0.0+)**: The deprecated `wicked-garden:mem:store` / `wicked-garden:mem:recall` commands were removed in v8.0.0. This scenario has been rewritten to use `wicked-brain:memory` directly (the canonical replacement). See `docs/cluster-a/mem-zombie-postmortem-and-remediation.md` for migration details.

## Setup

Requires wicked-jam plugin installed and wicked-brain plugin installed and running:

```bash
# Verify wicked-brain is running
curl -s http://localhost:${WICKED_BRAIN_PORT:-4242}/health | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('ok'), 'Brain not running'"

# Create test project directory
mkdir -p ~/test-wicked-jam/database-migration
cd ~/test-wicked-jam/database-migration
```

## Steps

1. **Store Initial Context via wicked-brain:memory**

   Use the `wicked-brain:memory` skill in store mode to persist context:

   ```
   Skill(
     skill="wicked-brain:memory",
     args="store \"Database migration evaluation: exploring PostgreSQL to Cassandra migration for time-series sensor data. 500 writes/sec current limit, 2TB data growing 500GB/month. Team has no Cassandra experience. Budget approved. Open questions: migration path, consistency during transition, training timeline.\" --type decision --tags database,migration,time-series --importance high"
   )
   ```

   Expected: Confirmation that context is stored in wicked-brain.

2. **Run Brainstorm That Should Recall Context**
   ```bash
   /wicked-garden:jam:brainstorm "time-series database migration from PostgreSQL"
   ```

   Expected:
   - `brainstorm-facilitator.md` Step 1a fires a `wicked-brain:memory` recall for past decisions
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

5. **Store Brainstorm Insights via wicked-brain:memory**

   After synthesis, store insights:

   ```
   Skill(
     skill="wicked-brain:memory",
     args="store \"Brainstorm outcome on database migration: <synthesized decision> Rationale: <key rationale>\" --type decision --tags database,migration,jam,outcome --importance high"
   )
   ```

   Expected: Insights stored in wicked-brain.

6. **Recall Stored Insights**

   ```
   Skill(
     skill="wicked-brain:memory",
     args="recall \"database migration\" --filter_type decision"
   )
   ```

   Expected:
   - Original context retrieved
   - New brainstorm insights retrieved
   - Both associated by decision type

7. **Run Second Session on Related Topic**
   ```bash
   /wicked-garden:jam:brainstorm "data consistency during database migration"
   ```

   Expected:
   - Recalls both original context AND first brainstorm insights via `wicked-brain:memory` recall
   - Builds on previous discussion
   - Doesn't start from scratch

8. **Test Standalone Mode (Without wicked-brain)**

   Note: This step simulates behavior when wicked-brain is not available.

   Expected behavior documented:
   - Session runs without context recall (brain adapter returns empty)
   - Full brainstorm functionality otherwise intact
   - No hard failure — graceful degradation per plugin design

## Expected Outcome

- First brainstorm session recalls prior context from wicked-brain
- Personas reference or build on stored context
- Session stores insights in wicked-brain after completion
- Stored insights can be recalled in future sessions
- Second brainstorm builds on both original context and first session
- Progressive knowledge building across sessions
- Graceful degradation when wicked-brain unavailable

## Success Criteria

- [ ] Initial context successfully stored via wicked-brain:memory (store mode)
- [ ] Brainstorm session Step 1a triggers wicked-brain:memory recall
- [ ] Session references specific details from stored context
- [ ] Personas don't repeat already-covered ground
- [ ] Insights stored via wicked-brain:memory after synthesis
- [ ] Stored insights can be recalled with wicked-brain:memory (recall mode)
- [ ] Second session on related topic recalls previous insights
- [ ] Second session builds on (not repeats) prior discussion
- [ ] Graceful degradation when wicked-brain unavailable (brain adapter returns empty, not error)

## Value Demonstrated

**Real-world value**: Complex decisions rarely happen in a single session. Teams revisit architecture choices, product decisions, and technical strategies over days or weeks. wicked-jam's integration with wicked-brain enables **progressive decision-making** where each brainstorm session builds on prior context.

## Integration Architecture (v8.0.0+)

```
wicked-garden:jam:brainstorm
  |
  ├─> Skill(wicked-brain:memory, recall ...) [Step 1a in brainstorm-facilitator.md]
  |     └─> inject recalled decisions into facilitator
  |
  ├─> facilitator runs session
  |
  └─> Skill(wicked-brain:memory, store ...) [caller stores insights post-synthesis]
        └─> persist insights with type=decision, tags
```

## Council Consensus Integration

These steps validate the structured consensus protocol from `consensus.py`:

### 9. Format Council Result for Brain Storage

```bash
# Create test proposals
cat > /tmp/test-proposals.json <<'EOF'
[
  {"persona": "Architect", "proposal": "Use TimescaleDB for time-series", "rationale": "PostgreSQL extension, minimal migration", "confidence": 0.8, "concerns": ["Scaling limits at 10TB+"]},
  {"persona": "DBA", "proposal": "Use TimescaleDB with partitioning", "rationale": "Best balance of familiarity and performance", "confidence": 0.85, "concerns": ["Compression tuning needed"]},
  {"persona": "SRE", "proposal": "Use ClickHouse for analytics, keep PostgreSQL for OLTP", "rationale": "Separation of concerns", "confidence": 0.7, "concerns": ["Two systems to maintain"]}
]
EOF

# Synthesize consensus
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/consensus.py" synthesize \
  --proposals /tmp/test-proposals.json \
  --question "Which database for time-series data?" > /tmp/consensus-result.json

# Verify structured output
python3 -c "
import json
r = json.load(open('/tmp/consensus-result.json'))
assert 'decision' in r, 'Missing decision'
assert 'confidence' in r, 'Missing confidence'
assert 'dissenting_views' in r, 'Missing dissenting_views'
assert 0 <= r['confidence'] <= 1, 'Confidence out of range'
print('CONSENSUS_VALID')
print(f'Confidence: {r[\"confidence\"]}')
print(f'Dissenting views: {len(r[\"dissenting_views\"])}')
"
```

**Expected**: `CONSENSUS_VALID` with confidence between 0-1 and at least one dissenting view

### 10. Verify format_for_memory Returns Brain-Compatible Dict

```bash
python3 -c "
import json, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/jam')
from consensus import synthesize, format_for_memory, Proposal

proposals = [Proposal(**p) for p in json.load(open('/tmp/test-proposals.json'))]
result = synthesize(proposals, question='Which database for time-series data?')
mem_record = format_for_memory(result)

assert mem_record.get('type') == 'decision', 'Memory type should be decision'
assert 'content' in mem_record, 'Missing content field'
assert 'metadata' in mem_record, 'Missing metadata'
print('MEMORY_FORMAT_VALID')
print(f'Type: {mem_record[\"type\"]}')
print(f'Has dissent metadata: {\"dissent_count\" in str(mem_record[\"metadata\"])}')
"
```

**Expected**: `MEMORY_FORMAT_VALID` with type=decision and dissent metadata. The caller would then pass this dict to `wicked-brain:memory` (store mode) rather than the removed `wicked-garden:mem:store`.

### Success Criteria (Consensus Integration)
- [ ] Council synthesis produces structured JSON with decision, confidence, dissenting_views
- [ ] Confidence score is between 0 and 1
- [ ] Dissenting views are preserved (not flattened)
- [ ] format_for_memory returns dict with type=decision suitable for wicked-brain:memory ingestion
