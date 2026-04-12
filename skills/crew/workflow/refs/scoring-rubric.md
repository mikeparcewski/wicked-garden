# Scoring Rubric

Composite complexity score algorithm (0-7) and normalized risk score model.
These are the explicit computation rules extracted from smart_decisioning.py.

---

## Composite Complexity Score (0-7)

The composite score combines 8 components. Final score is clamped to [0, 7].

### Component Definitions

| Component | Range | Source |
|-----------|-------|--------|
| impact | 0-3 | File role weight + integration surface (see risk-dimension-signals.md) |
| risk_premium | 0-2 | Multiplicative reversibility × novelty model |
| scope | 0-2 | Word count of input text |
| coordination | 0-1 | Stakeholder keyword presence |
| test_complexity | 0-3 | Test scope signals (weighted at 0.25) |
| documentation | 0-3 | Documentation need signals (weighted at 0.25) |
| coordination_cost | 0-3 | Coordination signals (weighted at 0.25) |
| operational | 0-3 | Operational signals (weighted at 0.25) |
| scope_effort | 0-3 | Build-from-scratch, component count, breadth signals (weighted at 0.25) |
| integration_surface | 0-3 | External boundary count — APIs, services, queues (weighted at 0.25) |
| state_complexity | 0-3 | Persistence, concurrency, ordering guarantees (weighted at 0.25) |

### Formula

```
risk_premium = min(round(reversibility × novelty × 0.22), 2)

scope:
  word_count > 100 → 2
  word_count > 50  → 1
  otherwise        → 0

coordination:
  any of [team, manager, lead, stakeholder, customer, user] in text → 1
  otherwise → 0

test_complexity_contrib     = round(test_complexity × 0.25)
documentation_contrib       = round(documentation × 0.25)
coordination_cost_contrib   = round(coordination_cost × 0.25)
operational_contrib         = round(operational × 0.25)
scope_effort_contrib        = round(scope_effort × 0.25)
integration_surface_contrib = round(integration_surface × 0.25)
state_complexity_contrib    = round(state_complexity × 0.25)

total = impact
      + risk_premium
      + scope
      + coordination
      + test_complexity_contrib
      + documentation_contrib
      + coordination_cost_contrib
      + operational_contrib
      + scope_effort_contrib
      + integration_surface_contrib
      + state_complexity_contrib

composite = min(total, 7)
```

### Risk Premium Detail

The risk_premium uses a multiplicative model so that BOTH reversibility AND
novelty must be elevated for a high premium. This eliminates the degenerate
case where reversibility=3 and novelty=0 produced the same result as
reversibility=3 and novelty=3 under additive models.

| reversibility | novelty | risk_premium |
|---------------|---------|-------------|
| 3 | 3 | 2 (3×3×0.22=1.98→2) |
| 2 | 2 | 1 (2×2×0.22=0.88→1) |
| 3 | 0 | 0 (3×0×0.22=0→0) |
| 1 | 1 | 0 (1×1×0.22=0.22→0) |

### Weighted Dimension Rationale

The 7 weighted dimensions are each multiplied by 0.25. This means:
- Each dimension contributes a maximum of round(3 × 0.25) = 1 point
- All 7 dimensions saturated = 7 points before capping
- The composite is still clamped to 7, preserving backward compatibility with
  existing complexity-based routing thresholds

The three newest dimensions (scope_effort, integration_surface, state_complexity)
capture effort and correctness complexity that the original risk-focused dimensions
miss. Greenfield projects score low on reversibility and coordination but high on
scope/effort and state complexity — these dimensions correct that blind spot.

### Score Interpretation

| Score | Label | Engagement |
|-------|-------|------------|
| 0-2 | Simple | Built-in agents only |
| 3-4 | Moderate | Core specialists per signal |
| 5-7 | Complex | All relevant + delivery always added |

---

## Min-Complexity Floor (Archetype Override)

After computing the composite score, apply the archetype min_complexity floor:

```
final_complexity = max(composite, max(archetype.min_complexity for each detected archetype))
```

If no archetypes detected: `final_complexity = composite`

---

## Normalized Score (11 Dimensions)

A separate representation in [0.0, 1.0] per dimension. Derived from the
existing keyword-based dimensions and detected signals. Does not replace
the composite score — provides a finer-grained view.

### Dimension Mapping

| Normalized Dimension | Source | Formula |
|---------------------|--------|---------|
| impact | RiskDimensions.impact | impact / 3.0 |
| reversibility | RiskDimensions.reversibility | reversibility / 3.0 |
| novelty | RiskDimensions.novelty | novelty / 3.0 |
| coupling | detected signal count | min(1.0, len(signals) / 6.0) |
| data_risk | data signal confidence | signal_confidences.get("data", 0.0) |
| compliance_exposure | compliance signal confidence | signal_confidences.get("compliance", 0.0) |
| ux_surface | ux signal confidence | signal_confidences.get("ux", 0.0) |
| team_coordination | stakeholder coordination indicator | min(1.0, coordination / 1.0) |
| scope_effort | RiskDimensions.scope_effort | scope_effort / 3.0 |
| integration_surface | RiskDimensions.integration_surface | integration_surface / 3.0 |
| state_complexity | RiskDimensions.state_complexity | state_complexity / 3.0 |

All output values rounded to 4 decimal places. On any computation error,
return all-zero score (fail open).

### Weighted Risk Index (WRI)

```
weight_sum = Σ(all dimension weights)    # = 1.00 with current weights
total = Σ(dimension_value × weight)      # for each of 8 dimensions
WRI = round(total / weight_sum, 4)       # normalized by weight_sum
```

WRI is in [0.0, 1.0]. Used for routing lane determination (see specialist-routing-rules.md).

---

## Signal Confidence Scoring

```
confidence = matched_keyword_count / total_keyword_count_in_category
```

A signal is "detected" when confidence >= signal_threshold (default: 0.1).

Keywords ending with `*` use stem matching (prefix). Non-starred keywords
use whole-word boundary matching. All matching is case-insensitive.

---

## Archetype Confidence Scoring

```
confidence = min(matched_keyword_count / max(total_keywords × 0.3, 1), 1.0)
```

Minimum 2 keyword matches required to trigger any archetype detection.
30% of an archetype's keywords matched = confidence 1.0.

---

## Override Mechanisms

### Complexity Override (user-supplied)

A user may supply a `complexity_override` value (0-7). When set, it completely
replaces the computed composite score. All other analysis (signals, specialists,
routing) continues using the overridden value.

### Component Overrides (user-supplied)

Individual breakdown components can be overridden before final computation:
`impact`, `risk_premium`, `scope`, `coordination`, `test_complexity`,
`documentation`, `coordination_cost`, `operational`, `scope_effort`,
`integration_surface`, `state_complexity`. Only recognized component
names are accepted.

### Force/Skip Signals (user-supplied)

- `force_signals`: list of signal categories to inject at confidence 1.0
- `skip_signals`: list of signal categories to remove from detection results
- `skip_injection`: if true, archetype signal injection is skipped

### Signal Threshold Override

Default threshold is 0.1. Can be lowered (more sensitive) or raised (less sensitive).
