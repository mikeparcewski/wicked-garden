"""generation.py — one GENERATION of a repository's requirements mapping, page by page.

A domain-extraction run maps a repository one page (worklist) at a time and keeps going until
the share of REAL requirements reaches the repository's target or the operator stops it. Real
means resolved to a stated, sourced business rule; a risk-flagged placeholder is shown but never
counts (operator decision 2026-11-01, wicked-core#1233). The host steps keep the generation's
record here: where it started, the real share after each page and when, the units each page
framed (so a page never re-asks a unit this generation already asked unless the operator chose
to ask the unresolved placeholders again), and the budget the
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
# Set by `frame_page`, removed by `close_page`: a page prepared and not closed yet. Only this
# marker says a page is in flight (`page_in_flight`); `pending: []` alone is also a closed page.
PAGE_OPEN = "page_open"
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def now_ms() -> int:
    return int(time.time() * 1000)


# A page that framed at least this many units and resolved under 1 in 20 of them asks the
# operator instead of mapping on: near-zero yield on product code is never passed silently.
LOW_YIELD_MIN_UNITS = 20
LOW_YIELD_PER = 20
# The one choice an ask offers when nothing can be mapped or lowered: go on to the coverage step,
# which states the share against the target (below it, its gate is the operator's).
FINISH = {"id": "finish", "label": "Go on: the coverage step states the share"}


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
    for key in ("visited", "pending", "answered", "changed"):
        ids = doc.get(key) or []
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            return False
    if "assign_only" in doc and not isinstance(doc["assign_only"], bool):
        return False
    if "assign_framed" in doc:
        n = doc["assign_framed"]
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
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
    """Units an earlier, closed page of this generation framed: a page never re-asks one on its
    own, so a placeholder the seat leaves empty again cannot loop the run (only the operator's
    `again` takes asked placeholders out of it, `reopen`). The page in flight (`pending`)
    is not in it, so a retried `extract-prepare` frames the same units again."""
    if not doc:
        return set()
    return set(doc.get("visited") or [])


def asked_again(doc: dict[str, Any] | None) -> set[str]:
    """Placeholders the operator's "again" reopened in this generation (wicked-garden#1533)."""
    if not doc:
        return set()
    return set(doc.get("asked_again") or [])


def asked_unresolved(doc: dict[str, Any] | None, placeholder_ids: set[str]) -> set[str]:
    """Placeholders a closed page of this generation asked about that are still placeholders
    (wicked-garden#1533): no page re-asks them on its own, but asking them again can still raise
    the real share (a new run did: 101 of 263 resolved on the second ask), so the operator may."""
    return set(placeholder_ids) & visited(doc)


def reopen(doc: dict[str, Any], placeholder_ids: set[str]) -> int:
    """The operator's "again": the asked, unresolved placeholders leave `visited`, so the next page
    frames them, and are remembered in `asked_again`. Returns how many were reopened."""
    ids = asked_unresolved(doc, placeholder_ids)
    doc["visited"] = sorted(visited(doc) - ids)
    doc["asked_again"] = sorted(asked_again(doc) | ids)
    return len(ids)


def page_in_flight(doc: dict[str, Any] | None) -> list[str] | None:
    """The units `extract-prepare` framed for the page in flight (possibly none), or None when no
    page is in flight: no record, a page `extract-next` closed, or a record written before the
    `page_open` marker (an old close left `pending: []` too, so only the marker says a page is
    open). `[]` therefore means exactly "this pass's prepare framed an empty page", which is how
    `extract-apply` tells a map with nothing left to ask (e2e-1105 F42) from an extract step that
    left its work undone. Host-side: the seat can neither write this record nor shrink the page."""
    if not doc or doc.get(PAGE_OPEN) is not True:
        return None
    pending = doc.get("pending")
    return list(pending) if isinstance(pending, list) else None


def assign_only(doc: dict[str, Any] | None) -> bool:
    """Whether the next prepared page only assigns business domains to resolved requirements."""
    return bool(doc and doc.get("assign_only") is True)


