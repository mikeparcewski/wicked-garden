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

v9.2.16 dogfood fix (#842): live telemetry showed SessionEnd fires for only
~40% of human and ~1% of agent sessions — SessionEnd is simply NOT emitted on
most exit paths (non-interactive `claude -p` runs, agent kills, crashes, abrupt
closes). The 60-min-only Stop gate meant short sessions (<60 min) that never
emit SessionEnd got NO heavy teardown at all — 78% of runs fell through to the
"fallback" path, i.e. the fallback WAS the primary path and it still missed the
short-session case. Verdict: UNHEALTHY (Pi/OpenCode's predicted failure mode).

The deterministic fix: stop no longer *hopes* SessionEnd fires. The Stop hook —
which fires reliably every turn — now carries the SAME heavy-cadence teardown,
guarded so it runs at most ONCE per session:
  - De-dupe by session_id: the sidecar records which session_id last ran heavy
    cadence. `should_run_fallback()` returns False when that session_id matches
    the current one, so (a) SessionEnd + Stop never double-run for one session,
    and (b) Stop never re-runs the heavy work on every subsequent turn.
  - Turn-count OR time gate: a *new* session that has not yet run heavy cadence
    fires when it has accrued FALLBACK_TURN_THRESHOLD turns OR the 60-min
    catch-up interval has elapsed — whichever comes first. The turn arm catches
    short-wall-clock agent/`-p` sessions that never emit SessionEnd; the time
    arm catches long, low-turn idle sessions.
SessionEnd still runs first when it *does* fire (best end-of-session snapshot);
it de-dupes against the sidecar so it no-ops if Stop already ran this session.

A sidecar file at <local store>/wicked-garden/heavy-cadence/last_run.json
records `last_heavy_run_ts` + `trigger` + `session_id` so the guard is
deterministic. SessionState is per-session (resets on new session), so it can't
gate cross-session fallback — sidecar is the right persistence boundary.

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

# Turn-count arm of the Stop gate (v9.2.16, #842). A session that has taken
# this many turns without heavy cadence having run yet is "worth a teardown"
# even if <60 min of wall-clock has passed since the last run. Catches busy
# short-wall-clock sessions (a lot happened fast) whose SessionEnd never fired.
# 30 mirrors the "typical 30-turn session" figure the per-turn cadence audit
# used. De-dupe by session_id still bounds this to one run per session.
FALLBACK_TURN_THRESHOLD: int = 30

SIDECAR_DIR_NAME: str = "heavy-cadence"
SIDECAR_FILENAME: str = "last_run.json"

# Trigger strings recorded in the sidecar — surfaced in observability if we
# ever need to debug "why did decay fire here". Not load-bearing for behavior.
TRIGGER_SESSION_END: str = "session_end"
TRIGGER_STOP_FALLBACK: str = "stop_fallback"

# Fallback/sentinel session ids used when neither stdin nor $CLAUDE_SESSION_ID
# supplies a real id (both stop.py and session_end.py default to "default").
# These are NON-dedupable: an id-less session cannot be uniquely identified, so
# recording one as a dedup key would suppress heavy-cadence teardown PERMANENTLY
# for every subsequent id-less session (#842 dedup wedge). Treating them as
# non-dedupable makes id-less sessions always fall through to the time/turn gate
# while real session ids still de-dupe exactly once per session.
_NON_DEDUP_SESSION_IDS = frozenset({"", "default", "unknown"})


def _is_dedupable_session_id(session_id: Optional[str]) -> bool:
    """True only for a real session id that may be used as a de-dupe key.

    False for None/empty and the ``default``/``unknown`` fallback sentinels —
    those must never short-circuit the run (see _NON_DEDUP_SESSION_IDS).
    """
    return bool(session_id) and str(session_id) not in _NON_DEDUP_SESSION_IDS


def _parse_iso_ts(raw_ts) -> Optional[datetime]:
    """Parse a sidecar ``last_heavy_run_ts`` defensively.

    Returns a tz-aware datetime, or None when the value is missing, not a
    string, or unparseable (corrupt/partial/migrated sidecar). Callers treat
    None as "no trustworthy run recorded" rather than trusting a bad value.
    """
    if not raw_ts or not isinstance(raw_ts, str):
        return None
    try:
        return datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


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


def already_ran_this_session(session_id: Optional[str]) -> bool:
    """Return True if heavy cadence already ran for `session_id` this session.

    The de-dupe guard (v9.2.16, #842). The sidecar records the session_id of
    the last heavy run; if it matches the current session, the work is done —
    whether SessionEnd or an earlier Stop did it. Both terminal hooks consult
    this so SessionEnd + Stop never double-run for one session.

    Fail-open to False (i.e. "not yet run") when session_id is unknown/empty or
    the sidecar has no recorded run — an unknown session cannot be matched, so
    the caller falls back to the time/turn gate rather than silently skipping.

    The ``default``/``unknown`` fallback sentinels are treated as NON-dedupable
    (#842): once a run recorded under ``default``, a bare equality check would
    make every subsequent id-less session dedupe against it and never run heavy
    cadence again. A recorded timestamp that is present but UNPARSEABLE
    (corrupt/partial/migrated) is likewise NOT trusted as "already ran".
    """
    if not _is_dedupable_session_id(session_id):
        return False
    data = _read_sidecar()
    if _parse_iso_ts(data.get("last_heavy_run_ts")) is None:
        return False
    return data.get("session_id") == str(session_id)


def should_run_fallback(
    session_id: Optional[str] = None,
    turn_count: int = 0,
    now_ts: Optional[float] = None,
) -> bool:
    """Return True if the Stop hook should run the heavy cadence teardown.

    v9.2.16 (#842): Stop is now a reliable co-primary carrier of the teardown,
    not a rare 60-min fallback. SessionEnd fires on <40% of exits, so relying on
    it dropped short sessions entirely. Stop fires every turn and IS reliable —
    this gate makes it run the heavy work at most ONCE per session:

      1. De-dupe guard — if heavy cadence already ran for THIS `session_id`
         (SessionEnd, or an earlier Stop this session), return False. This is
         what makes carrying the teardown on every Stop safe: it fires once,
         then no-ops for the rest of the session, and never double-runs against
         a SessionEnd that also fires.
      2. Never run for any session yet, or an unparseable timestamp → True
         (seed / self-heal).
      3. Otherwise a NEW session that has not run heavy cadence: fire when it
         has accrued `FALLBACK_TURN_THRESHOLD` turns OR the 60-min catch-up
         interval has elapsed since the last run — whichever comes first.

    `session_id`/`turn_count` are optional so the pre-v9.2.16 call shape
    (`should_run_fallback()` / `should_run_fallback(now_ts=...)`) still resolves
    to the pure time gate.
    """
    # 1. De-dupe: this session already got its teardown.
    if already_ran_this_session(session_id):
        return False

    data = _read_sidecar()

    # 2. Never run, or corrupt/unparseable timestamp → fire to seed / self-heal.
    last_dt = _parse_iso_ts(data.get("last_heavy_run_ts"))
    if last_dt is None:
        return True

    now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc) if now_ts else datetime.now(timezone.utc)
    elapsed = (now_dt - last_dt).total_seconds()

    # 3. New session, not yet torn down: turn arm OR time arm, whichever first.
    if turn_count >= FALLBACK_TURN_THRESHOLD:
        return True
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
    emits wicked.garden.guard.surfaced on the bus. Per-session-end cadence avoids
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
