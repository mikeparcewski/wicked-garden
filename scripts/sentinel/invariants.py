#!/usr/bin/env python3
"""invariants.py — the claim sentinel: state-transition gates without command lists.

The design problem (session-tested): steering that fires at *prompt time* ("this
is a build!") or as ambient tips gets ignored — the agent overrides even MUST
wording when local context says "irrelevant", and nothing records the skip. What
changes behavior is a check that fires **at the claim moment**, carries **observed
evidence**, names **one action**, and makes skipping a **recorded decision**.

And you can't catch claim moments by pattern-matching commands (`gh pr merge`,
raw `git push`, `glab`, an API curl, next year's tool…). You catch the state all
of them converge on:

  - a **git ref moving** is the universal "ship it" (ref-watch, below);
  - a **task completing** is the universal in-session "done" (TaskCompleted hook);
  - the **session ending** is the last exit (info tier).

Each toolkit component already has one observable state-store, so every gate here
is an *invariant between two observable states* — never a command match:

  invariant                 observable A            observable B
  ------------------------  ----------------------  -------------------------
  done-claim has a verdict  sentinel verdict ledger ref advance / task done
  evidence is fresh         .wicked-testing ledger  mtime of modified files
  learnings captured        brain memory dir        session activity
  playbooks current         repo-* skill dirs       commits since their mtime

Tiers: info (one line, ignorable) → **answer** (the agent must act or the skip
is logged to the bus as `wicked.sentinel.*` — the skip becomes evidence) →
block (git pre-push / CI, outside this module). Everything here fails OPEN on
error (a broken sentinel must never break a session) but never invents an OK.

Stdlib-only. All git access via argv subprocess, short timeouts, throttled.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess  # noqa: S404 — argv lists only, shell=False
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_GIT_TIMEOUT = 5
_LEDGER_MAX_STAMPS = 200          # ledger read window (recent stamps only)
_RECENT_HISTORY = 80              # a verdict covers a sha within this many ancestors
_PLAYBOOK_STALE_COMMITS = 30      # repo-playbooks "drifted" threshold


# ---------------------------------------------------------------------------
# git plumbing (fail-open: None / {} on any error)
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(  # noqa: S603 — argv list, shell=False
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


def repo_toplevel(cwd: Optional[Path] = None) -> Optional[Path]:
    top = _git(Path(cwd) if cwd else Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(top) if top else None


# ---------------------------------------------------------------------------
# The verdict ledger — stamped by the gate, read by every claim check.
# Keyed by repo toplevel (NOT cwd) so gate runs and hook checks agree even when
# they run from different directories of the same repo.
# ---------------------------------------------------------------------------

def _ledger_path(repo: Path) -> Path:
    slug = hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()[:12]
    base = Path.home() / ".something-wicked" / "wicked-garden" / "sentinel"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{slug}.jsonl"


def stamp_verdict(repo: Path, *, overall: str, satisfied: bool,
                  re_derived: bool, scope: str = "", phase: str = "") -> None:
    """Record a gate verdict for the repo's current HEAD. Called by the
    produces-gate (vault_gate.gate_satisfied) — the single front door — so any
    prove/gate run anywhere stamps the ledger. Fail-open."""
    try:
        sha = _git(repo, "rev-parse", "HEAD")
        if not sha:
            return
        rec = {"sha": sha, "overall": overall, "satisfied": bool(satisfied),
               "re_derived": bool(re_derived), "scope": scope, "phase": phase,
               "ts": time.time()}
        with _ledger_path(repo).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception:  # noqa: BLE001 — sentinel must never break the gate
        return


def _recent_stamps(repo: Path) -> List[Dict[str, Any]]:
    try:
        p = _ledger_path(repo)
        if not p.exists():
            return []
        lines = p.read_text(encoding="utf-8").splitlines()[-_LEDGER_MAX_STAMPS:]
        return [json.loads(ln) for ln in lines if ln.strip()]
    except Exception:  # noqa: BLE001
        return []


def verdict_for(repo: Path, sha: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The most recent satisfied+re-derived stamp covering `sha` (default HEAD):
    the stamped commit must be the sha itself or one of its recent ancestors."""
    target = sha or _git(repo, "rev-parse", "HEAD")
    if not target:
        return None
    history = _git(repo, "rev-list", f"-{_RECENT_HISTORY}", target)
    if history is None:
        return None
    recent = set(history.splitlines())
    for rec in reversed(_recent_stamps(repo)):
        if rec.get("sha") in recent and rec.get("satisfied") and rec.get("re_derived"):
            return rec
    return None


# ---------------------------------------------------------------------------
# Override / detection events → the bus (fire-and-forget; the skip is evidence)
# ---------------------------------------------------------------------------