def assign_framed(doc: dict[str, Any] | None) -> int:
    """How many assignments the host framed for the page in flight, else zero."""
    return int(doc.get("assign_framed", 0)) if page_in_flight(doc) is not None else 0


def changed(doc: dict[str, Any] | None) -> set[str]:
    """Mapped units this generation found changed since the map was built (wicked-garden#1425):
    the only resolved units a page may ask again (prepare frames each once: a closed page's units
    are `visited`)."""
    if not doc:
        return set()
    return set(doc.get("changed") or [])


def changed_left(doc: dict[str, Any] | None) -> int:
    """Changed mapped units no closed page of this generation has asked yet."""
    return len(changed(doc) - visited(doc))


def frame_page(db: str, run_id: str, symbol_ids: list[str],
               changed_ids: list[str] | None = None, *, assign_count: int = 0) -> None:
    """Record the units the page being prepared framed (`pending`). Re-preparing the same page
    (a retried step) replaces them, so a failed attempt never hides a unit from the next. Raises
    when the record cannot be saved: it decides what the next page skips and what the page's
    yield is, so a page is never prepared without it (codex on #1375)."""
    doc = load(db, run_id)
    if doc is None:
        raise ValueError(f"no generation record for run {run_id}")
    doc["assign_framed"] = int(assign_count)
    doc["pending"] = list(symbol_ids)
    doc[PAGE_OPEN] = True  # this page is open until `close_page` (see `page_in_flight`)
    if changed_ids:  # kept for the whole generation: apply accepts these, next-page counts them
        doc["changed"] = sorted(set(doc.get("changed") or []) | set(changed_ids))
    doc.pop("answered", None)  # not recorded yet (an empty list is "answered none")
    save(db, run_id, doc)


def record_answered(db: str, run_id: str, symbol_ids: list[str]) -> None:
    """`extract-apply` (on the host) records which of the page's units the seat answered and the
    host wrote: only those are closed with the page. A unit the seat never reached (its turn ran
    out) goes back to the pool for the next page."""
    doc = load(db, run_id)
    if doc is None:
        return
    pending = set(doc.get("pending") or [])
    # Accumulated across retries of the same page (codex r3 on #1375): a retry refuses what the
    # first attempt already resolved, and must not erase it.
    doc["answered"] = sorted((set(doc.get("answered") or []) | set(symbol_ids)) & pending)
    save(db, run_id, doc)


def close_page(doc: dict[str, Any], coverage: dict[str, Any]) -> tuple[int, int | None]:
    """Close the page in flight; returns (units it framed, of those now REAL requirements), both
    measured on the page's own units (another writer's progress elsewhere never counts as this
    page's yield). The units `extract-apply` recorded as answered join `visited`; without that
    record, every framed unit that is a real requirement now does, except a changed mapped unit
    (real before the page: it stays open). (0, 0) when an answer to an ask
    re-runs the step with no page in flight."""
    pending = list(doc.get("pending") or [])
    doc.pop("assign_framed", None)
    if not pending:
        doc["pending"] = []
        doc.pop(PAGE_OPEN, None)
        doc.pop("answered", None)
        return 0, 0
    unmapped = {n.get("symbol_id") for n in coverage.get("unaccounted_nodes") or []}
    held = {n.get("symbol_id") for n in coverage.get("placeholder_nodes") or []}
    answered = doc.get("answered")
    if isinstance(answered, list):  # recorded by extract-apply, possibly empty
        closed = set(answered) & set(pending)
    else:  # never recorded: only what is a real requirement now is known to be answered; a
        # changed mapped unit was real BEFORE the page, so it closes only on the record (codex r2)
        was_real = changed(doc)
        closed = {s for s in pending if s not in unmapped and s not in held and s not in was_real}
    doc["visited"] = sorted(set(doc.get("visited") or []) | closed)
    doc["pending"] = []
    doc.pop(PAGE_OPEN, None)
    doc.pop("answered", None)
    if "not_product" not in coverage:
        # An older wicked-core lists no placeholders, so "accounted" cannot be told from "real":
        # the page's yield is unknown, never counted as real (Copilot on #1375).
        return len(pending), None
    real = sum(1 for s in closed if s not in unmapped and s not in held)
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


