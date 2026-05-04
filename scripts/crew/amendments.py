#!/usr/bin/env python3
"""
Amendments log — append-only JSONL replacement for design-addendum-N.md (#478).

Historically, each mid-phase design correction was written as a new
``phases/{phase}/design-addendum-{N}.md`` file. This scales poorly:
per-file, human-authored markdown is hard to query, hard to diff
mechanically, and race-prone when two subagents produce addenda at the
same time. Issue #478 replaces the per-file pattern with a single
append-only JSONL log at ``phases/{phase}/amendments.jsonl``.

Record shape (one JSON object per line):

    {
        "amendment_id": "AMD-<slug>-<ts>",
        "trigger": "gate-conditional" | "re-eval" | "manual" | ...,
        "scope_version": int,       # monotonic per-phase version counter
        "timestamp": ISO-8601 UTC,
        "summary": str,             # one-line human summary
        "patches": [                # structured description of what changed
            {"target": "<rel-path-or-section>", "operation": "add|remove|replace",
             "rationale": str}
        ],
        "resolution_refs": [str]    # back-links to condition IDs, PR numbers, etc.
    }

Back-compat: existing ``design-addendum-N.md`` files remain readable —
:func:`list_amendments` will surface them as pseudo-records with
``source="legacy-md"`` so downstream tooling can treat them uniformly.

Public surface:
    - :func:`append`   — append one amendment record, returning the
      assigned ``amendment_id`` and ``scope_version``.
    - :func:`list_amendments` — read all amendments (JSONL + legacy .md).
    - :func:`render_markdown` — render amendments as human-readable markdown.
    - CLI: ``amendments show {phase} [--project P]`` — renders markdown
      to stdout for quick inspection.

This module is stdlib-only (no external deps) per the hook rulebook.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AMENDMENTS_FILENAME = "amendments.jsonl"
LEGACY_MD_PATTERN = re.compile(r"design-addendum-(\d+)\.md$", re.IGNORECASE)
AMENDMENT_ID_PREFIX = "AMD"

# Allowed trigger vocabulary. Free-text triggers are rejected to keep the
# log queryable. Callers who need a new trigger extend this tuple and
# send a PR.
VALID_TRIGGERS: Tuple[str, ...] = (
    "gate-conditional",
    "gate-reject",
    "re-eval",
    "manual",
    "council",
    "challenge",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slugify(value: str) -> str:
    """Produce a short lowercase-kebab slug from free-text summary.

    Keeps ASCII letters, digits, and hyphens; collapses runs of other
    characters to a single ``-``; trims to 32 chars. Empty input yields
    ``"amendment"`` as a fallback so the id shape is always stable.
    """
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    if not value:
        value = "amendment"
    return value[:32]


def _amendments_path(phase_dir: Path) -> Path:
    """Return ``phase_dir / amendments.jsonl``."""
    return Path(phase_dir) / AMENDMENTS_FILENAME


def _validate_record(record: Dict[str, Any]) -> None:
    """Raise ValueError if ``record`` is missing required fields."""
    required = ("trigger", "summary")
    missing = [k for k in required if not record.get(k)]
    if missing:
        raise ValueError(
            f"amendment record missing required field(s): {missing}"
        )
    trigger = record.get("trigger")
    if trigger not in VALID_TRIGGERS:
        raise ValueError(
            f"amendment trigger '{trigger}' not in allow-list "
            f"{VALID_TRIGGERS}"
        )
    patches = record.get("patches")
    if patches is not None and not isinstance(patches, list):
        raise ValueError("amendment 'patches' must be a list when present")


def _next_scope_version(phase_dir: Path) -> int:
    """Compute the next monotonic scope_version for this phase.

    Counts existing JSONL records + legacy ``design-addendum-N.md`` files
    so the version number is globally monotonic across the two formats.
    Returns ``1`` for a fresh phase.
    """
    highest = 0
    for rec in _iter_jsonl(phase_dir):
        try:
            v = int(rec.get("scope_version") or 0)
        except (TypeError, ValueError):
            v = 0
        if v > highest:
            highest = v
    for legacy_path in Path(phase_dir).glob("design-addendum-*.md"):
        m = LEGACY_MD_PATTERN.search(legacy_path.name)
        if m:
            try:
                v = int(m.group(1))
            except ValueError:
                continue
            if v > highest:
                highest = v
    return highest + 1


def _iter_jsonl(phase_dir: Path) -> Iterable[Dict[str, Any]]:
    """Yield parsed JSONL records from ``amendments.jsonl`` if present."""
    path = _amendments_path(phase_dir)
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Skip corrupt lines so one bad record doesn't blind the
                # whole log. Upstream linter flags these separately.
                continue


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def append(
    phase_dir: Path,
    *,
    trigger: str,
    summary: str,
    patches: Optional[List[Dict[str, Any]]] = None,
    resolution_refs: Optional[List[str]] = None,
    amendment_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append one amendment record to ``phase_dir/amendments.jsonl``.

    Args:
        phase_dir: ``phases/{phase}/`` directory. Created if missing.
        trigger: One of :data:`VALID_TRIGGERS`.
        summary: One-line human summary (trimmed, required).
        patches: Optional list of structured patch descriptors.
        resolution_refs: Optional list of back-links (condition IDs,
            PR numbers, commit SHAs, etc.).
        amendment_id: Optional explicit id. When omitted, one is
            auto-generated as ``AMD-<slug(summary)>-<ts-compact>``.
        extra: Optional dict merged into the record for forward-compat
            fields. Reserved keys (``amendment_id``, ``trigger``, ...)
            cannot be overridden.

    Returns:
        The full amendment record that was appended, including the
        resolved ``amendment_id``, ``scope_version``, and ``timestamp``.

    Raises:
        ValueError: on missing/invalid fields.
        OSError: on filesystem errors.
    """
    phase_dir = Path(phase_dir)
    phase_dir.mkdir(parents=True, exist_ok=True)

    # Reject non-list patches before any disk mutation so the caller sees
    # a predictable ValueError rather than a TypeError from ``list(...)``.
    if patches is not None and not isinstance(patches, list):
        raise ValueError("amendment 'patches' must be a list when present")

    timestamp = _utc_now_iso()
    scope_version = _next_scope_version(phase_dir)

    if not amendment_id:
        # Compact timestamp suffix keeps the id shell-safe.
        ts_compact = re.sub(r"[^0-9]", "", timestamp)[:14]
        amendment_id = (
            f"{AMENDMENT_ID_PREFIX}-{_slugify(summary)}-{ts_compact}"
        )

    record: Dict[str, Any] = {
        "amendment_id": amendment_id,
        "trigger": trigger,
        "scope_version": scope_version,
        "timestamp": timestamp,
        "summary": summary.strip(),
        "patches": list(patches or []),
        "resolution_refs": list(resolution_refs or []),
    }
    if extra:
        for k, v in extra.items():
            record.setdefault(k, v)

    _validate_record(record)

    path = _amendments_path(phase_dir)
    # Append with newline terminator. JSONL is append-only by contract;
    # callers MUST NOT rewrite earlier lines.
    line = json.dumps(record, sort_keys=False) + "\n"

    # Wave-2 Tranche B emit (#746 W6): fire BEFORE the disk append so
    # the projector handler can replay the same line.  phase_dir shape
    # is {project_dir}/phases/{phase}, so project_id = phase_dir.parent.parent.name
    # and phase = phase_dir.name.  Fail-open: bus unavailable must NOT
    # block the append.
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _scripts_root = str(_Path(__file__).resolve().parents[1])
        if _scripts_root not in _sys.path:
            _sys.path.insert(0, _scripts_root)
        from _bus import emit_event  # type: ignore[import]
        project_id_str = phase_dir.parent.parent.name
        phase_str = phase_dir.name
        emit_event(
            "wicked.amendment.appended",
            {
                "project_id": project_id_str,
                "phase": phase_str,
                "amendment_id": amendment_id,
                "trigger": trigger,
                "scope_version": scope_version,
                "raw_payload": line,
            },
            chain_id=f"{project_id_str}.{phase_str}.{amendment_id}",
        )
    except Exception:  # noqa: BLE001 — fail-open per Decision #8
        pass  # bus unavailable — append below still runs

    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            # Fsync not supported (e.g. tmpfs, some FUSE backends).
            # The append is still durable within the OS page cache for
            # crash-safety in the typical case.
            pass  # fail open: fsync unsupported on this FS

    return record


