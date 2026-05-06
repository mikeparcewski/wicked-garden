"""scripts/_heavy_cadence.py — session-end heavy cadence work + 60-min stop fallback.

Provenance: v9.2.15 redesign of stop.py per-turn cadence. Pre-fix, four heavy
functions ran on EVERY Stop hook (per turn end):

  - _run_memory_decay        (brain `lint`)
  - _run_working_consolidation (brain `compile` + `lint`, 10s heaviest call)
  - _run_quality_telemetry   (timeline.jsonl append + drift bus event)
  - _run_guard_pipeline      (scalpel/standard profile + findings.json + bus)

Per-turn cadence costs:
  ~90 brain HTTP calls per 30-turn session  (vs 3 if session-end-scoped)
  30 timeline.jsonl appends                 (vs 1)
  30 findings.json overwrites               (vs 1; mid-session signal lost)
  4-session drift baseline → 4-turn baseline (CORRECTNESS BUG, not just perf)

The v9.2.11 audit + v9.2.15 quick brainstorm settled on Option C (hybrid):
  - SessionEnd hook is the primary cadence (new in this PR — was unwired).
  - stop.py keeps a 60-min time-gated fallback for the partial-session
    failure mode (CLI killed, network drop, user walks away — SessionEnd
    never fires).

A sidecar file at <local store>/wicked-garden/heavy-cadence/last_run.json
records `last_heavy_run_ts` + `trigger` so the Stop fallback is deterministic.
SessionState is per-session (resets on new session), so it can't gate cross-
session fallback — sidecar is the right persistence boundary.

Brain calls themselves are unchanged. Only WHEN they fire changed.

v9.2.15 council mitigation (3-of-4 reviewers cited TOCTOU race as top risk):
sidecar writes use the write-temp-then-os.replace pattern instead of bare
write_text. os.replace is atomic on both POSIX and Windows, so two parallel
Stop calls passing the should_run_fallback() check simultaneously cannot
produce a corrupt sidecar JSON. The heavy operations themselves are
idempotent (per the inventory), so duplicate runs waste work but don't
corrupt state.

R1: no dead code — every helper is called from main flow + tests.
R3: constants named (FALLBACK_INTERVAL_SECS, SIDECAR_FILENAME).
R5: subprocess-free in module body (subprocess only via _brain_api).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# 60-minute fallback interval. Picked because:
#  - Long enough that a normal multi-turn session never crosses it (typical
#    "I'm doing real work" sessions complete in <30 min and SessionEnd fires).
#  - Short enough that abruptly-killed sessions get caught up the next time
#    a Stop fires after the user resumes work — no >1hr gap in decay/
#    consolidation activity.
#  - Same magnitude as wicked-brain's own stale-content thresholds so brain
#    decay decisions remain timely even under fallback.
FALLBACK_INTERVAL_SECS: int = 60 * 60

SIDECAR_DIR_NAME: str = "heavy-cadence"
SIDECAR_FILENAME: str = "last_run.json"

# Trigger strings recorded in the sidecar — surfaced in observability if we
# ever need to debug "why did decay fire here". Not load-bearing for behavior.
TRIGGER_SESSION_END: str = "session_end"
TRIGGER_STOP_FALLBACK: str = "stop_fallback"


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sidecar_path() -> Optional[Path]:
    """Resolve the per-project sidecar file path. None on resolution failure.

    Per-project automatic because get_local_path("wicked-garden", ...) is
    scoped under the active project's slug. A user with multiple projects
    gets one sidecar per project — fallback gating is correctly isolated.
    """
    try:
        from _domain_store import get_local_path  # type: ignore
        return get_local_path("wicked-garden", SIDECAR_DIR_NAME) / SIDECAR_FILENAME
    except Exception:
        return None


def _read_sidecar() -> dict:
    """Return the sidecar dict or {} if missing/corrupt. Best-effort, no raise."""
    p = _sidecar_path()
    if p is None or not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_sidecar(trigger: str, session_id: Optional[str] = None) -> None:
    """Record `last_heavy_run_ts` + trigger. Best-effort, no raise.

    Atomic write via temp-file + os.replace (v9.2.15 council mitigation,
    3-of-4 reviewers cited TOCTOU race as top risk):

      1. Write payload to `<sidecar>.tmp.<pid>` (PID disambiguates parallel
         writers — two processes won't clobber each other's temp files).
      2. `os.replace(tmp, sidecar)` — atomic on both POSIX and Windows.
         Either the old sidecar OR the new sidecar is observable by any
         concurrent reader; never a half-written file.

    Heavy operations are idempotent (decay is set-difference, compile is
    deterministic given input chunks, telemetry appends are tagged with
    session_id, guard overwrites a session-scoped findings file), so two
    parallel runs waste work but cannot corrupt domain state.
    """
    p = _sidecar_path()
    if p is None:
        return
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "last_heavy_run_ts": _utc_iso_now(),
            "trigger": trigger,
            "session_id": session_id or "",
        })
        # PID-disambiguated temp path so two parallel writers don't collide
        # on the same temp file before either calls os.replace.
        tmp = p.with_name(f"{p.name}.tmp.{os.getpid()}")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        # Best-effort cleanup of orphaned temp file. Failure to clean up is
        # not load-bearing — the next successful write displaces it.
        try:
            tmp.unlink(missing_ok=True)  # type: ignore[name-defined]
        except (NameError, OSError):
            pass


def should_run_fallback(now_ts: Optional[float] = None) -> bool:
    """Return True if Stop should run the heavy cadence as a fallback.

    Triggers True when:
      - sidecar file missing (first run ever for this project)
      - sidecar exists but `last_heavy_run_ts` is unparseable
      - last run was more than FALLBACK_INTERVAL_SECS ago

    Defaults False when the sidecar is fresh — most Stop calls are per-turn
    and should NOT trigger heavy work.
    """
    data = _read_sidecar()
    raw_ts = data.get("last_heavy_run_ts")
    if not raw_ts:
        return True  # never run — fire fallback to seed the sidecar
    try:
        last_dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return True  # corrupt timestamp — treat as never-run
    now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc) if now_ts else datetime.now(timezone.utc)
    elapsed = (now_dt - last_dt).total_seconds()
    return elapsed >= FALLBACK_INTERVAL_SECS


def run_heavy_cadence(trigger: str, session_id: Optional[str] = None,
                       plugin_root: Optional[Path] = None) -> List[str]:
    """Run all four heavy functions + record the run in the sidecar.

    Used by:
      - hooks/scripts/session_end.py (primary, trigger=session_end)
      - hooks/scripts/stop.py (fallback when should_run_fallback() True,
        trigger=stop_fallback)

    Returns aggregated message strings (decay + consolidation + telemetry +
    guard) suitable for a systemMessage emit. Each underlying function fails
    open — a brain outage doesn't block the others.
    """
    if plugin_root is None:
        # Default — used when called from a hook. Tests pass plugin_root.
        plugin_root = Path(__file__).resolve().parents[1]

    messages: List[str] = []
    messages.extend(_run_memory_consolidation(plugin_root))
    messages.extend(_run_memory_decay(plugin_root))
    messages.extend(_run_quality_telemetry(plugin_root, session_id or ""))
    messages.extend(_run_guard_pipeline(plugin_root))

    _write_sidecar(trigger, session_id=session_id)
    return messages


# ---------------------------------------------------------------------------
# The four heavy functions — extracted from stop.py and unchanged in behavior.
# Brain APIs called identically; what changed is only WHEN they fire.
# ---------------------------------------------------------------------------

def _brain_api_call(plugin_root: Path, action: str, params: dict, timeout: int = 5):
    """Lightweight brain HTTP wrapper — same shape as stop.py::_brain_api but
    importable without pulling in stop.py's hook-specific dependencies.
    """
    try:
        sys.path.insert(0, str(plugin_root / "scripts"))
        from _brain_port import resolve_port
        import urllib.request
        import urllib.error

        port = resolve_port()
        url = f"http://localhost:{port}/api/{action}"
        data = json.dumps(params or {}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _run_memory_decay(plugin_root: Path) -> List[str]:
    """Run decay maintenance via brain lint API. Idempotent."""
    messages: List[str] = []
    try:
        result = _brain_api_call(plugin_root, "lint", {}, timeout=5)
        if result and (result.get("archived", 0) > 0 or result.get("deleted", 0) > 0):
            messages.append(
                f"[Memory] Decay: {result.get('archived', 0)} archived, {result.get('deleted', 0)} cleaned"
            )
    except Exception as e:
        print(f"[wicked-garden] decay error: {e}", file=sys.stderr)
    return messages


def _run_memory_consolidation(plugin_root: Path) -> List[str]:
    """Consolidate working-tier memories via brain compile + lint.

    Heaviest call in the cadence (10s timeout on compile). Idempotent —
    same chunks won't re-synthesize the same wiki article.
    """
    messages: List[str] = []
    try:
        compile_result = _brain_api_call(plugin_root, "compile", {}, timeout=10)
        lint_result = _brain_api_call(plugin_root, "lint", {}, timeout=5)
        compiled = compile_result.get("compiled", 0) if compile_result else 0
        cleaned = lint_result.get("deleted", 0) if lint_result else 0
        if compiled > 0 or cleaned > 0:
            messages.append(
                f"[Memory] Consolidation: {compiled} compiled, {cleaned} cleaned"
            )
    except Exception as e:
        print(f"[wicked-garden] consolidation error: {e}", file=sys.stderr)
    return messages


def _run_quality_telemetry(plugin_root: Path, session_id: str) -> List[str]:
    """Append a timeline record + detect drift. Returns any messages.

    Per-session-end cadence is REQUIRED for correctness — per-turn capture
    inflates timeline.jsonl 30x and reduces the 4-session drift baseline to
    a 4-turn baseline (signal dilution).
    """
    messages: List[str] = []
    try:
        sys.path.insert(0, str(plugin_root / "scripts" / "delivery"))
        import telemetry as _telemetry  # type: ignore
        import drift as _drift  # type: ignore

        record = _telemetry.capture_session(session_id)
        if record is None:
            return messages

        project = record.get("project") or "_global"
        records = _telemetry.read_timeline(project)
        cls = _drift.classify(records)
        emitted = _drift.emit_drift_event(project, cls)
        if cls.get("drift"):
            messages.append(
                f"[Telemetry] Drift detected for {project}: " + _drift.summarize(cls)
                + (" (emitted to wicked-bus)" if emitted else "")
            )
        elif cls.get("zone") == "warn":
            messages.append(
                f"[Telemetry] Watch signal for {project}: " + _drift.summarize(cls)
            )
    except Exception as e:
        print(f"[wicked-garden] telemetry error: {e}", file=sys.stderr)
    return messages


def _run_guard_pipeline(plugin_root: Path) -> List[str]:
    """Run the autonomous session-close guard pipeline.

    Writes findings.json (consumed by next-session bootstrap briefing) and
    emits wicked.guard.findings on the bus. Per-session-end cadence avoids
    overwriting mid-session findings before bootstrap can read them.
    """
    try:
        sys.path.insert(0, str(plugin_root / "scripts" / "platform"))
        from guard_pipeline import (  # type: ignore
            run_pipeline, write_briefing_file, emit_findings_event, render_summary,
        )
    except Exception as exc:
        print(f"[wicked-garden] guard pipeline unavailable: {exc}", file=sys.stderr)
        return []

    try:
        build_just_closed = False
        try:
            sys.path.insert(0, str(plugin_root / "scripts"))
            from _session import SessionState  # type: ignore
            state = SessionState.load()
            build_just_closed = bool(getattr(state, "last_phase_approved", None) == "build")
        except Exception:
            pass

        report = run_pipeline(build_phase_just_closed=build_just_closed)
        write_briefing_file(report)
        emit_findings_event(report)

        if report.total_findings > 0 or report.status != "ok":
            return [render_summary(report)]
        return []
    except Exception as exc:
        print(f"[wicked-garden] guard pipeline error: {exc}", file=sys.stderr)
        return []
