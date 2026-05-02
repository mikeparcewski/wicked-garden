#!/usr/bin/env python3
"""
drift.py — quality-telemetry drift detection for wicked-garden.

Closes Issue #443: distinguish noise (common-cause) from signal (special-cause)
on the session-level quality timeline maintained by telemetry.py.

Algorithms
----------
1. Moving average (N=4 baseline window). Flags ``drop_pct`` when the current
   session's metric drops >15% below the baseline mean — the minimal viable
   alarm specified in the issue.
2. EWMA slope over the last ``ewma_window`` sessions with alpha=0.3. A
   monotonically negative slope across the smoothed points is reported as a
   trending degradation signal distinct from a single-point drop.
3. 3σ Western Electric zone-A rule (baseline mean ± 3 * baseline_stddev).
   Points outside 3σ are tagged ``special-cause``. Points outside 2σ are
   reported as ``warn`` (zone B). Everything else is ``common-cause`` noise.
4. Western Electric runs rules (issues #459, #719) beyond zone A:
   - ``2_of_3_zone_b``: 2 of the last 3 points are beyond 2σ on the bad side
     (below-baseline). Fires ``special-cause`` even when the latest point is
     inside zone A.
   - ``4_of_5_zone_c``: 4 of the last 5 points beyond 1σ on the bad side
     (issue #719). Catches sustained drift one zone closer to the mean.
   - ``8_consecutive_one_side``: 8 consecutive points all on the bad side of
     the mean (issue #719). Catches subtle but persistent bias.
   - ``trending_down``: 6 consecutive points each lower than the one before
     (monotonic degradation). Fires ``special-cause``.
   - ``trending_up``: symmetric monotonic climb. Reported but never flips
     ``drift`` — rising metrics on a "higher is better" axis are good news.
   These runs rules are additive — they OR with the zone-A sigma check.

Classification output
---------------------
    {
        "metric":     "gate_pass_rate",
        "latest":     0.55,
        "baseline":   {"mean": 0.88, "stddev": 0.06, "window": 4, "samples": [...]},
        "drop_pct":   0.375,        # 37.5% below baseline mean
        "ewma_slope": -0.018,       # negative slope = worsening
        "zone":       "special-cause" | "warn" | "common-cause" | "insufficient",
        "drift":      True,         # final decision: alarm should fire
        "reasons":    ["drop_pct 37.5% >= 15%", "outside 3σ"],
        "session_count": 5,
    }

Guardrails
----------
- Stdlib-only. Fail-open. No hard dependency on wicked-bus.
- Minimum-sample rule: require >= 5 sessions (issue acceptance criterion) before
  classifying anything as drift. Below that, return ``zone: "insufficient"``.
- "No new gate in response to common-cause variation" — we expose a helper
  ``is_actionable`` that returns True only for special-cause drift, so the
  caller (crew/status) can refuse to escalate on noise.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup — co-located with telemetry.py under scripts/delivery/
# ---------------------------------------------------------------------------

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

# Defaults — kept as module constants so callers can tune via kwargs.
DEFAULT_BASELINE_WINDOW = 4      # sessions preceding the latest one
DEFAULT_EWMA_WINDOW = 6
DEFAULT_EWMA_ALPHA = 0.3
DEFAULT_DROP_PCT_THRESHOLD = 0.15  # issue acceptance: 15% below 4-session baseline
DEFAULT_SPECIAL_CAUSE_SIGMA = 3.0  # Western Electric zone A
DEFAULT_WARN_SIGMA = 2.0           # zone B
DEFAULT_ZONE_C_SIGMA = 1.0         # zone C (issue #719)
MIN_SESSIONS_FOR_DRIFT = 5         # issue #459 acceptance
# Issue #719 acceptance: at least 8 samples before *any* WE rule may fire.
WARMUP_MIN_SAMPLES = 8

# Western Electric runs-rule thresholds (issues #459, #719).
# 2-of-3: "2 of the most recent 3 points beyond 2σ on the same side."
WE_2OF3_WINDOW = 3
WE_2OF3_COUNT = 2
# 4-of-5: "4 of the most recent 5 points beyond 1σ on the same side."
WE_4OF5_WINDOW = 5
WE_4OF5_COUNT = 4
# Run-of-8: "8 consecutive points on the same side of the centerline."
WE_RUN_OF_8_WINDOW = 8
# Trending: 6 consecutive monotonically increasing / decreasing points.
WE_TRENDING_WINDOW = 6


# ---------------------------------------------------------------------------
# Low-level statistics (stdlib only, deterministic)
# ---------------------------------------------------------------------------

def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stddev(xs: List[float]) -> float:
    """Population standard deviation. Returns 0 on fewer than 2 points."""
    if len(xs) < 2:
        return 0.0
    mu = _mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / len(xs))


def _ewma(xs: List[float], alpha: float = DEFAULT_EWMA_ALPHA) -> List[float]:
    """Return the EWMA series. Empty input → empty output."""
    out: List[float] = []
    prev: Optional[float] = None
    for x in xs:
        if prev is None:
            prev = x
        else:
            prev = alpha * x + (1 - alpha) * prev
        out.append(prev)
    return out


def _slope(xs: List[float]) -> float:
    """Simple linear regression slope with x = [0, 1, 2, ...]."""
    n = len(xs)
    if n < 2:
        return 0.0
    x = list(range(n))
    mx = _mean([float(i) for i in x])
    my = _mean(xs)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, xs))
    den = sum((xi - mx) ** 2 for xi in x)
    if den == 0:
        return 0.0
    return num / den


# ---------------------------------------------------------------------------
# Metric extraction from a timeline
# ---------------------------------------------------------------------------

def _pull_metric(records: List[Dict[str, Any]], metric: str) -> List[float]:
    """Extract a numeric metric series from the timeline, skipping missing."""
    out: List[float] = []
    for r in records:
        m = r.get("metrics") or {}
        v = m.get(metric)
        if isinstance(v, (int, float)):
            out.append(float(v))
    return out


# ---------------------------------------------------------------------------
# Western Electric runs rules (issue #459)
# ---------------------------------------------------------------------------

def _we_2_of_3_zone_b(
    series: List[float],
    mean: float,
    stddev: float,
    *,
    warn_sigma: float = DEFAULT_WARN_SIGMA,
) -> bool:
    """WE rule: 2 of the last 3 points beyond 2σ below the baseline mean.

    Requires at least 3 points and a non-zero baseline stddev. We only flag
    the "bad" (below-baseline) side — metrics like gate_pass_rate are
    higher-is-better. Callers with lower-is-better metrics should invert
    the series before passing it in.
    """
    if stddev <= 0:
        return False
    if len(series) < WE_2OF3_WINDOW:
        return False
    recent = series[-WE_2OF3_WINDOW:]
    # Point counts as "beyond 2σ on the bad side" when it sits at least
    # warn_sigma standard deviations below the baseline mean.
    threshold = mean - warn_sigma * stddev
    breaches = sum(1 for x in recent if x < threshold)
    return breaches >= WE_2OF3_COUNT


def _we_4_of_5_zone_c(
    series: List[float],
    mean: float,
    stddev: float,
    *,
    side: str = "below",
    zone_c_sigma: float = DEFAULT_ZONE_C_SIGMA,
) -> bool:
    """WE rule (#719): 4 of the last 5 points beyond 1σ on one side of the baseline.

    ``side`` mirrors ``_we_8_consecutive_one_side``: "below" (default — the
    bad side for higher-is-better metrics) or "above". Requires non-zero
    baseline stddev and at least ``WE_4OF5_WINDOW`` observations.
    """
    if stddev <= 0:
        return False
    if len(series) < WE_4OF5_WINDOW:
        return False
    recent = series[-WE_4OF5_WINDOW:]
    if side == "above":
        threshold = mean + zone_c_sigma * stddev
        breaches = sum(1 for x in recent if x > threshold)
    else:
        threshold = mean - zone_c_sigma * stddev
        breaches = sum(1 for x in recent if x < threshold)
    return breaches >= WE_4OF5_COUNT


def _we_8_consecutive_one_side(
    series: List[float],
    mean: float,
    *,
    side: str = "below",
) -> bool:
    """WE rule (#719): 8 consecutive points on one side of the centerline.

    ``side="below"`` is the bad side for higher-is-better metrics.
    Equality with the mean does not count — SPC theory requires strict
    one-sided runs to indicate a process shift.
    """
    if len(series) < WE_RUN_OF_8_WINDOW:
        return False
    window = series[-WE_RUN_OF_8_WINDOW:]
    if side == "below":
        return all(x < mean for x in window)
    if side == "above":
        return all(x > mean for x in window)
    return False


def _we_trending(series: List[float], direction: str = "down") -> bool:
    """WE rule: 6 consecutive points moving monotonically.

    ``direction`` is "down" (each point strictly less than the previous) or
    "up" (strictly greater). Flat runs (equal values) do NOT count — SPC
    theory requires strict monotonicity for a trend signal.
    """
    if len(series) < WE_TRENDING_WINDOW:
        return False
    window = series[-WE_TRENDING_WINDOW:]
    if direction == "down":
        return all(window[i] < window[i - 1] for i in range(1, len(window)))
    if direction == "up":
        return all(window[i] > window[i - 1] for i in range(1, len(window)))
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(
    records: List[Dict[str, Any]],
    metric: str = "gate_pass_rate",
    *,
    baseline_window: int = DEFAULT_BASELINE_WINDOW,
    ewma_window: int = DEFAULT_EWMA_WINDOW,
    drop_pct_threshold: float = DEFAULT_DROP_PCT_THRESHOLD,
    special_cause_sigma: float = DEFAULT_SPECIAL_CAUSE_SIGMA,
    warn_sigma: float = DEFAULT_WARN_SIGMA,
    min_sessions: int = MIN_SESSIONS_FOR_DRIFT,
) -> Dict[str, Any]:
    """Classify the latest point against its baseline.

    Returns a dict with fields documented in the module docstring. Always
    returns a dict — never raises. Missing metric → ``zone: insufficient``.
    """
    series = _pull_metric(records, metric)
    session_count = len(series)

    result: Dict[str, Any] = {
        "metric": metric,
        "session_count": session_count,
        "latest": series[-1] if series else None,
        "baseline": None,
        "drop_pct": None,
        "ewma_slope": None,
        "zone": "insufficient",
        "drift": False,
        "reasons": [],
    }

    if session_count < min_sessions:
        result["reasons"].append(
            f"need >= {min_sessions} sessions, have {session_count}"
        )
        return result

    # Baseline: the N sessions immediately preceding the latest.
    baseline = series[-(baseline_window + 1):-1] if baseline_window < session_count else series[:-1]
    if not baseline:
        result["reasons"].append("no baseline samples available")
        return result

    mu = _mean(baseline)
    sigma = _stddev(baseline)
    latest = series[-1]
    result["baseline"] = {
        "mean": round(mu, 6),
        "stddev": round(sigma, 6),
        "window": len(baseline),
        "samples": [round(x, 6) for x in baseline],
    }

    # Moving-average deviation (issue acceptance: >15% drop).
    if mu > 0:
        drop_pct = (mu - latest) / mu  # positive ⇒ latest is below baseline
    elif mu == 0 and latest < 0:
        drop_pct = 1.0
    else:
        drop_pct = 0.0
    result["drop_pct"] = round(drop_pct, 6)

    # 3σ classification.
    if sigma > 0:
        z = (mu - latest) / sigma
    else:
        # Flat baseline: any delta is instantly "special-cause" in SPC theory,
        # but we soften: require drop_pct threshold *and* a non-zero delta.
        z = math.inf if latest < mu else 0.0

    # EWMA slope over the last ewma_window points.
    window_series = series[-ewma_window:] if len(series) >= ewma_window else series
    ewma_series = _ewma(window_series)
    slope = _slope(ewma_series)
    result["ewma_slope"] = round(slope, 6)

    # Zone classification (zone-A sigma test).
    # Surface structured fields so _classify_rule doesn't have to substring-match
    # the human-readable reasons text (Copilot review on PR #730).
    result["outside_special_cause_sigma"] = z >= special_cause_sigma
    result["special_cause_sigma_threshold"] = special_cause_sigma
    if z >= special_cause_sigma:
        zone = "special-cause"
        result["reasons"].append(f"outside {special_cause_sigma:.0f}σ (z={z:.2f})")
    elif z >= warn_sigma:
        zone = "warn"
        result["reasons"].append(f"outside {warn_sigma:.0f}σ (z={z:.2f})")
    else:
        zone = "common-cause"

    # Western Electric runs rules (issues #459, #719) — operate on the full
    # observed series using the baseline mean/stddev as the reference frame.
    # Issue #719 acceptance: at least WARMUP_MIN_SAMPLES observations before
    # *any* WE rule may fire, regardless of which rule is configured. Below
    # warmup we still classify zone-A from the latest z-score, but suppress
    # WE flags entirely. ``insufficient_warmup`` lets callers tell "below
    # warmup" apart from "warm but quiet".
    we_rules: List[str] = []
    insufficient_warmup = session_count < WARMUP_MIN_SAMPLES
    result["insufficient_warmup"] = insufficient_warmup
    result["warmup_min_samples"] = WARMUP_MIN_SAMPLES

    if not insufficient_warmup:
        if _we_2_of_3_zone_b(series, mu, sigma, warn_sigma=warn_sigma):
            we_rules.append("2_of_3_zone_b")
            result["reasons"].append(
                f"WE 2-of-3: 2+ of last {WE_2OF3_WINDOW} points beyond "
                f"{warn_sigma:.0f}σ below baseline"
            )
        if _we_4_of_5_zone_c(series, mu, sigma):
            we_rules.append("4_of_5_zone_c")
            result["reasons"].append(
                f"WE 4-of-5: 4+ of last {WE_4OF5_WINDOW} points beyond "
                f"{DEFAULT_ZONE_C_SIGMA:.0f}σ below baseline"
            )
        if _we_8_consecutive_one_side(series, mu, side="below"):
            we_rules.append("8_consecutive_one_side")
            result["reasons"].append(
                f"WE run-of-8: {WE_RUN_OF_8_WINDOW} consecutive points below baseline mean"
            )
        if _we_trending(series, direction="down"):
            we_rules.append("trending_down")
            result["reasons"].append(
                f"WE trending-down: {WE_TRENDING_WINDOW} consecutive decreasing points"
            )
        if _we_trending(series, direction="up"):
            we_rules.append("trending_up")
            result["reasons"].append(
                f"WE trending-up: {WE_TRENDING_WINDOW} consecutive increasing points"
            )
    else:
        result["reasons"].append(
            f"warmup gate: need {WARMUP_MIN_SAMPLES} samples for WE rules, "
            f"have {session_count}"
        )
    result["we_rules"] = we_rules

    # Any "bad-side" WE runs rule escalates zone to special-cause.
    # trending_up is informational only (higher-is-better metrics).
    bad_side_rules = {"2_of_3_zone_b", "4_of_5_zone_c", "8_consecutive_one_side", "trending_down"}
    if any(r in bad_side_rules for r in we_rules):
        zone = "special-cause"

    # Drift alarm: >=15% drop below baseline OR special-cause zone.
    # Issue #719 acceptance: gate all flags behind WARMUP_MIN_SAMPLES so we
    # don't fire on a freshly-onboarded project's first noisy week. The
    # existing ``min_sessions`` (default 5) is the *classification* floor; the
    # warmup gate is the *flag* floor.
    drift = False
    if drop_pct >= drop_pct_threshold:
        result["reasons"].append(
            f"drop_pct {drop_pct * 100:.1f}% >= {drop_pct_threshold * 100:.0f}%"
        )
        if not insufficient_warmup:
            drift = True
    if zone == "special-cause" and not insufficient_warmup:
        drift = True

    # Trending degradation: EWMA slope meaningfully negative.
    if slope < -0.01 and len(ewma_series) >= 3:
        result["reasons"].append(f"ewma_slope {slope:.4f} trending down")
        # Trending slope alone does not flip drift=True unless combined with
        # a drop or special-cause — slope is advisory context.

    result["zone"] = zone
    result["drift"] = drift
    return result


def is_actionable(classification: Dict[str, Any]) -> bool:
    """Should the caller escalate (e.g. add a gate, alert a user)?

    Issue acceptance: "No new process gate added in response to common-cause
    variation." Actionable = special-cause OR drop_pct breach — both
    unambiguous signal, not noise.
    """
    if not classification:
        return False
    if classification.get("zone") == "special-cause":
        return True
    drop = classification.get("drop_pct") or 0
    if drop >= DEFAULT_DROP_PCT_THRESHOLD:
        return True
    return False


def summarize(classification: Dict[str, Any]) -> str:
    """Render a one-line human summary for status output."""
    if not classification:
        return "no telemetry data"
    zone = classification.get("zone", "unknown")
    metric = classification.get("metric", "metric")
    latest = classification.get("latest")
    base = classification.get("baseline") or {}
    mu = base.get("mean")
    drop = classification.get("drop_pct")
    latest_s = "n/a" if latest is None else f"{latest:.3f}"
    mu_s = "n/a" if mu is None else f"{mu:.3f}"
    drop_s = "n/a" if drop is None else f"{drop * 100:+.1f}%"
    if zone == "insufficient":
        return f"{metric}: insufficient data ({classification.get('session_count', 0)} sessions)"
    label = {
        "special-cause": "SIGNAL",
        "warn": "watch",
        "common-cause": "noise",
    }.get(zone, zone)
    return f"{metric}: latest={latest_s} baseline={mu_s} delta={drop_s} [{label}]"


# ---------------------------------------------------------------------------
# Bus emission (fail-open)
# ---------------------------------------------------------------------------

def emit_drift_event(
    project: str,
    classification: Dict[str, Any],
) -> bool:
    """Emit a wicked-bus drift event if the classification is actionable.

    Returns True if emission was attempted (bus may have been unavailable),
    False if the classification didn't warrant emission.
    Never raises.
    """
    try:
        if not is_actionable(classification):
            return False
        # Import lazily so drift.py remains importable without the bus shim.
        from _bus import emit_event  # type: ignore
        payload = {
            "project": project,
            "metric": classification.get("metric"),
            "zone": classification.get("zone"),
            "latest": classification.get("latest"),
            "baseline_mean": (classification.get("baseline") or {}).get("mean"),
            "baseline_stddev": (classification.get("baseline") or {}).get("stddev"),
            "drop_pct": classification.get("drop_pct"),
            "ewma_slope": classification.get("ewma_slope"),
            "reasons": classification.get("reasons"),
            "session_count": classification.get("session_count"),
        }
        emit_event("wicked.quality.drift_detected", payload)
        return True
    except Exception as exc:
        # Fail-open — bus absence must never break telemetry.
        print(f"[wicked-garden] drift emit error: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# SPC flag emission via DomainStore (issue #719)
# ---------------------------------------------------------------------------

# Critical = zone-A (3σ) breach or 8-in-a-row run; warn = lesser WE rules
# or simple drop_pct trigger. Severity drives downstream alert routing.
_CRITICAL_RULES = {"1_outside_3sigma", "8_consecutive_one_side"}


def _classify_rule(classification: Dict[str, Any]) -> List[str]:
    """Return all rule identifiers that fired for this classification.

    A single classification can fire multiple rules — emit one flag per rule
    so downstream consumers can deduplicate by (metric, rule) instead of
    forcing the priority decision here.
    """
    rules = list(classification.get("we_rules") or [])
    # Synthesize a rule id for the zone-A z-score breach using the structured
    # field set by classify() — substring-matching the reasons text was brittle
    # against tuned ``special_cause_sigma`` (e.g. "z=4.2" matches "3" by accident).
    if classification.get("outside_special_cause_sigma"):
        if "1_outside_3sigma" not in rules:
            rules.append("1_outside_3sigma")
    drop = classification.get("drop_pct") or 0.0
    if drop >= DEFAULT_DROP_PCT_THRESHOLD and not rules:
        rules.append("drop_pct_threshold")
    # Strip informational-only rules from emission set.
    return [r for r in rules if r != "trending_up"]


def emit_spc_flag(
    project: str,
    classification: Dict[str, Any],
    *,
    metric: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Persist one ``delivery:spc:flag`` record per fired rule.

    Returns the list of payloads written (empty when nothing fired or warmup
    blocks emission). Never raises — DomainStore failures are logged to stderr.
    """
    if classification.get("insufficient_warmup"):
        return []
    if not classification.get("drift"):
        return []
    rules = _classify_rule(classification)
    if not rules:
        return []

    metric_name = metric or classification.get("metric") or "unknown"
    base = classification.get("baseline") or {}
    samples = base.get("samples") or []
    sample_window = {
        "start": samples[0] if samples else None,
        "end": classification.get("latest"),
        "n": classification.get("session_count"),
    }
    written: List[Dict[str, Any]] = []
    try:
        from _domain_store import DomainStore  # type: ignore
        ds = DomainStore("delivery", hook_mode=True)
    except Exception as exc:  # pragma: no cover — DomainStore is plugin core
        print(f"[wicked-garden] spc flag store error: {exc}", file=sys.stderr)
        return []

    for rule in rules:
        payload = {
            "project": project,
            "metric": metric_name,
            "rule": rule,
            "severity": "critical" if rule in _CRITICAL_RULES else "warn",
            "sample_window": sample_window,
            "current_value": classification.get("latest"),
            "baseline_mean": base.get("mean"),
            "baseline_stddev": base.get("stddev"),
            "drop_pct": classification.get("drop_pct"),
            "reasons": classification.get("reasons"),
            "recorded_at": _utc_iso_now(),
        }
        try:
            rec = ds.create("spc", payload)
            if rec is not None:
                written.append(rec)
        except Exception as exc:  # pragma: no cover
            print(f"[wicked-garden] spc flag write error: {exc}", file=sys.stderr)
    return written


def _utc_iso_now() -> str:
    """Local helper — drift.py is otherwise time-free, so import datetime here."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def list_recent_flags(
    project: str,
    *,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Return recent SPC flags for a project, newest first. Fail-open."""
    try:
        from _domain_store import DomainStore  # type: ignore
        ds = DomainStore("delivery", hook_mode=True)
        flags = ds.list("spc", project=project) or []
    except Exception:
        return []
    flags.sort(key=lambda r: r.get("recorded_at") or "", reverse=True)
    return flags[:limit] if limit and limit > 0 else flags


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_classify(args: List[str]) -> int:
    if not args:
        print(json.dumps({"ok": False, "reason": "project required"}))
        return 0
    project = args[0]
    metric = args[1] if len(args) > 1 else "gate_pass_rate"
    try:
        from delivery.telemetry import read_timeline  # type: ignore
    except Exception:
        # When invoked via direct path, the delivery package import may not
        # be on sys.path. Fall back to relative import.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from telemetry import read_timeline  # type: ignore
    records = read_timeline(project)
    cls = classify(records, metric)
    print(json.dumps({
        "ok": True,
        "project": project,
        "metric": metric,
        "classification": cls,
        "summary": summarize(cls),
        "actionable": is_actionable(cls),
    }, indent=2))
    return 0


def _cli_emit(args: List[str]) -> int:
    """Classify + conditionally emit bus event. Used by hooks."""
    if not args:
        print(json.dumps({"ok": False, "reason": "project required"}))
        return 0
    project = args[0]
    metric = args[1] if len(args) > 1 else "gate_pass_rate"
    try:
        from delivery.telemetry import read_timeline  # type: ignore
    except Exception:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from telemetry import read_timeline  # type: ignore
    cls = classify(read_timeline(project), metric)
    emitted = emit_drift_event(project, cls)
    print(json.dumps({
        "ok": True,
        "emitted": emitted,
        "actionable": is_actionable(cls),
        "classification": cls,
    }))
    return 0


def _cli_flag(args: List[str]) -> int:
    """Classify and persist any SPC flags via DomainStore. Used by /delivery:health."""
    if not args:
        print(json.dumps({"ok": False, "reason": "project required"}))
        return 0
    project = args[0]
    metric = args[1] if len(args) > 1 else "gate_pass_rate"
    try:
        from delivery.telemetry import read_timeline  # type: ignore
    except Exception:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from telemetry import read_timeline  # type: ignore
    cls = classify(read_timeline(project), metric)
    flags = emit_spc_flag(project, cls, metric=metric)
    print(json.dumps({
        "ok": True,
        "project": project,
        "metric": metric,
        "classification": cls,
        "flags_written": flags,
    }))
    return 0


def _cli_list_flags(args: List[str]) -> int:
    if not args:
        print(json.dumps({"ok": False, "reason": "project required"}))
        return 0
    project = args[0]
    limit = 20
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            limit = 20
    flags = list_recent_flags(project, limit=limit)
    print(json.dumps({"ok": True, "project": project, "flags": flags}))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "Usage:\n"
            "  drift.py classify <project> [metric]\n"
            "  drift.py emit <project> [metric]\n"
            "  drift.py flag <project> [metric]\n"
            "  drift.py list-flags <project> [limit]\n",
            file=sys.stderr,
        )
        return 0
    cmd = argv[0]
    rest = argv[1:]
    if cmd == "classify":
        return _cli_classify(rest)
    if cmd == "emit":
        return _cli_emit(rest)
    if cmd == "flag":
        return _cli_flag(rest)
    if cmd == "list-flags":
        return _cli_list_flags(rest)
    print(json.dumps({"ok": False, "reason": f"unknown command: {cmd}"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
