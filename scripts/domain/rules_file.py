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
import stat
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
# The seat a file DECLARES: a short plain token, reported as declared. It is never authorship —
# the file is seat-written, so a name in it proves nothing (the host authors what it applies).
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
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:  # a lone surrogate (`\\ud800` parses as JSON, never encodes)
        return "is not valid Unicode"
    return None


def _shown(value: Any, limit: int = MAX_SYMBOL_ID) -> str:
    """A string from the document, safe to print and to serialize into a report."""
    text = value if isinstance(value, str) else ""
    return text[:limit].encode("utf-8", "backslashreplace").decode("utf-8")


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
        return f"unknown key(s) {_shown(repr(extra), 200)}"
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
    # The range test comes first: a JSON integer can be too large to convert to a float.
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1 \
            or not math.isfinite(conf):
        return f"confidence {_shown(repr(conf), 40)} is not a number in [0,1]"
    if "provenance" in entry:
        prov = entry["provenance"]
        if not isinstance(prov, dict):
            return f"provenance is {type(prov).__name__}, expected an object"
        extra = sorted(set(prov) - _PROVENANCE_KEYS)
        if extra:
            return f"provenance has unknown key(s) {_shown(repr(extra), 200)}"
        for key, limit in (("source", MAX_PROVENANCE_STR), ("ref", MAX_SYMBOL_ID)):
            if key in prov:
                why = _bad_text(prov[key], limit, allow_empty=True)
                if why:
                    return f"provenance.{key} {why}"
        if "source_kinds" in prov:
            kinds = prov["source_kinds"]
            if not isinstance(kinds, list) or len(kinds) > MAX_SOURCE_KINDS:
                return f"provenance.source_kinds must be a list of at most {MAX_SOURCE_KINDS}"
            bad = [k for k in kinds if not isinstance(k, str) or k not in SOURCE_KINDS]
            if bad:
                return (f"provenance.source_kinds {_shown(repr(bad), 100)} outside "
                        f"{sorted(SOURCE_KINDS)}")
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
        raise RulesFileRefused(f"the rules file has unknown top-level key(s) "
                               f"{_shown(repr(extra), 200)}")
    if doc.get("schema") != RULES_SCHEMA:
        raise RulesFileRefused(f"the rules file's schema is {_shown(repr(doc.get('schema')), 80)}, "
                               f"expected {RULES_SCHEMA!r}")
    seat = doc.get("seat", "")
    if not isinstance(seat, str) or (seat and not _SEAT_RE.fullmatch(seat)):
        raise RulesFileRefused(f"the rules file's seat {_shown(repr(seat), 60)} is not a plain "
                               "seat name")
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
            refused.append({"index": i, "symbol_id": _shown(sid), "why": why})
            continue
        seen.add(sid)
        accepted.append(entry)
    return seat, accepted, refused


def rules_doc(seat: str, rules: list[dict]) -> dict:
    return {"schema": RULES_SCHEMA, "seat": seat, "rules": rules}


def seat_name(raw: str | None) -> str:
    """The seat name a rules file declares: the run agent when it is a plain token, else ''."""
    raw = (raw or "").strip()
    return raw if _SEAT_RE.fullmatch(raw) else ""


# --- files inside the worktree ----------------------------------------------------------------
#
# The worktree is seat-writable: a seat could plant `.wicked/domain` (or the file itself) as a
# symlink to anywhere on the host, or a directory where a file is expected. Checking a path and
# then opening it races a seat that swaps it in between, so on POSIX every component is opened
# relative to its parent's descriptor with O_NOFOLLOW, the file is checked through its own
# descriptor, and a write goes to a fresh temp file in the checked directory that is then renamed
# over the target (a rename replaces a planted link or hard link; it never writes through it).
# Windows has no descriptor-relative opens (and no container seat); there the path checks apply.

_FD_SAFE = (os.name == "posix" and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
            and {os.open, os.mkdir, os.rename, os.stat, os.unlink} <= os.supports_dir_fd)


def _parts(rel: str) -> tuple[str, ...]:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or not p.parts or p.parts[-1] in (".", ""):
        raise RulesFileRefused(f"{rel!r} must be a relative path inside the run's worktree")
    return p.parts


def inside(base: Path, rel: str) -> Path:
    """`rel` under `base`, refusing an absolute path, a `..` step, or a symlink on the way (the
    path-level check; the I/O below re-checks through descriptors)."""
    cur = Path(base)
    for part in _parts(rel):
        cur = cur / part
        if cur.is_symlink():
            raise RulesFileRefused(f"{rel!r}: {cur.name!r} is a symbolic link; refusing to "
                                   "follow it out of the run's worktree")
    return cur


