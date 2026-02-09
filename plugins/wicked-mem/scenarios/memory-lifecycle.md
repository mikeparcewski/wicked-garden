---
name: memory-lifecycle
title: Memory Lifecycle and Decay
description: Test memory status transitions, TTL, and archival behavior
type: feature
difficulty: advanced
estimated_minutes: 10
---

# Memory Lifecycle and Decay

Test that memories follow the correct lifecycle: active → archived → decayed → deleted based on type, importance, and access patterns.

## Setup

Create memories with different characteristics to observe lifecycle behavior.

1. **Store episodic memory (90-day TTL)**
   ```
   /wicked-mem:store "Deployed v2.1.0 with new checkout flow. Monitoring error rates closely." --type episodic --tags deployment,checkout
   ```

2. **Store episodic with high importance (180-day effective TTL: 90 * 2.0)**
   ```
   /wicked-mem:store "Critical bug in payment processing: race condition caused duplicate charges. Fixed by adding distributed lock with Redis. Must monitor for recurrence." --type episodic --tags bug,payment,critical
   ```

3. **Store episodic with low importance (45-day effective TTL: 90 * 0.5)**
   ```
   /wicked-mem:store "Updated README with new setup instructions." --type episodic --tags docs,maintenance
   ```

4. **Store permanent memory (procedural)**
   ```
   /wicked-mem:store "Database migration checklist: (1) Backup production, (2) Test on staging, (3) Run during low traffic window, (4) Monitor error rates for 1 hour, (5) Rollback plan ready." --type procedural --tags database,process,migration
   ```

5. **Store permanent memory (decision)**
   ```
   /wicked-mem:store "Chose Stripe over Braintree for payment processing. Primary reasons: Better international support, clearer pricing, superior documentation." --type decision --tags payments,stripe
   ```

## Steps

1. **Check initial state**
   ```
   /wicked-mem:stats
   ```

   Should show:
   - 5 total memories
   - 3 episodic (temporary)
   - 1 procedural (permanent)
   - 1 decision (permanent)
   - All status: active

2. **Access a memory multiple times** (to test access_boost)
   ```
   /wicked-mem:recall "payment race condition"
   /wicked-mem:recall "duplicate charges"
   /wicked-mem:recall --tags payment,critical
   ```

3. **Check access tracking**
   - Open the memory file directly or use stats
   - Verify access_count increased
   - Effective TTL should extend: `base_ttl * importance * (1 + access_count * 0.1)`

4. **Simulate time passing** (manual test)

   Option A: Manually edit memory files to simulate aging
   - Navigate to `~/.something-wicked/memory/projects/[project]/episodic/`
   - Edit frontmatter to set `created` date to 91 days ago for the low-importance memory
   - Edit to 181 days ago for the regular episodic memory

   Option B: Wait for natural decay (impractical for testing)

5. **Run cleanup/archival**
   ```
   /wicked-mem:stats
   ```

   Or explicitly trigger the memory-archivist (if available):
   - The archivist agent should handle decay logic
   - Active memories past TTL should become archived
   - Archived memories past grace period should decay

6. **Test forget command**

   Soft delete (archive):
   ```
   /wicked-mem:forget mem_[id-of-readme-memory]
   ```

   Verify status changed to archived:
   ```
   /wicked-mem:recall --tags docs,maintenance
   ```

   Hard delete:
   ```
   /wicked-mem:forget mem_[id] --hard
   ```

   Verify permanently deleted (should not appear anywhere).

## Expected Outcome

**Lifecycle transitions:**
- New memories: status = active
- Expired episodic: status = archived (soft deleted)
- Old archived: status = decayed
- Hard deleted: removed from file system

**TTL calculations:**
- Low importance episodic (0.5x): ~45 days
- Normal episodic (1.0x): 90 days
- High importance episodic (2.0x): 180 days
- Permanent types: no auto-archival

**Access boost:**
- Memory accessed 5 times: TTL * 1.5 (boost of 1 + 5*0.1)
- Frequently accessed memories stay active longer

**Manual control:**
- /wicked-mem:forget archives the memory
- /wicked-mem:forget --hard permanently deletes
- Archived memories don't appear in standard recall

## Success Criteria

- [ ] Episodic memories have 90-day base TTL
- [ ] Procedural and decision memories never auto-archive
- [ ] Importance multiplier affects effective TTL (high=2x, low=0.5x)
- [ ] Access count boosts TTL (formula: 1 + access_count * 0.1)
- [ ] Expired memories transition to archived status
- [ ] /wicked-mem:forget sets status to archived
- [ ] /wicked-mem:forget --hard deletes file
- [ ] /wicked-mem:stats shows counts by status (active, archived, decayed)
- [ ] Archived memories don't appear in standard /wicked-mem:recall
- [ ] High-importance memories stay active longer than low-importance

## Value Demonstrated

Intelligent memory lifecycle prevents:
- **Stale context pollution** - Old episodic events don't clutter current context
- **Losing critical knowledge** - Important things stay active longer
- **Manual cleanup burden** - System self-maintains based on usage patterns
- **Binary delete problem** - Archival gives grace period before permanent deletion

Real-world impact:
- **Adaptive retention** - Frequently referenced memories automatically persist
- **Natural forgetting** - Mimics human memory - recent events fade, important patterns persist
- **Storage efficiency** - Old memories archived/deleted instead of growing unbounded
- **Trust in permanence** - Procedural knowledge and decisions never auto-delete

The lifecycle mirrors how human memory works:
- **Episodic** - "What happened last quarter" fades with time
- **Procedural** - "How to ride a bike" never forgotten
- **Importance** - Traumatic or significant events remembered longer
- **Rehearsal** - Things you reference stay fresh

This prevents the common problem with note-taking systems: they become graveyards of outdated information. The memory system stays current and relevant.
