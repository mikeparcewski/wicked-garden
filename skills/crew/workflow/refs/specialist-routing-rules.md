# Specialist Routing Rules

Signal-to-specialist mapping, complexity thresholds, fallback agents,
and routing tier definitions.

---

## Signal-to-Specialist Mapping

| Signal | Specialists Triggered |
|--------|----------------------|
| security | platform, qe |
| performance | engineering, qe |
| product | product |
| compliance | platform |
| ambiguity | jam |
| complexity | delivery, engineering |
| data | data |
| infrastructure | platform |
| architecture | agentic, engineering |
| ux | product |
| strategy | product |
| content | jam, product |
| text-as-code | qe, engineering |
| reversibility | platform, delivery |
| novelty | jam, engineering |
| quality | qe |
| imagery | _(no specialist in default set)_ |

Note: Each signal maps to a SET of specialists — all specialists in the set are
considered for engagement when that signal is detected above threshold.

---

## Specialist Routing Tiers

Each specialist is assigned a routing tier based on signal strength and complexity:

| Tier | Meaning | Threshold |
|------|---------|-----------|
| REQUIRED | Must engage — signal is high confidence and critical | confidence >= 0.4 OR complexity >= 5 |
| RECOMMENDED | Should engage — signal detected at moderate confidence | confidence >= 0.1 |
| OPTIONAL | May engage — low signal confidence, discretionary | below RECOMMENDED |

Specialists below the OPTIONAL threshold are not recommended.

---

## Complexity-Based Engagement Rules

These rules apply AFTER signal-based routing:

| Complexity | Rule |
|------------|------|
| 0-2 | Built-in agents only (facilitator, reviewer, implementer, researcher) |
| 3-4 | Core specialists based on detected signals |
| 5-7 | All relevant specialists + always include delivery |

For complexity >= 5, `delivery` specialist is always added regardless of signals.

---

## Ambiguity Rule

When input is detected as ambiguous (see signal-keywords.md detection patterns),
`jam` specialist is always added to the recommended list regardless of confidence
threshold. Ambiguity = jam.

---

## Fallback Agents

When a specialist is not available (not installed), use this fallback:

| Specialist | Fallback Agent |
|------------|----------------|
| jam | facilitator |
| qe | reviewer |
| product | facilitator |
| engineering | implementer |
| platform | implementer |
| delivery | _(no fallback — skip if unavailable)_ |
| data | researcher |
| agentic | reviewer |
| design | facilitator |

Valid built-in fallback agents: `facilitator`, `reviewer`, `implementer`, `researcher`

Maximum fallback chain depth: 1 (no chained fallbacks)

---

## Routing Lanes

After specialist selection, projects are assigned a routing lane based on
the normalized risk score:

| Lane | Weighted Risk Index | Meaning |
|------|---------------------|---------|
| AUTO | < 0.15 | Execute immediately — very low risk |
| FAST | 0.15–0.30 | Minimal gates — trivial, well-understood |
| STANDARD | 0.30–0.55 | Full crew gates — non-trivial but understood |
| ELEVATED | 0.55–1.00 | Human review required — complex/regulated/high-risk |
| LOOP | (hard rule) | Incident/iterative with learning checkpoints |

### Hard Rules (override weighted index)

Hard rules are evaluated FIRST. First matching rule wins:

| Rule | Condition | Lane |
|------|-----------|------|
| 1 — Incident | impact >= 0.7 AND team_coordination >= 0.8 | LOOP |
| 2 — Regulatory | compliance_exposure >= 0.85 | ELEVATED |
| 3 — Risky irreversible | reversibility >= 0.8 AND (impact >= 0.7 OR novelty >= 0.8) | ELEVATED |
| 4 — Safe auto | novelty <= 0.25 AND impact <= 0.3 AND reversibility <= 0.2 | AUTO |
| 5 — Low-risk fast | impact <= 0.2 AND novelty <= 0.2 AND reversibility <= 0.2 | FAST |

If no hard rule matches, use the Weighted Risk Index thresholds above.

---

## Normalized Dimension Weights

Used to compute the Weighted Risk Index (WRI). All dimensions sum to ≤1.0.

| Dimension | Weight |
|-----------|--------|
| impact | 0.24 |
| reversibility | 0.24 |
| novelty | 0.18 |
| coupling | 0.10 |
| data_risk | 0.06 |
| compliance_exposure | 0.05 |
| ux_surface | 0.03 |
| team_coordination | 0.03 |

WRI = Σ(dimension_value × weight) / Σ(weights)

---

## Specialist Discovery

Specialists are discovered at runtime from `specialist.json` files in each plugin.
Short names (e.g., `engineering`, `platform`) are matched against the
Signal-to-Specialist mapping above.

When specialists are unavailable, crew falls back to built-in agents per the
Fallback Agents table above.

---

## Cross-Reference

- Signal keywords per category: [signal-keywords.md](signal-keywords.md)
- Archetype scoring adjustments: [archetype-adjustments.md](archetype-adjustments.md)
- Risk dimension scoring: [risk-dimension-signals.md](risk-dimension-signals.md)
- Composite score formula: [scoring-rubric.md](scoring-rubric.md)
