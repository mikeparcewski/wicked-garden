# risk_level Translation Table

## The Problem

`Reading` uses counter-intuitive direction: HIGH = safest, LOW = riskiest.
This is calibrated against factor-definitions.md where HIGH reading = best outcome.
Downstream consumers (display, reporting, gate logic) expecting standard risk language
would invert the meaning — HIGH normally means more dangerous.

## The Fix

`score_all` now emits a `risk_level` field alongside `reading`:

| Reading | risk_level    | User-facing language         |
|---------|--------------|------------------------------|
| HIGH    | low_risk     | Low risk / safe to proceed   |
| MEDIUM  | medium_risk  | Moderate risk / review       |
| LOW     | high_risk    | High risk / elevated scrutiny|

## Backward Compatibility

`reading` field is unchanged. All existing consumers continue to work.
`risk_level` is additive.

## Usage Guidance (from SKILL.md)

When displaying factor results to users, prefer `risk_level`:

```
scope_effort: medium_risk (MEDIUM)  ← human-readable direction
```

rather than:

```
scope_effort: MEDIUM  ← direction ambiguous to new readers
```

Internal scoring logic (threshold comparisons) should continue using `reading`
since all calibration tables and factor-definitions.md use HIGH/MEDIUM/LOW.
