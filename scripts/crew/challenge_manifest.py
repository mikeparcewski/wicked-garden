#!/usr/bin/env python3
"""
Challenge-artifact manager for the crew contrarian gate (Issues #442 + #721).

The contrarian specialist is the persistent minority-view keeper. Its work
is materialised as ``phases/design/challenge-artifacts.md`` — a file that
is carried across sessions.

v2 schema (Issue #721 — "structured dissent artifact")
------------------------------------------------------
The artifact MUST contain four sections, each with a minimum-content rule:

    1. ## Incongruent Representation     (>= 3 sentences)
    2. ## Unasked Question               (>= 1 question, i.e. one '?')
    3. ## Steelman of Alternative Path   (>= 5 sentences, advocate voice)
    4. ## Dissent Vectors Covered        (>= 3 '[x]' checkmarks across
                                          the canonical six vectors:
                                          security, cost, operability,
                                          ethics, ux, maintenance)

Convergence collapse (v2): coverage of fewer than 3 dissent vectors fires
``CONDITIONAL`` with reason "convergence collapse: only N dissent vector(s)
covered, >= 3 required". Same rule applies whether the count is derived
from the markdown checkmark list or the optional sidecar.

Optional sidecar
----------------
``phases/{phase}/challenge-artifacts.meta.json`` — schema:

    {"vectors": ["security", "cost", ...], "questions_count": int}

If the sidecar is present and well-formed, ``parse_meta_sidecar`` returns
its structured contents and ``detect_convergence_collapse`` prefers it
over markdown re-parsing (faster + less brittle for tooling that already
emits the sidecar).

Backward-compat note
--------------------
v1 (``strongest opposing view`` / ``challenges`` / ``convergence check`` /
``resolution``) is replaced — there is no flag to revert. Callers that
depended on the per-challenge ``CH-XX`` block parser still get
``parsed["challenges"]`` because the old block format is still recognised
*anywhere in the artifact* (parsing is unscoped — the regex scans the whole
body). The blocks are optional in v2 and the dissent-vector list is the
load-bearing convergence signal.

This module is intentionally stdlib-only so the PreToolUse hook can
import it without pulling in any third-party dependency.

Public API
----------
    parse_artifact(text)                                -> dict
    parse_dissent_vectors(text)                         -> list[str]
    parse_meta_sidecar(project_dir, phase=...)          -> dict | None
    validate_artifact(text)                             -> str | None
    artifact_exists(project_dir, phase=...)             -> bool
    artifact_satisfies_gate(project_dir, phase=...)     -> (bool, str)
    detect_convergence_collapse(parsed_or_iterable)     -> (bool, str)
    is_required(complexity, phase)                      -> bool
    required_sections()                                 -> tuple[str, ...]
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Filename that the contrarian maintains inside ``phases/{phase}/``.
CHALLENGE_ARTIFACT_FILENAME = "challenge-artifacts.md"

#: Optional sidecar consumed by ``parse_meta_sidecar``. Same directory.
CHALLENGE_ARTIFACT_META_FILENAME = "challenge-artifacts.meta.json"

#: Phase that the challenge artifact is anchored to by default.
DEFAULT_CHALLENGE_PHASE = "design"

#: Minimum complexity at which the challenge gate is enforced.
DEFAULT_MIN_COMPLEXITY = 4

#: Minimum byte size for a well-formed artifact — below this the file is
#: treated as a stub even if all section headers happen to be present.
MIN_ARTIFACT_BYTES = 300

#: Minimum number of dissent vectors that must be covered (v2 schema).
#: Below this the convergence-collapse detector fires.
MIN_DISSENT_VECTORS = 3

# v2 required section headers. Header matching is case-insensitive and
# tolerant of ``##`` or ``###``.
_REQUIRED_SECTIONS = (
    "incongruent representation",
    "unasked question",
    "steelman of alternative path",
    "dissent vectors covered",
)

# Canonical dissent-vector names (lowercased, in checklist order).
_DISSENT_VECTORS = (
    "security",
    "cost",
    "operability",
    "ethics",
    "ux",
    "maintenance",
)

# Minimum-content thresholds per section.
_MIN_INCONGRUENT_SENTENCES = 3
_MIN_STEELMAN_SENTENCES = 5
_MIN_UNASKED_QUESTIONS = 1

# Optional CH-XX block parser, kept for tools that still emit them. The
# regex scans the whole body — there is no required parent section. Not
# load-bearing in v2; the dissent-vector list is the convergence signal.
_CHALLENGE_HEADER_RE = re.compile(
    r"^#{2,4}\s+challenge\s+([A-Za-z0-9][A-Za-z0-9_\-]{0,32})\s*[:\-]?\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
_FIELD_RE = re.compile(
    r"^\s*[-*]\s*([a-z][a-z0-9_\-]*)\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Section-extraction regex: capture from one ## header to the next ##/EOF.
_SECTION_HEADER_RE = re.compile(
    r"^#{2,4}\s+(.+?)\s*$",
    re.MULTILINE,
)

# Checkmark line: ``- [x] vector_name``  (case-insensitive, x or X).
_CHECKMARK_RE = re.compile(
    r"^\s*[-*]\s*\[[xX]\]\s+([a-z][a-z0-9_\-/]*)",
    re.MULTILINE,
)

# Sentence/question counters strip fenced and inline code blocks first so
# punctuation inside ``v2.0`` or ``foo()`` does not inflate the count, then
# only count terminators followed by whitespace or end-of-text. Crude but
# good enough for a structural gate.
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_SENTENCE_TERMINATOR_RE = re.compile(r"[.!](?=\s|$)|\?(?=\s|$)")
_QUESTION_TERMINATOR_RE = re.compile(r"\?(?=\s|$)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def required_sections() -> tuple[str, ...]:
    """Return the tuple of v2 required section headers (lowercased)."""
    return _REQUIRED_SECTIONS


def _has_section(text: str, heading: str) -> bool:
    # Mirror _extract_section's tolerance — ``\b`` for word boundary, then
    # ``.*$`` to allow trailing decoration on the heading line.
    pattern = re.compile(
        rf"^#{{2,4}}\s+{re.escape(heading)}\b.*$",
        re.IGNORECASE | re.MULTILINE,
    )
    return bool(pattern.search(text))


def _extract_section(text: str, heading: str) -> str:
    """Return the body text of the first section matching ``heading``.

    Empty string when not found. The body runs from the line after the
    matched header to (exclusive) the next ``##``/``###``/``####`` header
    or end-of-file.
    """
    # Tolerate trailing decoration like ``## Incongruent Representation (v2)``
    # or ``## Steelman of Alternative Path — design``. ``\b`` enforces a word
    # boundary so ``unasked questions`` does not match ``unasked question``.
    pattern = re.compile(
        rf"^#{{2,4}}\s+{re.escape(heading)}\b.*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_header = _SECTION_HEADER_RE.search(text, pos=start)
    end = next_header.start() if next_header else len(text)
    return text[start:end]


def _strip_code(text: str) -> str:
    """Remove fenced ``` blocks and inline `code` spans before counting.

    Punctuation inside ``v2.0`` or ``arr[1].len()`` should not inflate the
    sentence or question count.
    """
    return _INLINE_CODE_RE.sub("", _CODE_BLOCK_RE.sub("", text))


def _count_sentences(text: str) -> int:
    """Count sentence terminators outside code blocks."""
    return len(_SENTENCE_TERMINATOR_RE.findall(_strip_code(text)))


def _count_questions(text: str) -> int:
    """Count ``?`` terminators outside code blocks."""
    return len(_QUESTION_TERMINATOR_RE.findall(_strip_code(text)))


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_dissent_vectors(text: str) -> list[str]:
    """Return the list of canonical dissent vectors marked ``[x]``.

    Only canonical names from :data:`_DISSENT_VECTORS` count — checking
    ``- [x] vibes`` does not contribute to the coverage tally. Order
    follows the canonical list, not the file order, and duplicates are
    deduplicated.
    """
    section = _extract_section(text or "", "dissent vectors covered")
    if not section:
        return []
    found = {match.group(1).lower() for match in _CHECKMARK_RE.finditer(section)}
    return [v for v in _DISSENT_VECTORS if v in found]


def parse_meta_sidecar(
    project_dir: Path,
    phase: str = DEFAULT_CHALLENGE_PHASE,
) -> "dict | None":
    """Return parsed sidecar dict, or ``None`` if absent / unreadable.

    Schema enforced (loosely)::

        {"vectors": [str, ...], "questions_count": int}

    Unknown fields are preserved. ``vectors`` are filtered to canonical
    names and lowercased. Returns ``None`` on missing file, unreadable
    file, malformed JSON, or wrong root type — never raises.
    """
    try:
        path = Path(project_dir) / "phases" / phase / CHALLENGE_ARTIFACT_META_FILENAME
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None

    vectors_raw = raw.get("vectors", [])
    if isinstance(vectors_raw, list):
        vectors = [
            str(v).lower()
            for v in vectors_raw
            if isinstance(v, str) and str(v).lower() in _DISSENT_VECTORS
        ]
    else:
        vectors = []

    qcount_raw = raw.get("questions_count", 0)
    try:
        questions_count = int(qcount_raw)
    except (TypeError, ValueError):
        questions_count = 0

    out = dict(raw)
    out["vectors"] = vectors
    out["questions_count"] = questions_count
    return out


def parse_artifact(text: str) -> dict:
    """Parse a v2 ``challenge-artifacts.md`` body into a structured dict.

    Returned dict shape::

        {
            "sections_present": [str, ...],
            "sections_missing": [str, ...],
            "dissent_vectors": [str, ...],   # canonical vectors with [x]
            "questions_count": int,           # '?' in unasked-question section
            "incongruent_sentences": int,
            "steelman_sentences": int,
            "challenges": [ {id, title, theme, status, raised_by,
                             steelman}, ... ],   # legacy CH-XX blocks
            "bytes": int,
        }

    Never raises on malformed markdown — it records what was parseable
    and leaves judgment to :func:`validate_artifact`.
    """
    body = text or ""

    sections_present: list[str] = []
    sections_missing: list[str] = []
    for section in _REQUIRED_SECTIONS:
        (sections_present if _has_section(body, section) else sections_missing).append(section)

    dissent_vectors = parse_dissent_vectors(body)
    questions_count = _count_questions(_extract_section(body, "unasked question"))
    incongruent_sentences = _count_sentences(_extract_section(body, "incongruent representation"))
    steelman_sentences = _count_sentences(_extract_section(body, "steelman of alternative path"))

    # Legacy CH-XX block parsing (now optional, but preserved).
    challenges: list[dict] = []
    matches = list(_CHALLENGE_HEADER_RE.finditer(body))
    for i, match in enumerate(matches):
        ch_id = match.group(1).strip()
        title = (match.group(2) or "").strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]
        fields: dict[str, str] = {}
        for fmatch in _FIELD_RE.finditer(block):
            fields[fmatch.group(1).strip().lower()] = fmatch.group(2).strip()
        challenges.append({
            "id": ch_id,
            "title": title,
            "theme": fields.get("theme", "").lower(),
            "status": fields.get("status", "open").lower(),
            "raised_by": fields.get("raised_by", ""),
            "steelman": fields.get("steelman", ""),
        })

    return {
        "sections_present": sections_present,
        "sections_missing": sections_missing,
        "dissent_vectors": dissent_vectors,
        "questions_count": questions_count,
        "incongruent_sentences": incongruent_sentences,
        "steelman_sentences": steelman_sentences,
        "challenges": challenges,
        "bytes": len(body.encode("utf-8", errors="replace")),
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_artifact(text: str) -> "str | None":
    """Return an error message or ``None`` for a v2-conformant artifact.

    Checks performed (in order — first failure wins for clarity):
      1. Byte size >= :data:`MIN_ARTIFACT_BYTES`.
      2. All four required sections present.
      3. Incongruent representation has >= 3 sentences.
      4. Unasked question has >= 1 ``?``.
      5. Steelman of alternative path has >= 5 sentences.
      6. Dissent vectors covered has >= 3 canonical ``[x]`` checkmarks.
    """
    parsed = parse_artifact(text)

    if parsed["bytes"] < MIN_ARTIFACT_BYTES:
        return (
            f"artifact is too small ({parsed['bytes']} bytes, "
            f"minimum {MIN_ARTIFACT_BYTES}). A v2 challenge artifact must "
            f"contain incongruent representation, unasked question, "
            f"steelman of alternative path, and dissent vectors covered."
        )

    missing = parsed["sections_missing"]
    if missing:
        return (
            f"challenge artifact is missing required section(s): "
            f"{', '.join(missing)}."
        )

    if parsed["incongruent_sentences"] < _MIN_INCONGRUENT_SENTENCES:
        return (
            f"'incongruent representation' has only "
            f"{parsed['incongruent_sentences']} sentence(s); "
            f">= {_MIN_INCONGRUENT_SENTENCES} required."
        )

    if parsed["questions_count"] < _MIN_UNASKED_QUESTIONS:
        return (
            f"'unasked question' has no '?' — at least "
            f"{_MIN_UNASKED_QUESTIONS} question is required."
        )

    if parsed["steelman_sentences"] < _MIN_STEELMAN_SENTENCES:
        return (
            f"'steelman of alternative path' has only "
            f"{parsed['steelman_sentences']} sentence(s); "
            f">= {_MIN_STEELMAN_SENTENCES} required, written as advocate."
        )

    if len(parsed["dissent_vectors"]) < MIN_DISSENT_VECTORS:
        return (
            f"'dissent vectors covered' has only "
            f"{len(parsed['dissent_vectors'])} canonical [x] checkmark(s); "
            f">= {MIN_DISSENT_VECTORS} required from "
            f"{{{', '.join(_DISSENT_VECTORS)}}}."
        )

    return None


# ---------------------------------------------------------------------------
# Convergence collapse detection
# ---------------------------------------------------------------------------

def detect_convergence_collapse(
    parsed_or_iterable,
) -> "tuple[bool, str]":
    """Return ``(collapsed, reason)`` for v2 dissent-vector coverage.

    Accepted inputs:
      * a ``parse_artifact`` dict — uses its ``"dissent_vectors"`` list
      * a list of vector-name strings — counted directly
      * a legacy iterable of challenge dicts — back-compat: their
        ``theme`` values are extracted and intersected with the canonical
        vector list.

    Convergence has *collapsed* when fewer than
    :data:`MIN_DISSENT_VECTORS` distinct canonical vectors are covered.
    """
    vectors: list[str]

    if isinstance(parsed_or_iterable, dict) and "dissent_vectors" in parsed_or_iterable:
        vectors = list(parsed_or_iterable["dissent_vectors"])
    elif isinstance(parsed_or_iterable, (list, tuple)):
        items = list(parsed_or_iterable)
        if items and all(isinstance(it, str) for it in items):
            vectors = [v.lower() for v in items if v.lower() in _DISSENT_VECTORS]
        else:
            # Legacy challenge-dict iterable
            themes = {
                (c.get("theme") or "").lower()
                for c in items
                if isinstance(c, dict)
            }
            vectors = [v for v in _DISSENT_VECTORS if v in themes]
    else:
        vectors = []

    distinct = sorted(set(vectors))
    if len(distinct) < MIN_DISSENT_VECTORS:
        return True, (
            f"convergence collapse: only {len(distinct)} dissent vector(s) "
            f"covered, >= {MIN_DISSENT_VECTORS} required. Covered: "
            f"{distinct or '[]'}. Canonical set: "
            f"{{{', '.join(_DISSENT_VECTORS)}}}."
        )
    return False, ""


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------

def is_required(complexity: int, phase: str = "build") -> bool:
    """Return True iff a challenge artifact is required for this phase.

    Configurable via env var ``WG_CHALLENGE_MIN_COMPLEXITY`` (default 4).
    """
    if phase != "build":
        return False
    try:
        min_cx = int(os.environ.get("WG_CHALLENGE_MIN_COMPLEXITY") or DEFAULT_MIN_COMPLEXITY)
    except ValueError:
        min_cx = DEFAULT_MIN_COMPLEXITY
    return int(complexity) >= min_cx


def _artifact_path(project_dir: Path, phase: str = DEFAULT_CHALLENGE_PHASE) -> Path:
    return Path(project_dir) / "phases" / phase / CHALLENGE_ARTIFACT_FILENAME


def artifact_exists(project_dir: Path, phase: str = DEFAULT_CHALLENGE_PHASE) -> bool:
    """Return True iff ``phases/{phase}/challenge-artifacts.md`` exists."""
    try:
        return _artifact_path(project_dir, phase).is_file()
    except Exception:
        return False


def artifact_satisfies_gate(
    project_dir: Path,
    phase: str = DEFAULT_CHALLENGE_PHASE,
) -> "tuple[bool, str]":
    """Return ``(ok, reason)`` for whether the challenge gate is cleared.

    ``ok=True`` when the artifact validates AND the dissent-vector
    coverage does not trigger convergence collapse. Coverage is read
    from the optional sidecar when present (faster + tooling-friendly),
    otherwise from the markdown checklist.
    """
    path = _artifact_path(project_dir, phase)
    if not path.is_file():
        return False, (
            f"challenge artifact missing: {path.as_posix()} does not "
            f"exist. Invoke the contrarian specialist to produce it."
        )

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return False, f"challenge artifact unreadable: {exc}"

    err = validate_artifact(text)
    if err:
        return False, err

    sidecar = parse_meta_sidecar(project_dir, phase=phase)
    if sidecar is not None and sidecar.get("vectors"):
        collapsed, why = detect_convergence_collapse(sidecar["vectors"])
    else:
        collapsed, why = detect_convergence_collapse(parse_artifact(text))
    if collapsed:
        return False, why

    return True, ""


# ---------------------------------------------------------------------------
# CLI entrypoint (small — used by commands / tests)
# ---------------------------------------------------------------------------

def _cli(argv: list[str]) -> int:
    """Minimal CLI. Usage::

        challenge_manifest.py validate <path>
        challenge_manifest.py check <project_dir> [<phase>]
    """
    if len(argv) < 2:
        print("usage: challenge_manifest.py validate|check <path> [<phase>]")
        return 2

    cmd = argv[1]
    if cmd == "validate":
        if len(argv) < 3:
            print("usage: challenge_manifest.py validate <path>")
            return 2
        path = Path(argv[2])
        if not path.is_file():
            print(f"error: {path} is not a file")
            return 1
        text = path.read_text(encoding="utf-8", errors="replace")
        err = validate_artifact(text)
        if err:
            print(f"INVALID: {err}")
            return 1
        collapsed, why = detect_convergence_collapse(parse_artifact(text))
        if collapsed:
            print(f"CONVERGENCE-COLLAPSE: {why}")
            return 1
        print("OK")
        return 0

    if cmd == "check":
        if len(argv) < 3:
            print("usage: challenge_manifest.py check <project_dir> [<phase>]")
            return 2
        project_dir = Path(argv[2])
        phase = argv[3] if len(argv) >= 4 else DEFAULT_CHALLENGE_PHASE
        ok, reason = artifact_satisfies_gate(project_dir, phase)
        if ok:
            print("OK")
            return 0
        print(f"BLOCKED: {reason}")
        return 1

    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":  # pragma: no cover — CLI wrapper
    import sys as _sys
    _sys.exit(_cli(_sys.argv))
