#!/usr/bin/env python3
"""retro_action_items.py — scan retro markdown and auto-populate action items.

Purpose
-------
The retro command (``/wicked-garden:crew:retro``) generates a markdown
retrospective with a ``## Action Items`` section. Prior to this wiring
(issue #461), action items surfaced in that section evaporated between
sessions — they were only ever rendered to the retro artifact and not
tracked anywhere durable.

This helper is invoked by the retro command AFTER the markdown artifact
is written. It scans the retro content for action-item patterns and calls
``delivery.process_memory.add_action_item()`` so each item receives a
stable ``AI-NNN`` identifier and becomes visible to the facilitator at
future session starts (via ``aging_action_items``).

**Additive side-effect only.** The retro markdown output is not modified.
If ``delivery.process_memory`` is not importable (legacy environments or
module removed), the helper fails open — no action items are added, no
errors are raised, exit code is 0.

Invocation
----------
::

    sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
        "${CLAUDE_PLUGIN_ROOT}/scripts/crew/retro_action_items.py" \
        --project PROJECT --retro-md PATH

Arguments
---------
--project:      Crew project slug (required).
--retro-md:     Path to the retro markdown file (required).
--session-id:   Session identifier to stamp on created action items.
--json:         Emit JSON summary on stdout instead of human text.

Stdlib-only. Safe to run in a hook or command context.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Action-item parsing
# ---------------------------------------------------------------------------
#
# Pattern: retros write action items as a bulleted checkbox list under a
# heading that contains "Action Items" (case-insensitive). We extract each
# bullet's text as the title, keeping the original line as description so
# reviewers can always trace the source back to the retro.
#
# A bullet is any line matching one of:
#   - [ ] <text>        (GitHub checkbox)
#   - [x] <text>        (completed — still captured; owner may re-open)
#   * <text>            (plain bullet)
#   - <text>            (plain bullet)
#
# We stop collecting when we hit another top-level heading or the end of
# the document. This keeps action-item parsing confined to the intended
# section.

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_ACTION_HEADING_RE = re.compile(r"action\s+items?", re.IGNORECASE)
_BULLET_RE = re.compile(
    r"^\s*[-*]\s*(?:\[[ xX]\]\s*)?(?P<title>.+?)\s*$"
)


def _iter_action_items(md_text: str) -> Iterator[dict]:
    """Yield {title, description} dicts for each action-item bullet found.

    The scanner walks the markdown line-by-line, tracking whether we're
    currently inside an Action Items section. A new top-level heading
    closes the section.
    """
    in_section = False
    section_level = 0
    for raw_line in md_text.splitlines():
        heading = _HEADING_RE.match(raw_line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if _ACTION_HEADING_RE.search(title):
                in_section = True
                section_level = level
                continue
            # Another heading at the same or shallower level ends the section
            if in_section and level <= section_level:
                in_section = False
            continue

        if not in_section:
            continue

        bullet = _BULLET_RE.match(raw_line)
        if not bullet:
            continue
        title = bullet.group("title").strip()
        if not title:
            continue
        yield {"title": title, "description": raw_line.strip()}


def scan_action_items(md_text: str) -> list[dict]:
    """Return every action-item bullet discovered in ``md_text``."""
    return list(_iter_action_items(md_text))


# ---------------------------------------------------------------------------
# process_memory integration (lazy + fail-open)
# ---------------------------------------------------------------------------


def _load_process_memory():
    """Import delivery.process_memory lazily; return None if absent."""
    _scripts_root = Path(__file__).resolve().parents[1]
    if str(_scripts_root) not in sys.path:
        sys.path.insert(0, str(_scripts_root))
    try:
        from delivery import process_memory  # type: ignore
        return process_memory
    except Exception as exc:  # pragma: no cover — only in broken envs
        print(
            f"[retro_action_items] delivery.process_memory not importable "
            f"({exc!r}); skipping add_action_item calls",
            file=sys.stderr,
        )
        return None


def populate_action_items(
    project: str,
    retro_md_path: Path,
    *,
    session_id: str = "",
) -> dict:
    """Scan ``retro_md_path`` and append each action item via process_memory.

    Returns a dict summarising what was done::

        {
          "project": "<slug>",
          "retro_md": "<path>",
          "items_found": <int>,
          "items_added": [<AI-id>, ...],
          "errors": [<str>, ...],
          "process_memory_available": <bool>,
        }

    Fail-open: missing module, missing retro file, or per-item exceptions
    are all captured in ``errors`` but never raise.
    """
    summary = {
        "project": project,
        "retro_md": str(retro_md_path),
        "items_found": 0,
        "items_added": [],
        "errors": [],
        "process_memory_available": False,
    }

    if not retro_md_path.exists():
        summary["errors"].append(f"retro markdown not found: {retro_md_path}")
        return summary

    try:
        md_text = retro_md_path.read_text(encoding="utf-8")
    except OSError as exc:
        summary["errors"].append(f"cannot read retro markdown: {exc!r}")
        return summary

    items = scan_action_items(md_text)
    summary["items_found"] = len(items)
    if not items:
        return summary

    pm = _load_process_memory()
    if pm is None:
        return summary
    summary["process_memory_available"] = True

    for item in items:
        try:
            created = pm.add_action_item(
                project,
                title=item["title"],
                description=item["description"],
                source_session=session_id,
            )
            if isinstance(created, dict) and created.get("id"):
                summary["items_added"].append(created["id"])
        except Exception as exc:
            summary["errors"].append(
                f"add_action_item failed for {item['title']!r}: {exc!r}"
            )
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan a retro markdown file and auto-populate action items "
            "via delivery.process_memory (issue #461)."
        )
    )
    parser.add_argument("--project", required=True, help="Crew project slug.")
    parser.add_argument(
        "--retro-md",
        required=True,
        help="Path to the retro markdown artifact to scan.",
    )
    parser.add_argument(
        "--session-id",
        default=os.environ.get("CLAUDE_SESSION_ID", ""),
        help="Session identifier to stamp on new action items.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON summary on stdout.",
    )
    args = parser.parse_args()

    retro_path = Path(args.retro_md).expanduser()
    summary = populate_action_items(
        args.project, retro_path, session_id=args.session_id
    )

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    added = summary["items_added"]
    found = summary["items_found"]
    if not summary["process_memory_available"]:
        print(
            "[retro_action_items] process_memory unavailable — "
            f"{found} action item(s) parsed but not persisted."
        )
    else:
        print(
            f"[retro_action_items] {len(added)} of {found} action item(s) "
            f"added to process memory for project '{args.project}'."
        )
        for ai_id in added:
            print(f"  {ai_id}")
    for err in summary["errors"]:
        print(f"  warning: {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