def log_sentinel_event(repo: Path, event: str, detail: Dict[str, Any]) -> None:
    """Emit wicked.sentinel.<event> to the bus if available; always append to a
    local trail so the record exists even without the bus layer."""
    payload = {"repo": str(repo), "ts": time.time(), **detail}
    try:
        trail = _ledger_path(repo).with_suffix(".events.jsonl")
        with trail.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"event": event, **payload}) + "\n")
    except Exception:  # noqa: BLE001
        pass
    try:
        import sys
        plugin_scripts = Path(__file__).resolve().parents[1]
        if str(plugin_scripts) not in sys.path:
            sys.path.insert(0, str(plugin_scripts))
        from _bus import emit_event  # type: ignore
        emit_event(f"wicked.sentinel.{event}", payload)
    except Exception:  # noqa: BLE001 — bus is an opt-in layer; fail open
        pass


# ---------------------------------------------------------------------------
# Invariant 1 — claim-gate (answer tier): a done/passing CLAIM must have a
# verdict. Fires at the Stop boundary, and only when the turn's final message
# actually asserts done/passing/shipped — never as a side effect of a tool
# call. Ship/publish protection (an actual push to main or a tag) is the BLOCK
# tier (pre_push.py + CI); this is the harness backstop nudge.
#
# History: this replaced a PostToolUse ref-watch that keyed off git-ref state
# (origin default branch + newest tag advancing) with no claim check, wired to
# a blanket Bash matcher — so any Bash call (git log, cat, find) during pure
# planning tripped "the claim sentinel that never checked for a claim".
# ---------------------------------------------------------------------------

# Verification-completion phrases. Deliberately conservative — the failure mode
# being fixed is OVER-firing, so we match explicit verification/publish
# assertions, not bare "done" (too common in progress chatter).
_CLAIM_PATTERNS = (
    r"\btests?\s+(?:all\s+)?(?:pass|passing|passes|passed)\b",
    r"\ball\s+tests?\s+(?:are\s+)?(?:pass|passing|green)",
    r"\ball\s+green\b",
    r"\ball\s+checks?\s+(?:pass|passing|green)",
    r"\bbuild\s+(?:is\s+)?clean\b",
    r"\bready\s+to\s+(?:merge|ship)\b",
    r"\bshipped\b",
    r"\bship(?:ping)?\s+it\b",
    r"\bit\s+works\b",
    r"\bverified\b",
)
_CLAIM_RE = re.compile("|".join(_CLAIM_PATTERNS), re.IGNORECASE)


def is_done_claim(text: Optional[str]) -> bool:
    """True iff `text` asserts verified completion / shipping — a 'done' claim.
    Conservative by design (matches explicit verification/publish phrases, not
    bare 'done') so planning and progress chatter never trip the sentinel."""
    if not text:
        return False
    return bool(_CLAIM_RE.search(text))


