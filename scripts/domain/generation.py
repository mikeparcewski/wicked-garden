"""generation.py — one GENERATION of a repository's requirements mapping, page by page.

A domain-extraction run maps a repository one page (worklist) at a time and keeps going until
the share of REAL requirements reaches the repository's target or the operator stops it. Real
means resolved to a stated, sourced business rule; a risk-flagged placeholder is shown but never
counts (operator decision 2026-11-01, wicked-core#1233). The host steps keep the generation's
record here: where it started, the real share after each page and when, the units each page
framed (so a page never re-asks a unit this generation already asked), and the budget the
operator granted. `prepare_worklist.py` opens it and records the page it framed, `next_page.py`
adds a point after every page and decides what comes next.

The record lives on the HOST, beside the repository's estate store
(`<store dir>/domain-generations/<run id>.json`), never in the run's worktree: the seat
container can write the worktree, and the budget must not be the seat's to extend.

Pure helpers (`decide`, `progress_line`) take the record and the numbers; the file helpers do
the I/O. Cross-platform (pathlib, os.replace).
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

SCHEMA = "wicked-garden/domain-generation@2"
DIR_NAME = "domain-generations"
MAX_PAGES_ENV = "WICKED_DOMAIN_MAX_PAGES"
MAX_MINUTES_ENV = "WICKED_DOMAIN_MAX_MINUTES"
DEFAULT_MAX_PAGES = 20
DEFAULT_MAX_MINUTES = 240
# The most points one record keeps (the engine stops a loop at 200 passes).
MAX_POINTS = 512
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def now_ms() -> int:
    return int(time.time() * 1000)


# A page that framed at least this many units and resolved under 1 in 20 of them asks the
# operator instead of mapping on: near-zero yield on product code is never passed silently.
LOW_YIELD_MIN_UNITS = 20
LOW_YIELD_PER = 20


def real_pct(real: int, behaviours: int) -> int:
    """floor(real * 100 / behaviours), 100 on an empty denominator — the engine's own rounding
    (`wicked_governance::real_pct`), so the number shown never rounds up past a target."""
    if behaviours <= 0:
        return 100
    return (real * 100) // behaviours


def point_of(coverage: dict[str, Any], page: int, at: int | None = None,
             took: int = 0) -> dict[str, Any]:
    """A curve point from a `wicked-core coverage` report. `took`: how long the page itself ran
    (ms, from the later of the previous page and the latest grant), so an operator's wait at an
    ask never counts as mapping time."""
    behaviours = int(coverage.get("behavior_bearing") or 0)
    real = int(coverage.get("resolved") or 0)
    return {"page": int(page), "pct": real_pct(real, behaviours), "real": real,
            "placeholders": int(coverage.get("risk_flagged") or 0),
            "behaviours": behaviours, "at": int(at if at is not None else now_ms()),
            "took": max(0, int(took))}


def budget_from_env(env: dict[str, str] | None = None) -> tuple[int, int]:
    """(max pages, max minutes) per grant: the daemon's settings, else the defaults. A value that
    is not a positive whole number is the default (said by the caller's line, not fatal)."""
    env = os.environ if env is None else env

    def num(key: str, default: int) -> int:
        raw = (env.get(key) or "").strip()
        try:
            v = int(raw)
        except ValueError:
            return default
        return v if v > 0 else default

    return num(MAX_PAGES_ENV, DEFAULT_MAX_PAGES), num(MAX_MINUTES_ENV, DEFAULT_MAX_MINUTES)


# --- the record on disk -------------------------------------------------------------------

def record_path(db: str, run_id: str) -> Path:
    if not _RUN_ID.match(run_id or ""):
        raise ValueError(f"not a run id: {run_id!r}")
    return Path(db).resolve().parent / DIR_NAME / f"{run_id}.json"


def _valid(doc: Any) -> bool:
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return False
    pts = doc.get("points")
    grant = doc.get("grant")
    if not isinstance(pts, list) or not pts or len(pts) > MAX_POINTS:
        return False
    for p in pts:
        if not isinstance(p, dict) or not all(
                isinstance(p.get(k), int) and not isinstance(p.get(k), bool)
                for k in ("page", "pct", "real", "behaviours", "at")):
            return False
    for key in ("visited", "pending", "answered"):
        ids = doc.get(key, [])
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            return False
    return (isinstance(grant, dict) and isinstance(grant.get("page"), int)
            and isinstance(grant.get("at"), int))


def load(db: str, run_id: str) -> dict[str, Any] | None:
    """The run's record, or None when there is none (or it does not parse: a fresh one is opened)."""
    path = record_path(db, run_id)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if _valid(doc) else None


def save(db: str, run_id: str, doc: dict[str, Any]) -> None:
    path = record_path(db, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {**doc, "points": doc["points"][-MAX_POINTS:]}
    fd, tmp = tempfile.mkstemp(prefix=".gen-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, separators=(",", ":"))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def open_record(db: str, run_id: str, coverage: dict[str, Any], repo: str, *,
                at: int | None = None) -> dict[str, Any]:
    """The run's record, opened at its starting point when the run has none yet (the first page's
    `extract-prepare`). A later page keeps the record it has."""
    doc = load(db, run_id)
    if doc is not None:
        return doc
    start = point_of(coverage, 0, at)
    doc = {"schema": SCHEMA, "run_id": run_id, "repo": repo, "points": [start],
           "grant": {"page": 0, "at": start["at"]}}
    save(db, run_id, doc)
    return doc


def visited(doc: dict[str, Any] | None) -> set[str]:
    """Units an earlier, closed page of this generation framed: a page never re-asks one, so a
    placeholder the seat leaves empty again cannot loop the run. The page in flight (`pending`)
    is not in it, so a retried `extract-prepare` frames the same units again."""
    if not doc:
        return set()
    return set(doc.get("visited") or [])


def frame_page(db: str, run_id: str, symbol_ids: list[str]) -> None:
    """Record the units the page being prepared framed (`pending`). Re-preparing the same page
    (a retried step) replaces them, so a failed attempt never hides a unit from the next. Raises
    when the record cannot be saved: it decides what the next page skips and what the page's
    yield is, so a page is never prepared without it (codex on #1375)."""
    doc = load(db, run_id)
    if doc is None:
        raise ValueError(f"no generation record for run {run_id}")
    doc["pending"] = list(symbol_ids)
    doc["answered"] = []
    save(db, run_id, doc)


def record_answered(db: str, run_id: str, symbol_ids: list[str]) -> None:
    """`extract-apply` (on the host) records which of the page's units the seat answered and the
    host wrote: only those are closed with the page. A unit the seat never reached (its turn ran
    out) goes back to the pool for the next page."""
    doc = load(db, run_id)
    if doc is None:
        return
    pending = set(doc.get("pending") or [])
    doc["answered"] = sorted(pending & set(symbol_ids))
    save(db, run_id, doc)


def close_page(doc: dict[str, Any], coverage: dict[str, Any]) -> tuple[int, int]:
    """Close the page in flight; returns (units it framed, of those now REAL requirements), both
    measured on the page's own units (another writer's progress elsewhere never counts as this
    page's yield). The units `extract-apply` recorded as answered join `visited`; without that
    record, every framed unit that is no longer unmapped does. (0, 0) when an answer to an ask
    re-runs the step with no page in flight."""
    pending = list(doc.get("pending") or [])
    if not pending:
        doc["pending"], doc["answered"] = [], []
        return 0, 0
    unmapped = {n.get("symbol_id") for n in coverage.get("unaccounted_nodes") or []}
    held = {n.get("symbol_id") for n in coverage.get("placeholder_nodes") or []}
    answered = doc.get("answered")
    closed = set(answered) if answered else {s for s in pending if s not in unmapped}
    doc["visited"] = sorted(set(doc.get("visited") or []) | closed)
    doc["pending"], doc["answered"] = [], []
    real = sum(1 for s in pending if s not in unmapped and s not in held)
    return len(pending), real


# --- the decision -------------------------------------------------------------------------

def _duration(ms: float) -> str:
    mins = max(1, int(round(ms / 60000)))
    if mins < 60:
        return f"{mins} min"
    h, m = divmod(mins, 60)
    return f"{h} h {m} min" if m else f"{h} h"


def curve_text(points: list[dict[str, Any]]) -> str:
    pcts = [f"{p['pct']}%" for p in points]
    if len(pcts) > 6:
        pcts = [pcts[0], "…", *pcts[-4:]]
    return " → ".join(pcts)


def _page_ms(points: list[dict[str, Any]]) -> float | None:
    """The mean time one page ran (its own `took`, never an operator's wait), or None."""
    took = [p.get("took", 0) for p in points[1:] if p.get("took", 0) > 0]
    return sum(took) / len(took) if took else None


def eta_ms(points: list[dict[str, Any]], target: int) -> float | None:
    """How long the rest takes at this generation's own pace (real requirements gained per page,
    the time a page runs), or None before a page has resolved anything."""
    first, last = points[0], points[-1]
    pages = last["page"] - first["page"]
    gained = last["real"] - first["real"]
    per_page_ms = _page_ms(points)
    if pages <= 0 or gained <= 0 or per_page_ms is None:
        return None
    need = math.ceil(target * last["behaviours"] / 100) - last["real"]
    if need <= 0:
        return 0.0
    return math.ceil(need / (gained / pages)) * per_page_ms


def page_yield(points: list[dict[str, Any]]) -> tuple[int, int] | None:
    """(of the last page's units, how many are real requirements now; units it framed), or None
    when the last point is not a page that framed units (the start, or an answer re-run)."""
    if len(points) < 2:
        return None
    last = points[-1]
    framed, real = last.get("framed"), last.get("page_real")
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (framed, real)) \
            or framed <= 0:
        return None
    return real, framed


def _yield_text(points: list[dict[str, Any]]) -> str | None:
    y = page_yield(points)
    return f"last page resolved {y[0]} of {y[1]} units" if y else None


def progress_line(repo: str, points: list[dict[str, Any]], target: int, *,
                  next_page: int | None, done: bool = False) -> str:
    """"Mapping wicked-crew · real requirements 23% → 27% · target 80% · page 2 · 4397
    placeholders · last page resolved 212 of 500 units · about 3 h left"."""
    last = points[-1]
    curve = f"real requirements {curve_text(points)}"
    if done:
        pages = last["page"] - points[0]["page"]
        ran = sum(p.get("took", 0) for p in points[1:])
        took = _duration(ran) if pages > 0 and ran > 0 else None
        return (f"Mapped {repo} · {curve} · target {target}% reached"
                + (f" · {pages} page{'s' if pages != 1 else ''} in {took}" if took else ""))
    parts = [f"Mapping {repo}", curve, f"target {target}%"]
    if next_page is not None:
        parts.append(f"page {next_page}")
    if last.get("placeholders"):
        parts.append(f"{last['placeholders']} placeholders")
    yt = _yield_text(points)
    if yt:
        parts.append(yt)
    eta = eta_ms(points, target)
    if eta is not None and eta > 0:
        parts.append(f"about {_duration(eta)} left")
    return " · ".join(parts)


def decide(doc: dict[str, Any], *, repo: str, target: int, now: int, max_pages: int,
           max_minutes: int, left_to_map: int) -> dict[str, Any]:
    """The loop's decision after the record's last point (pure). Returns the `wicked-repeat`
    object: `done` when the REAL share reaches the target; `ask` when nothing is left to map,
    when the last page resolved almost nothing of what it framed, when the last two pages added
    no real requirement, or when the grant's pages or minutes are spent; `continue` otherwise."""
    points = doc["points"]
    last = points[-1]
    page = last["page"]
    if last["pct"] >= target:
        return {"next": "done",
                "line": progress_line(repo, points, target, next_page=None, done=True)}
    line = progress_line(repo, points, target, next_page=page + 1)
    # A target is a whole percentage 1..100 the real share so far must meet: below 1% nothing
    # can be lowered to (codex/agy r1 on #1369 — "lower to 1%" at 0.5% asked again forever).
    lower = ({"id": "lower", "label": f"Lower the target to {last['pct']}% for {repo} and build "
                                      f"the graph"} if last["pct"] >= 1 else None)
    more = {"id": "continue", "label": f"Map up to {max_pages} more pages"}
    # Near-zero yield on a full page (domain-real): the page's review passed a page that stated
    # almost nothing (wicked-crew run 4b49cbe1: 3 rules of 500 units). Never mapped on silently,
    # and asked before "nothing left" too (codex on #1375), so the last page is not passed either.
    y = page_yield(points)
    if (y is not None and y[1] >= LOW_YIELD_MIN_UNITS and y[0] * LOW_YIELD_PER < y[1]
            and last["page"] > doc["grant"]["page"]):
        choices = [c for c in ((more if left_to_map > 0 else None), lower) if c is not None]
        if choices:
            return {"next": "ask", "choices": choices, "recommended": choices[0]["id"],
                    "line": f"{line} · the last page resolved under 1 in {LOW_YIELD_PER} of its "
                            f"units: read its review before mapping more"}
    if left_to_map <= 0:
        rest = (f"{progress_line(repo, points, target, next_page=None)} · nothing left to map "
                f"in the files the repository tracks")
        if lower is None:
            # Nothing can change: the coverage step says the share against the target.
            return {"next": "done", "line": rest}
        return {"next": "ask", "choices": [lower], "recommended": "lower", "line": rest}
    grant = doc["grant"]
    # Two pages since the latest grant that added no real requirement: a fresh grant lets the
    # operator try again (codex/agy r1 on #1369: "Map more" re-asked at once).
    since = [p for p in points if p["page"] >= grant["page"]]
    if len(since) >= 3 and since[-3]["real"] == last["real"]:
        return {"next": "ask", "choices": [c for c in (more, lower) if c is not None],
                "recommended": "lower" if lower is not None else "continue",
                "line": f"{line} · the last two pages added no real requirement"}
    pages_used = page - grant["page"]
    minutes_used = (now - grant["at"]) / 60000
    if pages_used >= max_pages or minutes_used >= max_minutes:
        spent = (f"{pages_used} page{'s' if pages_used != 1 else ''}"
                 if pages_used >= max_pages else f"{int(minutes_used)} minutes")
        return {"next": "ask", "choices": [c for c in (more, lower) if c is not None],
                "recommended": "continue",
                "line": f"{line} · budget reached ({spent}; the budget is {max_pages} pages "
                        f"or {max_minutes} minutes)"}
    return {"next": "continue", "line": line}


def marker(decision: dict[str, Any]) -> str:
    """The engine's decision line (wicked-core `repeat`): one compact JSON object."""
    return "wicked-repeat " + json.dumps(decision, ensure_ascii=False, separators=(",", ":"))
