# Scoring Rubric (HISTORICAL — v5)

**Status**: Deprecated. This file describes the v5 weighted-sum complexity-scoring
algorithm that lived in `scripts/crew/smart_decisioning.py`. The script was deleted
in the v6 rebuild (Gate 4 Phase 2, #428).

**v6 replacement**: the `wicked-garden:propose-process` facilitator rubric
replaces this scoring model with a 9-factor judgment read (reversibility,
blast_radius, compliance_scope, user_facing_impact, novelty, scope_effort,
state_complexity, operational_risk, coordination_cost) plus a judgment-driven 0-7
complexity estimate. See:

- `skills/propose-process/SKILL.md`
- `skills/propose-process/refs/output-schema.md`

This file is kept as a historical reference for anyone reading v5 commit archeology
or comparing v5 vs v6 behaviour. Do NOT use the composite-score formula below as a
current contract — it does not reflect v6 behaviour.

---

## v5 Composite Complexity Score (historical)

The v5 composite score combined 8 weighted components (impact, risk_premium, scope,
coordination, test_complexity, novelty, file_impact, archetype_bonus) clamped to
[0, 7]. The algorithm relied on `SIGNAL_KEYWORDS` regex matching + archetype
detection + keyword-to-specialist mapping.

For the full historical algorithm, refer to the v5.2.0 tag:

```bash
git show v5.2.0:scripts/crew/smart_decisioning.py
```

## v6 replacement summary

| v5 concept | v6 equivalent |
|---|---|
| `SIGNAL_KEYWORDS` (18 categories) | 9 factors in facilitator rubric Step 3 |
| Complexity 0-7 via weighted sum | Judgment-driven 0-7 in rubric Step 8 |
| `routing_lane` (auto/fast/standard) | `rigor_tier` (minimal/standard/full) in Step 7 |
| `SPECIALIST_FALLBACKS` static map | Direct frontmatter read in rubric Step 4 |
| 12 archetype classes | Implicit in Step 1 "summarize surface area" |

See `scripts/ci/gate4-cutover-matrix.md` for the full coverage matrix.
