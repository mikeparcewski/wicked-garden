---
name: decision-recall
title: The Decision Recall
description: Agent recalls why a past decision was made
type: feature
difficulty: basic
estimated_minutes: 3
---

# The Decision Recall

Test that important decisions and their rationale persist and can answer "why did we..." questions.

## Setup

Store a realistic architectural decision with full context:

```
/wicked-mem:store "Chose PostgreSQL over MongoDB for the payment system. Reasons: (1) ACID compliance is non-negotiable for financial transactions - we can't have partial payments or duplicate charges, (2) Complex reporting queries need JOINs across customers, subscriptions, and invoices - document DB would require denormalization and eventual consistency, (3) Team has 3 engineers with deep Postgres experience vs 1 who's used MongoDB casually. Trade-offs accepted: (a) Less flexibility for schema changes - migrations required, (b) Harder to scale horizontally - but payment volume won't hit that scale for 2+ years, (c) JSON columns slower than native BSON - but we're only storing metadata there. Considered alternatives: MySQL (rejected - weaker JSON support), CockroachDB (rejected - overkill for current scale, expensive), DynamoDB (rejected - vendor lock-in and team expertise gap)." --type decision --tags database,architecture,payments,postgresql
```

## Steps

1. **Wait a moment** (simulate time passing)

2. **Ask about the decision naturally**
   - "Why did we choose PostgreSQL?"
   - "What database are we using and why?"
   - "A new engineer asked why we're not using MongoDB"

3. **Test explicit recall**
   ```
   /wicked-mem:recall "PostgreSQL MongoDB"
   /wicked-mem:recall --type decision --tags database
   ```

4. **Test related queries**
   ```
   /wicked-mem:recall "ACID transactions"
   /wicked-mem:recall --tags architecture
   ```

## Expected Outcome

- Full decision context is retrieved with rationale
- Agent can explain the trade-offs considered
- Agent mentions alternatives that were rejected and why
- Tag-based discovery works (finding by "database" or "architecture")
- Search finds it via technical terms like "ACID" or "PostgreSQL"

## Success Criteria

- [ ] Decision memory includes comprehensive "why" with multiple reasons
- [ ] Trade-offs and alternatives are documented
- [ ] Tags make it discoverable via multiple paths (database, architecture, payments)
- [ ] Agent can answer "why did we..." questions naturally without manual /recall
- [ ] Memory appears in /wicked-mem:stats as type "decision"
- [ ] Search by technical terms (ACID, JOIN) finds the memory

## Value Demonstrated

Institutional knowledge persists and remains accessible. Prevents:
- **Questioning settled decisions** - "Why aren't we using X?" is answered instantly
- **Forgetting rationale** - 6 months later when requirements change, you remember why trade-offs were acceptable
- **Repeating debates** - New team members see the full reasoning, not just the outcome
- **Context loss during scaling** - As team grows, decisions don't live in one person's head

Real-world value: This is the difference between "we use Postgres" (unhelpful) and understanding the full technical and team context that led to that choice.
