"""rules_file.py — the two files that carry domain extraction across the seat boundary.

A seat container has no `wicked-core`, no `wicked-estate` and no writable store (the broker
relay is read-only by design), so `domain-extraction` splits the harness along the vault line
(wicked-garden#1362):

  1. HOST  `prepare_worklist.py` — `wicked-core coverage` + the hub-first order → the framed
     WORKLIST file in the run's worktree (`wicked-garden/domain-worklist@1`).
  2. SEAT  `extract_loop.py --worklist … --rules-out …` — the model states the rules → the
     RULES file in the same worktree (`wicked-garden/domain-rules@1`). No store, no binaries.
  3. HOST  `apply_rules.py` — checks the rules file against this schema and the store, then
     writes it with today's authorship and validation, and writes `coverage-report.json`.

Both files live in a tree the seat can write, so the host trusts NEITHER: the schema here is
closed (unknown keys are refused, types and sizes are bounded), and the apply step re-derives
everything else (which symbols are unmapped, which files the repository tracks) on the host.

stdlib-only, cross-platform.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

WORKLIST_SCHEMA = "wicked-garden/domain-worklist@1"
RULES_SCHEMA = "wicked-garden/domain-rules@1"

# Where the preset's steps put the two files, relative to the run's worktree.
WORKLIST_REL = ".wicked/domain/worklist.json"
RULES_REL = ".wicked/domain/rules.json"

# Bounds. A rules file is model output carried across a trust boundary: every size is capped.
MAX_RULES_BYTES = 16 * 1024 * 1024
MAX_RULES = 20000
MAX_SYMBOL_ID = 1000
MAX_STATEMENT = 2000
MAX_PROVENANCE_STR = 500
MAX_SOURCE_KINDS = 4
SOURCE_KINDS = frozenset({"code-body", "type-def", "comment", "doc"})

_TOP_KEYS = frozenset({"schema", "seat", "rules"})
_RULE_KEYS = frozenset({"symbol_id", "statement", "confidence", "provenance"})
_PROVENANCE_KEYS = frozenset({"source", "ref", "source_kinds"})
# A seat name rides into the annotation author (`extract-loop:<seat>`): a short plain token.
_SEAT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$")
# C0 controls other than tab and newline (and DEL) never belong in a rule; NUL would also
# break the argv the host hands estate.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class RulesFileRefused(Exception):
    """The whole rules file is refused: nothing in it is applied."""


def _bad_text(value: Any, limit: int, *, allow_empty: bool) -> str | None:
    if not isinstance(value, str):
        return f"is {type(value).__name__}, expected a string"
    if not allow_empty and not value.strip():
        return "is empty"
    if len(value) > limit:
        return f"is {len(value)} characters, the limit is {limit}"
    if _CONTROL_RE.search(value):
        return "contains control characters"
    return None


def check_rule_entry(entry: Any) -> str | None:
    """Why one rules-file entry is outside the schema, or None when it conforms.

    The schema says what an entry may SAY; whether what it says is a usable rule (a non-empty
    statement, grounded provenance, a confidence worth resolving) is the extraction validator's
    call (`_rule_extractor.validate_rule`), exactly as for a rule the host's own model returned:
    a conforming entry that fails it is RISK-flagged, never asserted."""
    if not isinstance(entry, dict):
        return f"entry is {type(entry).__name__}, expected an object"
    extra = sorted(set(entry) - _RULE_KEYS)
    if extra:
        return f"unknown key(s) {extra}"
    for key in ("symbol_id", "statement", "confidence"):
        if key not in entry:
            return f"missing {key!r}"
    why = _bad_text(entry["symbol_id"], MAX_SYMBOL_ID, allow_empty=False)
    if why:
        return f"symbol_id {why}"
    why = _bad_text(entry["statement"], MAX_STATEMENT, allow_empty=True)
    if why:
        return f"statement {why}"
    conf = entry["confidence"]
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not math.isfinite(conf) \
            or not 0.0 <= conf <= 1.0:
        return f"confidence {conf!r} is not a number in [0,1]"
    if "provenance" in entry:
        prov = entry["provenance"]
        if not isinstance(prov, dict):
            return f"provenance is {type(prov).__name__}, expected an object"
        extra = sorted(set(prov) - _PROVENANCE_KEYS)
        if extra:
            return f"provenance has unknown key(s) {extra}"
        for key in ("source", "ref"):
            if key in prov:
                why = _bad_text(prov[key], MAX_PROVENANCE_STR, allow_empty=True)
                if why:
                    return f"provenance.{key} {why}"
        if "source_kinds" in prov:
            kinds = prov["source_kinds"]
            if not isinstance(kinds, list) or len(kinds) > MAX_SOURCE_KINDS:
                return f"provenance.source_kinds must be a list of at most {MAX_SOURCE_KINDS}"
            bad = [k for k in kinds if not isinstance(k, str) or k not in SOURCE_KINDS]
            if bad:
                return f"provenance.source_kinds {bad!r} outside {sorted(SOURCE_KINDS)}"
    return None


def check_rules_doc(doc: Any) -> tuple[str, list[dict], list[dict]]:
    """Check a parsed rules document. Returns (seat, accepted, refused): `accepted` are the
    conforming entries (first occurrence of each symbol), `refused` is one
    `{index, symbol_id, why}` per entry outside the schema or repeated.

    Raises RulesFileRefused when the document itself is outside the schema (wrong tag,
    unknown top-level key, a bad seat name, too many entries)."""
    if not isinstance(doc, dict):
        raise RulesFileRefused(f"the rules file is {type(doc).__name__}, expected a JSON object")
    extra = sorted(set(doc) - _TOP_KEYS)
    if extra:
        raise RulesFileRefused(f"the rules file has unknown top-level key(s) {extra}")
    if doc.get("schema") != RULES_SCHEMA:
        raise RulesFileRefused(f"the rules file's schema is {doc.get('schema')!r}, expected "
                               f"{RULES_SCHEMA!r}")
    seat = doc.get("seat", "")
    if not isinstance(seat, str) or (seat and not _SEAT_RE.match(seat)):
        raise RulesFileRefused(f"the rules file's seat {seat!r} is not a plain seat name")
    rules = doc.get("rules")
    if not isinstance(rules, list):
        raise RulesFileRefused("the rules file has no `rules` list")
    if len(rules) > MAX_RULES:
        raise RulesFileRefused(f"the rules file has {len(rules)} entries, the limit is {MAX_RULES}")
    accepted: list[dict] = []
    refused: list[dict] = []
    seen: set[str] = set()
    for i, entry in enumerate(rules):
        why = check_rule_entry(entry)
        sid = entry.get("symbol_id") if isinstance(entry, dict) else None
        sid = sid if isinstance(sid, str) else None
        if why is None and sid in seen:
            why = "repeats a symbol an earlier entry already covers"
        if why is not None:
            refused.append({"index": i, "symbol_id": (sid or "")[:MAX_SYMBOL_ID], "why": why})
            continue
        seen.add(sid)
        accepted.append(entry)
    return seat, accepted, refused


def rules_doc(seat: str, rules: list[dict]) -> dict:
    return {"schema": RULES_SCHEMA, "seat": seat, "rules": rules}


def seat_name(raw: str | None) -> str:
    """The seat name a rules file declares: the run agent when it is a plain token, else ''."""
    raw = (raw or "").strip()
    return raw if _SEAT_RE.match(raw) else ""


# --- paths inside the worktree ----------------------------------------------------------------

def inside(base: Path, rel: str) -> Path:
    """`rel` under `base`, refusing an absolute path, a `..` step, or a symlink on the way.

    The worktree is seat-writable: a seat could plant `.wicked/domain` as a link to anywhere on
    the host, and a host step that followed it would read or write outside the run. Missing
    components are fine (the caller creates them)."""
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise RulesFileRefused(f"{rel!r} must be a relative path inside the run's worktree")
    cur = Path(base)
    for part in p.parts:
        cur = cur / part
        if cur.is_symlink():
            raise RulesFileRefused(f"{rel!r}: {cur.name!r} is a symbolic link; refusing to "
                                   "follow it out of the run's worktree")
    return cur


def read_json_file(base: Path, rel: str, *, limit: int = MAX_RULES_BYTES) -> Any:
    """Read a JSON file under `base` (see `inside`), refusing anything but a regular file
    within `limit` bytes."""
    path = inside(base, rel)
    if not path.exists():
        raise FileNotFoundError(str(rel))
    if not path.is_file():
        raise RulesFileRefused(f"{rel!r} is not a regular file")
    size = path.stat().st_size
    if size > limit:
        raise RulesFileRefused(f"{rel!r} is {size} bytes, the limit is {limit}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:  # ValueError covers JSON and UTF-8 decode errors
        raise RulesFileRefused(f"{rel!r} is not valid UTF-8 JSON: {e}") from e


def write_json_file(base: Path, rel: str, doc: Any) -> Path:
    """Write `doc` to `rel` under `base` atomically (temp file in the same directory, then
    rename), creating the directory; refuses symlinks on the way (see `inside`)."""
    path = inside(base, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    inside(base, rel)  # re-check: a component created concurrently must not be a link either
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def tracked_files(repo_root: str | Path) -> set[str]:
    """Every path git tracks in the repository at `repo_root`, repo-relative with `/` — the
    authority for "a file in the repo". Fails loud: no answer is never "everything"."""
    import subprocess
    try:
        proc = subprocess.run(["git", "-C", str(repo_root), "ls-files", "-z"], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"git ls-files in {repo_root} could not run: {e}") from e
    if proc.returncode != 0:
        raise RuntimeError(f"git ls-files in {repo_root} exited {proc.returncode}: "
                           f"{proc.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return {p for p in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if p}