def count(n: int) -> str:
    """A count as people read it: "2,174", never "2174" (studio prints the same numbers so)."""
    return f"{n:,}"


def _yield_text(points: list[dict[str, Any]]) -> str | None:
    y = page_yield(points)
    return f"last page resolved {count(y[0])} of {count(y[1])} units" if y else None


def progress_line(repo: str, points: list[dict[str, Any]], target: int, *,
                  next_page: int | None, done: bool = False,
                  left_to_map: int | None = None) -> str:
    """"Mapping wicked-crew · real requirements 23% → 27% · minimum 80% · page 2 · 4,397
    placeholders · last page resolved 212 of 500 units · about 3 h left". The repository's target is
    a MINIMUM share (studio's word for it), and every count carries thousands separators."""
    last = points[-1]
    curve = f"real requirements {curve_text(points)}"
    if done:
        pages = last["page"] - points[0]["page"]
        ran = sum(p.get("took", 0) for p in points[1:])
        took = _duration(ran) if pages > 0 and ran > 0 else None
        return (f"Mapped {repo} · {curve} · minimum {target}% reached"
                + (f" · {pages} page{'s' if pages != 1 else ''} in {took}" if took else ""))
    parts = [f"Mapping {repo}", curve, f"minimum {target}%"]
    if next_page is not None:
        parts.append(f"page {next_page}")
    if last.get("placeholders"):
        parts.append(f"{count(last['placeholders'])} placeholders")
    yt = _yield_text(points)
    if yt:
        parts.append(yt)
    need = math.ceil(target * last["behaviours"] / 100) - last["real"]
    if left_to_map == 0 and need > 0:
        return " · ".join(parts)  # nothing left to ask: no time estimate (the caller says why)
    if left_to_map is not None and 0 < left_to_map < need:
        # No time estimate for a target this run cannot reach (wicked-crew run 29bbbfb1 read
        # "about 3 h 37 min left" with 1,900 units left to ask and 2,000 real requirements to go).
        parts.append(f"minimum out of reach in this run: {count(need)} more real requirements "
                     f"needed, {count(left_to_map)} units left to ask")
        return " · ".join(parts)
    eta = eta_ms(points, target)
    if eta is not None and eta > 0:
        parts.append(f"about {_duration(eta)} left")
    return " · ".join(parts)


def _budget_spent(doc: dict[str, Any], now: int, max_pages: int,
                  max_minutes: int) -> str | None:
    """What of the latest grant is spent ("20 pages", "240 minutes"), or None."""
    grant, page = doc["grant"], doc["points"][-1]["page"]
    pages_used = page - grant["page"]
    minutes_used = (now - grant["at"]) / 60000
    if pages_used >= max_pages:
        return f"{count(pages_used)} page{'s' if pages_used != 1 else ''}"
    if minutes_used >= max_minutes:
        return f"{count(int(minutes_used))} minutes"
    return None


def _asked_text(asked_left: int, asked_once: int) -> str:
    """What the placeholders this run already asked about are, said as such (wicked-garden#1533:
    the card read "nothing left to map" with 263 of them left). It claims only what the record
    shows: every unit left to map was framed by a page of this run."""
    n = count(asked_left)
    s = "s" if asked_left != 1 else ""
    if asked_once >= asked_left:
        return f"{n} placeholder{s} this run asked about once, unresolved: asking again can help"
    if asked_once <= 0:
        return f"{n} placeholder{s} asked again and still unresolved"
    return f"{n} placeholder{s} this run asked about, unresolved ({count(asked_once)} asked once)"


# The longest choice label the engine shows whole (wicked-core `repeat.rs`: `one_line(label, 120)`).
MAX_LABEL = 120


