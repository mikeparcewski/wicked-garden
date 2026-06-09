# Stakeholder Alignment Rubric

Apply this inline. Surface concerns across divergent stakeholder positions, map them
to trade-offs, and build consensus. (Not requirements elicitation — `refs/elicit.md`;
not UX — `refs/ux.md`.)

## Process

1. **Identify stakeholders** — primary (direct users/customers), secondary (teams
   impacted: eng, QE, ops, support), influencers (leadership, partners, compliance).
   Map interest + influence.
2. **Surface concerns per group** — needs, concerns, constraints, success criteria.
3. **Analyze alignment**:
   - **ALIGNED** — areas of agreement
   - **CONFLICTED** — where interests diverge (with options + recommendation)
   - **UNCLEAR** — items needing clarification
4. **Facilitate resolution** — make trade-offs explicit, highlight shared goals,
   propose compromise options, escalate when needed.
5. **Document** — decisions, accepted trade-offs, open items, owners + deadlines.

## Facilitation checklist

- [ ] All stakeholders identified
- [ ] Concerns surfaced and documented
- [ ] Conflicts made explicit
- [ ] Trade-offs clarified
- [ ] Consensus areas identified
- [ ] Open items tracked (owner + deadline)
- [ ] Communication plan defined

## Questions to ask

Who needs to be in this decision? What concerns haven't been voiced? Where are
interests misaligned? What trade-offs are we making? Who might block/resist? What
information is missing? How do we communicate the decision?

## Output

```markdown
## Stakeholder Alignment Analysis
### Status: ALIGNED | PARTIAL | CONFLICTED

### Stakeholder Map
| Stakeholder | Interest | Influence | Key Concerns |
|-------------|----------|-----------|--------------|

### Alignment Status
**ALIGNED**: …
**CONFLICTED**:
- {conflict} — Positions: {A wants X, B wants Y} — Trade-offs: … — Recommendation: …
**UNCLEAR**: {needs discussion}

### Trade-offs Accepted
| Trade-off | Chosen Path | Alternative | Rationale |

### Decisions Required
| Decision | Options | Stakeholders | Deadline |

### Next Steps
1. {action} — {owner} — {deadline}
```

## When conflicts arise

Make trade-offs explicit · find shared goals · propose compromise · escalate if
needed · document the decision. Persist status via `TaskCreate`/`TaskUpdate`
(`metadata.event_type="task"`); store stakeholder patterns via `wicked-brain:memory`.
