# SPC Drift Detection — Chart-Reading Guide

This document explains the Statistical Process Control (SPC) drift detection that wicked-garden runs over the gate-quality timeline. It is written for engineers and tech leads, not statisticians.

## What problem this solves

Quality regressions rarely arrive as a single catastrophic session. They creep in across a week or two of small drops, each one inside the normal range. By the time the latest score is obviously bad, the regression has been compounding for many sessions. SPC catches that drift early using a small set of well-studied rules from manufacturing quality control (Western Electric, 1956).

## Where to look

```
/wicked-garden:delivery:process-health --project <name> --spc
```

The `--spc` section reports:

- **Sample count** vs. the warmup threshold (currently 8). No flags fire below warmup.
- **Classifications** for the headline `gate_pass_rate` and any per-`(phase, tier)` `min_score` series with enough history.
- **Recent flags** persisted to the `delivery:spc:flag` source in the DomainStore — newest first, with rule, severity, sample window, and the value that tripped it.

You can also drive the underlying script directly:

```
sh scripts/_python.sh scripts/delivery/drift.py classify <project> [metric]
sh scripts/_python.sh scripts/delivery/drift.py flag <project> [metric]    # persists flags
sh scripts/_python.sh scripts/delivery/drift.py list-flags <project>
```

## EWMA in plain English

EWMA stands for **Exponentially Weighted Moving Average**. It is a smoothed line through your raw data that gives the most recent points more weight than older ones (alpha = 0.3 — the most recent point counts ~30% toward the smoothed value, and the rest fades over the previous samples).

Why use it instead of a plain average? A plain average treats a sudden cliff and a gradual slide the same way. EWMA reacts faster to change, which is exactly what you want for drift detection. We report the **slope** of the EWMA series — a meaningfully negative slope is advisory context that the trend is downward.

## The four Western Electric rules

All four rules look at the timeline relative to a baseline `(mean, stddev)` computed from the four sessions immediately before the latest one.

### Rule (a) — 1 point outside 3σ (`1_outside_3sigma`)

> The most recent point is more than three standard deviations below the baseline mean.

**What it catches:** a single session that is unambiguously broken. A point this far out is approximately a 1-in-700 event under normal variation — almost always a real signal.

**Severity:** `critical`.

### Rule (b) — 2 of 3 outside 2σ on the same side (`2_of_3_zone_b`)

> Of the most recent three points, at least two are more than two standard deviations below the baseline mean.

**What it catches:** the process is starting to live in the bad-tail of normal variation. One outlier is noise; two of the last three is signal.

**Severity:** `warn`.

### Rule (c) — 4 of 5 outside 1σ on the same side (`4_of_5_zone_c`)

> Of the most recent five points, at least four are more than one standard deviation below the baseline mean.

**What it catches:** sustained mediocrity. The points haven't crossed any dramatic line individually, but four-of-five sitting on the bad side of the first sigma band means the process has drifted closer to its lower control limit.

**Severity:** `warn`.

### Rule (d) — 8 in a row on one side of the mean (`8_consecutive_one_side`)

> The most recent eight points are all below the baseline mean.

**What it catches:** a subtle but persistent bias. None of the points have to be unusual on their own — eight consecutive coin flips landing the same way is roughly a 1-in-256 event, so eight points all on one side of the mean strongly suggests the underlying process has shifted, not that you got unlucky.

**Severity:** `critical`.

### Bonus rule — 6 consecutive monotonically decreasing (`trending_down`)

This one is from the broader SPC literature, not the original Western Electric set, but it shipped with the v1 detector for issue #459 and remains. It catches a strict downward staircase — useful when degradation is gradual but unmistakable.

## How to read a flag

A flag record looks like:

```json
{
  "id": "...",
  "metric": "gate_pass_rate",
  "rule": "4_of_5_zone_c",
  "severity": "warn",
  "sample_window": {"start": 0.91, "end": 0.62, "n": 12},
  "current_value": 0.62,
  "baseline_mean": 0.85,
  "baseline_stddev": 0.06,
  "drop_pct": 0.27,
  "reasons": ["WE 4-of-5: 4+ of last 5 points beyond 1σ below baseline", "..."],
  "recorded_at": "2026-04-29T12:34:56Z"
}
```

Reading order:

1. **`metric` + `rule`** — what dropped, and which rule caught it.
2. **`baseline_mean` vs. `current_value`** — how far the latest reading is from the recent norm.
3. **`drop_pct`** — the same comparison as a percentage, easier for non-statistical readers.
4. **`severity`** — `critical` warrants immediate triage; `warn` warrants attention by end of week.
5. **`reasons`** — the human-readable trail of every check that fired.
6. **`sample_window.n`** — sanity check that you have enough history to trust the call.

## Warmup gate

No SPC flag fires until the project has at least 8 sessions of telemetry. This prevents:

- Freshly-onboarded projects from spamming flags during their first noisy week.
- A trivial 5-session baseline producing wildly different `mean ± stddev` figures from one session to the next.

The `--spc` report shows `Warmup: PENDING` when below the threshold and `Warmup: satisfied` once you cross it.

## Silencing noise

If a metric you don't care about is producing flags, you have a few levers:

- **Don't query it.** Only `gate_pass_rate` is auto-classified by `process-health --spc`. Per-(phase, tier) `min_score` series only appear when the project has accumulated at least 5 sessions of that exact slot.
- **Re-baseline.** Flags persist in the DomainStore. Once you've addressed the underlying regression, archive old flag records — they continue to show up in `list-flags` until soft-deleted.
- **Tune thresholds at the call site.** `drift.classify(records, metric, drop_pct_threshold=0.20, special_cause_sigma=4.0)` accepts overrides. The defaults match the issue acceptance criteria; tune them for your team's tolerance.
- **Investigate before silencing.** A flag that "always fires" usually means the metric is genuinely unstable, not that the rule is wrong. Look at the underlying timeline (`scripts/delivery/telemetry.py show <project>`) before you tune the alarm down.

## Related

- `scripts/delivery/drift.py` — the classifier implementation.
- `scripts/delivery/telemetry.py` — the per-session capture that feeds the timeline.
- `commands/delivery/process-health.md` — the `--spc` surface.
- `scenarios/delivery/07-spc-drift-detected.md`, `scenarios/delivery/08-spc-stable-no-flag.md` — positive and negative scenarios.
- Issue #719 — original specification.
