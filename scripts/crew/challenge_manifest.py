#!/usr/bin/env python3
"""
Challenge-artifact manager for the crew contrarian gate (Issue #442).

The contrarian specialist is the persistent minority-view keeper. Its work
is materialised as ``phases/design/challenge-artifacts.md`` — a file that
is carried across sessions and must contain, at minimum:

    * the strongest articulated opposing position (steelman)
    * a list of concrete challenges raised against the dominant direction
    * a convergence-collapse check (are all challenges pointing one way?)
    * a resolution section for each challenge

This module is intentionally stdlib-only so the PreToolUse hook can
import it without pulling in any third-party dependency. Parsing is done
with regex on a small, structured markdown format (NOT arbitrary
markdown) to keep behaviour deterministic and fast.

Public API
----------
    parse_artifact(text)            -> dict
    validate_artifact(text)         -> str | None
    artifact_exists(project_dir, phase="design")  -> bool
    artifact_satisfies_gate(project_dir, phase="design") -> (bool, str)
    detect_convergence_collapse(challenges) -> (bool, str)
    is_required(complexity, phase)  -> bool
    required_sections()             -> tuple[str, ...]

Design rationale
----------------
* The gate must *never* silently pass. If the file is missing or the
  steelman section is empty, ``artifact_satisfies_gate`` returns
  ``(False, reason)`` so the hook can emit a precise blocking message.
* Convergence collapse is a second-order check: even with several
  challenges, if they all share the same theme we treat the dissent
  surface as insufficient. The heuristic is conservative — it only
  flags collapse when ``len(challenges) >= 3`` *and* the themes set has
  size 1. That way small projects (1-2 challenges) are not penalised
  for not being broad.
* Complexity threshold is 4 by default (configurable via env var
  ``WG_CHALLENGE_MIN_COMPLEXITY``). Below 4 the artifact is optional —
  the gate returns ``(True, "")`` automatically.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Filename that the contrarian maintains inside ``phases/{phase}/``.
CHALLENGE_ARTIFACT_FILENAME = "challenge-artifacts.md"

#: Phase that the challenge artifact is anchored to by default.
DEFAULT_CHALLENGE_PHASE = "design"

#: Minimum complexity at which the challenge gate is enforced.
DEFAULT_MIN_COMPLEXITY = 4

#: Minimum byte size for a well-formed artifact — below this the file is
#: treated as a stub even if all section headers happen to be present.
MIN_ARTIFACT_BYTES = 300

#: Minimum number of challenges that must be present before convergence
#: collapse can be reported. Small dissent surfaces are not penalised.
CONVERGENCE_MIN_CHALLENGES = 3

# Required section headers. The artifact must contain *all* of these.
# Header matching is case-insensitive and tolerant of ``##`` or ``###``.
_REQUIRED_SECTIONS = (
    "strongest opposing view",   # the steelman
    "challenges",                # enumerated challenges with IDs
    "convergence check",         # explicit collapse self-assessment
    "resolution",                # per-challenge disposition
)

# A single challenge is expected to look like:
#     ### Challenge CH-01: short-title
#     - theme: {concurrency,correctness,security,...}
#     - raised_by: contrarian
#     - status: open | resolved
#     - steelman: ...
_CHALLENGE_HEADER_RE = re.compile(
    r"^#{2,4}\s+challenge\s+([A-Za-z0-9][A-Za-z0-9_\-]{0,32})\s*[:\-]?\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)

# Bullet field within a challenge block: ``- key: value``.
_FIELD_RE = re.compile(
    r"^\s*[-*]\s*([a-z][a-z0-9_\-]*)\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# A resolved challenge must include a written steelman field, even after
# resolution — this is the "cannot close without a steelman" rule.
_MIN_STEELMAN_LENGTH = 40


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def required_sections() -> tuple[str, ...]:
    """Return the tuple of required section headers (lowercased)."""
    return _REQUIRED_SECTIONS


def _has_section(text: str, heading: str) -> bool:
    """Return True iff ``text`` contains a markdown header matching heading.

    Matches ``##`` through ``####`` headers. Case-insensitive. Requires
    word-boundary matching so that renaming ``## Resolution`` to
    ``## NotResolution`` DOES count as a missing section.
    """
    pattern = re.compile(
        rf"^#{{2,4}}\s+\b{re.escape(heading)}\b",
        re.IGNORECASE | re.MULTILINE,
    )
    return bool(pattern.search(text))


def parse_artifact(text: str) -> dict:
    """Parse a ``challenge-artifacts.md`` body into a structured dict.

    Returned dict shape::

        {
            "sections_present": [str, ...],
            "sections_missing": [str, ...],
            "challenges": [
                {"id": "CH-01", "title": "...", "theme": "...",
                 "status": "open|resolved", "steelman": "..."},
                ...
            ],
            "bytes": int,
        }

    This function never raises on malformed markdown — it simply records
    which sections and fields were unparseable. Validation is the
    caller's job (see :func:`validate_artifact`).
    """
    body = text or ""
    sections_present = []
    sections_missing = []
    for section in _REQUIRED_SECTIONS:
        (sections_present if _has_section(body, section) else sections_missing).append(section)

    challenges: list[dict] = []
    # Split on challenge headers then parse each block
    matches = list(_CHALLENGE_HEADER_RE.finditer(body))
    for i, match in enumerate(matches):
        ch_id = match.group(1).strip()
        title = (match.group(2) or "").strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]

        fields: dict[str, str] = {}
        for fmatch in _FIELD_RE.finditer(block):
            key = fmatch.group(1).strip().lower()
            val = fmatch.group(2).strip()
            fields[key] = val

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
        "challenges": challenges,
        "bytes": len(body.encode("utf-8", errors="replace")),
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_artifact(text: str) -> "str | None":
    """Return an error message describing why ``text`` is an invalid
    challenge-artifact, or ``None`` if it is well-formed.

    Checks performed:
      1. Byte size >= :data:`MIN_ARTIFACT_BYTES`.
      2. All required sections are present.
      3. At least one challenge block exists.
      4. Every resolved challenge has a non-empty steelman field
         (>= :data:`_MIN_STEELMAN_LENGTH` characters).
    """
    parsed = parse_artifact(text)

    if parsed["bytes"] < MIN_ARTIFACT_BYTES:
        return (
            f"artifact is too small ({parsed['bytes']} bytes, "
            f"minimum {MIN_ARTIFACT_BYTES}). A challenge artifact must "
            f"contain a written steelman, enumerated challenges, "
            f"convergence check, and resolution."
        )

    missing = parsed["sections_missing"]
    if missing:
        return (
            f"challenge artifact is missing required section(s): "
            f"{', '.join(missing)}."
        )

    challenges = parsed["challenges"]
    if not challenges:
        return (
            "challenge artifact has no enumerated Challenge blocks. "
            "Add at least one '### Challenge CH-XX: ...' entry."
        )

    # Rule: cannot resolve a challenge without a steelman
    for ch in challenges:
        if ch["status"] == "resolved" and len(ch["steelman"]) < _MIN_STEELMAN_LENGTH:
            return (
                f"challenge {ch['id']!r} is marked 'resolved' but has "
                f"no articulated steelman (min {_MIN_STEELMAN_LENGTH} chars). "
                f"The contrarian gate forbids closing a challenge without "
                f"writing down the strongest version of the opposing view."
            )

    return None


# ---------------------------------------------------------------------------
# Convergence collapse detection
# ---------------------------------------------------------------------------

def detect_convergence_collapse(
    challenges: Iterable[dict],
) -> "tuple[bool, str]":
    """Return ``(collapsed, reason)`` for a list of challenge dicts.

    Convergence has *collapsed* when the dissent surface has become
    monochromatic: multiple challenges all pointing in the same
    direction. That is a signal of false consensus inside the
    contrarian role itself.

    Rules (conservative — avoid false positives on small dissent):
      * If fewer than :data:`CONVERGENCE_MIN_CHALLENGES` challenges exist,
        collapse is *not* reported (returns ``(False, "")``).
      * If all challenges share the same non-empty ``theme``, collapse
        is reported.
      * If all challenges' statuses are identical *and* all themes are
        either empty or identical, collapse is reported.
    """
    entries = [c for c in challenges if isinstance(c, dict)]
    if len(entries) < CONVERGENCE_MIN_CHALLENGES:
        return False, ""

    themes = {c.get("theme", "").lower() for c in entries}
    # Remove blank theme entries so we don't flag on "everything is untagged"
    non_empty_themes = {t for t in themes if t}

    if len(non_empty_themes) == 1 and len(entries) >= CONVERGENCE_MIN_CHALLENGES:
        theme = next(iter(non_empty_themes))
        return True, (
            f"convergence collapse detected: all {len(entries)} challenges "
            f"share theme {theme!r}. Surface additional dissent dimensions "
            f"(security, correctness, operability, ethics, cost) before "
            f"resolving."
        )

    # If themes are entirely empty — the contrarian hasn't been tagging dissent
    # vectors. Treat as collapse so the user is prompted to enrich the artifact.
    if not non_empty_themes:
        return True, (
            f"convergence collapse suspected: none of the {len(entries)} "
            f"challenges declare a theme. Tag each challenge with a theme "
            f"field so dissent variety can be evaluated."
        )

    return False, ""


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------

def is_required(complexity: int, phase: str = "build") -> bool:
    """Return True iff a challenge artifact is required for this phase.

    The artifact is anchored to the *design* phase output but the gate
    fires before *build* — that's the point at which the challenges
    must have been written down. Other phases do not require the
    artifact.

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

    ``ok=True, reason=""`` when:
      * The artifact exists,
      * :func:`validate_artifact` returns None,
      * :func:`detect_convergence_collapse` does not flag collapse on
        resolved challenges.

    ``ok=False, reason=<why>`` otherwise. The reason is a single-line
    human-readable string suitable for display in a hook
    ``permissionDecisionReason`` or phase-manager preflight message.
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

    parsed = parse_artifact(text)
    resolved = [c for c in parsed["challenges"] if c.get("status") == "resolved"]
    collapsed, why = detect_convergence_collapse(resolved or parsed["challenges"])
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
        parsed = parse_artifact(text)
        collapsed, why = detect_convergence_collapse(parsed["challenges"])
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