def _open_dirs(base: Path, rel: str, dirs: tuple[str, ...], create: bool) -> int:
    """A descriptor for `base/dirs…`, each component opened no-follow through its parent."""
    fd = os.open(str(base), os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in dirs:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            try:
                nfd = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
                nfd = os.open(part, flags, dir_fd=fd)
            except OSError as e:  # ELOOP (a symlink) or ENOTDIR (not a directory)
                raise RulesFileRefused(f"{rel!r}: {part!r} is not a directory of the run's "
                                       f"worktree ({e.strerror})") from None
            os.close(fd)
            fd = nfd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _leaf_must_be_file_or_absent(dfd: int, rel: str, leaf: str) -> None:
    try:
        st = os.stat(leaf, dir_fd=dfd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(st.st_mode):
        raise RulesFileRefused(f"{rel!r} exists and is not a regular file")


def check_writable(base: Path, rel: str) -> None:
    """Refuse now, before anything else is written, a destination a later write would refuse:
    a symlink or non-directory on the way, or something other than a regular file at the leaf.
    Creates the missing directories."""
    parts = _parts(rel)
    if not _FD_SAFE:
        path = inside(base, rel)
        if path.exists() and not path.is_file():
            raise RulesFileRefused(f"{rel!r} exists and is not a regular file")
        return
    dfd = _open_dirs(base, rel, parts[:-1], create=True)
    try:
        _leaf_must_be_file_or_absent(dfd, rel, parts[-1])
    finally:
        os.close(dfd)


def _decode(rel: str, raw: bytes, limit: int) -> Any:
    if len(raw) > limit:
        raise RulesFileRefused(f"{rel!r} is over the {limit}-byte limit")
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError as e:  # JSON and UTF-8 decode errors
        raise RulesFileRefused(f"{rel!r} is not valid UTF-8 JSON: {e}") from e


def read_json_file(base: Path, rel: str, *, limit: int = MAX_RULES_BYTES) -> Any:
    """Read a JSON file under `base`, refusing anything but a regular file within `limit` bytes
    reached without a symlink. FileNotFoundError when it is absent."""
    parts = _parts(rel)
    if not _FD_SAFE:
        path = inside(base, rel)
        if not path.exists():
            raise FileNotFoundError(str(rel))
        if not path.is_file():
            raise RulesFileRefused(f"{rel!r} is not a regular file")
        with open(path, "rb") as f:
            return _decode(rel, f.read(limit + 1), limit)
    dfd = _open_dirs(base, rel, parts[:-1], create=False)
    try:
        try:
            ffd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        except FileNotFoundError:
            raise
        except OSError as e:
            raise RulesFileRefused(f"{rel!r} could not be opened as a plain file ({e.strerror})"
                                   ) from None
    finally:
        os.close(dfd)
    with os.fdopen(ffd, "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise RulesFileRefused(f"{rel!r} is not a regular file")
        return _decode(rel, f.read(limit + 1), limit)


def write_json_file(base: Path, rel: str, doc: Any) -> None:
    """Write `doc` to `rel` under `base` atomically: a fresh temp file in the checked directory,
    renamed over the target. Creates missing directories; refuses symlinks and non-directories
    on the way and a non-file at the leaf."""
    parts = _parts(rel)
    data = (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8", "backslashreplace")
    if not _FD_SAFE:
        path = inside(base, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return
    dfd = _open_dirs(base, rel, parts[:-1], create=True)
    try:
        _leaf_must_be_file_or_absent(dfd, rel, parts[-1])
        tmp = f".tmp-{os.getpid()}-{os.urandom(6).hex()}.json"
        ffd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=dfd)
        try:
            with os.fdopen(ffd, "wb") as f:
                f.write(data)
            # rename(2) replaces the target atomically on POSIX (os.replace is the same call).
            os.rename(tmp, parts[-1], src_dir_fd=dfd, dst_dir_fd=dfd)
        except BaseException:
            try:
                os.unlink(tmp, dir_fd=dfd)
            except OSError:
                pass
            raise
    finally:
        os.close(dfd)


def tracked_files(repo_root: str | Path) -> set[str]:
    """Every path git tracks in the repository at `repo_root`, repo-relative with `/` — the
    authority for "a file in the repo". Fails loud: no answer is never "everything"."""
    import subprocess
    try:
        # core.fsmonitor would run a configured command; the repository's config is shared with
        # its worktrees, so it is not taken on trust here.
        proc = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(repo_root),
                               "ls-files", "-z"], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"git ls-files in {repo_root} could not run: {e}") from e
    if proc.returncode != 0:
        raise RuntimeError(f"git ls-files in {repo_root} exited {proc.returncode}: "
                           f"{proc.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return {p for p in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if p}
