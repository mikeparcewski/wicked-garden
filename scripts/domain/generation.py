"""generation.py — one GENERATION of a repository's requirements mapping, page by page.

A domain-extraction run maps a repository one page (worklist) at a time and keeps going until
the mapped share reaches the repository's target or the operator stops it. The host steps keep
the generation's record here: where it started, the mapped share after each page and when, and
the budget the operator granted. `prepare_worklist.py` opens it, `next_page.py` adds a point after
every page and decides what comes next.

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

SCHEMA = "wicked-garden/domain-generation@1"
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


def mapped_pct(mapped: int, behaviours: int) -> int:
    """floor(mapped * 100 / behaviours), 100 on an empty denominator — the engine's own rounding
    (`wicked_governance::mapped_pct`), so the number shown never rounds up past a target."""
    if behaviours <= 0:
        return 100
    return (mapped * 100) // behaviours


def point_of(coverage: dict[str, Any], page: int, at: int | None = None) -> dict[str, Any]:
    """A curve point from a `wicked-core coverage` report."""
    behaviours = int(coverage.get("behavior_bearing") or 0)
    mapped = int(coverage.get("resolved") or 0) + int(coverage.get("risk_flagged") or 0)
    return {"page": int(page), "pct": mapped_pct(mapped, behaviours), "mapped": mapped,
            "behaviours": behaviours, "at": int(at if at is not None else now_ms())}


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
                for k in ("page", "pct", "mapped", "behaviours", "at")):
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


def open_record(db: str, run_id: str, coverage: dict[str, Any], repo: str) -> dict[str, Any]:
    """The run's record, opened at its starting point when the run has none yet (the first page's
    `extract-prepare`). A later page keeps the record it has."""
    doc = load(db, run_id)
    if doc is not None:
        return doc
    start = point_of(coverage, 0)
    doc = {"schema": SCHEMA, "run_id": run_id, "repo": repo, "points": [start],
           "grant": {"page": 0, "at": start["at"]}}
    save(db, run_id, doc)
    return doc


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


def eta_ms(points: list[dict[str, Any]], target: int) -> float | None:
    """How long the rest takes at this generation's own pace (mapped behaviours per page, time
    per page), or None before a page has mapped anything."""
    first, last = points[0], points[-1]
    pages = last["page"] - first["page"]
    gained = last["mapped"] - first["mapped"]
    if pages <= 0 or gained <= 0:
        return None
    need = math.ceil(target * last["behaviours"] / 100) - last["mapped"]
    if need <= 0:
        return 0.0
    per_page_ms = (last["at"] - first["at"]) / pages
    return math.ceil(need / (gained / pages)) * per_page_ms


def progress_line(repo: str, points: list[dict[str, Any]], target: int, *,
                  next_page: int | None, done: bool = False) -> str:
    """"Mapping wicked-crew · 3% → 12% → 19% · target 80% · page 4 · about 2 h 10 min left"."""
    last = points[-1]
    if done:
        pages = last["page"] - points[0]["page"]
        took = _duration(last["at"] - points[0]["at"]) if pages > 0 else None
        return (f"Mapped {repo} · {curve_text(points)} · target {target}% reached"
                + (f" · {pages} page{'s' if pages != 1 else ''} in {took}" if took else ""))
    parts = [f"Mapping {repo}", curve_text(points), f"target {target}%"]
    if next_page is not None:
        parts.append(f"page {next_page}")
    eta = eta_ms(points, target)
    if eta is not None and eta > 0:
        parts.append(f"about {_duration(eta)} left")
    return " · ".join(parts)


def decide(doc: dict[str, Any], *, repo: str, target: int, now: int, max_pages: int,
           max_minutes: int, left_to_map: int) -> dict[str, Any]:
    """The loop's decision after the record's last point (pure). Returns the `wicked-repeat`
    object: `done` at the target; `ask` when nothing is left to map, when the last two pages
    mapped nothing new, or when the grant's pages or minutes are spent; `continue` otherwise."""
    points = doc["points"]
    last = points[-1]
    page = last["page"]
    if last["pct"] >= target:
        return {"next": "done",
                "line": progress_line(repo, points, target, next_page=None, done=True)}
    line = progress_line(repo, points, target, next_page=page + 1)
    lower_to = max(1, last["pct"])
    lower = {"id": "lower", "label": f"Lower the target to {lower_to}% for {repo} and build the "
                                     f"graph"}
    more = {"id": "continue", "label": f"Map up to {max_pages} more pages"}
    if left_to_map <= 0:
        return {"next": "ask", "choices": [lower], "recommended": "lower",
                "line": f"{progress_line(repo, points, target, next_page=None)} · nothing "
                        f"left to map in the files the repository tracks"}
    if len(points) >= 3 and points[-3]["mapped"] == last["mapped"] and page >= 2:
        return {"next": "ask", "choices": [more, lower], "recommended": "lower",
                "line": f"{line} · the last two pages mapped nothing new"}
    grant = doc["grant"]
    pages_used = page - grant["page"]
    minutes_used = (now - grant["at"]) / 60000
    if pages_used >= max_pages or minutes_used >= max_minutes:
        spent = (f"{pages_used} page{'s' if pages_used != 1 else ''}"
                 if pages_used >= max_pages else f"{int(minutes_used)} minutes")
        return {"next": "ask", "choices": [more, lower], "recommended": "continue",
                "line": f"{line} · budget reached ({spent}; the budget is {max_pages} pages "
                        f"or {max_minutes} minutes)"}
    return {"next": "continue", "line": line}


def marker(decision: dict[str, Any]) -> str:
    """The engine's decision line (wicked-core `repeat`): one compact JSON object."""
    return "wicked-repeat " + json.dumps(decision, ensure_ascii=False, separators=(",", ":"))