def list_amendments(
    phase_dir: Path,
    *,
    include_legacy: bool = True,
) -> List[Dict[str, Any]]:
    """Return all amendments for a phase, JSONL first then legacy .md.

    Args:
        phase_dir: ``phases/{phase}/`` directory.
        include_legacy: When True (default), legacy
            ``design-addendum-N.md`` files are surfaced as pseudo-records
            with ``source="legacy-md"`` and ``path`` pointing at the .md.

    Returns:
        List of amendment records sorted by ``scope_version``. Records
        that cannot be parsed are skipped.
    """
    phase_dir = Path(phase_dir)
    out: List[Dict[str, Any]] = []

    for rec in _iter_jsonl(phase_dir):
        rec.setdefault("source", "jsonl")
        out.append(rec)

    if include_legacy and phase_dir.exists():
        for legacy_path in sorted(phase_dir.glob("design-addendum-*.md")):
            m = LEGACY_MD_PATTERN.search(legacy_path.name)
            if not m:
                continue
            try:
                version = int(m.group(1))
            except ValueError:
                continue
            try:
                stat = legacy_path.stat()
                mtime = datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat().replace("+00:00", "Z")
            except OSError:
                mtime = ""
            out.append({
                "amendment_id": f"LEGACY-{version}",
                "trigger": "manual",
                "scope_version": version,
                "timestamp": mtime,
                "summary": legacy_path.name,
                "patches": [],
                "resolution_refs": [],
                "source": "legacy-md",
                "path": str(legacy_path),
            })

    out.sort(key=lambda r: int(r.get("scope_version") or 0))
    return out


