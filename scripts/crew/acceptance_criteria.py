#!/usr/bin/env python3
"""
Typed AcceptanceCriterion records with structured evidence maps.

Replaces the #587 / #598 substring / canonical-token path with a data-layer fix:
each AC declares its evidence references explicitly rather than relying on text
scanning. The canonical-token path is preserved as a SOFT fallback for projects
that have not yet migrated.

Resolves: wicked-garden #591 (v8 PR-5 spec), root-cause of #587.

Public API
----------
AcceptanceCriterion   — frozen dataclass; id, statement, satisfied_by, verification
ACParseError          — raised when markdown is structurally malformed (not on missing ACs)
parse_acs_from_markdown(path)  — extract ACs from a clarify .md file
load_acs(project_dir)          — load from JSON if present, else parse + auto-migrate
save_acs(project_dir, acs)     — persist to acceptance-criteria.json
link_evidence(project_dir, ac_id, evidence_ref) — add a reference to satisfied_by
main()                         — CLI: parse | link | list
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants (R3: no magic strings)
# ---------------------------------------------------------------------------

_AC_FILE_NAME = "acceptance-criteria.json"
_AC_FILE_VERSION = "1"

# Subdirs searched for clarify deliverables, in priority order.
_CLARIFY_SUBDIRS = ("clarify", "test-strategy", "qe")

# Maximum number of AC IDs extracted per file (R5: bounded).
_MAX_ACS_PER_FILE = 500

# Regex patterns for extraction (5 formats — table / bullet / inline / dotted / prefixed).
#
# AC-ID pattern: matches:
#   - Simple:   AC-3, FR-1, REQ-2
#   - Dotted:   AC-3.1, AC-2.1.3
#   - Compound: FR-auth-1, REQ-login-2, US-admin-5.2
# The pattern allows an optional alphanumeric word segment between the prefix
# and the trailing numeric component.
_ID_PAT = r"[A-Z]{1,6}(?:-[A-Za-z][A-Za-z0-9]*)?-\d+(?:\.\d+)*"

# Format 1: Markdown table row  | AC-N | description | ... |
_RE_TABLE = re.compile(
    r"\|\s*(?P<id>" + _ID_PAT + r"|(?:\d+))\s*\|"
    r"\s*(?P<desc>[^|]{1,300})\s*\|",
    re.IGNORECASE,
)

# Format 2: Bulleted/listed with bold or plain label  - **AC-N**: prose
_RE_BULLET = re.compile(
    r"[-*]\s+(?:\*\*)?(?P<id>" + _ID_PAT + r")(?:\*\*)?\s*[:\-]\s*(?P<desc>.+)",
    re.IGNORECASE,
)

# Format 3: Inline label starting a line  AC-3: prose  or  AC-3 — prose
_RE_INLINE = re.compile(
    r"^\s*(?P<id>" + _ID_PAT + r")\s*[:\-—]\s*(?P<desc>.+)",
    re.IGNORECASE | re.MULTILINE,
)

# Format 4: Numbered list item where the number IS the AC id  1. prose
# Only captured when inside a section explicitly labelled "acceptance criteria".
# We detect section context separately so this doesn't over-capture numbered lists.
_RE_NUMBERED = re.compile(
    r"^\s*(?P<id>\d+)\.\s+(?P<desc>.+)",
    re.MULTILINE,
)

# Section header detector for numbered-list context.
#
# Matches three families of headings (hashes 1-6, any depth):
#   1. Canonical:        "## Acceptance Criteria"
#   2. Per-feature:      "## Auth Acceptance Criteria", "## Payments Acceptance Criteria"
#                        — any prefix words followed by "Acceptance Criteria"
#                        (Issue #618: required so multi-section AC handling
#                        actually picks up the per-feature blocks the
#                        _extract_ac_section_slices walker is designed to find)
#   3. Short alias:      "## ACs", "## ACs for module X"
#
# The "acceptance[\s_-]*criteri\w*" leg keeps the original camel-case-friendly
# behaviour (matches "AcceptanceCriteria" with no separator) and tolerates
# trailing inflections ("Criterion", "Criteria").
_RE_AC_SECTION = re.compile(
    r"^#{1,6}\s+(?:"
    r"(?:[^\n]*?\b)?acceptance[\s_-]*criteri\w*"
    r"|acs?\b"
    r")",
    re.IGNORECASE,
)

# Description filter: skip header-like rows.
_HEADER_WORDS = frozenset({"criterion", "criteria", "description", "desc", "test", "id", "requirement"})


def _is_header_desc(desc: str) -> bool:
    """Return True when the description looks like a table header row."""
    low = desc.strip().lower()
    return low in _HEADER_WORDS or all(w in _HEADER_WORDS for w in low.split())


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AcceptanceCriterion:
    """Typed record for a single acceptance criterion.

    Fields
    ------
    id            Canonical identifier: "AC-3", "FR-auth-1", "REQ-login-2", etc.
    statement     Human-readable description (preserves the original prose).
    satisfied_by  Tuple of evidence references: file paths, test IDs, issue refs,
                  or check names.  Empty = UNLINKED.
    verification  Optional name of a check function in verification_protocol.py.
    """
    id: str
    statement: str
    satisfied_by: tuple[str, ...] = field(default_factory=tuple)
    verification: str | None = None


class ACParseError(Exception):
    """Raised when a markdown file cannot be parsed for structural reasons."""


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _ac_to_dict(ac: AcceptanceCriterion) -> dict[str, Any]:
    d = asdict(ac)
    d["satisfied_by"] = list(ac.satisfied_by)  # tuple → list for JSON
    return d


def _ac_from_dict(d: dict[str, Any]) -> AcceptanceCriterion:
    return AcceptanceCriterion(
        id=str(d["id"]),
        statement=str(d.get("statement", "")),
        satisfied_by=tuple(d.get("satisfied_by") or []),
        verification=d.get("verification") or None,
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _extract_ac_section_slices(text: str) -> list[str]:
    """Return ALL slices matching AC-section headings (Issue #618).

    Multiple AC sections (e.g. ``## Auth Acceptance Criteria`` followed by
    ``## Payments Acceptance Criteria``) used to silently drop items in
    subsequent sections — only the first heading was sliced. This version
    walks the whole document and returns one slice per AC-section heading.

    Each slice starts on the line after its AC heading and ends at the next
    heading whose level is <= the AC heading's level (so a sub-heading like
    ``### Sub`` under ``## AC`` stays inside; ``## Other`` ends the section).

    Returns an empty list when no AC section heading is found.
    """
    lines = text.splitlines(keepends=True)
    _heading_re = re.compile(r"^(#{1,6})\s+")
    slices: list[str] = []

    i = 0
    n = len(lines)
    while i < n:
        if _RE_AC_SECTION.match(lines[i]):
            hm = _heading_re.match(lines[i])
            ac_level = len(hm.group(1)) if hm else 1
            start_idx = i + 1

            # Find the next heading at the same or higher level (lower # count).
            end_idx = n
            for j in range(start_idx, n):
                hm2 = _heading_re.match(lines[j])
                if hm2 and len(hm2.group(1)) <= ac_level:
                    end_idx = j
                    break

            slices.append("".join(lines[start_idx:end_idx]))
            # Resume scanning *at* the closing heading so a follow-on AC
            # section under the same parent is detected as well.
            i = end_idx
            continue
        i += 1

    return slices


def _extract_ac_section_slice(text: str) -> str | None:
    """Backward-compat alias for :func:`_extract_ac_section_slices`.

    Returns the first AC section slice only, mirroring the pre-#618 behaviour
    for any external callers that depended on the singular return shape.
    Deprecated — new callers should use the plural helper to capture multiple
    AC sections.
    """
    slices = _extract_ac_section_slices(text)
    return slices[0] if slices else None


def parse_acs_from_markdown(path: Path) -> list[AcceptanceCriterion]:
    """Extract AcceptanceCriterion records from a clarify markdown file.

    Supports 5 formats:
      1. Markdown table:    | AC-N | description | ... |
      2. Bulleted list:     - **AC-N**: prose
      3. Inline label:      AC-N: prose  (line-start)
      4. Prefixed IDs:      FR-auth-1, REQ-login-2 (same patterns as above)
      5. Dotted IDs:        AC-3.1 (handled by all patterns above)

    Returns an empty list (not an exception) when no ACs are found.
    Raises ACParseError when the file cannot be read for structural reasons.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ACParseError(f"Cannot read {path}: {exc}") from exc

    seen_ids: set[str] = set()
    results: list[AcceptanceCriterion] = []

    def _add(ac_id: str, desc: str) -> None:
        if len(results) >= _MAX_ACS_PER_FILE:
            return
        norm_id = ac_id.strip()
        if norm_id in seen_ids:
            return
        desc_clean = desc.strip()
        if _is_header_desc(desc_clean):
            return
        seen_ids.add(norm_id)
        results.append(AcceptanceCriterion(id=norm_id, statement=desc_clean))

    # Pattern 1: table rows
    for m in _RE_TABLE.finditer(text):
        _add(m.group("id"), m.group("desc"))

    # Pattern 2: bulleted with bold or plain label (runs even when table found)
    for m in _RE_BULLET.finditer(text):
        _add(m.group("id"), m.group("desc"))

    # Pattern 3: inline label (line-start)  AC-N: prose
    for m in _RE_INLINE.finditer(text):
        _add(m.group("id"), m.group("desc"))

    # Pattern 4: numbered list items ONLY within an "Acceptance Criteria" section.
    # This avoids over-capturing every ordered list in the document.
    # Issue #618: walk ALL AC sections, not just the first — multi-section
    # documents (e.g. per-feature AC blocks) used to silently drop items in
    # the second and later sections.
    for section in _extract_ac_section_slices(text):
        for m in _RE_NUMBERED.finditer(section):
            raw_id = m.group("id")
            # Emit as "AC-N" canonical form for numbered items.
            canonical = f"AC-{raw_id}"
            _add(canonical, m.group("desc"))

    return results


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def _find_clarify_dir(project_dir: Path) -> Path | None:
    """Return the first clarify-type subdirectory found under project_dir/phases/."""
    phases = project_dir / "phases"
    if not phases.is_dir():
        return None
    for subdir in _CLARIFY_SUBDIRS:
        candidate = phases / subdir
        if candidate.is_dir():
            return candidate
    return None


def _find_clarify_markdowns(project_dir: Path) -> list[Path]:
    """Enumerate clarify markdown files for the project."""
    clarify = _find_clarify_dir(project_dir)
    if clarify is None:
        return []
    return sorted(clarify.glob("*.md"))


def _ac_json_path(project_dir: Path) -> Path:
    """Canonical path for the acceptance-criteria.json file."""
    return project_dir / "phases" / "clarify" / _AC_FILE_NAME


def load_acs(project_dir: Path) -> list[AcceptanceCriterion]:
    """Load AcceptanceCriterion records for a project.

    Primary path: read from phases/clarify/acceptance-criteria.json if present.
    Migration path: if JSON doesn't exist but clarify markdown does, parse the
    markdown and write the JSON (one-time auto-migration).  Re-running is
    idempotent.

    Returns an empty list for projects with no clarify deliverables.
    """
    json_path = _ac_json_path(project_dir)
    if json_path.is_file():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            return [_ac_from_dict(d) for d in raw.get("acs", [])]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            # Corrupted file — fall through to re-parse.
            import sys as _sys
            print(f"warning: load_acs: corrupt {json_path}: {exc}", file=_sys.stderr)

    # Auto-migration: parse clarify markdown → write JSON.
    mds = _find_clarify_markdowns(project_dir)
    if not mds:
        return []

    all_acs: list[AcceptanceCriterion] = []
    seen: set[str] = set()
    for md in mds:
        try:
            for ac in parse_acs_from_markdown(md):
                if ac.id not in seen:
                    seen.add(ac.id)
                    all_acs.append(ac)
        except ACParseError:
            pass  # graceful: unreadable file is skipped

    if all_acs:
        # Persist so next call uses the structured path.
        save_acs(project_dir, all_acs)

    return all_acs


def save_acs(project_dir: Path, acs: list[AcceptanceCriterion]) -> None:
    """Persist AcceptanceCriterion records to the canonical JSON file.

    Creates the directory if needed.  Write is atomic via a temp-then-rename
    pattern to avoid partial writes.
    """
    json_path = _ac_json_path(project_dir)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": _AC_FILE_VERSION,
        "acs": [_ac_to_dict(ac) for ac in acs],
    }
    tmp = json_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(json_path)
    except OSError as exc:
        # Clean up temp file on failure; propagate to caller.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise OSError(f"save_acs: cannot write {json_path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Evidence linking
# ---------------------------------------------------------------------------

def link_evidence(project_dir: Path, ac_id: str, evidence_ref: str) -> bool:
    """Add evidence_ref to the AC identified by ac_id.

    Returns True when the AC was found and updated, False when ac_id was not
    found in the project's AC list (the reference is silently skipped, not an
    error — partial evidence links are valid during build phase).
    """
    acs = load_acs(project_dir)
    updated = []
    found = False
    for ac in acs:
        if ac.id == ac_id:
            if evidence_ref not in ac.satisfied_by:
                ac = replace(ac, satisfied_by=ac.satisfied_by + (evidence_ref,))
            found = True
        updated.append(ac)
    if found:
        save_acs(project_dir, updated)
    return found


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_parse(args: argparse.Namespace) -> int:
    """Print parsed ACs from the project's clarify markdown."""
    project_dir = Path(args.project)
    mds = _find_clarify_markdowns(project_dir)
    if not mds:
        print(f"No clarify markdown files found under {project_dir}/phases/", file=sys.stderr)
        return 1
    for md in mds:
        try:
            for ac in parse_acs_from_markdown(md):
                print(f"{ac.id}: {ac.statement}")
        except ACParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
    return 0


def _cmd_link(args: argparse.Namespace) -> int:
    """Link an evidence reference to an AC."""
    project_dir = Path(args.project)
    found = link_evidence(project_dir, args.ac_id, args.evidence_ref)
    if found:
        print(f"Linked {args.evidence_ref!r} to {args.ac_id}")
        return 0
    print(f"AC {args.ac_id!r} not found in {project_dir}", file=sys.stderr)
    return 1


def _cmd_list(args: argparse.Namespace) -> int:
    """List ACs with their evidence status."""
    project_dir = Path(args.project)
    acs = load_acs(project_dir)
    if not acs:
        print("No acceptance criteria found.", file=sys.stderr)
        return 1
    for ac in acs:
        status = "LINKED" if ac.satisfied_by else "UNLINKED"
        refs = ", ".join(ac.satisfied_by) if ac.satisfied_by else "(none)"
        print(f"[{status}] {ac.id}: {ac.statement}")
        if ac.satisfied_by:
            print(f"          evidence: {refs}")
    return 0


def main() -> None:
    """CLI entry point: acceptance-criteria parse|link|list <project> ..."""
    parser = argparse.ArgumentParser(
        description="Structured acceptance-criteria management (v8-PR-5 #591)",
        prog="acceptance-criteria",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    parse_p = subparsers.add_parser("parse", help="Parse ACs from clarify markdown")
    parse_p.add_argument("project", help="Path to project directory (contains phases/)")

    link_p = subparsers.add_parser("link", help="Link an evidence reference to an AC")
    link_p.add_argument("project", help="Path to project directory")
    link_p.add_argument("ac_id", help="AC identifier, e.g. AC-3")
    link_p.add_argument("evidence_ref", help="Evidence reference: file path, test ID, issue ref")

    list_p = subparsers.add_parser("list", help="List ACs with LINKED / UNLINKED status")
    list_p.add_argument("project", help="Path to project directory")

    args = parser.parse_args()

    dispatch = {
        "parse": _cmd_parse,
        "link": _cmd_link,
        "list": _cmd_list,
    }
    fn = dispatch.get(args.subcommand)
    if fn is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(fn(args))


if __name__ == "__main__":
    main()