def _lower_label(repo: str, last: dict[str, Any]) -> str:
    """"Lower the minimum" says what the person gives up (wicked-garden#1536): the behaviours
    the graph is then built without a requirement for. The repository is left out only when
    the label would be cut."""
    left = max(0, int(last["behaviours"]) - int(last["real"]))
    tail = (f"and build the graph with {count(left)} behaviour{'s' if left != 1 else ''} left "
            f"without a requirement")
    label = f"Lower the minimum to {last['pct']}% for {repo} {tail}"
    return label if len(label) <= MAX_LABEL else f"Lower the minimum to {last['pct']}% {tail}"


def _again_can_help(points: list[dict[str, Any]], asked_once: int) -> bool:
    """Can asking the placeholders again still move the share? Yes while some were asked only
    once, and while the last page still added real requirements (wicked-garden#1536: re-asks
    that resolved 11 and 14 units were followed by a card recommending to lower the minimum).
    The share itself is read, not the page's yield, which also counts a changed mapped unit
    that was real before the page (codex r1). Only a page that added none leaves lowering as the
    recommendation."""
    if asked_once > 0:
        return True
    return len(points) >= 2 and points[-1]["real"] > points[-2]["real"]


def decide(doc: dict[str, Any], *, repo: str, target: int, now: int, max_pages: int,
           max_minutes: int, left_to_map: int, changed_left: int = 0,
           assign_left: int = 0, assign_progress: bool = False,
           asked_left: int = 0, asked_once: int = 0) -> dict[str, Any]:
    """The loop's decision after the record's last point (pure). Returns the `wicked-repeat`
    object: `done` when the REAL share reaches the target and no mapped behaviour that changed
    since the map was built is left to re-ask (`changed_left`, wicked-garden#1425: those are
    paged through under the same budget ask); `ask` when nothing is left to map,
    when the last page resolved almost nothing of what it framed, when the last two pages added
    no real requirement, or when the grant's pages or minutes are spent; `continue` otherwise.
    `asked_left` counts the placeholders a page of this run asked about and left unresolved, of
    which `asked_once` were never asked again (wicked-garden#1533): when nothing unasked is left,
    the ask offers to ask them again, recommended while asking again can still move the share
    (`_again_can_help`, wicked-garden#1536)."""
    points = doc["points"]
    last = points[-1]
    page = last["page"]
    if last["pct"] >= target:
        line = progress_line(repo, points, target, next_page=None, done=True)
        if changed_left <= 0:
            if assign_left > 0:
                if assign_progress and not _budget_spent(doc, now, max_pages, max_minutes):
                    return {"next": "continue", "line": line +
                            f" · {count(assign_left)} requirement(s) left to give a business domain",
                            "assign_only": True}
                line += f" · {count(assign_left)} requirement(s) left without a business domain"
            return {"next": "done", "line": line}
        line += (f" · {count(changed_left)} mapped behaviour{'s' if changed_left != 1 else ''} "
                 f"changed since the map was built left to re-ask")
        choices = [{"id": "continue", "label": f"Map up to {count(max_pages)} more pages"},
                   FINISH]
        y = page_yield(points)
        if (y is not None and y[1] >= LOW_YIELD_MIN_UNITS and y[0] * LOW_YIELD_PER < y[1]
                and last["page"] > doc["grant"]["page"]):
            # The seat answered almost none of the page (pi r2): asked, not paged on silently.
            return {"next": "ask", "choices": choices, "recommended": "continue",
                    "line": f"{line} · the last page answered under 1 in {LOW_YIELD_PER} of its "
                            f"units: read its review before mapping more"}
        spent = _budget_spent(doc, now, max_pages, max_minutes)
        if spent:
            return {"next": "ask", "choices": choices, "recommended": "continue",
                    "line": f"{line} · budget reached ({spent}; the budget is "
                            f"{count(max_pages)} pages or {count(max_minutes)} minutes)"}
        return {"next": "continue", "line": line}
    # An "again" can reopen the asked placeholders in this run, so they count toward what can
    # still be asked before a minimum is called out of reach (codex r1 on #1533).
    line = progress_line(repo, points, target, next_page=page + 1,
                         left_to_map=left_to_map + asked_left)
    # A target is a whole percentage 1..100 the real share so far must meet: below 1% nothing
    # can be lowered to (codex/agy r1 on #1369 — "lower to 1%" at 0.5% asked again forever).
    lower = ({"id": "lower", "label": _lower_label(repo, last)} if last["pct"] >= 1 else None)
    more = {"id": "continue", "label": f"Map up to {count(max_pages)} more pages"}
    again = ({"id": "again", "label": f"Ask the {count(asked_left)} placeholder"
                                      f"{'s' if asked_left != 1 else ''} again"}
             if asked_left > 0 else None)
    # With changed units left there is always work, so an ask with no "lower" (a share under 1%)
    # still offers a way to finish (codex r2).
    stop = lower if lower is not None else (FINISH if changed_left > 0 else None)
    # Near-zero yield on a full page (domain-real): the page's review passed a page that stated
    # almost nothing (wicked-crew run 4b49cbe1: 3 rules of 500 units). Never mapped on silently,
    # and asked before "nothing left" too (codex on #1375), so the last page is not passed either.
    y = page_yield(points)
    if (y is not None and y[1] >= LOW_YIELD_MIN_UNITS and y[0] * LOW_YIELD_PER < y[1]
            and last["page"] > doc["grant"]["page"]):
        if left_to_map > 0 or changed_left > 0:
            choices = [c for c in (more, stop) if c is not None]
            warn = (f"{line} · the last page resolved under 1 in {LOW_YIELD_PER} of its units: "
                    f"read its review before mapping more")
        elif again is not None:
            # Every unit was asked, but placeholders this run asked about are left: asking them
            # again is a choice, never hidden behind "nothing is left" (wicked-garden#1533).
            choices = [again, lower if lower is not None else FINISH]
            head = progress_line(repo, points, target, next_page=None, left_to_map=0)
            warn = (f"{head} · the last page resolved under 1 in {LOW_YIELD_PER} of its units: "
                    f"read its review · {_asked_text(asked_left, asked_once)}")
            return {"next": "ask", "choices": choices,
                    "recommended": "again" if _again_can_help(points, asked_once)
                    else choices[1]["id"], "line": warn}
        else:
            # Nothing left to ask (agy/codex r2 on #1375): still the operator's word, never a
            # silent "done"; going on hands the share to the coverage step.
            choices = [lower] if lower is not None else [FINISH]
            head = progress_line(repo, points, target, next_page=None, left_to_map=0)
            warn = (f"{head} · the last page "
                    f"resolved under 1 in {LOW_YIELD_PER} of its units and nothing is left to "
                    f"map: read its review")
        return {"next": "ask", "choices": choices, "recommended": choices[0]["id"], "line": warn}
    if left_to_map <= 0 and changed_left <= 0:
        head = progress_line(repo, points, target, next_page=None, left_to_map=0)
        if again is not None:
            # wicked-garden#1533: "nothing left to map" with 263 placeholders a second ask could
            # still resolve steered the operator to lower the minimum. Say what is left and offer it.
            choices = [again, lower if lower is not None else FINISH]
            return {"next": "ask", "choices": choices,
                    "recommended": "again" if _again_can_help(points, asked_once)
                    else choices[1]["id"],
                    "line": f"{head} · {_asked_text(asked_left, asked_once)}"}
        rest = (f"{head} · nothing left to map "
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
        return {"next": "ask", "choices": [c for c in (more, stop) if c is not None],
                "recommended": "lower" if lower is not None else "continue",
                "line": f"{line} · the last two pages added no real requirement"}
    spent = _budget_spent(doc, now, max_pages, max_minutes)
    if spent:
        return {"next": "ask", "choices": [c for c in (more, stop) if c is not None],
                "recommended": "continue",
                "line": f"{line} · budget reached ({spent}; the budget is {count(max_pages)} pages "
                        f"or {count(max_minutes)} minutes)"}
    return {"next": "continue", "line": line}


def marker(decision: dict[str, Any]) -> str:
    """The engine's decision line (wicked-core `repeat`): one compact JSON object."""
    return "wicked-repeat " + json.dumps(decision, ensure_ascii=False, separators=(",", ":"))