def render_markdown(amendments: List[Dict[str, Any]]) -> str:
    """Render a list of amendments as human-readable markdown."""
    if not amendments:
        return "# Amendments\n\n_No amendments recorded._\n"

    lines: List[str] = ["# Amendments", ""]
    for rec in amendments:
        header = (
            f"## v{rec.get('scope_version', '?')} — "
            f"{rec.get('amendment_id', 'UNKNOWN')}"
        )
        lines.append(header)
        lines.append("")
        lines.append(f"- **trigger:** {rec.get('trigger', 'manual')}")
        lines.append(f"- **timestamp:** {rec.get('timestamp', '')}")
        source = rec.get("source")
        if source and source != "jsonl":
            lines.append(f"- **source:** {source}")
        if rec.get("path"):
            lines.append(f"- **path:** `{rec['path']}`")
        summary = rec.get("summary") or ""
        if summary:
            lines.append("")
            lines.append(summary)
        patches = rec.get("patches") or []
        if patches:
            lines.append("")
            lines.append("### Patches")
            for p in patches:
                target = p.get("target", "?")
                op = p.get("operation", "?")
                rationale = p.get("rationale", "")
                lines.append(f"- `{target}` ({op}) — {rationale}")
        refs = rec.get("resolution_refs") or []
        if refs:
            lines.append("")
            lines.append("### Resolution refs")
            for r in refs:
                lines.append(f"- {r}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_phase_dir(
    project: Optional[str], phase: str
) -> Path:
    """Resolve ``phases/{phase}/`` for the given project.

    When ``project`` is provided, uses ``crew.py find-project`` via
    :mod:`_domain_store` through a lightweight path convention:
    ``~/.something-wicked/wicked-crew/local/projects/{project}/phases/{phase}``
    — but we don't hardcode that path. Instead we re-use the same
    resolver ``phase_manager.py`` uses.

    When ``project`` is None or the resolver is unavailable, treats
    ``phase`` as a filesystem path (``./phases/{phase}``) relative to
    the current working directory — useful for tests.
    """
    if project:
        try:
            here = Path(__file__).resolve().parent.parent
            if str(here) not in sys.path:
                sys.path.insert(0, str(here))
            from _domain_store import get_local_path  # type: ignore
            base = Path(get_local_path("wicked-crew")) / "projects" / project
            candidate = base / "phases" / phase
            if candidate.parent.exists():
                return candidate
        except Exception:
            # Fall through to relative resolution.
            pass  # intentional: CLI fallback to cwd-relative phase_dir
    return Path.cwd() / "phases" / phase


def _cmd_show(args: argparse.Namespace) -> int:
    phase_dir = _resolve_phase_dir(args.project, args.phase)
    amendments = list_amendments(
        phase_dir, include_legacy=not args.no_legacy
    )
    if args.json:
        print(json.dumps(amendments, indent=2))
    else:
        print(render_markdown(amendments))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="amendments",
        description="Append-only amendments log CLI (#478).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser(
        "show", help="Render amendments for a phase as markdown."
    )
    show.add_argument("phase", help="Phase name (e.g. 'design').")
    show.add_argument("--project", help="Project name.", default=None)
    show.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of markdown.",
    )
    show.add_argument(
        "--no-legacy",
        action="store_true",
        help="Skip legacy design-addendum-N.md files.",
    )
    show.set_defaults(func=_cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "AMENDMENTS_FILENAME",
    "VALID_TRIGGERS",
    "append",
    "list_amendments",
    "render_markdown",
    "main",
]