def claim_tick(state_get, state_set, *, final_message: Optional[str],
               cwd: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Stop-hook entry point. Fires ONLY when the turn's final assistant message
    asserts done/passing/shipped (is_done_claim) AND the repo HEAD has no
    re-derived verdict. Debounced once per unproven sha per session. Fail-open.

    `state_get(key)`/`state_set(key, value)` wrap SessionState so this module
    stays import-light."""
    try:
        if not is_done_claim(final_message):
            return None
        repo = repo_toplevel(cwd)
        if repo is None:
            return None
        head = _git(repo, "rev-parse", "HEAD")
        if not head:
            return None
        if verdict_for(repo, head):  # a re-derived verdict covers HEAD — suppress
            return None
        if state_get("sentinel_claim_sha") == head:  # debounce: once per sha/session
            return None
        state_set("sentinel_claim_sha", head)
        violation = {
            "tier": "answer",
            "invariant": "done-claim-verdict",
            "evidence": (f"a done/passing claim was made but HEAD {head[:9]} has no "
                         "re-derived verdict on record"),
            "action": ("Run `/wicked-garden:prove` to re-derive the claim now, or state "
                       "the override reason — the claim is logged either way."),
        }
        log_sentinel_event(repo, "unverified_claim",
                           {"sha": head, "invariant": "done-claim-verdict"})
        return violation
    except Exception:  # noqa: BLE001 — sentinel never breaks a hook
        return None


# ---------------------------------------------------------------------------
# Invariant 2 — evidence freshness: a claim is stale when source moved after
# the newest recorded evidence. Applies only when the testing layer is present.
# ---------------------------------------------------------------------------

def _newest_evidence_ts(repo: Path) -> Optional[float]:
    root = repo / ".wicked-testing"
    if not root.is_dir():
        return None
    newest = 0.0
    try:
        for p in root.rglob("*"):
            if p.is_file():
                ts = p.stat().st_mtime
                if ts > newest:
                    newest = ts
    except OSError:
        return None
    return newest or None


def check_evidence_freshness(repo: Path) -> Optional[Dict[str, Any]]:
    """Answer-tier (only when .wicked-testing exists). Modified-but-uncommitted /
    just-committed files newer than the newest evidence record = stale claim."""
    newest_evidence = _newest_evidence_ts(repo)
    if newest_evidence is None:
        return None  # testing layer absent or no runs — not applicable
    changed = _git(repo, "diff", "--name-only", "HEAD")
    if changed is None:
        return None
    paths = [repo / ln for ln in changed.splitlines() if ln.strip()]
    newest_src = 0.0
    for p in paths:
        try:
            ts = p.stat().st_mtime
            if ts > newest_src:
                newest_src = ts
        except OSError:
            continue
    if newest_src <= newest_evidence:
        return None
    age_min = (newest_src - newest_evidence) / 60
    return {
        "tier": "answer",
        "invariant": "evidence-freshness",
        "evidence": (f"source files changed {age_min:.0f}m after the newest "
                     f".wicked-testing evidence — the recorded runs predate this work"),
        "action": "Re-run the relevant scenario (/wicked-testing:execution) or state why the evidence still holds.",
    }


# ---------------------------------------------------------------------------
# Invariant 3+4+5 — session-end info tier (one line each, never blocking)
# ---------------------------------------------------------------------------

def _brain_memory_dir(repo: Path) -> Optional[Path]:
    projects = Path.home() / ".wicked-brain" / "projects"
    if not projects.is_dir():
        return None
    try:
        for proj in projects.iterdir():
            cfg = proj / "_meta" / "config.json"
            if cfg.is_file():
                try:
                    src = json.loads(cfg.read_text(encoding="utf-8")).get("source_path", "")
                    if src and Path(src).resolve() == repo.resolve():
                        mem = proj / "memory"
                        return mem if mem.is_dir() else None
                except (json.JSONDecodeError, OSError):
                    continue
    except OSError:
        return None
    return None


def check_session_capture(repo: Path, session_start_ts: float,
                          activity_count: int) -> Optional[Dict[str, Any]]:
    """Info-tier: a significant session (>= 10 tracked activities) that captured
    zero brain memories. Only applies when the brain layer is present."""
    if activity_count < 10:
        return None
    mem = _brain_memory_dir(repo)
    if mem is None:
        return None  # brain layer absent for this repo — not applicable
    try:
        wrote = any(p.stat().st_mtime >= session_start_ts
                    for p in mem.glob("*.md"))
    except OSError:
        return None
    if wrote:
        return None
    return {
        "tier": "info",
        "invariant": "session-capture",
        "evidence": f"{activity_count} tracked activities this session, 0 memories captured",
        "action": "Worth one `wicked-brain:memory` store (decision/gotcha) before you go?",
    }


def check_playbook_freshness(repo: Path) -> Optional[Dict[str, Any]]:
    """Info-tier: wicked-understanding playbooks exist but the repo has moved
    well past them (commits since their newest mtime > threshold)."""
    roots = [Path.home() / ".claude" / "skills"]
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    if cfg:
        roots.append(Path(cfg) / "skills")
    newest = 0.0
    for root in roots:
        try:
            if root.is_dir():
                for entry in root.iterdir():
                    if entry.is_dir() and entry.name.startswith(("repo-", "fix-bug", "add-feature")):
                        ts = entry.stat().st_mtime
                        if ts > newest:
                            newest = ts
        except OSError:
            continue
    if not newest:
        return None  # understanding layer absent — not applicable
    iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(newest))
    count = _git(repo, "rev-list", "--count", f"--since={iso}", "HEAD")
    try:
        behind = int(count) if count else 0
    except ValueError:
        return None
    if behind < _PLAYBOOK_STALE_COMMITS:
        return None
    return {
        "tier": "info",
        "invariant": "playbook-freshness",
        "evidence": f"repo playbooks were generated ~{behind} commits ago",
        "action": "Re-run `repo-analyst` so the how-to playbooks track HEAD.",
    }


def session_end_lines(cwd: Optional[Path], session_start_ts: float,
                      activity_count: int) -> List[str]:
    """The Stop/SessionEnd bundle — info-tier lines only, each fail-open."""
    repo = repo_toplevel(cwd)
    if repo is None:
        return []
    lines: List[str] = []
    for check in (lambda: check_session_capture(repo, session_start_ts, activity_count),
                  lambda: check_playbook_freshness(repo)):
        try:
            v = check()
        except Exception:  # noqa: BLE001
            v = None
        if v:
            lines.append(f"[Sentinel:{v['invariant']}] {v['evidence']} → {v['action']}")
    return lines


# ---------------------------------------------------------------------------
# Rendering — one consistent voice for the answer tier
# ---------------------------------------------------------------------------

def render(violation: Dict[str, Any]) -> str:
    return (f"[Sentinel:{violation['invariant']}] {violation['evidence']}.\n"
            f"→ {violation['action']}")


__all__ = [
    "repo_toplevel", "stamp_verdict", "verdict_for", "log_sentinel_event",
    "is_done_claim", "claim_tick",
    "check_evidence_freshness", "check_session_capture",
    "check_playbook_freshness", "session_end_lines", "render",
]
